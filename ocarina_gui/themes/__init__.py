"""Public API for the GUI theme system."""

from __future__ import annotations

import warnings

from app.version import get_app_version as _get_app_version
from ocarina_gui.preferences import (
    load_preferences as _load_preferences,
    save_preferences as _save_preferences,
)
from shared.logging_config import ensure_app_logging as _ensure_app_logging

from .library import (
    ThemeLibrary,
    _load_library,
    get_available_themes,
    get_current_theme,
    get_current_theme_id,
    get_theme,
    register_theme_listener,
    set_active_theme,
)
from .palettes import (
    LayoutEditorPalette,
    ListboxPalette,
    PianoRollPalette,
    StaffPalette,
    TablePalette,
    ThemePalette,
)
from .runtime import (
    INSERT_BACKGROUND_PATTERNS,
    apply_insert_cursor_color,
    apply_theme_to_toplevel,
    ensure_insert_bindings,
    set_ttk_caret_color,
)
from .spec import ThemeChoice, ThemeSpec


def load_preferences(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Return preferences while keeping older imports working."""

    warnings.warn(
        "ocarina_gui.themes.load_preferences is deprecated; import from "
        "ocarina_gui.preferences instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _load_preferences(*args, **kwargs)


def save_preferences(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Persist preferences via the legacy theme shim."""

    warnings.warn(
        "ocarina_gui.themes.save_preferences is deprecated; import from "
        "ocarina_gui.preferences instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _save_preferences(*args, **kwargs)


def ensure_app_logging(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Ensure application logging using the legacy import path."""

    warnings.warn(
        "ocarina_gui.themes.ensure_app_logging is deprecated; import from "
        "shared.logging_config instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _ensure_app_logging(*args, **kwargs)


def get_app_version(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Expose the app version for backwards compatibility."""

    warnings.warn(
        "ocarina_gui.themes.get_app_version is deprecated; import from "
        "app.version instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _get_app_version(*args, **kwargs)

__all__ = [
    "INSERT_BACKGROUND_PATTERNS",
    "ensure_app_logging",
    "get_app_version",
    "LayoutEditorPalette",
    "ListboxPalette",
    "PianoRollPalette",
    "StaffPalette",
    "TablePalette",
    "ThemeChoice",
    "ThemeLibrary",
    "ThemePalette",
    "ThemeSpec",
    "_load_library",
    "apply_insert_cursor_color",
    "apply_theme_to_toplevel",
    "ensure_insert_bindings",
    "get_available_themes",
    "get_current_theme",
    "get_current_theme_id",
    "get_theme",
    "load_preferences",
    "save_preferences",
    "register_theme_listener",
    "set_active_theme",
    "set_ttk_caret_color",
]
