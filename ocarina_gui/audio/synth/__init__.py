"""Preview synthesiser package."""

from .patches import _SynthPatch, _patch_for_program
from .renderer import _SynthRenderer, Event
from .tone import _midi_to_frequency

__all__ = [
    "Event",
    "_SynthPatch",
    "_SynthRenderer",
    "_patch_for_program",
    "_midi_to_frequency",
]
