"""Translate GP programs into structured explanation events."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Sequence, Tuple

from ocarina_tools.pitch import midi_to_name

from shared.ottava import OttavaShift

from domain.arrangement.config import GraceSettings
from domain.arrangement.difficulty import difficulty_score, summarize_difficulty
from domain.arrangement.explanations import (
    ExplanationEvent,
    octave_shifted_notes,
    span_label_for_notes,
)
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange

from .ops import GPPrimitive, GlobalTranspose, LocalOctave, SimplifyRhythm


def _apply_local_octave(operation: LocalOctave, span: PhraseSpan) -> PhraseSpan:
    try:
        start, end = operation.span.resolve(span)
    except ValueError:
        return span

    if operation.octaves == 0:
        return span

    semitones = operation.octaves * 12
    direction = "up" if semitones > 0 else "down"
    shift = OttavaShift(source="gp-octave", direction=direction, size=8 * abs(operation.octaves))

    updated: list[PhraseNote] = []
    for note in span.notes:
        if start <= note.onset < end:
            updated.append(note.with_midi(note.midi + semitones).add_ottava_shift(shift))
        else:
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


def _apply_operation(operation: GPPrimitive, span: PhraseSpan) -> PhraseSpan:
    if isinstance(operation, GlobalTranspose):
        return span.transpose(operation.semitones)
    if isinstance(operation, LocalOctave):
        return _apply_local_octave(operation, span)
    if isinstance(operation, SimplifyRhythm):
        return _apply_simplify_rhythm(operation, span)
    return span


def _operation_window(operation: GPPrimitive, span: PhraseSpan) -> tuple[int, int]:
    try:
        return operation.span.resolve(span)
    except ValueError:
        return (0, span.total_duration)


def _notes_within(span: PhraseSpan, start: int, end: int) -> Tuple[PhraseNote, ...]:
    return tuple(note for note in span.notes if start <= note.onset < end)


def _label_for_operation(
    operation: GPPrimitive,
    before: PhraseSpan,
    *,
    start: int,
    end: int,
    beats_per_measure: int,
    candidate_notes: Iterable[PhraseNote] | None = None,
) -> str | None:
    notes = tuple(candidate_notes or ())
    if not notes:
        notes = _notes_within(before, start, end)
    if notes:
        label = span_label_for_notes(
            notes,
            pulses_per_quarter=before.pulses_per_quarter,
            beats_per_measure=beats_per_measure,
        )
        if label:
            return label
    return operation.span.label or None


def _span_identifier(operation: GPPrimitive, start: int, end: int) -> str:
    label = operation.span.label or "span"
    normalized = "-".join(label.strip().split()) or "span"
    return f"{normalized}-{start}-{end}"
def _reason_for_transpose(operation: GlobalTranspose) -> str:
    semitones = int(operation.semitones)
    if semitones == 0:
        return "Retained original transposition"
    direction = "up" if semitones > 0 else "down"
    steps = abs(semitones)
    plural = "s" if steps != 1 else ""
    return f"Transposed phrase {direction} by {steps} semitone{plural}"


def _reason_for_octave(
    operation: LocalOctave,
    before: PhraseSpan,
    after: PhraseSpan,
    instrument: InstrumentRange,
) -> tuple[str, Tuple[PhraseNote, ...]]:
    shifted = octave_shifted_notes(before, after)
    if not shifted:
        direction = "up" if operation.octaves > 0 else "down"
        steps = abs(operation.octaves)
        plural = "s" if steps != 1 else ""
        return (f"Shifted span {direction} by {steps} octave{plural}", shifted)

    lowest = min(note.midi for note in shifted)
    highest = max(note.midi for note in shifted)
    lowest_name = midi_to_name(lowest)
    highest_name = midi_to_name(highest)
    min_name = midi_to_name(instrument.min_midi)
    max_name = midi_to_name(instrument.max_midi)

    if highest > instrument.max_midi:
        reason = f"RANGE_EDGE ({lowest_name}..{highest_name} > max {max_name})"
    elif lowest < instrument.min_midi:
        reason = f"RANGE_EDGE ({lowest_name}..{highest_name} < min {min_name})"
    else:
        direction = "up" if operation.octaves > 0 else "down"
        steps = abs(operation.octaves)
        plural = "s" if steps != 1 else ""
        reason = f"Shifted span {direction} by {steps} octave{plural}"
    return reason, shifted


def _reason_for_rhythm(operation: SimplifyRhythm) -> str:
    subdivisions = max(1, int(operation.subdivisions))
    plural = "s" if subdivisions != 1 else ""
    return f"Simplified rhythm to {subdivisions}-note subdivision{plural}"


def explain_program(
    program: Sequence[GPPrimitive],
    span: PhraseSpan,
    instrument: InstrumentRange,
    *,
    beats_per_measure: int = 4,
    grace_settings: GraceSettings | None = None,
) -> Tuple[ExplanationEvent, ...]:
    """Return ordered ``ExplanationEvent`` entries for ``program``."""

    if not program:
        return ()

    beats_per_measure = max(1, int(beats_per_measure))
    current = span
    events: list[tuple[int, int, ExplanationEvent]] = []

    for index, operation in enumerate(program):
        before = current
        after = _apply_operation(operation, before)
        if after == before:
            current = after
            continue

        start, end = _operation_window(operation, before)
        span_id = _span_identifier(operation, start, end)

        before_score = difficulty_score(
            summarize_difficulty(before, instrument, grace_settings=grace_settings),
            grace_settings=grace_settings,
        )
        after_score = difficulty_score(
            summarize_difficulty(after, instrument, grace_settings=grace_settings),
            grace_settings=grace_settings,
        )

        if isinstance(operation, GlobalTranspose):
            reason = _reason_for_transpose(operation)
            reason_code = operation.reason_code()
            label_notes: Iterable[PhraseNote] | None = None
        elif isinstance(operation, LocalOctave):
            reason, shifted = _reason_for_octave(operation, before, after, instrument)
            reason_code = operation.reason_code()
            label_notes = shifted
        elif isinstance(operation, SimplifyRhythm):
            reason = _reason_for_rhythm(operation)
            reason_code = operation.reason_code()
            label_notes = None
        else:
            reason = f"Applied {operation.action_name()}"
            reason_code = operation.reason_code()
            label_notes = None

        span_label = _label_for_operation(
            operation,
            before,
            start=start,
            end=end,
            beats_per_measure=beats_per_measure,
            candidate_notes=label_notes,
        )

        event = ExplanationEvent.from_step(
            action=operation.action_name(),
            reason=reason,
            before=before,
            after=after,
            difficulty_before=before_score,
            difficulty_after=after_score,
            beats_per_measure=beats_per_measure,
            reason_code=reason_code,
            span_id=span_id,
            span_label=span_label,
        )
        pulses_per_bar = max(1, before.pulses_per_quarter * beats_per_measure)
        bar_override = (start // pulses_per_bar) + 1
        if bar_override != event.bar:
            event = replace(event, bar=bar_override)
        events.append((start, index, event))
        current = after

    ordered = [entry[2] for entry in sorted(events, key=lambda item: (item[0], item[1]))]
    return tuple(ordered)


__all__ = ["explain_program"]
