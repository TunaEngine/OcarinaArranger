"""Windows-specific helpers for menu and title styling."""

from __future__ import annotations

from .frame import apply_window_frame_colors, schedule_window_frame_refresh
from .menu import apply_menu_bar_colors
from .interop import is_dark_color

__all__ = [
    "apply_menu_bar_colors",
    "apply_window_frame_colors",
    "is_dark_color",
    "schedule_window_frame_refresh",
]
