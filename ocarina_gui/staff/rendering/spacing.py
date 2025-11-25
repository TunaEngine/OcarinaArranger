"""Helpers for spacing staff events to avoid cramped note heads."""

from __future__ import annotations

from typing import Callable, Iterable, Sequence

from ocarina_tools import NoteEvent

from ...note_values import describe_note_glyph
from .note_painter import GRACE_NOTE_SCALE


def default_note_scale(event: NoteEvent) -> float:
    """Return the scale factor for an event's rendered size."""

    if getattr(event, "is_grace", False):
        return GRACE_NOTE_SCALE
    return 1.0


def minimum_px_per_tick(
    events: Sequence[NoteEvent],
    base_note_width: float,
    *,
    scale_for_event: Callable[[NoteEvent], float] = default_note_scale,
    grace_extra_gap_ratio: float = 0.0,
    safety_margin: float = 0.1,
) -> float:
    """Estimate the px-per-tick needed to keep adjacent noteheads separated."""

    if len(events) < 2:
        return 0.0

    starts: list[tuple[int, float, bool]] = []
    for event in events:
        scale = scale_for_event(event)
        width = base_note_width * scale
        is_grace = bool(getattr(event, "is_grace", False))
        starts.append((event.onset, width, is_grace))
        for offset in getattr(event, "tie_offsets", ()):  # type: ignore[attr-defined]
            starts.append((event.onset + offset, width, is_grace))

    starts.sort(key=lambda item: item[0])

    minimum_px_per_tick = 0.0
    for (tick, width, is_grace), (next_tick, next_width, next_is_grace) in zip(
        starts, starts[1:]
    ):
        delta = next_tick - tick
        if delta <= 0:
            continue
        gap = 0.0
        if grace_extra_gap_ratio > 0.0 and (is_grace or next_is_grace):
            gap += base_note_width * grace_extra_gap_ratio
        required = ((width + next_width) * 0.5 + gap) / delta
        minimum_px_per_tick = max(minimum_px_per_tick, required)

    return minimum_px_per_tick * (1.0 + max(0.0, safety_margin))


def _dot_spacing_requirements(
    note_width: float,
    available_space: float,
    *,
    dot_radius_ratio: float = 0.18,
    default_gap_ratio: float = 0.45,
    min_gap_ratio: float = 0.15,
    padding_ratio: float = 0.05,
    max_extra_ratio: float = 0.25,
) -> tuple[float, float]:
    """Return the dot gap to use and any extra spacing needed to avoid overlap."""

    dot_radius = note_width * dot_radius_ratio
    default_gap = note_width * default_gap_ratio
    min_gap = note_width * min_gap_ratio
    padding = note_width * padding_ratio

    max_gap_without_overlap = available_space - dot_radius - padding
    if max_gap_without_overlap >= default_gap:
        return default_gap, 0.0

    gap = max(min_gap, min(default_gap, max_gap_without_overlap))
    extra_spacing = max(0.0, min_gap - max_gap_without_overlap)
    if extra_spacing > 0.0:
        extra_spacing = min(extra_spacing, note_width * max_extra_ratio)

    return gap, extra_spacing


def dot_gap_for_available_space(note_width: float, available_space: float) -> float:
    """Return a gap width for dots that keeps them as close as safely possible."""

    gap, _ = _dot_spacing_requirements(note_width, available_space)
    return gap


def dotted_spacing_offsets(
    events: Sequence[NoteEvent],
    *,
    base_note_width: float,
    pulses_per_quarter: int,
    px_per_tick: float,
    base_offsets: Sequence[float] | None = None,
    scale_for_event: Callable[[NoteEvent], float] = default_note_scale,
) -> tuple[float, ...]:
    """Return cumulative offsets that keep dotted-note dots off neighboring heads."""

    if len(events) < 2:
        return tuple(0.0 for _ in events)

    normalized_offsets = tuple(base_offsets or (0.0 for _ in events))
    cumulative = 0.0
    offsets: list[float] = []

    for index, event in enumerate(events):
        offsets.append(cumulative)
        if index == len(events) - 1:
            continue

        glyph = describe_note_glyph(int(event.tied_durations[0]), pulses_per_quarter)
        if glyph is None or glyph.dots <= 0:
            continue

        next_event = events[index + 1]
        delta_ticks = next_event.onset - event.onset
        if delta_ticks <= 0:
            continue

        scale = scale_for_event(event)
        note_width = base_note_width * scale
        current_offset = normalized_offsets[index] + cumulative
        next_offset = normalized_offsets[index + 1] + cumulative
        available_space = (
            delta_ticks * px_per_tick + (next_offset - current_offset) - note_width
        )
        _, extra_spacing = _dot_spacing_requirements(note_width, available_space)
        cumulative += extra_spacing

    return tuple(offsets)


def ornament_spacing_offsets(
    events: Iterable[NoteEvent],
    *,
    base_note_width: float,
    grace_extra_gap_ratio: float = 0.0,
) -> tuple[float, ...]:
    """Return cumulative x-offsets to separate grace and normal notes.

    The returned offsets are ordered to match the provided sequence (which should
    already be sorted by onset). Each element is the cumulative pixel offset that
    should be added to the corresponding event to introduce a small gap whenever
    a grace note sits next to a non-grace (or another grace) note.
    """

    offsets: list[float] = []
    cumulative = 0.0
    gap_px = base_note_width * max(0.0, grace_extra_gap_ratio)
    previous: NoteEvent | None = None

    for event in events:
        if (
            previous is not None
            and gap_px > 0.0
            and event.onset > previous.onset
            and (
                getattr(event, "is_grace", False)
                or getattr(previous, "is_grace", False)
            )
        ):
            cumulative += gap_px
        offsets.append(cumulative)
        previous = event

    return tuple(offsets)

