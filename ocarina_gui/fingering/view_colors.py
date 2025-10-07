"""Color resolution helpers for fingering canvases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ocarina_gui.color_utils import hex_to_rgb

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
        style = spec.style
        background = style.background_color or "#ffffff"
        outline = style.outline_color or "#000000"
        hole_outline = style.hole_outline_color or outline
        covered_fill = style.covered_fill_color or hole_outline

        if self._is_dark_theme():
            swap_background = hole_outline or background
            swap_foreground = background or outline
            background = swap_background
            outline = swap_foreground
            hole_outline = swap_foreground
            covered_fill = swap_foreground

        return FingeringCanvasColors(
            background=background,
            outline=outline,
            hole_outline=hole_outline,
            covered_fill=covered_fill,
        )

    def _is_dark_theme(self) -> bool:
        theme = self._theme
        if theme is None:
            return False

        background = theme.palette.window_background
        try:
            red, green, blue = hex_to_rgb(background)
        except ValueError:
            return "dark" in theme.theme_id.lower()

        # Rec. 601 luma approximation to determine perceived brightness.
        luminance = (0.299 * red + 0.587 * green + 0.114 * blue) / 255.0
        return luminance < 0.5


__all__ = ["FingeringCanvasColors", "FingeringColorMixin"]
