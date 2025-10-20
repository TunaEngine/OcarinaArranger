from __future__ import annotations

from typing import Iterable

from .config import DEFAULT_GRACE_SETTINGS, GraceSettings
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
from .phrase import PhraseNote, PhraseSpan
from .soft_key import InstrumentRange

_SUBHOLE_RATE_ACTION = "SUBHOLE_RATE_REPLACE"
_BREATH_INSERT_ACTION = "BREATH_INSERT"
_GRACE_ACTION = "GRACE_NORMALIZE"
_GRACE_DURATION = 1


def apply_grace_realization(
    span: PhraseSpan,
    instrument: InstrumentRange,
    *,
    tempo_bpm: float | None,
    settings: GraceSettings | None = None,
) -> tuple[PhraseSpan, tuple[ExplanationEvent, ...]]:
    active_settings = settings or DEFAULT_GRACE_SETTINGS
    notes = list(span.notes)
    if not notes:
        return span, ()

    adjusted: list[PhraseNote] = []
    shift = 0
    modified = False
    reasons: set[str] = set()
    tempo = float(tempo_bpm) if tempo_bpm is not None else None
    anchor_min = active_settings.anchor_min_ticks(span.pulses_per_quarter)

    index = 0
    count = len(notes)
    while index < count:
        note = notes[index]
        if "grace" not in note.tags:
            adjusted.append(note.with_onset(max(0, note.onset - shift)))
            index += 1
            continue

        chain: list[PhraseNote] = []
        while index < count and "grace" in notes[index].tags:
            chain.append(notes[index])
            index += 1
        anchor = notes[index] if index < count else None

        if anchor is None:
            local_removed = sum(note.duration for note in chain)
            if local_removed:
                shift += local_removed
                modified = True
                reasons.add("trailing-grace-drop")
            continue

        keep_indices: Iterable[int]
        chain_length = len(chain)
        if tempo is not None and tempo > active_settings.fast_tempo_bpm:
            keep_indices = ()
            reasons.add("tempo-fast")
        elif active_settings.max_chain == 0:
            keep_indices = ()
            reasons.add("max-chain")
        elif active_settings.max_chain > 0 and chain_length > active_settings.max_chain:
            keep_indices = range(chain_length - active_settings.max_chain, chain_length)
            reasons.add("max-chain")
        else:
            keep_indices = range(chain_length)

        kept_set = set(keep_indices)
        if anchor.duration < anchor_min and kept_set:
            kept_set = set()
            reasons.add("anchor-min")

        dropped_duration = 0
        local_shift = 0
        kept_notes: list[PhraseNote] = []
        for idx_in_chain, grace_note in enumerate(chain):
            if idx_in_chain not in kept_set:
                local_shift += grace_note.duration
                dropped_duration += grace_note.duration
                modified = True
                reasons.add("grace-drop")
                continue

            resolved = _resolve_grace_midi(
                grace_note.midi,
                anchor.midi,
                instrument,
                active_settings,
            )
            if resolved is None:
                local_shift += grace_note.duration
                dropped_duration += grace_note.duration
                modified = True
                reasons.add("grace-drop")
                continue
            if resolved != grace_note.midi:
                grace_note = grace_note.with_midi(resolved)
                modified = True
                reasons.add("grace-fold")

            kept_notes.append(grace_note)

        updated_anchor = anchor
        if dropped_duration:
            updated_anchor = updated_anchor.with_duration(anchor.duration + dropped_duration)
            modified = True
            reasons.add("anchor-extended")
        principal_total = updated_anchor.duration

        allocations = _allocate_grace_durations(
            principal_total,
            len(kept_notes),
            tempo,
            active_settings,
        )

        if len(allocations) < len(kept_notes):
            drop_count = len(kept_notes) - len(allocations)
            if drop_count:
                reasons.add("grace-drop")
            kept_notes = kept_notes[drop_count:]
            allocations = allocations[-len(kept_notes) :] if kept_notes else []

        total_grace_duration = sum(allocations)
        max_grace_duration = max(0, principal_total - anchor_min)
        if total_grace_duration > max_grace_duration and total_grace_duration > 0:
            scale = max_grace_duration / total_grace_duration if max_grace_duration else 0.0
            scaled: list[int] = []
            for duration in allocations:
                scaled.append(max(1, int(round(duration * scale))))
            allocations = scaled
            total_grace_duration = sum(allocations)
            overflow = max(0, total_grace_duration - max_grace_duration)
            if allocations and overflow > 0:
                allocations[-1] = max(1, allocations[-1] - overflow)
                total_grace_duration = sum(allocations)

        anchor_duration = max(anchor_min, principal_total - total_grace_duration)
        if anchor_duration > principal_total:
            anchor_duration = principal_total
            allocations = []
            kept_notes = []
            total_grace_duration = 0

        anchor_start = max(0, updated_anchor.onset - shift - local_shift)
        base_onset = max(0, anchor_start - total_grace_duration)
        current_onset = base_onset

        for note, duration in zip(kept_notes, allocations):
            new_note = note.with_onset(current_onset).with_duration(max(1, int(duration)))
            if new_note.onset != note.onset or new_note.duration != note.duration:
                modified = True
            adjusted.append(new_note)
            current_onset += max(1, int(duration))

        updated_anchor = updated_anchor.with_onset(current_onset).with_duration(max(1, int(anchor_duration)))
        if (
            updated_anchor.onset != anchor.onset
            or updated_anchor.duration != anchor.duration
        ):
            modified = True
        adjusted.append(updated_anchor)
        index += 1

    if not modified:
        return span, ()

    updated_span = span.with_notes(adjusted)
    before_summary = summarize_difficulty(span, instrument, grace_settings=active_settings)
    after_summary = summarize_difficulty(
        updated_span,
        instrument,
        grace_settings=active_settings,
    )
    before_difficulty = difficulty_score(before_summary, grace_settings=active_settings)
    after_difficulty = difficulty_score(after_summary, grace_settings=active_settings)
    reason = _grace_reason(reasons, tempo, active_settings)
    event = ExplanationEvent.from_step(
        action=_GRACE_ACTION,
        reason=reason,
        before=span,
        after=updated_span,
        difficulty_before=before_difficulty,
        difficulty_after=after_difficulty,
        beats_per_measure=4,
        reason_code="grace-normalize",
    )
    return updated_span, (event,)


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
    grace_tags = set(grace_source.tags)
    grace_tags.add("grace")
    grace_tags.add("ornamental")
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


def _resolve_grace_midi(
    midi: int,
    anchor_midi: int | None,
    instrument: InstrumentRange,
    settings: GraceSettings,
) -> int | None:
    value = int(midi)
    if settings.fold_out_of_range and anchor_midi is not None:
        while value - anchor_midi > 12:
            value -= 12
        while anchor_midi - value > 12:
            value += 12
    if instrument.min_midi <= value <= instrument.max_midi:
        return value
    if settings.fold_out_of_range:
        while value < instrument.min_midi:
            value += 12
        while value > instrument.max_midi:
            value -= 12
    if instrument.min_midi <= value <= instrument.max_midi:
        return value
    if settings.drop_out_of_range:
        return None
    return value


def _allocate_grace_durations(
    total_ticks: int,
    count: int,
    tempo_bpm: float | None,
    settings: GraceSettings,
) -> list[int]:
    if count <= 0 or total_ticks <= 1 or settings.max_chain == 0:
        return []

    available = max(0, int(total_ticks) - 1)
    if available <= 0:
        return []

    scale = 1.0
    if tempo_bpm is not None and settings.fast_tempo_bpm > settings.slow_tempo_bpm:
        tempo = float(tempo_bpm)
        if tempo <= settings.slow_tempo_bpm:
            scale = 1.0
        elif tempo >= settings.fast_tempo_bpm:
            scale = 0.5
        else:
            span = settings.fast_tempo_bpm - settings.slow_tempo_bpm
            ratio = (tempo - settings.slow_tempo_bpm) / span
            scale = max(0.5, 1.0 - 0.5 * ratio)

    durations: list[int] = []
    remaining = available
    for index in range(count):
        fraction_index = min(index, len(settings.fractions) - 1)
        fraction = settings.fractions[fraction_index] * scale
        raw = int(round(total_ticks * fraction))
        minimum_remaining = max(0, count - index - 1)
        if minimum_remaining >= remaining:
            assigned = 1
        else:
            assigned = max(1, min(remaining - minimum_remaining, raw))
        durations.append(assigned)
        remaining -= assigned
        if remaining <= 0 and index < count - 1:
            break
    return durations


def _grace_reason(reasons: set[str], tempo: float | None, settings: GraceSettings) -> str:
    parts: list[str] = []
    if "tempo-fast" in reasons and tempo is not None:
        parts.append(f"Removed grace chain above {settings.fast_tempo_bpm:.0f} BPM")
    if "max-chain" in reasons:
        if settings.max_chain == 0:
            parts.append("Removed grace notes (disabled by max_chain)")
        else:
            parts.append(f"Trimmed grace chain to <= {settings.max_chain}")
    if "anchor-min" in reasons:
        parts.append("Dropped graces to protect anchor duration")
    if "grace-fold" in reasons:
        parts.append("Folded grace pitches into range")
    if "grace-drop" in reasons or "trailing-grace-drop" in reasons:
        parts.append("Dropped out-of-range grace notes")
    if "anchor-extended" in reasons:
        parts.append("Extended anchor after grace removal")
    if not parts:
        parts.append("Normalized grace notes")
    return "; ".join(parts)


__all__ = [
    "apply_grace_realization",
    "apply_subhole_constraints",
    "apply_breath_planning",
]

