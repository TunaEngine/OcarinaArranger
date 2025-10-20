"""Utilities for collapsing arranger note events into a monophonic line."""

from __future__ import annotations

from typing import Sequence

from ocarina_tools.events import NoteEvent


def ensure_monophonic(events: Sequence[NoteEvent]) -> tuple[NoteEvent, ...]:
    """Return ``events`` collapsed so only one note sounds at a time."""

    if not events:
        return tuple(events)

    ordered = sorted(events, key=lambda event: (event.onset, event.midi, event.duration))
    collapsed: list[NoteEvent] = []

    for event in ordered:
        if not collapsed:
            collapsed.append(event)
            continue

        previous = collapsed[-1]

        # Handle simultaneous onsets first – keep the highest-priority note.
        if event.onset <= previous.onset:
            if _event_priority(event) > _event_priority(previous):
                collapsed[-1] = event
            continue

        previous_end = previous.onset + previous.duration
        if event.onset < previous_end:
            if _event_priority(event) > _event_priority(previous):
                trimmed = _trim_event(previous, max(0, event.onset - previous.onset))
                if trimmed is None:
                    collapsed.pop()
                else:
                    collapsed[-1] = trimmed
                collapsed.append(event)
            continue

        collapsed.append(event)

    return tuple(collapsed)


def _event_priority(event: NoteEvent) -> tuple[int, int]:
    base_priority = 0 if event.is_grace else 1
    return base_priority, int(event.midi), int(event.duration)


def _trim_event(event: NoteEvent, duration: int) -> NoteEvent | None:
    if duration <= 0:
        return None

    return NoteEvent(
        onset=event.onset,
        duration=duration,
        midi=event.midi,
        program=event.program,
        tied_durations=(duration,),
        ottava_shifts=event.ottava_shifts,
        is_grace=event.is_grace,
        grace_type=event.grace_type,
    )


__all__ = ["ensure_monophonic"]
