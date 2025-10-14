"""Backward compatible entry-point for the piano roll widget."""

from __future__ import annotations

from .piano_roll import PianoRoll
from .tempo_markers import (
    _TEMPO_MARKER_BARLINE_PADDING,
    _TEMPO_MARKER_LEFT_PADDING,
    _TEMPO_MARKER_MIN_BOTTOM,
    _TEMPO_MARKER_VERTICAL_OFFSET,
)

__all__ = [
    "PianoRoll",
    "_TEMPO_MARKER_BARLINE_PADDING",
    "_TEMPO_MARKER_LEFT_PADDING",
    "_TEMPO_MARKER_MIN_BOTTOM",
    "_TEMPO_MARKER_VERTICAL_OFFSET",
]

