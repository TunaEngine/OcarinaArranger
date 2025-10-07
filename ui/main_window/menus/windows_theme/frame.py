"""Window frame theming helpers for Windows hosts."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Any

import tkinter as tk

from .interop import (
    IS_WINDOWS,
    apply_windows_dark_mode_for_window,
    colorref_from_hex,
    ensure_windows_dark_mode_allowed,
    is_dark_color,
    load_dwmapi,
    load_user32,
)


__all__ = [
    "apply_window_frame_colors",
    "perform_window_frame_refresh_nudge",
    "schedule_window_frame_refresh",
]


def apply_window_frame_colors(host: Any, palette: Any) -> None:
    """Apply Windows frame colours for the given host widget."""

    if not IS_WINDOWS:
        return

    hwnd_getter = getattr(host, "winfo_id", None)
    if not callable(hwnd_getter):
        return
    try:
        raw_handle = hwnd_getter()
    except tk.TclError:
        return
    if not raw_handle:
        return

    handle = int(raw_handle)

    user32 = load_user32()
    if user32 is not None:
        get_parent = getattr(user32, "GetParent", None)
        if callable(get_parent):
            try:
                parent_handle = get_parent(handle)
            except OSError:
                parent_handle = 0
            if parent_handle:
                handle = int(parent_handle)

    dwmapi = load_dwmapi()
    if dwmapi is None:
        return

    dark_mode_enabled = is_dark_color(palette.window_background)

    host._last_title_hwnd_attempt = handle
    host._windows_dark_mode_app_allowed = ensure_windows_dark_mode_allowed()
    host._last_dark_mode_window_attempt = dark_mode_enabled
    host._last_dark_mode_window_result = apply_windows_dark_mode_for_window(
        handle, dark_mode_enabled
    )

    dark_mode_values = (
        (20, ctypes.c_int(2 if dark_mode_enabled else 0)),  # DWMWA_USE_IMMERSIVE_DARK_MODE
        (19, ctypes.c_int(1 if dark_mode_enabled else 0)),
    )

    for attribute, value in dark_mode_values:
        try:
            dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(handle),
                ctypes.c_uint(attribute),
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
        except OSError:
            continue
        else:
            if attribute == 20:
                break

    caption_color = ctypes.c_int(colorref_from_hex(palette.window_background))
    text_color = ctypes.c_int(colorref_from_hex(palette.text_primary))
    border_color = ctypes.c_int(colorref_from_hex(palette.window_background))

    for attribute, value in (
        (35, caption_color),
        (36, text_color),
        (34, border_color),
    ):
        try:
            dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(handle),
                ctypes.c_uint(attribute),
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
        except OSError:
            continue


def schedule_window_frame_refresh(host: Any) -> None:
    """Schedule a geometry nudge so Windows applies updated colours."""

    if getattr(host, "_pending_title_geometry_nudge", False):
        return

    after_idle = getattr(host, "after_idle", None)
    if not callable(after_idle):
        return

    host._pending_title_geometry_nudge = True

    def _nudge() -> None:
        perform_window_frame_refresh_nudge(host)

    try:
        after_idle(_nudge)
    except tk.TclError:
        host._pending_title_geometry_nudge = False


def perform_window_frame_refresh_nudge(host: Any) -> None:
    """Temporarily resize the window to force a redraw.
    
    For maximized windows, we need a different approach since geometry changes
    don't work the same way when the window is in zoomed state.
    """

    host._pending_title_geometry_nudge = False
    host._last_title_geometry_nudge = None

    try:
        width = host.winfo_width()
        height = host.winfo_height()
        window_state = host.state()
    except tk.TclError:
        return

    if width <= 1 or height <= 1:
        after = getattr(host, "after", None)
        if callable(after):
            host._pending_title_geometry_nudge = True
            try:
                after(16, lambda: perform_window_frame_refresh_nudge(host))
            except tk.TclError:
                host._pending_title_geometry_nudge = False
        return

    # Handle maximized windows specially
    if window_state == 'zoomed':
        try:
            # For maximized windows: temporarily restore, nudge, then re-maximize
            # This forces a complete redraw including the title bar
            host.state('normal')
            host.update_idletasks()
            
            # Give the system a moment to process the state change
            after = getattr(host, "after", None)
            if callable(after):
                def _complete_maximized_nudge():
                    try:
                        # Small geometry nudge while in normal state
                        current_width = host.winfo_width()
                        current_height = host.winfo_height()
                        host.geometry(f"{current_width + 1}x{current_height + 1}")
                        host.update_idletasks()
                        host.geometry(f"{current_width}x{current_height}")
                        host.update_idletasks()
                        
                        # Restore maximized state
                        host.state('zoomed')
                        host.update_idletasks()
                        
                        host._last_title_geometry_nudge = (width, height)
                    except tk.TclError:
                        pass
                
                after(50, _complete_maximized_nudge)  # Slightly longer delay for maximized windows
            else:
                # Fallback if after is not available
                host.state('zoomed')
                host._last_title_geometry_nudge = (width, height)
        except tk.TclError:
            return
    else:
        # Normal window handling - original geometry nudge approach
        try:
            x = host.winfo_x()
            y = host.winfo_y()
        except tk.TclError:
            x = None
            y = None

        def _geometry_string(width_value: int, height_value: int) -> str:
            if x is None or y is None:
                return f"{width_value}x{height_value}"
            return f"{width_value}x{height_value}+{x}+{y}"

        try:
            host.geometry(_geometry_string(width + 1, height + 1))
            host.update_idletasks()
            host.geometry(_geometry_string(width, height))
            host._last_title_geometry_nudge = (width, height)
        except tk.TclError:
            return
