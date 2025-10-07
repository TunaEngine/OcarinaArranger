"""Scaling helpers shared by fingering view components."""

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from .specs import InstrumentSpec


class FingeringScalingMixin:
    """Provides geometry scaling helpers for fingering canvases."""

    _scale: float

    def _scaled_canvas_size(self, instrument: "InstrumentSpec") -> tuple[int, int]:
        width, height = instrument.canvas_size
        scaled_width = max(1, int(round(float(width) * self._scale)))
        scaled_height = max(1, int(round(float(height) * self._scale)))
        return (scaled_width, scaled_height)

    def _scale_distance(self, value: float) -> float:
        return float(value) * self._scale

    def _scale_radius(self, radius: float) -> float:
        scaled = float(radius) * self._scale
        return max(1.0, scaled)

    def _scale_outline_width(self, width: float) -> float:
        scaled = float(width) * self._scale
        return max(0.5, scaled)


__all__ = ["FingeringScalingMixin"]
