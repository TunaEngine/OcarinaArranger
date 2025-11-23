"""Shared geometry helpers for treble staff rendering.

These functions intentionally mirror the calculations used by the on-screen
staff widgets so that other rendering targets (for example PDF export) can
reuse the same positioning logic without duplicating math.
"""

from __future__ import annotations


def staff_pos(midi: int) -> int:
    """Return the staff position index for a MIDI pitch value."""

    return int(round((midi - 64) * 7 / 12))


def staff_y(staff_top: float, pos: int, spacing: float) -> float:
    """Convert a staff position into a y-coordinate relative to ``staff_top``."""

    return float(staff_top + (8 - pos) * (spacing / 2.0))


def tie_control_offsets(spacing: float, pos: int) -> tuple[float, float]:
    """Return the base and curve offsets for tie rendering.

    The offsets match the values used by the interactive staff renderer so that
    ties curve in the same direction and with the same visual weight across UI
    and PDF outputs.
    """

    direction = 1 if pos < 6 else -1
    base_offset = spacing * 0.55
    curve_offset = spacing * 0.95
    return direction * base_offset, direction * curve_offset


__all__ = ["staff_pos", "staff_y", "tie_control_offsets"]
