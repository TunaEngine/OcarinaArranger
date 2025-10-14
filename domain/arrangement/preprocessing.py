"""Preprocessing helpers applied before salvage in the arranger pipeline."""

from __future__ import annotations

from typing import Tuple

from .constraints import (
    BreathSettings,
    SubholeConstraintSettings,
    TempoContext,
    calculate_subhole_speed,
    enforce_subhole_and_speed,
    plan_breaths,
)
from .difficulty import difficulty_score, summarize_difficulty
from .explanations import ExplanationEvent
from .phrase import PhraseSpan
from .soft_key import InstrumentRange

_SUBHOLE_RATE_ACTION = "SUBHOLE_RATE_REPLACE"
_BREATH_INSERT_ACTION = "BREATH_INSERT"
_GRACE_DURATION = 1


def apply_subhole_constraints(
    span: PhraseSpan,
    instrument: InstrumentRange,
    *,
    tempo_bpm: float,
    subhole_settings: SubholeConstraintSettings,
) -> tuple[PhraseSpan, tuple[ExplanationEvent, ...]]:
    if tempo_bpm <= 0:
        return span, ()

    tempo = TempoContext(bpm=tempo_bpm, pulses_per_quarter=max(1, span.pulses_per_quarter))
    metrics = calculate_subhole_speed(span, tempo, subhole_settings)

    violating_pairs = tuple(
        pair
        for pair, rate in metrics.pair_rates
        if rate > subhole_settings.pair_limits[pair].max_hz
    )
    over_cap = (
        metrics.changes_per_second > subhole_settings.max_changes_per_second
        or metrics.subhole_changes_per_second > subhole_settings.max_subhole_changes_per_second
        or bool(violating_pairs)
    )
    if not over_cap:
        return span, ()

    replacement = _replace_subhole_run(span)
    if replacement is None:
        enforced = enforce_subhole_and_speed(span, tempo, subhole_settings)
        replacement = enforced.span
        if replacement == span:
            return span, ()

    before_summary = summarize_difficulty(span, instrument)
    after_summary = summarize_difficulty(replacement, instrument)

    event = ExplanationEvent.from_step(
        action=_SUBHOLE_RATE_ACTION,
        reason="subhole_changes/sec > cap",
        before=span,
        after=replacement,
        difficulty_before=difficulty_score(before_summary),
        difficulty_after=difficulty_score(after_summary),
        reason_code="subhole-rate-replace",
    )
    return replacement, (event,)


def apply_breath_planning(
    span: PhraseSpan,
    instrument: InstrumentRange,
    *,
    tempo_bpm: float,
    settings: BreathSettings,
    beats_per_measure: int = 4,
) -> tuple[PhraseSpan, tuple[ExplanationEvent, ...]]:
    if tempo_bpm <= 0:
        return span, ()

    tempo = TempoContext(bpm=tempo_bpm, pulses_per_quarter=max(1, span.pulses_per_quarter))
    plan = plan_breaths(span, tempo, settings)
    if not plan.breath_points:
        return span, ()

    current = span
    events: list[ExplanationEvent] = []

    total_duration = span.total_duration
    for breath_onset in plan.breath_points:
        if total_duration and breath_onset >= total_duration:
            continue
        inserted = _insert_breath(current, breath_onset)
        if inserted is None:
            continue

        updated, split_point = inserted

        before_summary = summarize_difficulty(current, instrument)
        after_summary = summarize_difficulty(updated, instrument)

        event = ExplanationEvent.from_step(
            action=_BREATH_INSERT_ACTION,
            reason="continuous_blow_time > T",
            before=current,
            after=updated,
            difficulty_before=difficulty_score(before_summary),
            difficulty_after=difficulty_score(after_summary),
            beats_per_measure=beats_per_measure,
            reason_code="breath-insert",
            span_label=_breath_span_label(split_point, current, beats_per_measure),
        )

        events.append(event)
        current = updated

    return current, tuple(events)


def _replace_subhole_run(span: PhraseSpan) -> PhraseSpan | None:
    notes = span.notes
    if len(notes) < 2:
        return None

    start_onset = notes[0].onset
    total_duration = max(1, span.total_duration)

    grace_source = notes[0]
    grace_tags = tuple(tag for tag in grace_source.tags if tag != "ornamental")
    grace_note = grace_source.with_onset(start_onset).with_duration(_GRACE_DURATION).with_tags(grace_tags)

    sustain_source = max(notes[1:], key=lambda note: (note.duration, note.midi), default=notes[0])
    sustain_tags = tuple(tag for tag in sustain_source.tags if tag != "ornamental")
    sustain_note = sustain_source.with_onset(start_onset).with_duration(total_duration).with_tags(sustain_tags)

    candidate = span.with_notes((grace_note, sustain_note))
    if candidate.notes == span.notes:
        return None
    return candidate


def _insert_breath(span: PhraseSpan, breath_onset: int) -> tuple[PhraseSpan, int] | None:
    notes = list(span.notes)
    for index, note in enumerate(notes):
        start = note.onset
        end = note.onset + note.duration
        if breath_onset < start:
            continue
        if breath_onset > end:
            continue
        split_point = _normalized_breath_onset(note, breath_onset)
        if split_point is None:
            continue

        before_duration = split_point - start
        after_duration = end - split_point
        if before_duration <= 0 or after_duration <= 0:
            continue

        first_tags = set(note.tags)
        first_tags.add("breath-mark")
        second_tags = set(note.tags)
        second_tags.discard("breath-mark")

        first = note.with_duration(before_duration).with_tags(first_tags)
        second = note.with_onset(split_point).with_duration(after_duration).with_tags(second_tags)

        notes[index : index + 1] = [first, second]
        return span.with_notes(notes), split_point

    return None


def _normalized_breath_onset(note, breath_onset: int) -> int | None:
    start = note.onset
    end = note.onset + note.duration
    candidate = int(breath_onset)
    if candidate <= start or candidate >= end:
        midpoint = start + max(1, note.duration // 2)
        if midpoint <= start or midpoint >= end:
            return None
        candidate = midpoint
    return candidate


def _breath_span_label(breath_onset: int, span: PhraseSpan, beats_per_measure: int) -> str | None:
    pulses_per_quarter = max(1, span.pulses_per_quarter)
    pulses_per_measure = max(1, pulses_per_quarter * max(1, beats_per_measure))
    measure_start = (breath_onset // pulses_per_measure) * pulses_per_measure
    beat_index = int((breath_onset - measure_start) / pulses_per_quarter) + 1
    if beat_index <= 0:
        return None
    return f"beat {beat_index}"


__all__ = ["apply_subhole_constraints", "apply_breath_planning"]
