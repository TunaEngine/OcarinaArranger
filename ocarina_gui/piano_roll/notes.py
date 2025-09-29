"""Pitch-related helpers for the piano roll."""

from __future__ import annotations

_ACCIDENTAL_STEPS = {1, 3, 6, 8, 10}
_NOTE_NAMES = ["C", "C", "D", "D", "E", "F", "F", "G", "G", "A", "A", "B"]


def is_accidental(midi: int) -> bool:
    """Return ``True`` if the given MIDI value represents a sharp/flat."""

    return midi % 12 in _ACCIDENTAL_STEPS


def label_for_midi(midi: int) -> str:
    """Return the human readable label for the MIDI pitch."""

    octave = midi // 12 - 1
    return f"{_NOTE_NAMES[midi % 12]}{octave}"
