"""Helpers that clamp arranged spans to the active instrument range."""

from __future__ import annotations

from typing import Optional, Tuple

from shared.ottava import OttavaShift

from .config import GraceSettings, DEFAULT_GRACE_SETTINGS
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
    note: PhraseNote,
    instrument: InstrumentRange,
    *,
    is_top_voice: bool = False,
    previous_top_voice: Optional[int] = None,
    next_top_voice: Optional[int] = None,
    prefer_octave_top_voice: bool = False,
) -> Tuple[PhraseNote, bool]:
    boundary_target = min(max(note.midi, instrument.min_midi), instrument.max_midi)

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
        target = boundary_target
        shift_octaves = 0

    if target != note.midi:
        preserves_pitch_class = (target - note.midi) % 12 == 0
        prefer_boundary = note.midi < instrument.min_midi or not preserves_pitch_class
        if (
            prefer_boundary
            and prefer_octave_top_voice
            and is_top_voice
            and preserves_pitch_class
            and instrument.min_midi <= target <= instrument.max_midi
        ):
            prefer_boundary = False
        if prefer_boundary:
            octave_distance = abs(target - note.midi)
            boundary_distance = abs(boundary_target - note.midi)
            boundary_preferred = False

            if boundary_distance < octave_distance:
                boundary_preferred = True
            elif boundary_distance == octave_distance and boundary_target < target:
                boundary_preferred = True

            if boundary_preferred:
                if not is_top_voice:
                    target = boundary_target
                    shift_octaves = 0
                else:
                    neighbor_matches = 0
                    if previous_top_voice is not None and previous_top_voice == boundary_target:
                        neighbor_matches += 1
                    if next_top_voice is not None and next_top_voice == boundary_target:
                        neighbor_matches += 1

                    improvement = octave_distance - boundary_distance
                    if neighbor_matches < 2 and (improvement >= 4 or boundary_distance <= 5):
                        target = boundary_target
                        shift_octaves = 0

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
    span: PhraseSpan,
    instrument: InstrumentRange,
    *,
    prefer_octave_top_voice: bool = False,
) -> Tuple[PhraseSpan, bool]:
    """Return a span with every note transposed by octaves into range."""

    # ``prefer_octave_top_voice`` allows callers that already applied a uniform
    # register shift (for example a pure ``GlobalTranspose``) to keep the top
    # voice aligned by favouring octave-adjusted notes over boundary snaps.

    if not span.notes:
        return span, False

    grouped: dict[int, list[PhraseNote]] = {}
    for note in span.notes:
        grouped.setdefault(note.onset, []).append(note)

    top_voice_map = {
        onset: max(group, key=lambda item: item.midi).midi for onset, group in grouped.items()
    }

    notes = list(span.notes)
    top_voice_flags = [
        note.midi >= top_voice_map.get(note.onset, note.midi) for note in notes
    ]
    next_top_voice: list[Optional[int]] = [None] * len(notes)
    upcoming: Optional[int] = None
    for index in range(len(notes) - 1, -1, -1):
        next_top_voice[index] = upcoming
        if top_voice_flags[index]:
            upcoming = notes[index].midi

    updated: list[PhraseNote] = []
    changed = False
    previous_top_voice: Optional[int] = None
    for index, note in enumerate(notes):
        is_top_voice = top_voice_flags[index]
        adjusted, modified = _clamp_note_to_range(
            note,
            instrument,
            is_top_voice=is_top_voice,
            previous_top_voice=previous_top_voice,
            next_top_voice=next_top_voice[index],
            prefer_octave_top_voice=prefer_octave_top_voice,
        )
        updated.append(adjusted)
        changed = changed or modified
        if is_top_voice:
            previous_top_voice = adjusted.midi

    if not changed:
        return span, False

    return span.with_notes(updated), True


def enforce_instrument_range(
    span: PhraseSpan,
    instrument: InstrumentRange,
    *,
    beats_per_measure: int,
    prefer_octave_top_voice: bool = False,
    grace_settings: GraceSettings | None = None,
) -> tuple[PhraseSpan, ExplanationEvent | None, float | None]:
    """Clamp ``span`` to ``instrument`` range and emit an explanation event."""

    if not span_exceeds_range(span, instrument):
        return span, None, None

    clamped_span, changed = clamp_span_to_range(
        span,
        instrument,
        prefer_octave_top_voice=prefer_octave_top_voice,
    )
    if not changed:
        return span, None, None

    active_settings = grace_settings or DEFAULT_GRACE_SETTINGS
    before_summary = summarize_difficulty(span, instrument, grace_settings=active_settings)
    before_difficulty = difficulty_score(before_summary, grace_settings=active_settings)
    after_summary = summarize_difficulty(clamped_span, instrument, grace_settings=active_settings)
    after_difficulty = difficulty_score(after_summary, grace_settings=active_settings)
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

