"""Shared constants and note helpers for the Ocarina arranger GUI."""

from __future__ import annotations

from app.version import get_app_version

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_name(midi: int) -> str:
    """Return scientific pitch name for a MIDI note number."""
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def natural_of(midi: int) -> str:
    """Return the natural-name version of a MIDI pitch (drops sharps)."""
    name = midi_to_name(midi)
    return name.replace("#", "") if "#" in name else name


APP_TITLE = f"Ocarina Arranger v{get_app_version()}"
DEFAULT_MIN = "A4"
DEFAULT_MAX = "F6"
