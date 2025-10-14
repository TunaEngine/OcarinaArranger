from __future__ import annotations

import sys
import tkinter as tk
import types
from typing import Dict, List

from shared.ttk import ttk

from ocarina_gui.color_utils import hex_to_rgb, mix_colors, rgb_to_hex
from ocarina_gui.themes import TablePalette, ThemePalette

from ..windows_theme import (
    apply_menu_bar_colors,
    apply_window_frame_colors,
    is_dark_color,
    schedule_window_frame_refresh,
)


class ThemePaletteMixin:
    """Provide helpers for applying palette values to widgets."""

    _headless: bool
    _style: ttk.Style | None
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
    fingering_table: object | None

    def _apply_runtime_base_widget_palette(self, palette: ThemePalette) -> None:
        """Update core ttk widget colors for the active palette."""

        if self._headless:
            return
        style = getattr(self, "_style", None)
        if style is None:
            return
        if getattr(style, "__module__", "").startswith("ttkbootstrap"):
            return

        base_bg = palette.window_background
        fg = palette.text_primary
        muted = palette.text_muted
        entry_bg = palette.listbox.background
        selection_bg = palette.table.selection_background
        selection_fg = palette.table.selection_foreground

        def _safe_config(name: str, **kwargs) -> None:
            try:
                style.configure(name, **kwargs)
            except (tk.TclError, KeyError):
                pass

        for name in (
            "TFrame",
            "TLabelframe",
            "TLabelframe.Label",
            "TLabel",
            "TNotebook",
            "TNotebook.Tab",
        ):
            _safe_config(name, background=base_bg, foreground=fg)

        for name in ("TEntry", "TCombobox", "TSpinbox"):
            _safe_config(
                name,
                fieldbackground=entry_bg,
                foreground=fg,
                insertcolor=palette.text_cursor,
            )

        for name in ("TRadiobutton", "TCheckbutton"):
            _safe_config(name, background=base_bg, foreground=fg)

        _safe_config("TButton", foreground=fg)

        if getattr(self, "_supports_bootstyle", False):
            try:
                style.map(
                    "TNotebook.Tab",
                    background=[("selected", selection_bg)],
                    foreground=[("selected", selection_fg)],
                )
            except tk.TclError:
                pass

        try:
            style.map("TButton", foreground=[("disabled", muted)])
        except tk.TclError:
            pass

        _safe_config("Hint.TLabel", background=base_bg, foreground=muted)

    def _apply_app_widget_styles(self, palette: ThemePalette) -> None:
        """Create derived ``App.*`` ttk styles and assign them to widgets."""

        if self._headless:
            return
        style = getattr(self, "_style", None)
        if style is None:
            return
        if getattr(style, "__module__", "").startswith("ttkbootstrap"):
            return

        try:
            from .windows_theme import is_dark_color as _is_dark_color  # type: ignore
        except Exception:  # pragma: no cover

            def _is_dark_color(_c: str) -> bool:  # type: ignore
                return False

        dark = _is_dark_color(palette.window_background)

        def _blend(base: str, other: str, ratio: float) -> str:
            mixed = _blend_colors(base, other, ratio)
            return mixed or base

        base_bg = palette.window_background
        fg = palette.text_primary
        muted = palette.text_muted
        entry_bg = palette.listbox.background
        select_bg = palette.table.selection_background
        select_fg = palette.table.selection_foreground

        if dark:
            surface = _blend(base_bg, "#ffffff", 0.07)
            hover = _blend(base_bg, "#ffffff", 0.14)
            active = _blend(base_bg, "#000000", 0.25)
            disabled_bg = _blend(base_bg, "#000000", 0.18)
            border = _blend(base_bg, "#ffffff", 0.22)
        else:
            surface = _blend(base_bg, "#000000", 0.02)
            hover = _blend(base_bg, "#000000", 0.06)
            active = _blend(base_bg, "#000000", 0.12)
            disabled_bg = _blend(base_bg, "#000000", 0.08)
            border = _blend(base_bg, "#000000", 0.10)

        try:
            style.configure(
                "App.TButton",
                background=surface,
                foreground=fg,
                focusthickness=1,
                focuscolor=border,
                bordercolor=border,
                padding=4,
            )
            style.map(
                "App.TButton",
                background=[
                    ("disabled", disabled_bg),
                    ("pressed", active),
                    ("active", hover),
                ],
                foreground=[("disabled", muted)],
            )
        except tk.TclError:
            pass

        for base_name, dest in (
            ("TEntry", "App.TEntry"),
            ("TCombobox", "App.TCombobox"),
            ("TSpinbox", "App.TSpinbox"),
        ):
            try:
                style.configure(
                    dest,
                    fieldbackground=entry_bg,
                    background=entry_bg,
                    foreground=fg,
                    bordercolor=border,
                    focusthickness=1,
                    focuscolor=border,
                    insertcolor=palette.text_cursor,
                    padding=2,
                )
                style.map(
                    dest,
                    fieldbackground=[
                        ("disabled", disabled_bg),
                        ("readonly", surface),
                        ("active", hover),
                    ],
                    foreground=[("disabled", muted)],
                )
            except tk.TclError:
                continue

        try:
            style.configure("App.TNotebook", background=base_bg, bordercolor=border)
            style.configure(
                "App.TNotebook.Tab",
                background=surface,
                foreground=fg,
                padding=(10, 4),
            )
            style.map(
                "App.TNotebook.Tab",
                background=[
                    ("selected", _blend(base_bg, "#ffffff" if dark else "#000000", 0.10)),
                    ("active", hover),
                    ("disabled", disabled_bg),
                ],
                foreground=[("disabled", muted), ("selected", fg)],
            )
        except tk.TclError:
            pass

        def _apply_to_children(widget: tk.Misc) -> None:
            try:
                children = widget.winfo_children()
            except tk.TclError:
                return
            for child in children:
                try:
                    style_name = child.cget("style")  # type: ignore[attr-defined]
                except Exception:
                    style_name = ""

                cls = child.winfo_class().lower()
                target = None
                if cls == "tbutton" and (not style_name or style_name == "TButton"):
                    target = "App.TButton"
                elif cls == "tentry" and (not style_name or style_name == "TEntry"):
                    target = "App.TEntry"
                elif cls == "tcombobox" and (not style_name or style_name == "TCombobox"):
                    target = "App.TCombobox"
                elif cls == "tspinbox" and (not style_name or style_name == "TSpinbox"):
                    target = "App.TSpinbox"
                elif cls == "tnotebook" and (not style_name or style_name == "TNotebook"):
                    target = "App.TNotebook"
                elif cls == "tnotebook.tab" and (not style_name or style_name == "TNotebook.Tab"):
                    target = "App.TNotebook.Tab"

                if target is not None:
                    try:
                        child.configure(style=target)  # type: ignore[attr-defined]
                    except Exception:
                        pass

                _apply_to_children(child)

        _apply_to_children(self)

    def _apply_table_palette(self, palette: TablePalette) -> Dict[str, List[str]]:
        if self._headless:
            return {}
        style = getattr(self, "_style", None)
        if style is None:
            return {}

        applied: Dict[str, List[str]] = {}
        style_names = ["Treeview"]
        table_style = getattr(self, "_fingering_table_style", None)
        if table_style:
            style_names.append(table_style)

        for style_name in style_names:
            try:
                style.configure(
                    style_name,
                    background=palette.background,
                    fieldbackground=palette.background,
                    foreground=palette.foreground,
                )
            except (tk.TclError, KeyError):
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
            except (tk.TclError, KeyError):
                continue
            applied[heading_style] = ["background", "foreground"]

        for style_name in style_names:
            try:
                style.map(
                    style_name,
                    background=[("selected", palette.selection_background)],
                    foreground=[("selected", palette.selection_foreground)],
                )
            except (tk.TclError, KeyError):
                continue
            applied[style_name] = ["background", "foreground"]

        table = getattr(self, "fingering_table", None)
        if table is not None:
            try:
                table.tag_configure("even", background=palette.background, foreground=palette.foreground)
                table.tag_configure("odd", background=palette.row_stripe, foreground=palette.foreground)
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
                self.option_add(pattern, value)
            except tk.TclError:
                continue

        for menu in getattr(self, "_registered_menus", []):
            self._configure_menu_widget(menu, colors)

        style = getattr(self, "_style", None)
        if style is not None:
            is_bootstrap = type(style).__module__.startswith("ttkbootstrap")
            if not is_bootstrap:
                try:
                    style.configure(
                        "MenuBar.TLabel",
                        background=background,
                        foreground=foreground,
                    )
                    style.map(
                        "MenuBar.TLabel",
                        background=[("active", selection_background)],
                        foreground=[("active", selection_foreground)],
                    )
                except Exception:
                    pass
            else:
                try:
                    menubar = getattr(self, "_menubar", None)
                    if menubar is not None:
                        menubar.configure(background=background, foreground=foreground)
                except Exception:
                    pass

        custom_bar = getattr(self, "_custom_menubar", None)
        if custom_bar is not None:
            try:
                hover_color = (
                    selection_background
                    if background != selection_background
                    else foreground
                )
                custom_bar.apply_palette(
                    background=background,
                    foreground=foreground,
                    active_background=hover_color,
                    active_foreground=selection_foreground,
                )
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
        setattr(self, "_last_title_dark_mode_attempt", is_dark_color(palette.window_background))
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
                setattr(self, "_last_menubar_brush_color_attempt", palette.window_background)
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
