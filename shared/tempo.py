"""Shared data structures and helpers for representing tempo information."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class TempoChange:
    """Describe a tempo change occurring at a specific tick position."""

    tick: int
    tempo_bpm: float


def slowest_tempo(
    tempo_changes: Sequence[TempoChange] | Iterable[TempoChange],
    *,
    default: float = 120.0,
) -> float:
    """Return the slowest tempo from ``tempo_changes`` or ``default`` when empty."""

    minimum = None
    for change in tempo_changes:
        tempo = max(1e-6, float(change.tempo_bpm))
        if minimum is None or tempo < minimum:
            minimum = tempo
    if minimum is None:
        return max(1e-6, float(default))
    return minimum


def scaled_tempo_values(
    tempo_changes: Sequence[TempoChange] | Iterable[TempoChange],
    target_slowest: float,
) -> tuple[float, ...]:
    """Scale tempos so the slowest equals ``target_slowest`` while preserving ratios."""

    sorted_changes = _sorted_unique_tempo_changes(tempo_changes)
    if not sorted_changes:
        return ()

    base_first = _first_tempo(sorted_changes, default=target_slowest)
    if base_first <= 1e-6:
        base_first = 1e-6
    scale = max(1e-6, float(target_slowest)) / base_first

    scaled: list[float] = []
    last_value: float | None = None
    for change in sorted_changes:
        value = max(1e-6, float(change.tempo_bpm) * scale)
        if last_value is not None and abs(value - last_value) <= 1e-6:
            continue
        scaled.append(value)
        last_value = value
    return tuple(scaled)


def scaled_tempo_markings(
    tempo_changes: Sequence[TempoChange] | Iterable[TempoChange],
    target_slowest: float,
) -> tuple[str, ...]:
    """Return formatted tempo markings for the scaled tempo values."""

    values = scaled_tempo_values(tempo_changes, target_slowest)
    return tuple(_format_tempo_marking(value) for value in values)


def scaled_tempo_changes(
    tempo_changes: Sequence[TempoChange] | Iterable[TempoChange],
    target_slowest: float,
) -> tuple[TempoChange, ...]:
    """Return scaled tempo changes paired with their original tick positions."""

    sorted_changes = _sorted_unique_tempo_changes(tempo_changes)
    if not sorted_changes:
        return ()

    base_first = _first_tempo(sorted_changes, default=target_slowest)
    if base_first <= 1e-6:
        base_first = 1e-6
    scale = max(1e-6, float(target_slowest)) / base_first

    scaled: list[TempoChange] = []
    last_value: float | None = None
    for change in sorted_changes:
        tick = max(0, int(change.tick))
        value = max(1e-6, float(change.tempo_bpm) * scale)
        if last_value is not None and abs(value - last_value) <= 1e-6:
            continue
        scaled.append(TempoChange(tick=tick, tempo_bpm=value))
        last_value = value
    return tuple(scaled)


def scaled_tempo_marker_pairs(
    tempo_changes: Sequence[TempoChange] | Iterable[TempoChange],
    target_slowest: float,
) -> tuple[tuple[int, str], ...]:
    """Return tick/label pairs for scaled tempo markings."""

    markings = scaled_tempo_markings(tempo_changes, target_slowest)
    if len(markings) <= 1:
        return ()
    scaled_changes = scaled_tempo_changes(tempo_changes, target_slowest)
    return tuple(
        (change.tick, label)
        for change, label in zip(scaled_changes, markings)
    )


def _sorted_unique_tempo_changes(
    tempo_changes: Sequence[TempoChange] | Iterable[TempoChange],
) -> list[TempoChange]:
    dedup: dict[int, TempoChange] = {}
    for change in tempo_changes:
        tick = max(0, int(change.tick))
        tempo = max(1e-6, float(change.tempo_bpm))
        dedup[tick] = TempoChange(tick=tick, tempo_bpm=tempo)
    return sorted(dedup.values(), key=lambda entry: entry.tick)


def _format_tempo_marking(value: float) -> str:
    display = f"{int(round(value))}"
    return f"♩ = {display}"


def _first_tempo(
    tempo_changes: Sequence[TempoChange] | Iterable[TempoChange],
    *,
    default: float = 120.0,
) -> float:
    """Return the tempo of the first change in chronological order."""

    sorted_changes = _sorted_unique_tempo_changes(tempo_changes)
    if not sorted_changes:
        return max(1e-6, float(default))
    return max(1e-6, float(sorted_changes[0].tempo_bpm))


def first_tempo(
    tempo_changes: Sequence[TempoChange] | Iterable[TempoChange],
    *,
    default: float = 120.0,
) -> float:
    """Public wrapper returning the first tempo value or ``default`` when empty."""

    return _first_tempo(tempo_changes, default=default)


def normalized_tempo_changes(
    target_first: float,
    tempo_changes: Sequence[TempoChange] | Iterable[TempoChange],
) -> list[TempoChange]:
    """Scale tempo changes so the first tempo equals ``target_first``."""

    base_first = _first_tempo(tempo_changes, default=target_first)
    desired_first = max(1e-6, float(target_first))
    sorted_changes = _sorted_unique_tempo_changes(tempo_changes)

    if not sorted_changes:
        return [TempoChange(tick=0, tempo_bpm=desired_first)]

    scale = 1.0
    if base_first > 1e-6:
        scale = desired_first / base_first

    normalized: list[TempoChange] = []
    seen_tick: int | None = None
    for change in sorted_changes:
        tick = max(0, int(change.tick))
        scaled = max(1e-6, float(change.tempo_bpm) * scale)
        entry = TempoChange(tick=tick, tempo_bpm=scaled)
        if seen_tick == tick:
            normalized[-1] = entry
        else:
            normalized.append(entry)
            seen_tick = tick

    if normalized[0].tick > 0:
        normalized.insert(0, TempoChange(tick=0, tempo_bpm=desired_first))

    deduped: list[TempoChange] = []
    for change in normalized:
        if deduped and abs(deduped[-1].tempo_bpm - change.tempo_bpm) <= 1e-6:
            continue
        deduped.append(change)

    return deduped


@dataclass(frozen=True)
class _TempoSegment:
    tick: int
    tempo_bpm: float
    ticks_per_second: float
    seconds_at_start: float


class TempoMap:
    """Convert between tick positions and elapsed seconds for variable tempo."""

    def __init__(
        self, pulses_per_quarter: int, tempo_changes: Sequence[TempoChange]
    ) -> None:
        self._segments: list[_TempoSegment] = []
        self._ticks: list[int] = []
        self.sample_rate: int = 0

        ppq = max(1, int(pulses_per_quarter))
        sorted_changes = _sorted_unique_tempo_changes(tempo_changes)
        if not sorted_changes:
            raise ValueError("TempoMap requires at least one tempo change entry")

        first_tick = max(0, int(sorted_changes[0].tick))
        first_tempo = max(1e-3, float(sorted_changes[0].tempo_bpm))
        first_ticks_per_second = max((first_tempo / 60.0) * ppq, 1e-6)
        self._segments.append(
            _TempoSegment(first_tick, first_tempo, first_ticks_per_second, 0.0)
        )
        self._ticks.append(first_tick)
        elapsed_seconds = 0.0

        last_tick = first_tick
        last_ticks_per_second = first_ticks_per_second

        for change in sorted_changes[1:]:
            tick = max(0, int(change.tick))
            tempo_bpm = max(1e-3, float(change.tempo_bpm))
            if tick < last_tick:
                continue
            if tick == last_tick:
                last_ticks_per_second = max((tempo_bpm / 60.0) * ppq, 1e-6)
                self._segments[-1] = _TempoSegment(
                    tick, tempo_bpm, last_ticks_per_second, elapsed_seconds
                )
                continue
            elapsed_seconds += (tick - last_tick) / last_ticks_per_second
            last_tick = tick
            last_ticks_per_second = max((tempo_bpm / 60.0) * ppq, 1e-6)
            self._segments.append(
                _TempoSegment(tick, tempo_bpm, last_ticks_per_second, elapsed_seconds)
            )
            self._ticks.append(tick)

    def tempo_at(self, tick: int) -> float:
        segment = self._segment_for_tick(tick)
        return segment.tempo_bpm

    def ticks_per_second_at(self, tick: int) -> float:
        segment = self._segment_for_tick(tick)
        return segment.ticks_per_second

    def seconds_at(self, tick: int) -> float:
        segment = self._segment_for_tick(tick)
        offset = max(0, tick - segment.tick)
        return segment.seconds_at_start + offset / segment.ticks_per_second

    def duration_between(self, start_tick: int, end_tick: int) -> float:
        if end_tick <= start_tick:
            return 0.0
        return self.seconds_at(end_tick) - self.seconds_at(start_tick)

    def seconds_to_tick(self, seconds: float) -> int:
        target = max(0.0, float(seconds))
        segments = self._segments
        if not segments:
            return 0
        # Handle times before the first segment explicitly.
        if target <= segments[0].seconds_at_start:
            return segments[0].tick
        for index, segment in enumerate(segments):
            next_start = (
                segments[index + 1].seconds_at_start
                if index + 1 < len(segments)
                else None
            )
            if next_start is not None and target >= next_start:
                continue
            offset_seconds = target - segment.seconds_at_start
            if offset_seconds <= 0.0:
                return segment.tick
            tick_offset = int(round(offset_seconds * segment.ticks_per_second))
            return segment.tick + max(0, tick_offset)
        # Past the last segment; extrapolate using the final tempo.
        last = segments[-1]
        offset_seconds = target - last.seconds_at_start
        tick_offset = int(round(offset_seconds * last.ticks_per_second))
        return last.tick + max(0, tick_offset)

    def tick_to_sample(self, tick: int, sample_rate: int) -> int:
        rate = max(sample_rate or self.sample_rate, 1)
        seconds = self.seconds_at(tick)
        return int(round(seconds * rate))

    def _segment_for_tick(self, tick: int) -> _TempoSegment:
        if not self._segments:
            raise RuntimeError("TempoMap has no segments configured")
        index = bisect_right(self._ticks, max(0, tick)) - 1
        if index < 0:
            index = 0
        return self._segments[index]


__all__ = [
    "TempoChange",
    "TempoMap",
    "first_tempo",
    "normalized_tempo_changes",
    "scaled_tempo_changes",
    "scaled_tempo_markings",
    "scaled_tempo_marker_pairs",
    "scaled_tempo_values",
    "slowest_tempo",
]

