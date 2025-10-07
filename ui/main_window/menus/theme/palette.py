"""Palette application helpers shared by theme-related mixins."""

from __future__ import annotations

import logging
import sys
import tkinter as tk
import types
from typing import Dict, List

from shared.tk_style import configure_style, map_style
from shared.ttk import ttk

from ocarina_gui.color_utils import hex_to_rgb, mix_colors, rgb_to_hex
from ocarina_gui.themes import TablePalette, ThemePalette

from ..windows_theme import (
    apply_menu_bar_colors,
    apply_window_frame_colors,
    is_dark_color,
    schedule_window_frame_refresh,
)

logger = logging.getLogger(__name__)


class ThemePaletteMixin:
    """Provide helpers for applying palette values to widgets."""

    _headless: bool
    _style: ttk.Style | None
    _fingering_table_style: str | None
    fingering_table: ttk.Treeview | None
    _registered_menus: List[tk.Menu]

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
            configure_style(
                style,
                style_name,
                background=palette.background,
                fieldbackground=palette.background,
                foreground=palette.foreground,
            )

            heading_style = f"{style_name}.Heading"
            configure_style(
                style,
                heading_style,
                background=palette.heading_background,
                foreground=palette.heading_foreground,
            )

            if not map_style(
                style,
                heading_style,
                background=[
                    ("pressed", palette.selection_background),
                    ("active", palette.selection_background),
                ],
                foreground=[
                    ("pressed", palette.selection_foreground),
                    ("active", palette.selection_foreground),
                ],
            ):
                continue
            applied[heading_style] = ["background", "foreground"]

        for style_name in style_names:
            if not map_style(
                style,
                style_name,
                background=[("selected", palette.selection_background)],
                foreground=[("selected", palette.selection_foreground)],
            ):
                continue
            applied[style_name] = ["background", "foreground"]

        table = self.fingering_table
        if table is not None:
            try:
                table.tag_configure(
                    "even", background=palette.background, foreground=palette.foreground
                )
                table.tag_configure(
                    "odd", background=palette.row_stripe, foreground=palette.foreground
                )
            except tk.TclError:
                pass

        update_indicator = getattr(self, "_update_fingering_drop_indicator_palette", None)
        if callable(update_indicator):
            update_indicator(palette)

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
        select_color = _blend_colors(background, foreground, 0.5)
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
        setattr(self, "_menu_palette_snapshot", colors.copy())

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
                self.option_add(pattern, value, 100)
            except tk.TclError:
                continue

        for menu in getattr(self, "_registered_menus", []):
            self._configure_menu_widget(menu, colors)

        style = self._style
        if style is not None:
            tk_app = getattr(style, "tk", None)
            if tk_app is None:
                master_widget = getattr(style, "master", None)
                if master_widget is not None:
                    tk_app = getattr(master_widget, "tk", None)
            if tk_app is not None:
                try:
                    tk_app.call(
                        "ttk::style",
                        "configure",
                        "MenuBar.TLabel",
                        "-background",
                        background,
                        "-foreground",
                        foreground,
                    )
                    tk_app.call(
                        "ttk::style",
                        "map",
                        "MenuBar.TLabel",
                        "-background",
                        ("active", selection_background),
                        "-foreground",
                        ("active", selection_foreground),
                    )
                except tk.TclError:
                    pass
            else:
                configure_style(
                    style,
                    "MenuBar.TLabel",
                    background=background,
                    foreground=foreground,
                )
                map_style(
                    style,
                    "MenuBar.TLabel",
                    background=[("active", selection_background)],
                    foreground=[("active", selection_foreground)],
                )

        custom_bar = getattr(self, "_custom_menubar", None)
        if custom_bar is not None:
            try:
                custom_bar.apply_palette(
                    background=background,
                    foreground=foreground,
                    active_background=selection_background,
                    active_foreground=selection_foreground,
                )
            except Exception:
                logger.debug("Failed to apply custom menubar palette", exc_info=True)

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

        setattr(self, "_last_title_background_attempt", palette.window_background)
        setattr(self, "_last_title_color_attempt", palette.text_primary)
        setattr(
            self,
            "_last_title_dark_mode_attempt",
            is_dark_color(palette.window_background),
        )
        setattr(self, "_last_title_hwnd_attempt", None)
        setattr(self, "_last_title_geometry_nudge", None)
        setattr(self, "_pending_title_geometry_nudge", False)
        setattr(self, "_last_menubar_brush_color_attempt", None)
        setattr(self, "_pending_menubar_refresh", False)
        setattr(self, "_windows_dark_mode_app_allowed", None)
        setattr(self, "_last_dark_mode_window_attempt", None)
        setattr(self, "_last_dark_mode_window_result", None)

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
            if getattr(self, "_use_native_menubar", False):
                apply_menu_bar_colors(self, palette)
            else:
                setattr(
                    self,
                    "_last_menubar_brush_color_attempt",
                    palette.window_background,
                )
            schedule_window_frame_refresh(self)


def _blend_colors(base: str, other: str, ratio: float) -> str | None:
    try:
        base_rgb = hex_to_rgb(base)
        other_rgb = hex_to_rgb(other)
    except ValueError:
        return None
    blended = mix_colors(base_rgb, other_rgb, ratio)
    return rgb_to_hex(blended)


__all__ = ["ThemePaletteMixin"]
