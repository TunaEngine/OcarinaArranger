"""Common helpers for note event operations."""

from __future__ import annotations

from typing import Sequence

from .pdf_export.types import NoteEvent

__all__ = ["trim_leading_silence"]


def trim_leading_silence(events: Sequence[NoteEvent]) -> list[NoteEvent]:
    """Shift note events so the earliest onset starts at time zero."""

    if not events:
        return list(events)

    earliest_onset = min(event.onset for event in events)
    if earliest_onset <= 0:
        return list(events)

    return [event.shift(-earliest_onset) for event in events]
