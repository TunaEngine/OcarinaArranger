"""Difficulty scoring helpers for arranger spans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .config import DEFAULT_GRACE_SETTINGS, GraceSettings
from .phrase import PhraseSpan
from .soft_key import InstrumentRange

_LEAP_INTERVAL_THRESHOLD = 5
_LEAP_WEIGHT = 0.75
_FAST_SWITCH_WEIGHT = 0.6


@dataclass(frozen=True)
class DifficultySummary:
    """Aggregate playability metrics for an arranged span."""

    easy: float
    medium: float
    hard: float
    very_hard: float
    tessitura_distance: float
    leap_exposure: float = 0.0
    fast_windway_switch_exposure: float = 0.0
    total_duration: float = 0.0
    grace_duration: float = 0.0

    @property
    def hard_and_very_hard(self) -> float:
        return self.hard + self.very_hard


def _classify_note_difficulty(midi: int, instrument: InstrumentRange) -> str:
    if midi < instrument.min_midi - 2 or midi > instrument.max_midi + 2:
        return "very_hard"
    if midi < instrument.min_midi or midi > instrument.max_midi:
        return "hard"

    span = max(1.0, float(instrument.span))
    center = instrument.comfort_center or (instrument.min_midi + instrument.max_midi) / 2.0
    distance = abs(midi - center)
    medium_threshold = span * 0.2
    hard_threshold = span * 0.35
    if distance <= medium_threshold:
        return "easy"
    if distance <= hard_threshold:
        return "medium"
    return "hard"


def _windways_for(note_midi: int, instrument: InstrumentRange) -> Iterable[int]:
    windway_map = getattr(instrument, "windway_map", None)
    if not windway_map:
        return ()
    if hasattr(instrument, "windways_for"):
        return getattr(instrument, "windways_for")(note_midi)
    return windway_map.get(int(note_midi), ())


def summarize_difficulty(
    span: PhraseSpan,
    instrument: InstrumentRange,
    grace_settings: GraceSettings | None = None,
) -> DifficultySummary:
    active_settings = grace_settings or DEFAULT_GRACE_SETTINGS
    totals = {"easy": 0.0, "medium": 0.0, "hard": 0.0, "very_hard": 0.0}
    weighted_distance = 0.0
    total_duration = 0.0
    grace_duration = 0.0
    center = instrument.comfort_center or (instrument.min_midi + instrument.max_midi) / 2.0
    leap_weight = 0.0
    fast_switch_weight = 0.0

    pairs = list(zip(span.notes, span.notes[1:]))
    sixteenth_duration = max(1, span.pulses_per_quarter // 4)

    for note in span.notes:
        duration = float(note.duration)
        total_duration += duration
        if "grace" in note.tags:
            grace_duration += duration
        category = _classify_note_difficulty(note.midi, instrument)
        totals[category] += duration
        weighted_distance += duration * abs(note.midi - center)

    for first, second in pairs:
        weight = (first.duration + second.duration) / 2.0
        interval = abs(second.midi - first.midi)
        if interval > _LEAP_INTERVAL_THRESHOLD:
            leap_weight += weight

        first_windways = set(_windways_for(first.midi, instrument))
        second_windways = set(_windways_for(second.midi, instrument))
        if not first_windways or not second_windways:
            continue
        if not first_windways.isdisjoint(second_windways):
            continue
        transition_duration = min(first.duration, second.duration)
        if transition_duration <= sixteenth_duration:
            fast_switch_weight += transition_duration

    tessitura_distance = 0.0
    if total_duration > 0:
        tessitura_distance = weighted_distance / total_duration
    leap_exposure = 0.0
    if total_duration > 0:
        leap_exposure = min(1.0, leap_weight / total_duration)
    fast_switch_exposure = 0.0
    if total_duration > 0 and fast_switch_weight > 0:
        fast_switch_exposure = min(1.0, fast_switch_weight / total_duration)

    return DifficultySummary(
        easy=round(totals["easy"], 6),
        medium=round(totals["medium"], 6),
        hard=round(totals["hard"], 6),
        very_hard=round(totals["very_hard"], 6),
        tessitura_distance=round(tessitura_distance, 6),
        leap_exposure=round(leap_exposure, 6),
        fast_windway_switch_exposure=round(fast_switch_exposure, 6),
        total_duration=round(total_duration, 6),
        grace_duration=round(grace_duration, 6),
    )


def difficulty_score(
    summary: DifficultySummary,
    grace_settings: GraceSettings | None = None,
) -> float:
    active_settings = grace_settings or DEFAULT_GRACE_SETTINGS
    total = summary.easy + summary.medium + summary.hard + summary.very_hard
    if total <= 0:
        return 0.0
    base = (summary.hard + summary.very_hard) / total
    leap_penalty = min(1.0, summary.leap_exposure) * _LEAP_WEIGHT
    fast_switch_penalty = min(1.0, summary.fast_windway_switch_exposure) * _FAST_SWITCH_WEIGHT
    grace_bonus = 0.0
    if summary.total_duration > 0 and summary.grace_duration > 0:
        grace_ratio = min(1.0, summary.grace_duration / summary.total_duration)
        grace_bonus = grace_ratio * active_settings.grace_bonus
    return min(1.0, max(0.0, base + leap_penalty + fast_switch_penalty - grace_bonus))


__all__ = ["DifficultySummary", "difficulty_score", "summarize_difficulty"]
