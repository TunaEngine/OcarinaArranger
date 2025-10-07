"""High-level mixin responsible for applying themes to the main window."""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional, Sequence

import tkinter as tk

from shared.ttk import ttk

from ocarina_gui.themes import (
    INSERT_BACKGROUND_PATTERNS,
    ThemeSpec,
    apply_insert_cursor_color,
    ensure_insert_bindings,
    set_active_theme,
    set_ttk_caret_color,
)
from shared.tk_style import configure_style, get_ttk_style, map_style

from .palette import ThemePaletteMixin

logger = logging.getLogger("ui.main_window.menus.theme")


class ThemeMenuMixin(ThemePaletteMixin):
    """Provide theme menu helpers shared by the main window."""

    _theme_choices: Sequence
    _theme_actions: Dict[str, Callable[[], None]]
    _applied_style_maps: Dict[str, List[str]]
    _registered_menus: List[tk.Menu]
    _menubar: tk.Menu | None
    _menu_palette_snapshot: Dict[str, str] | None
    _last_title_hwnd_attempt: int | None
    _last_title_geometry_nudge: tuple[int, int] | None
    _pending_title_geometry_nudge: bool
    _pending_menubar_refresh: bool
    _last_menubar_brush_color_attempt: str | None
    _menubar_brush_handle: int | None
    _windows_dark_mode_app_allowed: bool | None
    _last_dark_mode_window_attempt: bool | None
    _last_dark_mode_window_result: bool | None

    theme_id: tk.Variable
    theme_name: tk.Variable
    _style: ttk.Style | None
    _headless: bool

    roll_orig: object | None
    roll_arr: object | None
    staff_orig: object | None
    staff_arr: object | None
    fingering_table: object | None

    def _build_theme_actions(self) -> None:
        self._theme_actions.clear()
        for choice in self._theme_choices:
            self._theme_actions[choice.theme_id] = self._make_theme_callback(
                choice.theme_id
            )

    def _make_theme_callback(self, theme_id: str) -> Callable[[], None]:
        def _callback() -> None:
            self.set_theme(theme_id)

        return _callback

    def set_theme(self, theme_id: str) -> None:
        """Activate and apply the given theme identifier."""

        if self._headless:
            set_active_theme(theme_id)
            return
        set_active_theme(theme_id)

    def _register_menu(self, menu: tk.Menu, *, role: str = "submenu") -> tk.Menu:
        registry = getattr(self, "_registered_menus", None)
        if registry is None:
            registry = []
            self._registered_menus = registry
        registry.append(menu)
        if role == "menubar":
            self._menubar = menu
        return menu

    def activate_theme_menu(self, theme_id: str) -> None:
        callback = self._theme_actions.get(theme_id)
        if callback is None:
            return
        callback()

    # ------------------------------------------------------------------
    # Theme application
    # ------------------------------------------------------------------
    def _apply_theme(self, theme: ThemeSpec) -> None:
        self._theme = theme
        self.theme_id.set(theme.theme_id)
        self.theme_name.set(theme.name)

        palette = theme.palette
        logger.info(
            "Applying theme '%s' (ttk target '%s')",
            theme.theme_id,
            theme.ttk_theme,
        )
        insert_color = palette.text_cursor
        try:
            ensure_insert_bindings(self, insert_color)
        except tk.TclError:
            pass
        if self._headless:
            logger.info(
                "Applied theme '%s'; ttk theme now '%s' (headless)",
                theme.theme_id,
                theme.ttk_theme,
            )
            return

        style: ttk.Style | None = getattr(self, "style", None)
        if style is not None:
            try:
                style.theme_use(theme.ttk_theme)
            except tk.TclError as e:
                logger.warning(
                    "ttk.Window style failed to switch to '%s': %s; recreating", theme.ttk_theme, e
                )
                style = None
        if style is None:
            style = get_ttk_style(self, theme=theme.ttk_theme)
            logger.info("Recreated ttk style with theme '%s'", theme.ttk_theme)
        self._style = style

        # Force theme switch after style creation to ensure we're using the correct theme
        try:
            current_theme = style.theme_use()
            if current_theme != theme.ttk_theme:
                logger.warning("Style theme mismatch: expected '%s', got '%s'. Forcing switch.", theme.ttk_theme, current_theme)
                style.theme_use(theme.ttk_theme)
                logger.info("Successfully forced theme switch to '%s'", theme.ttk_theme)
        except tk.TclError as e:
            logger.error("Failed to force theme switch to '%s': %s", theme.ttk_theme, e)

        for style_name, options in theme.styles.items():
            if not configure_style(style, style_name, **options):
                continue

        # Ensure core container / text styles inherit the palette window background.
        # Some ttkbootstrap themes (e.g. darkly) leave certain widget backgrounds
        # light or platform-default; explicitly overriding here guarantees a
        # cohesive dark appearance for panels and entry fields when switching
        # themes at runtime.
        try:
            window_bg = palette.window_background
            text_fg = palette.text_primary
            configure_style(
                style,
                "TFrame",
                background=window_bg,
            )
            # Generic panel frame style for container sections.
            configure_style(
                style,
                "Panel.TFrame",
                background=window_bg,
            )
            configure_style(
                style,
                "Panel.TLabelframe",
                background=window_bg,
                foreground=text_fg,
            )
            configure_style(
                style,
                "Panel.TLabelframe.Label",
                background=window_bg,
                foreground=text_fg,
            )
            configure_style(
                style,
                "TLabelframe",
                background=window_bg,
                foreground=text_fg,
            )
            configure_style(
                style,
                "TLabelframe.Label",
                background=window_bg,
                foreground=text_fg,
            )
            configure_style(
                style,
                "TLabel",
                background=window_bg,
                foreground=text_fg,
            )
            # Entry / Combobox internal area
            configure_style(
                style,
                "TEntry",
                fieldbackground=window_bg,
                foreground=text_fg,
            )
            configure_style(
                style,
                "TCombobox",
                fieldbackground=window_bg,
                foreground=text_fg,
            )
            # Buttons / toggles (avoid hover artifacts inheriting light backgrounds)
            configure_style(
                style,
                "TCheckbutton",
                background=window_bg,
                foreground=text_fg,
            )
            configure_style(
                style,
                "TRadiobutton",
                background=window_bg,
                foreground=text_fg,
            )
            configure_style(
                style,
                "TNotebook",
                background=window_bg,
            )
            configure_style(
                style,
                "TNotebook.Tab",
                background=window_bg,
                foreground=text_fg,
            )
        except Exception:
            logger.debug("Failed to apply base container styles", exc_info=True)

        if self._applied_style_maps:
            for style_name, options in list(self._applied_style_maps.items()):
                if not options:
                    continue
                clear_kwargs = {option: [] for option in options}
                if not map_style(style, style_name, **clear_kwargs):
                    continue
            self._applied_style_maps.clear()

        new_style_maps: Dict[str, List[str]] = {}
        for style_name, option_map in theme.style_maps.items():
            map_kwargs = {option: list(entries) for option, entries in option_map.items()}
            if not map_style(style, style_name, **map_kwargs):
                continue
            new_style_maps[style_name] = list(option_map.keys())

        table_maps = self._apply_table_palette(theme.palette.table)
        for style_name, options in table_maps.items():
            if not options:
                continue
            new_style_maps[style_name] = options

        self._applied_style_maps = new_style_maps

        configure_style(
            style,
            "Hint.TLabel",
            background=palette.window_background,
            foreground=palette.text_muted,
        )

        for pattern, value in theme.options.items():
            try:
                self.option_add(pattern, value, 100)
            except tk.TclError:
                continue

        set_ttk_caret_color(style, insert_color)
        for pattern in INSERT_BACKGROUND_PATTERNS:
            try:
                self.option_add(pattern, insert_color, 100)
            except tk.TclError:
                continue

        apply_insert_cursor_color(self, insert_color)
        self._apply_window_frame_palette(palette)
        self._apply_menu_palette(theme.palette)

        for roll in (self.roll_orig, self.roll_arr):
            if roll is not None:
                roll.apply_palette(palette.piano_roll)

        for staff in (self.staff_orig, self.staff_arr):
            if staff is not None:
                staff.apply_palette(palette.staff)

        if self.fingering_table is not None:
            for index, item in enumerate(self.fingering_table.get_children()):
                tag = "even" if index % 2 == 0 else "odd"
                self.fingering_table.item(item, tags=(tag,))
            refresh_heading = getattr(self, "_refresh_fingering_heading_style", None)
            if callable(refresh_heading):
                refresh_heading()

        refresh_assets = getattr(self, "_refresh_preview_theme_assets", None)
        if callable(refresh_assets):
            try:
                refresh_assets()
            except Exception:
                logger.debug("Failed to refresh preview theme assets", exc_info=True)

        # Apply Panel styles again after delays to handle ttkbootstrap resets
        # that occur during widget updates in the main application window
        if style is not None:
            from shared.tk_style import configure_panel_styles
            def _apply_panel_styles_later():
                try:
                    configure_panel_styles(style, palette.window_background, palette.text_primary)
                except Exception:
                    logger.debug("Failed to reapply Panel styles", exc_info=True)
            # Apply immediately after theme setup
            self.after(1, _apply_panel_styles_later)
            # Apply again after more widget operations may have completed
            self.after(100, _apply_panel_styles_later)
            # Apply one more time after full initialization 
            self.after(500, _apply_panel_styles_later)

        try:
            active_ttk_theme = str(style.theme_use()) if style is not None else None
        except tk.TclError:
            active_ttk_theme = None
        logger.info(
            "Applied theme '%s'; ttk theme now '%s'",
            theme.theme_id,
            active_ttk_theme,
        )


__all__ = ["ThemeMenuMixin"]
