"""Shared geometry helpers for treble staff rendering.

These functions intentionally mirror the calculations used by the on-screen
staff widgets so that other rendering targets (for example PDF export) can
reuse the same positioning logic without duplicating math.
"""

from __future__ import annotations

_PITCH_CLASS_TO_STEPS = {
    0: 0,  # C / C♯
    1: 0,
    2: 1,  # D / D♯
    3: 1,
    4: 2,  # E
    5: 3,  # F / F♯
    6: 3,
    7: 4,  # G / G♯
    8: 4,
    9: 5,  # A / A♯
    10: 5,
    11: 6,  # B
}


_REFERENCE_STEPS = (64 // 12) * 7 + _PITCH_CLASS_TO_STEPS[64 % 12]


def staff_pos(midi: int) -> int:
    """Return the staff position index for a MIDI pitch value."""

    octave_steps = (int(midi) // 12) * 7
    pitch_class_steps = _PITCH_CLASS_TO_STEPS[int(midi) % 12]
    return octave_steps + pitch_class_steps - _REFERENCE_STEPS


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
