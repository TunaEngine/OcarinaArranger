"""Shared Windows interop helpers for menu and title theming."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys
from typing import Any

from ocarina_gui.color_utils import hex_to_rgb

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    try:
        ULONG_PTR = wintypes.ULONG_PTR  # type: ignore[attr-defined]
    except AttributeError:  # pragma: no cover - depends on Python build
        if ctypes.sizeof(ctypes.c_void_p) == ctypes.sizeof(ctypes.c_ulonglong):
            ULONG_PTR = ctypes.c_ulonglong
        else:
            ULONG_PTR = ctypes.c_ulong

    class MENUINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", wintypes.DWORD),
            ("dwStyle", wintypes.DWORD),
            ("cyMax", wintypes.UINT),
            ("hbrBack", wintypes.HBRUSH),
            ("dwContextHelpID", wintypes.DWORD),
            ("dwMenuData", ULONG_PTR),
        ]

    MIM_BACKGROUND = 0x00000002
    MIM_APPLYTOSUBMENUS = 0x80000000

    try:
        _UXTHEME = ctypes.windll.uxtheme
    except AttributeError:  # pragma: no cover - Windows API availability
        _UXTHEME = None

    _WINDOWS_SET_PREFERRED_APP_MODE = None
    _WINDOWS_ALLOW_DARK_MODE_FOR_APP = None
    _WINDOWS_ALLOW_DARK_MODE_FOR_WINDOW = None
    _WINDOWS_SET_WINDOW_THEME = None

    if _UXTHEME is not None:
        try:
            _WINDOWS_SET_PREFERRED_APP_MODE = _UXTHEME.SetPreferredAppMode
            _WINDOWS_SET_PREFERRED_APP_MODE.restype = ctypes.c_int
            _WINDOWS_SET_PREFERRED_APP_MODE.argtypes = [ctypes.c_int]
        except AttributeError:  # pragma: no cover - depends on Windows build
            _WINDOWS_SET_PREFERRED_APP_MODE = None

        try:
            _WINDOWS_ALLOW_DARK_MODE_FOR_APP = _UXTHEME.AllowDarkModeForApp
            _WINDOWS_ALLOW_DARK_MODE_FOR_APP.restype = ctypes.c_bool
            _WINDOWS_ALLOW_DARK_MODE_FOR_APP.argtypes = [ctypes.c_bool]
        except AttributeError:  # pragma: no cover - depends on Windows build
            _WINDOWS_ALLOW_DARK_MODE_FOR_APP = None

        try:
            _WINDOWS_ALLOW_DARK_MODE_FOR_WINDOW = _UXTHEME.AllowDarkModeForWindow
            _WINDOWS_ALLOW_DARK_MODE_FOR_WINDOW.restype = ctypes.c_bool
            _WINDOWS_ALLOW_DARK_MODE_FOR_WINDOW.argtypes = [wintypes.HWND, ctypes.c_bool]
        except AttributeError:  # pragma: no cover - depends on Windows build
            _WINDOWS_ALLOW_DARK_MODE_FOR_WINDOW = None

        try:
            _WINDOWS_SET_WINDOW_THEME = _UXTHEME.SetWindowTheme
            _WINDOWS_SET_WINDOW_THEME.restype = ctypes.c_int
            _WINDOWS_SET_WINDOW_THEME.argtypes = [
                wintypes.HWND,
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
            ]
        except AttributeError:  # pragma: no cover - depends on Windows build
            _WINDOWS_SET_WINDOW_THEME = None

    _WINDOWS_DARK_MODE_APP_INITIALISED = False
    _WINDOWS_DARK_MODE_APP_ALLOWED = False
    _PREFERRED_APP_MODE_ALLOW_DARK = 1
else:  # pragma: no cover - non-Windows platforms do not use MENUINFO
    MENUINFO = None
    MIM_BACKGROUND = 0
    MIM_APPLYTOSUBMENUS = 0

    _WINDOWS_SET_PREFERRED_APP_MODE = None
    _WINDOWS_ALLOW_DARK_MODE_FOR_APP = None
    _WINDOWS_ALLOW_DARK_MODE_FOR_WINDOW = None
    _WINDOWS_SET_WINDOW_THEME = None

    _WINDOWS_DARK_MODE_APP_INITIALISED = False
    _WINDOWS_DARK_MODE_APP_ALLOWED = False
    _PREFERRED_APP_MODE_ALLOW_DARK = 0


def ensure_windows_dark_mode_allowed() -> bool:
    """Initialise Windows dark-mode hooks if available."""

    if not IS_WINDOWS:
        return False

    global _WINDOWS_DARK_MODE_APP_INITIALISED, _WINDOWS_DARK_MODE_APP_ALLOWED

    if _WINDOWS_DARK_MODE_APP_INITIALISED:
        return _WINDOWS_DARK_MODE_APP_ALLOWED

    allowed = False

    if _WINDOWS_SET_PREFERRED_APP_MODE is not None:
        try:
            _WINDOWS_SET_PREFERRED_APP_MODE(_PREFERRED_APP_MODE_ALLOW_DARK)
            allowed = True
        except OSError:  # pragma: no cover - depends on Windows build
            pass

    if _WINDOWS_ALLOW_DARK_MODE_FOR_APP is not None:
        try:
            if _WINDOWS_ALLOW_DARK_MODE_FOR_APP(True):
                allowed = True
        except OSError:  # pragma: no cover - depends on Windows build
            pass

    _WINDOWS_DARK_MODE_APP_INITIALISED = True
    _WINDOWS_DARK_MODE_APP_ALLOWED = allowed
    return allowed


def apply_windows_dark_mode_for_window(handle: int, enabled: bool) -> bool:
    """Request Windows dark-mode for the given HWND."""

    if not IS_WINDOWS:
        return False

    success = False
    hwnd = wintypes.HWND(handle)

    if _WINDOWS_ALLOW_DARK_MODE_FOR_WINDOW is not None:
        try:
            if _WINDOWS_ALLOW_DARK_MODE_FOR_WINDOW(hwnd, ctypes.c_bool(enabled)):
                success = True
        except OSError:  # pragma: no cover - depends on Windows build
            pass

    if _WINDOWS_SET_WINDOW_THEME is not None:
        theme = "DarkMode_Explorer" if enabled else None
        try:
            result = _WINDOWS_SET_WINDOW_THEME(
                hwnd,
                ctypes.c_wchar_p(theme) if theme else None,
                None,
            )
        except OSError:  # pragma: no cover - depends on Windows build
            result = -1
        if result == 0:
            success = True

    return success


def load_user32() -> Any:
    if not IS_WINDOWS:
        return None
    try:
        return ctypes.windll.user32
    except AttributeError:
        return None


def load_gdi32() -> Any:
    if not IS_WINDOWS:
        return None
    try:
        return ctypes.windll.gdi32
    except AttributeError:
        return None


def load_dwmapi() -> Any:
    if not IS_WINDOWS:
        return None
    try:
        return ctypes.windll.dwmapi
    except AttributeError:
        return None


def is_dark_color(value: str) -> bool:
    try:
        red, green, blue = hex_to_rgb(value)
    except ValueError:
        return False
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return luminance < 128


def colorref_from_hex(value: str) -> int:
    try:
        red, green, blue = hex_to_rgb(value)
    except ValueError:
        return 0
    return (blue << 16) | (green << 8) | red

__all__ = [
    "MENUINFO",
    "MIM_BACKGROUND",
    "MIM_APPLYTOSUBMENUS",
    "apply_windows_dark_mode_for_window",
    "colorref_from_hex",
    "ensure_windows_dark_mode_allowed",
    "is_dark_color",
    "load_dwmapi",
    "load_gdi32",
    "load_user32",
]
