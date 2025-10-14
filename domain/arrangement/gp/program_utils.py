"""Reusable helpers for applying and describing GP programs."""

from __future__ import annotations

import math
from typing import Iterable, Mapping, Sequence, Tuple

from shared.ottava import OttavaShift

from domain.arrangement.melody import isolate_melody
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange

from .ops import GPPrimitive, GlobalTranspose, LocalOctave, SimplifyRhythm


def describe_program(program: Sequence[GPPrimitive]) -> str:
    """Return a compact textual representation of a GP program."""

    if not program:
        return "<identity>"

    parts: list[str] = []
    for operation in program:
        if isinstance(operation, GlobalTranspose):
            parts.append(f"GlobalTranspose({operation.semitones:+d})")
            continue
        if isinstance(operation, LocalOctave):
            label = getattr(operation.span, "label", "span")
            parts.append(f"LocalOctave({operation.octaves:+d}@{label})")
            continue
        if isinstance(operation, SimplifyRhythm):
            label = getattr(operation.span, "label", "span")
            parts.append(f"SimplifyRhythm(div={operation.subdivisions}@{label})")
            continue
        parts.append(type(operation).__name__)
    return " -> ".join(parts)


def apply_program(program: Sequence[GPPrimitive], span: PhraseSpan) -> PhraseSpan:
    current = span
    for operation in program:
        if isinstance(operation, GlobalTranspose):
            current = current.transpose(operation.semitones)
            continue
        if isinstance(operation, LocalOctave):
            current = _apply_local_octave(operation, current)
            continue
        if isinstance(operation, SimplifyRhythm):
            current = _apply_simplify_rhythm(operation, current)
            continue
    return current


def program_candidates(
    programs: Sequence[Sequence[GPPrimitive]],
    phrase: PhraseSpan,
) -> Mapping[Tuple[GPPrimitive, ...], PhraseSpan]:
    resolved: dict[Tuple[GPPrimitive, ...], PhraseSpan] = {}
    for program in programs:
        key = tuple(program)
        if key in resolved:
            continue
        resolved[key] = apply_program(program, phrase)
    return resolved


def span_within_instrument_range(span: PhraseSpan, instrument: InstrumentRange) -> bool:
    """Return ``True`` when all notes in *span* stay inside *instrument* bounds."""

    low = instrument.min_midi
    high = instrument.max_midi

    for note in span.notes:
        if note.midi < low or note.midi > high:
            return False
    return True


def _top_voice_bounds(span: PhraseSpan) -> Tuple[int, int] | None:
    """Return the lowest and highest MIDI values in the top voice of *span*."""

    if not span.notes:
        return None

    top_by_onset: dict[int, int] = {}
    for note in span.notes:
        current = top_by_onset.get(note.onset)
        if current is None or note.midi > current:
            top_by_onset[note.onset] = note.midi

    if not top_by_onset:
        return None

    tops = top_by_onset.values()
    return min(tops), max(tops)


def _melody_bounds(
    phrase: PhraseSpan, *, beats_per_measure: int
) -> Tuple[int, int] | None:
    """Return the MIDI bounds for the isolated melody, falling back to top voice."""

    isolated = isolate_melody(phrase, beats_per_measure=beats_per_measure).span
    if isolated.notes:
        midis = sorted(note.midi for note in isolated.notes)
        if len(midis) >= 3:
            upper_half = midis[len(midis) // 2 :]
            anchor = sum(upper_half) / len(upper_half)
            threshold = anchor - 12
            filtered = [midi for midi in midis if midi >= threshold]
            if filtered:
                midis = filtered
        return min(midis), max(midis)
    return _top_voice_bounds(phrase)


def auto_range_programs(
    phrase: PhraseSpan,
    instrument: InstrumentRange,
    *,
    beats_per_measure: int = 4,
) -> tuple[tuple[GPPrimitive, ...], ...]:
    """Return global transpose programs that keep ``phrase`` inside ``instrument``."""

    if not phrase.notes:
        return ()

    lowest = min(note.midi for note in phrase.notes)
    highest = max(note.midi for note in phrase.notes)

    shift_values: set[int] = set()
    comfort_center = (
        instrument.comfort_center
        if instrument.comfort_center is not None
        else (instrument.min_midi + instrument.max_midi) / 2.0
    )
    needs_lower_clamp = instrument.min_midi > lowest

    def _candidate_shifts(lower: int, upper: int) -> Iterable[int]:
        shifts: set[int] = set()
        lo = min(lower, upper)
        hi = max(lower, upper)
        # Prefer octave-aligned adjustments when possible within the span bounds.
        start = math.ceil(lo / 12)
        end = math.floor(hi / 12)
        for step in range(start, end + 1):
            shift = step * 12
            if shift != 0:
                shifts.add(int(shift))
        for value in (lower, upper):
            if value != 0:
                shifts.add(int(value))
            floor_multiple = math.floor(value / 12) * 12
            ceil_multiple = math.ceil(value / 12) * 12
            for candidate in (floor_multiple, ceil_multiple):
                if candidate != 0:
                    shifts.add(int(candidate))
        return shifts

    def _extend_candidate_shifts(
        lower: int, upper: int, *, take_first_only: bool = False
    ) -> None:
        ordered_candidates = sorted(
            _candidate_shifts(lower, upper),
            key=lambda shift: (0 if shift % 12 == 0 else 1, abs(shift), shift),
        )
        for index, shift in enumerate(ordered_candidates):
            if shift == 0:
                continue
            shift_values.add(int(shift))
            if take_first_only and index == 0:
                break

    if instrument.min_midi > lowest or highest > instrument.max_midi:
        _extend_candidate_shifts(
            instrument.min_midi - lowest,
            instrument.max_midi - highest,
        )

    melody_bounds = _melody_bounds(phrase, beats_per_measure=beats_per_measure)
    if melody_bounds is not None:
        top_low, top_high = melody_bounds
        if instrument.min_midi > top_low or top_high > instrument.max_midi:
            _extend_candidate_shifts(
                instrument.min_midi - top_low,
                instrument.max_midi - top_high,
                take_first_only=True,
            )

    if needs_lower_clamp and melody_bounds is not None and not shift_values:
        top_low, top_high = melody_bounds
        top_lower_room = max(0, instrument.min_midi - top_low)
        top_upper_room = instrument.max_midi - top_high
        if top_lower_room <= top_upper_room and top_upper_room >= 0:
            top_mid = (top_low + top_high) / 2.0
            desired_shift = comfort_center - top_mid
            candidate_pool = [
                shift
                for shift in _candidate_shifts(top_lower_room, top_upper_room)
                if shift != 0
            ]
            if candidate_pool:
                best_shift = min(
                    candidate_pool,
                    key=lambda shift: (
                        abs(shift - desired_shift),
                        0 if shift % 12 == 0 else 1,
                        abs(shift),
                        shift,
                    ),
                )
                shift_values.add(int(best_shift))

    if not shift_values:
        return ()

    ordered = sorted(
        shift_values,
        key=lambda shift: (0 if shift % 12 == 0 else 1, abs(shift), shift),
    )

    programs: list[tuple[GPPrimitive, ...]] = []
    for semitones in ordered:
        programs.append((GlobalTranspose(semitones=semitones),))

    return tuple(programs)


def _apply_local_octave(operation: LocalOctave, span: PhraseSpan) -> PhraseSpan:
    try:
        start, end = operation.span.resolve(span)
    except ValueError:
        return span

    if operation.octaves == 0:
        return span

    semitones = operation.octaves * 12
    direction = "up" if semitones > 0 else "down"
    shift = OttavaShift(
        source="octave-shift",
        direction=direction,
        size=8 * abs(operation.octaves),
    )

    updated: list[PhraseNote] = []
    for note in span.notes:
        if start <= note.onset < end:
            updated.append(note.with_midi(note.midi + semitones).add_ottava_shift(shift))
            continue
        updated.append(note)
    return span.with_notes(updated)


def _apply_simplify_rhythm(operation: SimplifyRhythm, span: PhraseSpan) -> PhraseSpan:
    try:
        start, end = operation.span.resolve(span)
    except ValueError:
        return span

    subdivisions = max(1, int(operation.subdivisions))
    unit = max(1, span.pulses_per_quarter // subdivisions)
    updated: list[PhraseNote] = []

    for note in span.notes:
        if not (start <= note.onset < end):
            updated.append(note)
            continue

        quantized = max(unit, round(note.duration / unit) * unit)
        max_duration = max(1, end - note.onset)
        updated_duration = min(quantized, max_duration)
        updated.append(note.with_duration(updated_duration))

    return span.with_notes(updated)


__all__ = [
    "apply_program",
    "auto_range_programs",
    "describe_program",
    "program_candidates",
    "span_within_instrument_range",
]
