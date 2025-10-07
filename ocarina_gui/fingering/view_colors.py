"""Color resolution helpers for fingering canvases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ocarina_gui.themes import ThemeSpec
    from .specs import InstrumentSpec


@dataclass(frozen=True)
class FingeringCanvasColors:
    """Resolved palette for a fingering canvas."""

    background: str
    outline: str
    hole_outline: str
    covered_fill: str


class FingeringColorMixin:
    """Provides color helpers shared by fingering canvases."""

    _instrument: "InstrumentSpec"
    _theme: "ThemeSpec | None"

    def _resolve_canvas_colors(
        self, instrument: "InstrumentSpec | None" = None
    ) -> FingeringCanvasColors:
        spec = instrument or self._instrument
        theme = self._theme
        if theme is not None:
            palette = theme.palette.layout_editor
            background = palette.instrument_surface
            outline = palette.instrument_outline
            hole_outline = palette.hole_outline
            covered_fill = palette.covered_fill
        else:
            style = spec.style
            background = style.background_color or "#ffffff"
            outline = style.outline_color or "#000000"
            hole_outline = style.hole_outline_color or outline
            covered_fill = style.covered_fill_color or hole_outline

        return FingeringCanvasColors(
            background=background,
            outline=outline,
            hole_outline=hole_outline,
            covered_fill=covered_fill,
        )


__all__ = ["FingeringCanvasColors", "FingeringColorMixin"]
