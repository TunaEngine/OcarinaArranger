"""Helpers that clamp arranged spans to the active instrument range."""

from __future__ import annotations

from typing import Tuple

from shared.ottava import OttavaShift

from .difficulty import difficulty_score, summarize_difficulty
from .explanations import ExplanationEvent
from .phrase import PhraseNote, PhraseSpan
from .soft_key import InstrumentRange


def span_exceeds_range(span: PhraseSpan, instrument: InstrumentRange) -> bool:
    """Return ``True`` when any note falls outside the instrument range."""

    for note in span.notes:
        if note.midi < instrument.min_midi or note.midi > instrument.max_midi:
            return True
    return False


def _clamp_note_to_range(
    note: PhraseNote, instrument: InstrumentRange
) -> Tuple[PhraseNote, bool]:
    target = note.midi
    shift_octaves = 0
    for _ in range(8):
        if instrument.min_midi <= target <= instrument.max_midi:
            break
        if target > instrument.max_midi:
            target -= 12
            shift_octaves -= 1
        elif target < instrument.min_midi:
            target += 12
            shift_octaves += 1
    else:
        if target > instrument.max_midi:
            target = instrument.max_midi
        elif target < instrument.min_midi:
            target = instrument.min_midi

    if target == note.midi:
        return note, False

    adjusted = note.with_midi(target)
    if shift_octaves != 0:
        adjusted = adjusted.add_ottava_shift(
            OttavaShift(
                source="octave-shift",
                direction="up" if shift_octaves > 0 else "down",
                size=8 * abs(shift_octaves),
            )
        )
    return adjusted, True


def clamp_span_to_range(
    span: PhraseSpan, instrument: InstrumentRange
) -> Tuple[PhraseSpan, bool]:
    """Return a span with every note transposed by octaves into range."""

    if not span.notes:
        return span, False

    updated: list[PhraseNote] = []
    changed = False
    for note in span.notes:
        adjusted, modified = _clamp_note_to_range(note, instrument)
        updated.append(adjusted)
        changed = changed or modified

    if not changed:
        return span, False

    return span.with_notes(updated), True


def enforce_instrument_range(
    span: PhraseSpan,
    instrument: InstrumentRange,
    *,
    beats_per_measure: int,
) -> tuple[PhraseSpan, ExplanationEvent | None, float | None]:
    """Clamp ``span`` to ``instrument`` range and emit an explanation event."""

    if not span_exceeds_range(span, instrument):
        return span, None, None

    clamped_span, changed = clamp_span_to_range(span, instrument)
    if not changed:
        return span, None, None

    before_summary = summarize_difficulty(span, instrument)
    before_difficulty = difficulty_score(before_summary)
    after_summary = summarize_difficulty(clamped_span, instrument)
    after_difficulty = difficulty_score(after_summary)
    event = ExplanationEvent.from_step(
        action="range-clamp",
        reason="Clamped notes to instrument range",
        before=span,
        after=clamped_span,
        difficulty_before=before_difficulty,
        difficulty_after=after_difficulty,
        beats_per_measure=max(1, beats_per_measure),
        reason_code="range-clamp",
    )
    return clamped_span, event, after_difficulty


__all__ = [
    "clamp_span_to_range",
    "enforce_instrument_range",
    "span_exceeds_range",
]

