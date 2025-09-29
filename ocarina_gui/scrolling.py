"""Utilities for pixel-aligned canvas scrolling and auto-scroll settings."""

from __future__ import annotations

from typing import Optional

import tkinter as tk

from enum import Enum


class AutoScrollMode(str, Enum):
    """Enumerate supported preview auto-scroll strategies."""

    CONTINUOUS = "continuous"
    FLIP = "flip"

    @property
    def label(self) -> str:
        if self is AutoScrollMode.CONTINUOUS:
            return "Continuous"
        return "Flip through"


DEFAULT_AUTO_SCROLL_MODE = AutoScrollMode.FLIP


def move_canvas_to_pixel_fraction(canvas: tk.Canvas, fraction: float) -> float:
    """Move ``canvas`` horizontally ensuring it lands on a whole pixel.

    Tk's ``Canvas.xview_moveto`` accepts a fraction of the scrollregion width.
    When that fraction does not line up with a whole pixel the canvas renders
    slightly blurred while scrolling.  This helper snaps the movement to the
    nearest pixel before applying it.

    Args:
        canvas: The canvas to move.
        fraction: Desired horizontal scroll position expressed as a fraction
            in the inclusive range ``[0.0, 1.0]``.

    Returns:
        The actual fraction applied to the canvas after snapping.
    """

    width = _scrollregion_width(canvas)
    clamped_fraction = max(0.0, min(1.0, fraction))
    snapped_fraction = clamped_fraction
    if width is not None and width > 0:
        pixel = int(round(clamped_fraction * width))
        snapped_fraction = pixel / width

    try:
        current_fraction = canvas.xview()[0]
        if abs(current_fraction - snapped_fraction) < 1e-9:
            return current_fraction
    except Exception:
        pass

    canvas.xview_moveto(snapped_fraction)
    return canvas.xview()[0]


def _scrollregion_width(canvas: tk.Canvas) -> Optional[float]:
    try:
        region = canvas.cget("scrollregion")
    except Exception:
        return None
    if not region:
        return None
    parts = region.split()
    if len(parts) != 4:
        return None
    try:
        left, _top, right, _bottom = (float(value) for value in parts)
    except (TypeError, ValueError):
        return None
    width = right - left
    if width <= 0:
        return None
    return width


def normalize_auto_scroll_mode(value: object) -> AutoScrollMode:
    """Coerce ``value`` into a supported :class:`AutoScrollMode`."""

    if isinstance(value, AutoScrollMode):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        for mode in AutoScrollMode:
            if normalized in {mode.value, mode.name.lower()}:
                return mode
        if normalized in {"page", "paging"}:
            return AutoScrollMode.FLIP
    return DEFAULT_AUTO_SCROLL_MODE


__all__ = [
    "AutoScrollMode",
    "DEFAULT_AUTO_SCROLL_MODE",
    "move_canvas_to_pixel_fraction",
    "normalize_auto_scroll_mode",
]

