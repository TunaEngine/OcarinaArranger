"""Public API for the GUI theme system."""

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

__all__ = [
    "INSERT_BACKGROUND_PATTERNS",
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
    "register_theme_listener",
    "set_active_theme",
    "set_ttk_caret_color",
]
