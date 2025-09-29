"""Layout helpers for arranging PDF content."""

from __future__ import annotations

from dataclasses import dataclass

PAGE_SIZES = {
    "A4": (595.28, 841.89),  # 210mm x 297mm at 72dpi
    "A6": (298.0, 420.0),    # 105mm x 148mm at 72dpi
}


@dataclass(frozen=True)
class PdfLayout:
    page_size: str
    orientation: str
    width: float
    height: float
    margin_left: float = 48.0
    margin_top: float = 54.0
    margin_bottom: float = 54.0
    font_size: float = 12.0
    line_height: float = 16.0


def resolve_layout(page_size: str, orientation: str) -> PdfLayout:
    """Translate a page size string into a layout configuration."""

    key = page_size.strip().upper()
    if key not in PAGE_SIZES:
        raise ValueError(f"Unsupported page size: {page_size}")
    orient = orientation.strip().lower()
    if orient not in {"portrait", "landscape"}:
        raise ValueError(f"Unsupported orientation: {orientation}")
    width, height = PAGE_SIZES[key]
    if orient == "landscape":
        width, height = height, width
    return PdfLayout(page_size=key, orientation=orient, width=width, height=height)


__all__ = ["PdfLayout", "resolve_layout", "PAGE_SIZES"]
