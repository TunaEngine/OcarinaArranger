"""Time signature utilities for PDF page layout."""

from __future__ import annotations


def ticks_per_measure(pulses_per_quarter: int, beats: int, beat_type: int) -> int:
    """Return the ticks per measure honoring the supplied time signature."""

    quarter_ticks = max(1, pulses_per_quarter or 1)
    beat_unit = max(1, beat_type)
    ticks_per_beat = max(1, int(quarter_ticks * (4 / beat_unit)))
    return max(1, beats * ticks_per_beat)


__all__ = ["ticks_per_measure"]
