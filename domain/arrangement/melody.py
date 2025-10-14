"""Melody isolation helpers for the arranger pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import statistics
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


def _continuity_sort_key(
    candidate: PhraseNote,
    previous_midi: int,
    register_pivot: int,
    register_anchor: int | None,
    *,
    shortest_duration: int,
) -> tuple[int, int, int, int, int, int]:
    """Prefer notes near the prior melody while nudging back toward the pivot."""

    delta = abs(candidate.midi - previous_midi)
    pivot_delta = abs(candidate.midi - register_pivot)
    if register_anchor is not None:
        anchor_delta = abs(candidate.midi - register_anchor)
        if candidate.midi < register_anchor and candidate.duration <= shortest_duration:
            anchor_weight = 1
        elif candidate.midi > register_anchor and candidate.duration > shortest_duration:
            anchor_weight = 3
        else:
            anchor_weight = 2
        delta = delta + (anchor_delta * anchor_weight)
    else:
        anchor_delta = pivot_delta
    if candidate.duration > shortest_duration:
        excess = candidate.duration - shortest_duration
        duration_penalty = 1 + (excess - 1) // shortest_duration
        delta += duration_penalty
    else:
        duration_penalty = 0
    # Shorter notes tend to carry the moving melodic voice when harmony sustains.
    return (
        delta,
        duration_penalty,
        anchor_delta,
        pivot_delta,
        candidate.duration,
        candidate.midi,
    )


def _duplicate_sort_key(
    candidate: PhraseNote,
    anchor_midi: int,
    register_pivot: int,
    *,
    min_duration: int,
    lowest_midi: int,
    lowest_count: int,
    same_midi_count: int,
    max_duplicate_count: int,
    anchor_from_previous: bool,
) -> tuple[int, int, int, int, int, int, int]:
    """Score duplicate pitch-class options, prioritizing anchored registers."""

    if anchor_from_previous:
        raw_anchor_delta = abs(candidate.midi - anchor_midi)
        if candidate.midi <= anchor_midi:
            anchor_delta = max(0, raw_anchor_delta - 12)
        else:
            anchor_delta = raw_anchor_delta
    else:
        anchor_delta = abs(candidate.midi - anchor_midi)
    pivot_delta = abs(candidate.midi - register_pivot)

    # Penalize octave jumps away from the anchored register when we already
    # established a melody voice. This keeps long accompaniment notes from
    # yanking the melody up or down an octave when the pitch class repeats.
    if anchor_from_previous:
        octave_penalty = max(0, (candidate.midi - anchor_midi) // 12)
    else:
        octave_penalty = max(0, (candidate.midi - anchor_midi) // 12)

    if candidate.midi == lowest_midi:
        if lowest_count == 1 and max_duplicate_count > 1:
            register_bias = 0
        else:
            register_bias = 1
    else:
        register_bias = 1 if same_midi_count == 1 else 2

    duplicate_penalty = max(0, same_midi_count - 1)

    # Prefer the most melodic (usually shorter) duration when multiple voices
    # repeat the pitch class. Longer sustaining pads tend to belong to the
    # accompaniment and should lose ties when competing with the melody.
    if candidate.duration > min_duration:
        excess = candidate.duration - min_duration
        duration_penalty = 1 + (excess - 1) // min_duration
    else:
        duration_penalty = 0

    # Keep lower registers when everything else ties so we don't drift upward
    # across repeated duplicates.
    return (
        register_bias,
        duplicate_penalty,
        octave_penalty,
        duration_penalty,
        anchor_delta,
        pivot_delta,
        candidate.midi,
    )


def _is_high_octave_duplicate(high: PhraseNote, low: PhraseNote) -> bool:
    interval = high.midi - low.midi
    if interval < 12:
        return False
    return interval % 12 == 0 and low.duration >= high.duration


def _register_pivot(notes: Sequence[PhraseNote]) -> int:
    if not notes:
        return 0
    by_onset: dict[int, list[int]] = {}
    for note in notes:
        by_onset.setdefault(note.onset, []).append(note.midi)
    minima = [min(midis) for midis in by_onset.values()]
    ordered = sorted(note.midi for note in notes) + minima
    ordered.sort()
    pivot = statistics.median_low(ordered)
    return int(pivot)


def isolate_melody(span: PhraseSpan, *, beats_per_measure: int = 4) -> MelodyIsolationResult:
    """Return a span that keeps the melodic voice from polyphonic input."""

    if beats_per_measure <= 0:
        raise ValueError("beats_per_measure must be positive")

    if not span.notes:
        return MelodyIsolationResult(span=span, events=tuple(), actions=tuple())

    pulses_per_measure = span.pulses_per_quarter * beats_per_measure
    grouped = _group_by_onset(span.notes)
    register_pivot = _register_pivot(span.notes)
    kept_notes: list[PhraseNote] = []

    per_measure: dict[int, dict[str, list[PhraseNote]]] = {}

    for note in span.notes:
        measure = _measure_index(note, pulses_per_measure=pulses_per_measure)
        info = per_measure.setdefault(measure, {"before": [], "after": [], "removed": []})
        info["before"].append(note)

    previous_midi: int | None = None
    register_anchor_midi: int | None = None

    for onset in sorted(grouped.keys()):
        notes_at_onset = grouped[onset]
        measure = _measure_index(notes_at_onset[0], pulses_per_measure=pulses_per_measure)
        info = per_measure.setdefault(measure, {"before": [], "after": [], "removed": []})

        onset_shortest_duration = min(note.duration for note in notes_at_onset)

        if len(notes_at_onset) == 1:
            note = notes_at_onset[0]
            kept_notes.append(note)
            info["after"].append(note)
            previous_midi = note.midi
            continue

        pitch_class_groups: dict[int, list[PhraseNote]] = {}
        for candidate in notes_at_onset:
            group = pitch_class_groups.setdefault(candidate.midi % 12, [])
            group.append(candidate)

        duplicate_candidates = [
            candidate
            for group in pitch_class_groups.values()
            if len(group) > 1
            for candidate in group
        ]

        if register_anchor_midi is not None:
            anchor_midi = register_anchor_midi
            anchor_from_previous = False
        else:
            anchor_midi = previous_midi if previous_midi is not None else register_pivot
            anchor_from_previous = previous_midi is not None
            if previous_midi is not None and abs(previous_midi - register_pivot) >= 12:
                anchor_midi = register_pivot
                anchor_from_previous = False

        duplicate_midi_counts: dict[int, int] | None = None

        if duplicate_candidates:
            min_duration = min(candidate.duration for candidate in duplicate_candidates)
            lowest_midi = min(candidate.midi for candidate in duplicate_candidates)
            highest_midi = max(candidate.midi for candidate in duplicate_candidates)
            register_counts: dict[int, int] = {}
            for candidate in duplicate_candidates:
                register_counts[candidate.midi] = register_counts.get(candidate.midi, 0) + 1
            max_duplicate_count = max(register_counts.values())
            lowest_count = register_counts.get(lowest_midi, 0)
            duplicate_midi_counts = register_counts
            if (
                previous_midi is None
                and lowest_count == 1
                and max_duplicate_count > 1
                and highest_midi - lowest_midi >= 12
            ):
                anchor_midi = lowest_midi
                anchor_from_previous = False
            keep = min(
                duplicate_candidates,
                key=lambda candidate: _duplicate_sort_key(
                    candidate,
                    anchor_midi,
                    register_pivot,
                    min_duration=min_duration,
                    lowest_midi=lowest_midi,
                    lowest_count=lowest_count,
                    same_midi_count=register_counts[candidate.midi],
                    max_duplicate_count=max_duplicate_count,
                    anchor_from_previous=anchor_from_previous,
                ),
            )
            selection_reason = (
                "register_anchor"
                if previous_midi is None
                or abs(previous_midi - register_pivot) >= 12
                or abs(keep.midi - register_pivot) < abs(keep.midi - anchor_midi)
                else "voice_continuity"
            )
        elif previous_midi is not None:
            shortest_duration = min(candidate.duration for candidate in notes_at_onset)
            keep = min(
                notes_at_onset,
                key=lambda candidate: _continuity_sort_key(
                    candidate,
                    previous_midi,
                    register_pivot,
                    register_anchor_midi,
                    shortest_duration=shortest_duration,
                ),
            )
            selection_reason = "voice_continuity"
        else:
            keep = min(
                notes_at_onset,
                key=lambda candidate: (
                    abs(candidate.midi - register_pivot),
                    -candidate.duration,
                    candidate.midi,
                ),
            )
            selection_reason = "register_anchor"

        drop_reason: str | None = None

        for candidate in notes_at_onset:
            if candidate is keep:
                continue
            high, low = (candidate, keep) if candidate.midi > keep.midi else (keep, candidate)
            if _is_high_octave_duplicate(high, low):
                low_unique = (
                    duplicate_midi_counts is not None
                    and duplicate_midi_counts.get(low.midi, 0) == 1
                    and duplicate_midi_counts.get(high.midi, 0) > 1
                )
                if (
                    abs(low.midi - register_pivot) <= abs(high.midi - register_pivot)
                    or low_unique
                ):
                    drop_reason = _DROP_HIGH_DUPLICATE_REASON
                    keep = low
                    selection_reason = "register_anchor"
                    break

        if (
            selection_reason == "voice_continuity"
            and abs(keep.midi - register_pivot) >= 12
        ):
            anchored = min(
                notes_at_onset,
                key=lambda candidate: (
                    abs(candidate.midi - register_pivot),
                    candidate.duration,
                    candidate.midi,
                ),
            )
            if anchored is not keep and abs(anchored.midi - register_pivot) < abs(keep.midi - register_pivot):
                keep = anchored
                selection_reason = "register_anchor"

        kept_notes.append(keep)
        info["after"].append(keep)
        if selection_reason == "register_anchor":
            info["register_anchor_used"] = True
            register_anchor_midi = keep.midi
        elif (
            register_anchor_midi is not None
            and keep.midi < register_anchor_midi
            and keep.duration <= onset_shortest_duration
        ):
            info["register_anchor_used"] = True
            register_anchor_midi = keep.midi
        if selection_reason == "voice_continuity" or 'selection_reason' not in info:
            info["selection_reason"] = selection_reason
        previous_midi = keep.midi
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

        selection_reason = info.get("selection_reason")
        anchor_used = info.get("register_anchor_used", False)
        if selection_reason == "voice_continuity":
            reason_parts = ["register_anchor"] if anchor_used else []
            reason_parts.append("voice_continuity")
        elif selection_reason == "register_anchor" or anchor_used:
            reason_parts = ["register_anchor"]
        else:
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

