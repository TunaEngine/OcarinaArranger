"""Theme-related helpers for :class:`MenuActionsMixin`."""

from __future__ import annotations

from typing import Callable, Dict, List, Sequence

import tkinter as tk
from tkinter import ttk

from ocarina_gui.themes import (
    INSERT_BACKGROUND_PATTERNS,
    TablePalette,
    ThemeSpec,
    apply_insert_cursor_color,
    set_ttk_caret_color,
    set_active_theme,
)


class ThemeMenuMixin:
    """Provide theme menu helpers shared by the main window."""

    _theme_choices: Sequence  # populated by ``MainWindow``
    _theme_actions: Dict[str, Callable[[], None]]
    _applied_style_maps: Dict[str, List[str]]
    _fingering_table_style: str | None

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

        try:
            self.configure(background=palette.window_background)
        except tk.TclError:
            pass

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
