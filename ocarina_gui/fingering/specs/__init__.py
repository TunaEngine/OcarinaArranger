"""Public exports for fingering specifications."""

from __future__ import annotations

from .instrument import InstrumentSpec
from .models import HoleSpec, InstrumentChoice, OutlineSpec, StyleSpec, WindwaySpec
from .pitch import parse_note_name_safe
from .ranges import collect_instrument_note_names, preferred_note_window

__all__ = [
    "HoleSpec",
    "WindwaySpec",
    "OutlineSpec",
    "StyleSpec",
    "InstrumentSpec",
    "InstrumentChoice",
    "collect_instrument_note_names",
    "preferred_note_window",
    "parse_note_name_safe",
]
