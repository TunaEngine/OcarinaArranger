"""Utility helpers for basic musical calculations."""

from __future__ import annotations


def _midi_to_frequency(midi: int) -> float:
    if midi <= 0:
        return 0.0
    return 440.0 * (2 ** ((midi - 69) / 12.0))


__all__ = ["_midi_to_frequency"]
