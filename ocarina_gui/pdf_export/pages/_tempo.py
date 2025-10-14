"""Shared helpers for drawing tempo markers in PDF exports."""

from __future__ import annotations

from ..writer import PageBuilder

GLYPH_WIDTH_FACTOR = 0.6
TEMPO_MARKER_BARLINE_PADDING = 6.0


def _tempo_marker_text(label: str) -> str:
    if "=" in label:
        _, value = label.split("=", 1)
        return f"= {value.strip()}"
    return str(label).strip()


def tempo_marker_total_width(
    page: PageBuilder, label: str, font_size: float
) -> float:
    """Return the approximate width of the tempo marker at ``font_size``."""

    text = _tempo_marker_text(label)
    glyph_width = font_size * GLYPH_WIDTH_FACTOR
    return glyph_width + page.estimate_text_width(text, size=font_size)


def draw_tempo_marker(
    page: PageBuilder,
    left: float,
    top: float,
    label: str,
    *,
    font_size: float,
    fill_gray: float = 0.25,
) -> None:
    """Draw a quarter-note tempo marker followed by the numeric value."""

    text = _tempo_marker_text(label)
    radius = font_size * 0.25
    center_x = left + radius
    center_y = top + font_size * 0.4
    page.draw_circle(center_x, center_y, radius, fill_gray=0.0, stroke_gray=0.0, line_width=1.0)
    stem_x = center_x + radius * 0.7
    stem_bottom = center_y + font_size * 0.8
    page.draw_line(stem_x, center_y, stem_x, stem_bottom, gray=0.0, line_width=1.0)
    text_x = left + font_size * GLYPH_WIDTH_FACTOR
    page.draw_text(text_x, top, text, size=font_size, fill_gray=fill_gray)
