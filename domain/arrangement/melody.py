"""Melody isolation helpers for the arranger pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence, Tuple

from .explanations import ExplanationEvent
from .phrase import PhraseNote, PhraseSpan


@dataclass(frozen=True)
class MelodyIsolationAction:
    """Human-readable summary of a melody isolation decision."""

    measure: int
    action: str
    reason: str
    kept_voice: int
    removed_voice: int


@dataclass(frozen=True)
class MelodyIsolationResult:
    """Result of melody isolation containing the updated span and metadata."""

    span: PhraseSpan
    events: Tuple[ExplanationEvent, ...]
    actions: Tuple[MelodyIsolationAction, ...]


def _group_by_onset(notes: Sequence[PhraseNote]) -> Mapping[int, Tuple[PhraseNote, ...]]:
    grouped: dict[int, Tuple[PhraseNote, ...]] = {}
    for note in notes:
        onset_group = grouped.setdefault(note.onset, tuple())
        grouped[note.onset] = onset_group + (note,)
    return grouped


def _measure_index(note: PhraseNote, *, pulses_per_measure: int) -> int:
    if pulses_per_measure <= 0:
        raise ValueError("pulses_per_measure must be positive")
    return note.onset // pulses_per_measure


_DROP_HIGH_DUPLICATE_REASON = "salience*contrast < added_difficulty"


def _is_high_octave_duplicate(high: PhraseNote, low: PhraseNote) -> bool:
    interval = high.midi - low.midi
    if interval < 12:
        return False
    return interval % 12 == 0 and low.duration >= high.duration


def isolate_melody(span: PhraseSpan, *, beats_per_measure: int = 4) -> MelodyIsolationResult:
    """Return a span that keeps the melodic voice from polyphonic input."""

    if beats_per_measure <= 0:
        raise ValueError("beats_per_measure must be positive")

    if not span.notes:
        return MelodyIsolationResult(span=span, events=tuple(), actions=tuple())

    pulses_per_measure = span.pulses_per_quarter * beats_per_measure
    grouped = _group_by_onset(span.notes)
    kept_notes: list[PhraseNote] = []

    per_measure: dict[int, dict[str, list[PhraseNote]]] = {}

    for note in span.notes:
        measure = _measure_index(note, pulses_per_measure=pulses_per_measure)
        info = per_measure.setdefault(measure, {"before": [], "after": [], "removed": []})
        info["before"].append(note)

    for onset in sorted(grouped.keys()):
        notes_at_onset = grouped[onset]
        if len(notes_at_onset) == 1:
            note = notes_at_onset[0]
            kept_notes.append(note)
            measure = _measure_index(note, pulses_per_measure=pulses_per_measure)
            per_measure[measure]["after"].append(note)
            continue

        sorted_candidates = sorted(
            notes_at_onset,
            key=lambda candidate: (candidate.midi, -candidate.duration),
        )
        keep = sorted_candidates[-1]
        drop_reason: str | None = None

        for candidate in reversed(sorted_candidates[:-1]):
            if _is_high_octave_duplicate(keep, candidate):
                drop_reason = _DROP_HIGH_DUPLICATE_REASON
                keep = candidate
                break

        kept_notes.append(keep)
        measure = _measure_index(keep, pulses_per_measure=pulses_per_measure)
        info = per_measure.setdefault(measure, {"before": [], "after": [], "removed": []})
        info["after"].append(keep)
        for candidate in notes_at_onset:
            if candidate is keep:
                continue
            info["removed"].append(candidate)
        if drop_reason is not None:
            info["drop_reason"] = drop_reason

    kept_span = span.with_notes(kept_notes)

    events: list[ExplanationEvent] = []
    actions: list[MelodyIsolationAction] = []

    for measure in sorted(per_measure.keys()):
        info = per_measure[measure]
        removed = info.get("removed", [])
        if not removed:
            continue

        before_notes: Iterable[PhraseNote] = info.get("before", [])
        after_notes: Iterable[PhraseNote] = info.get("after", before_notes)
        before_span = PhraseSpan(tuple(before_notes), pulses_per_quarter=span.pulses_per_quarter)
        after_span = PhraseSpan(tuple(after_notes), pulses_per_quarter=span.pulses_per_quarter)

        drop_reason = info.get("drop_reason")
        if drop_reason is not None:
            event = ExplanationEvent.from_step(
                action="DROP_HIGH_DUPLICATE",
                reason=drop_reason,
                before=before_span,
                after=after_span,
                difficulty_before=0.0,
                difficulty_after=0.0,
                beats_per_measure=beats_per_measure,
                reason_code="drop-high-duplicate",
            )
            events.append(event)
            actions.append(
                MelodyIsolationAction(
                    measure=event.bar,
                    action=event.action,
                    reason=event.reason,
                    kept_voice=1,
                    removed_voice=2,
                )
            )
            continue

        reason_parts = ["highest_voice"]
        if all(note.onset % span.pulses_per_quarter == 0 for note in after_notes):
            reason_parts.append("onbeat")

        removed_midis = {note.midi for note in removed}
        kept_total = sum(note.duration for note in after_notes)
        removed_total = sum(note.duration for note in removed)
        if removed_midis and (len(removed_midis) > 1 or kept_total > removed_total):
            reason_parts.append("longer_durations")

        reason = " + ".join(reason_parts)
        event = ExplanationEvent.from_step(
            action="MELODY_ISOLATION",
            reason=reason,
            before=before_span,
            after=after_span,
            difficulty_before=0.0,
            difficulty_after=0.0,
            beats_per_measure=beats_per_measure,
            reason_code="melody-isolation",
        )
        events.append(event)
        actions.append(
            MelodyIsolationAction(
                measure=event.bar,
                action=event.action,
                reason=event.reason,
                kept_voice=1,
                removed_voice=2,
            )
        )

    return MelodyIsolationResult(
        span=kept_span,
        events=tuple(events),
        actions=tuple(actions),
    )


__all__ = [
    "MelodyIsolationAction",
    "MelodyIsolationResult",
    "isolate_melody",
]

