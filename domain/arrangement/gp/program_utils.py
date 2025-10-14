"""Reusable helpers for applying and describing GP programs."""

from __future__ import annotations

import math
from typing import Iterable, Mapping, Sequence, Tuple

from shared.ottava import OttavaShift

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


def auto_range_programs(
    phrase: PhraseSpan, instrument: InstrumentRange
) -> tuple[tuple[GPPrimitive, ...], ...]:
    """Return global transpose programs that keep ``phrase`` inside ``instrument``."""

    if not phrase.notes:
        return ()

    lowest = min(note.midi for note in phrase.notes)
    highest = max(note.midi for note in phrase.notes)

    if instrument.min_midi <= lowest and highest <= instrument.max_midi:
        return ()

    min_shift = instrument.min_midi - lowest
    max_shift = instrument.max_midi - highest

    programs: list[tuple[GPPrimitive, ...]] = []

    def _candidate_shifts(lower: int, upper: int) -> Iterable[int]:
        if lower > upper:
            return ()
        shifts: set[int] = set()
        # Prefer octave-aligned adjustments when possible.
        start = math.ceil(lower / 12)
        end = math.floor(upper / 12)
        for step in range(start, end + 1):
            shift = step * 12
            if shift == 0:
                continue
            if lower <= shift <= upper:
                shifts.add(int(shift))
        shifts.add(int(lower))
        shifts.add(int(upper))
        return shifts

    candidates = set(_candidate_shifts(min_shift, max_shift))
    ordered = sorted(
        (shift for shift in candidates if shift != 0),
        key=lambda shift: (0 if shift % 12 == 0 else 1, abs(shift), shift),
    )

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
