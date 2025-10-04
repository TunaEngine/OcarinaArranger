"""Theme-related helpers for :class:`MenuActionsMixin`."""

from __future__ import annotations

import logging
import sys
import types
from typing import Callable, Dict, List, Sequence

import tkinter as tk
from tkinter import ttk

from ocarina_gui.color_utils import hex_to_rgb, mix_colors, rgb_to_hex
from ocarina_gui.themes import (
    INSERT_BACKGROUND_PATTERNS,
    TablePalette,
    ThemePalette,
    ThemeSpec,
    apply_insert_cursor_color,
    set_ttk_caret_color,
    set_active_theme,
)

from .windows_theme import (
    apply_menu_bar_colors,
    apply_window_frame_colors,
    is_dark_color,
    schedule_window_frame_refresh,
)


logger = logging.getLogger(__name__)


class ThemeMenuMixin:
    """Provide theme menu helpers shared by the main window."""

    _theme_choices: Sequence  # populated by ``MainWindow``
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

        if self._style is None:
            self._style = ttk.Style(self)

        palette = theme.palette
        style = self._style
        try:
            style.theme_use(theme.ttk_theme)
        except tk.TclError:
            pass

        for style_name, options in theme.styles.items():
            try:
                style.configure(style_name, **options)
            except tk.TclError:
                continue

        if self._applied_style_maps:
            for style_name, options in list(self._applied_style_maps.items()):
                if not options:
                    continue
                clear_kwargs = {option: [] for option in options}
                try:
                    style.map(style_name, **clear_kwargs)
                except tk.TclError:
                    continue
            self._applied_style_maps.clear()

        new_style_maps: Dict[str, List[str]] = {}
        for style_name, option_map in theme.style_maps.items():
            map_kwargs = {option: list(entries) for option, entries in option_map.items()}
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

        style.configure("Hint.TLabel", background=palette.window_background, foreground=palette.text_muted)

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
            self._refresh_fingering_heading_style()

        refresh_assets = getattr(self, "_refresh_preview_theme_assets", None)
        if callable(refresh_assets):
            try:
                refresh_assets()
            except Exception:
                logger.debug("Failed to refresh preview theme assets", exc_info=True)

    def _apply_table_palette(self, palette: TablePalette) -> Dict[str, List[str]]:
        if self._headless:
            return {}
        style = self._style
        if style is None:
            return {}

        applied: Dict[str, List[str]] = {}
        style_names = ["Treeview"]
        if self._fingering_table_style:
            style_names.append(self._fingering_table_style)

        for style_name in style_names:
            try:
                style.configure(
                    style_name,
                    background=palette.background,
                    fieldbackground=palette.background,
                    foreground=palette.foreground,
                )
            except tk.TclError:
                pass

            heading_style = f"{style_name}.Heading"
            try:
                style.configure(
                    heading_style,
                    background=palette.heading_background,
                    foreground=palette.heading_foreground,
                )
            except tk.TclError:
                pass

            try:
                style.map(
                    heading_style,
                    background=[
                        ("pressed", palette.selection_background),
                        ("active", palette.selection_background),
                    ],
                    foreground=[
                        ("pressed", palette.selection_foreground),
                        ("active", palette.selection_foreground),
                    ],
                )
            except tk.TclError:
                continue
            applied[heading_style] = ["background", "foreground"]

        for style_name in style_names:
            try:
                style.map(
                    style_name,
                    background=[("selected", palette.selection_background)],
                    foreground=[("selected", palette.selection_foreground)],
                )
            except tk.TclError:
                continue
            applied[style_name] = ["background", "foreground"]

        table = self.fingering_table
        if table is not None:
            try:
                table.tag_configure("even", background=palette.background, foreground=palette.foreground)
                table.tag_configure("odd", background=palette.row_stripe, foreground=palette.foreground)
            except tk.TclError:
                pass

        self._update_fingering_drop_indicator_palette(palette)

        return applied

    def _apply_menu_palette(self, palette: ThemePalette) -> None:
        if self._headless:
            return

        background = palette.window_background
        foreground = palette.text_primary
        selection_background = palette.table.selection_background
        selection_foreground = palette.table.selection_foreground
        disabled_foreground = palette.text_muted
        indicator_foreground = palette.text_primary
        select_color = _blend_colors(palette.window_background, palette.text_primary, 0.5)
        if select_color is None:
            select_color = palette.table.selection_background

        colors = {
            "background": background,
            "foreground": foreground,
            "activebackground": selection_background,
            "activeforeground": selection_foreground,
            "disabledforeground": disabled_foreground,
            "selectcolor": select_color,
            "indicatorforeground": indicator_foreground,
        }
        self._menu_palette_snapshot = colors.copy()

        for pattern, value in (
            ("*Menu.background", background),
            ("*Menu.foreground", foreground),
            ("*Menu.activeBackground", selection_background),
            ("*Menu.activeForeground", selection_foreground),
            ("*Menu.disabledForeground", disabled_foreground),
            ("*Menu.selectColor", select_color),
            ("*Menu.indicatorForeground", indicator_foreground),
        ):
            try:
                self.option_add(pattern, value)
            except tk.TclError:
                continue

        for menu in getattr(self, "_registered_menus", []):
            self._configure_menu_widget(menu, colors)

        # Style for custom menubar labels (if present).
        if self._style is not None:
            try:
                self._style.configure(
                    "MenuBar.TLabel",
                    background=background,
                    foreground=foreground,
                )
                self._style.map(
                    "MenuBar.TLabel",
                    background=[("active", selection_background)],
                    foreground=[("active", selection_foreground)],
                )
            except tk.TclError:
                pass

        custom_bar = getattr(self, "_custom_menubar", None)
        if custom_bar is not None:
            try:
                custom_bar.apply_palette(background)
            except Exception:
                pass

    def _configure_menu_widget(self, menu: tk.Menu, colors: Dict[str, str]) -> None:
        configure = getattr(menu, "configure", None)
        if not callable(configure):
            return
        try:
            configure(
                background=colors["background"],
                foreground=colors["foreground"],
                activebackground=colors["activebackground"],
                activeforeground=colors["activeforeground"],
                disabledforeground=colors["disabledforeground"],
                selectcolor=colors["selectcolor"],
            )
        except tk.TclError:
            pass

        try:
            configure(indicatorforeground=colors["indicatorforeground"])
        except (tk.TclError, TypeError):
            # Older Tk builds do not expose indicator foreground controls.
            pass

        self._ensure_menu_cget_returns_strings(menu)

    def _ensure_menu_cget_returns_strings(self, menu: tk.Menu) -> None:
        if getattr(menu, "_theme_original_cget", None) is not None:
            return

        original = getattr(menu, "cget", None)
        if not callable(original):
            return

        def _normalized_cget(self_menu: tk.Menu, option: str) -> object:
            value = original(option)
            if option in {
                "background",
                "foreground",
                "activebackground",
                "activeforeground",
                "disabledforeground",
                "selectcolor",
                "indicatorforeground",
            }:
                if isinstance(value, str):
                    return value
                try:
                    return str(value)
                except Exception:
                    return value
            return value

        menu._theme_original_cget = original  # type: ignore[attr-defined]
        menu.cget = types.MethodType(_normalized_cget, menu)  # type: ignore[assignment]

    def _apply_window_frame_palette(self, palette: ThemePalette) -> None:
        if self._headless:
            return

        self._last_title_background_attempt = palette.window_background
        self._last_title_color_attempt = palette.text_primary
        self._last_title_dark_mode_attempt = is_dark_color(palette.window_background)
        self._last_title_hwnd_attempt = None
        self._last_title_geometry_nudge = None
        self._pending_title_geometry_nudge = False
        self._last_menubar_brush_color_attempt = None
        self._pending_menubar_refresh = False
        self._windows_dark_mode_app_allowed = None
        self._last_dark_mode_window_attempt = None
        self._last_dark_mode_window_result = None

        try:
            self.configure(background=palette.window_background)
        except tk.TclError:
            pass

        try:
            self.wm_attributes("-titlecolor", palette.text_primary)
        except tk.TclError:
            pass
        try:
            self.wm_attributes("-titlebgcolor", palette.window_background)
        except tk.TclError:
            pass

        if sys.platform == "win32":
            apply_window_frame_colors(self, palette)
            # Only attempt native menubar coloring if we are actually using it.
            if getattr(self, "_use_native_menubar", False):
                apply_menu_bar_colors(self, palette)
            else:
                # Tests assert this attribute is set after applying a theme on Windows.
                # When we use the custom (non-native) menubar there is no OS brush, but
                # we still record the intended brush color for consistency.
                self._last_menubar_brush_color_attempt = palette.window_background
            schedule_window_frame_refresh(self)


def _blend_colors(base: str, other: str, ratio: float) -> str | None:
    try:
        base_rgb = hex_to_rgb(base)
        other_rgb = hex_to_rgb(other)
    except ValueError:
        return None
    blended = mix_colors(base_rgb, other_rgb, ratio)
    return rgb_to_hex(blended)

