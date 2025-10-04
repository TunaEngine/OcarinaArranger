"""Windows menu bar theming helpers."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Any

import tkinter as tk

from .interop import (
    IS_WINDOWS,
    MENUINFO,
    MIM_APPLYTOSUBMENUS,
    MIM_BACKGROUND,
    colorref_from_hex,
    load_gdi32,
    load_user32,
)

__all__ = ["apply_menu_bar_colors", "schedule_menu_bar_retry"]


def apply_menu_bar_colors(host: Any, palette: Any) -> None:
    """Apply the palette to the native Windows menu bar."""

    if not IS_WINDOWS or MENUINFO is None:
        return

    menubar = getattr(host, "_menubar", None)
    if menubar is None:
        return

    host._last_menubar_brush_color_attempt = palette.window_background

    user32 = load_user32()
    gdi32 = load_gdi32()
    if user32 is None or gdi32 is None:
        return

    hwnd_getter = getattr(host, "winfo_id", None)
    if not callable(hwnd_getter):
        return

    try:
        hwnd = hwnd_getter()
    except tk.TclError:
        schedule_menu_bar_retry(host)
        return

    if not hwnd:
        schedule_menu_bar_retry(host)
        return

    window_handle = wintypes.HWND(int(hwnd))
    try:
        menu_handle = user32.GetMenu(window_handle)
    except AttributeError:
        menu_handle = 0
    if not menu_handle:
        schedule_menu_bar_retry(host)
        return

    colorref = colorref_from_hex(palette.window_background)
    brush = gdi32.CreateSolidBrush(ctypes.c_uint(colorref))
    if not brush:
        return

    brush_handle = int(brush)
    previous_brush = getattr(host, "_menubar_brush_handle", None)

    menu_info = MENUINFO()
    menu_info.cbSize = ctypes.sizeof(MENUINFO)
    menu_info.fMask = MIM_BACKGROUND | MIM_APPLYTOSUBMENUS
    menu_info.dwStyle = 0
    menu_info.cyMax = 0
    menu_info.hbrBack = wintypes.HBRUSH(brush_handle)
    menu_info.dwContextHelpID = 0
    menu_info.dwMenuData = 0

    try:
        result = user32.SetMenuInfo(wintypes.HMENU(menu_handle), ctypes.byref(menu_info))
    except OSError:
        gdi32.DeleteObject(ctypes.c_void_p(brush_handle))
        return

    if not result:
        gdi32.DeleteObject(ctypes.c_void_p(brush_handle))
        return

    if previous_brush and previous_brush != brush_handle:
        try:
            gdi32.DeleteObject(ctypes.c_void_p(previous_brush))
        except AttributeError:
            pass

    host._menubar_brush_handle = brush_handle

    try:
        item_count = user32.GetMenuItemCount(menu_handle)
    except AttributeError:
        item_count = 0

    if item_count > 0:
        for index in range(item_count):
            try:
                submenu_handle = user32.GetSubMenu(menu_handle, index)
            except AttributeError:
                submenu_handle = 0
            if not submenu_handle:
                continue
            submenu_info = MENUINFO()
            submenu_info.cbSize = ctypes.sizeof(MENUINFO)
            submenu_info.fMask = MIM_BACKGROUND
            submenu_info.dwStyle = 0
            submenu_info.cyMax = 0
            submenu_info.hbrBack = wintypes.HBRUSH(brush_handle)
            submenu_info.dwContextHelpID = 0
            submenu_info.dwMenuData = 0
            try:
                user32.SetMenuInfo(wintypes.HMENU(submenu_handle), ctypes.byref(submenu_info))
            except OSError:
                continue

    try:
        user32.DrawMenuBar(window_handle)
    except OSError:
        pass


def schedule_menu_bar_retry(host: Any) -> None:
    """Retry menu bar colour application when handles become available."""

    if getattr(host, "_pending_menubar_refresh", False):
        return

    after = getattr(host, "after", None)
    if not callable(after):
        return

    host._pending_menubar_refresh = True

    def _retry() -> None:
        host._pending_menubar_refresh = False
        theme = getattr(host, "_theme", None)
        palette = getattr(theme, "palette", None)
        if palette is None:
            return
        try:
            apply_menu_bar_colors(host, palette)
        except Exception:
            pass

    try:
        after(32, _retry)
    except tk.TclError:
        host._pending_menubar_refresh = False
