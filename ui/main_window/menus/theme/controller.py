"""High-level mixin responsible for applying themes to the main window."""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Sequence

import tkinter as tk

from shared.ttk import ttk, use_bootstrap_ttk, use_native_ttk

from ocarina_gui.themes import (
    INSERT_BACKGROUND_PATTERNS,
    ThemeSpec,
    apply_insert_cursor_color,
    set_active_theme,
    set_ttk_caret_color,
)
from ocarina_gui.themes.runtime import resolve_theme_style

from .palette import ThemePaletteMixin

logger = logging.getLogger("ui.main_window.menus.theme")


class ThemeMenuMixin(ThemePaletteMixin):
    """Provide theme menu helpers shared by the main window."""

    _theme_choices: Sequence
    _theme_actions: Dict[str, Callable[[], None]]
    _applied_style_maps: Dict[str, List[str]]
    _fingering_table_style: str | None
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
            self._theme_actions[choice.theme_id] = self._make_theme_callback(choice.theme_id)

    def _make_theme_callback(self, theme_id: str) -> Callable[[], None]:
        def _callback() -> None:
            self.set_theme(theme_id)

        return _callback

    def set_theme(self, theme_id: str) -> None:
        """Activate and apply the given theme identifier."""

        logger.info(
            "Theme menu requested theme change: %s", theme_id, extra={"theme_id": theme_id}
        )
        set_active_theme(theme_id)
        if self._headless:
            return

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
        """Invoke the theme menu command matching ``theme_id`` (for tests)."""

        callback = self._theme_actions.get(theme_id)
        if callback is None:
            return
        callback()

    def _apply_theme(self, theme: ThemeSpec) -> None:
        self._theme = theme
        self.theme_id.set(theme.theme_id)
        self.theme_name.set(theme.name)

        if self._headless:
            return

        palette = theme.palette
        resolution = resolve_theme_style(self, theme)
        style = resolution.style
        supports_bootstyle = resolution.bootstrap_active

        self._style = style
        self._supports_bootstyle = supports_bootstyle

        if supports_bootstyle:
            try:
                use_bootstrap_ttk()
            except ModuleNotFoundError:
                logger.debug(
                    "ttkbootstrap unavailable despite reported support; reverting to native ttk",
                    exc_info=True,
                )
                self._supports_bootstyle = False
                supports_bootstyle = False
                use_native_ttk()
        else:
            use_native_ttk()

        logger.info(
            "Theme applied: %s (%s)",
            theme.theme_id,
            theme.name,
            extra={"theme_id": theme.theme_id, "theme_name": theme.name},
        )

        for style_name, options in theme.styles.items():
            try:
                style.configure(style_name, **options)
            except tk.TclError:
                continue

        applied_maps = getattr(self, "_applied_style_maps", None)
        if applied_maps:
            for style_name, options in list(applied_maps.items()):
                if not options:
                    continue
                clear_kwargs = {option: [] for option in options}
                try:
                    style.map(style_name, **clear_kwargs)
                except tk.TclError:
                    continue
            applied_maps.clear()

        new_style_maps: Dict[str, List[str]] = {}
        for style_name, option_map in theme.style_maps.items():
            map_kwargs: Dict[str, List[tuple[str, str]]] = {}
            for option, entries in option_map.items():
                adjusted: List[tuple[str, str]] = []
                for statespec, value in entries:
                    spec = statespec
                    if not supports_bootstyle:
                        tokens = spec.split()
                        if "disabled" not in tokens and "!disabled" not in tokens:
                            spec = "!disabled" if not tokens else "!disabled " + spec
                    adjusted.append((spec, value))
                map_kwargs[option] = adjusted
            try:
                style.map(style_name, **map_kwargs)
            except tk.TclError:
                continue
            new_style_maps[style_name] = list(option_map.keys())

        table_maps = self._apply_table_palette(theme.palette.table)
        for style_name, options in table_maps.items():
            if not options:
                continue
            new_style_maps[style_name] = options

        self._applied_style_maps = new_style_maps

        try:
            style.configure(
                "Hint.TLabel",
                background=palette.window_background,
                foreground=palette.text_muted,
            )
        except tk.TclError:
            pass

        for pattern, value in theme.options.items():
            try:
                self.option_add(pattern, value)
            except tk.TclError:
                continue

        insert_color = palette.text_cursor
        set_ttk_caret_color(style, insert_color)
        for pattern in INSERT_BACKGROUND_PATTERNS:
            try:
                self.option_add(pattern, insert_color)
            except tk.TclError:
                continue

        apply_insert_cursor_color(self, insert_color)
        self._apply_window_frame_palette(palette)
        self._apply_menu_palette(theme.palette)
        self._apply_runtime_base_widget_palette(palette)
        self._apply_app_widget_styles(palette)

        for roll in (self.roll_orig, self.roll_arr):
            if roll is None:
                continue
            try:
                roll.apply_palette(palette.piano_roll)
            except Exception:
                logger.debug("Failed to apply piano roll palette", exc_info=True)

        for staff in (self.staff_orig, self.staff_arr):
            if staff is None:
                continue
            try:
                staff.apply_palette(palette.staff)
            except Exception:
                logger.debug("Failed to apply staff palette", exc_info=True)

        table = getattr(self, "fingering_table", None)
        if table is not None:
            try:
                for index, item in enumerate(table.get_children()):
                    tag = "even" if index % 2 == 0 else "odd"
                    table.item(item, tags=(tag,))
            except Exception:
                logger.debug("Failed to update fingering table row tags", exc_info=True)
            refresh_heading = getattr(self, "_refresh_fingering_heading_style", None)
            if callable(refresh_heading):
                try:
                    refresh_heading()
                except Exception:
                    logger.debug("Failed to refresh fingering heading style", exc_info=True)

        refresh_assets = getattr(self, "_refresh_preview_theme_assets", None)
        if callable(refresh_assets):
            try:
                refresh_assets()
            except Exception:
                logger.debug("Failed to refresh preview theme assets", exc_info=True)


__all__ = ["ThemeMenuMixin"]

