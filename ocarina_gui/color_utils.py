"""Shared color utility helpers for GUI rendering."""

from __future__ import annotations

from typing import Tuple


def hex_to_rgb(value: str) -> Tuple[int, int, int]:
    """Convert a ``#rrggbb`` or ``#rgb`` hex color to an RGB tuple."""
    text = value.lstrip("#")
    if len(text) == 3:
        text = "".join(component * 2 for component in text)
    if len(text) != 6:
        raise ValueError(f"Invalid hex color: {value}")
    return tuple(int(text[i : i + 2], 16) for i in range(0, 6, 2))


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert an RGB tuple into a ``#rrggbb`` string."""
    return "#" + "".join(f"{max(0, min(255, component)):02x}" for component in rgb)


def mix_colors(base: Tuple[int, int, int], other: Tuple[int, int, int], ratio: float) -> Tuple[int, int, int]:
    """Linearly interpolate between ``base`` and ``other`` with ``ratio``."""
    clamped = max(0.0, min(1.0, ratio))
    return tuple(int(round(base[index] * (1.0 - clamped) + other[index] * clamped)) for index in range(3))
