from __future__ import annotations

from typing import List, Optional, Tuple

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from ocarina_gui.themes import TablePalette


class FingeringStyleMixin:
    """Appearance helpers for the fingering table."""

    _fingering_heading_base_padding: Optional[Tuple[int, int, int, int]]

    def _normalize_style_padding(self, value: object) -> tuple[int, int, int, int] | None:
        if not value:
            return None
        if isinstance(value, str):
            tokens = value.split()
        else:
            try:
                tokens = list(value)
            except TypeError:
                tokens = [value]
        numeric: List[int] = []
        for token in tokens:
            if token in {"", None}:
                continue
            try:
                numeric.append(int(float(token)))
            except (TypeError, ValueError):
                continue
        if not numeric:
            return None
        if len(numeric) == 1:
            val = numeric[0]
            return (val, val, val, val)
        if len(numeric) == 2:
            horizontal, vertical = numeric
            return (horizontal, vertical, horizontal, vertical)
        if len(numeric) == 3:
            left, vertical, right = numeric
            return (left, vertical, right, vertical)
        left, top, right, bottom, *_ = numeric
        return (left, top, right, bottom)

    def _resolve_heading_font(self) -> tkfont.Font:
        if self._headless:
            return tkfont.nametofont("TkDefaultFont")

        candidates: List[str] = []
        if self._fingering_heading_font_name:
            candidates.append(self._fingering_heading_font_name)

        style = self._style or ttk.Style(self)
        style_name = self._fingering_table_style
        heading_style = f"{style_name}.Heading" if style_name else "Treeview.Heading"
        candidate = style.lookup(heading_style, "font")
        if candidate:
            candidates.append(str(candidate))
        candidate = style.lookup("Treeview.Heading", "font")
        if candidate:
            candidates.append(str(candidate))
        candidates.extend(["TkHeadingFont", "TkDefaultFont"])

        for name in candidates:
            if not name:
                continue
            try:
                font = tkfont.nametofont(name)
            except tk.TclError:
                continue
            self._fingering_heading_font_name = font.name
            return font

        font = tkfont.nametofont("TkDefaultFont")
        self._fingering_heading_font_name = font.name
        return font

    def _update_fingering_heading_padding(
        self, lines: int, heading_font: tkfont.Font | None = None
    ) -> None:
        if self._headless:
            return
        lines = max(lines, 1)
        self._fingering_heading_lines = lines

        style = self._style or ttk.Style(self)
        style_name = self._fingering_table_style
        heading_style = f"{style_name}.Heading" if style_name else "Treeview.Heading"

        base_padding = self._fingering_heading_base_padding
        if base_padding is None:
            base_padding = self._normalize_style_padding(style.configure(heading_style, "padding"))
        if base_padding is None:
            base_padding = self._normalize_style_padding(style.configure("Treeview.Heading", "padding"))
        if base_padding is None:
            base_padding = (4, 2, 4, 2)
        self._fingering_heading_base_padding = base_padding

        if heading_font is None:
            heading_font = self._resolve_heading_font()
        else:
            self._fingering_heading_font_name = heading_font.name

        linespace = int(heading_font.metrics("linespace"))
        margin = max(linespace // 6, 2)

        extra_lines = lines - 1
        left, top, right, bottom = base_padding
        top += margin
        bottom += margin

        if extra_lines > 0:
            additional = extra_lines * linespace
            additional_top = additional // 2
            additional_bottom = additional - additional_top
            top += additional_top
            bottom += additional_bottom
            bottom += margin

        new_padding = (left, top, right, bottom)

        style.configure(heading_style, padding=new_padding)

    def _refresh_fingering_heading_style(self) -> None:
        if self._headless or self.fingering_table is None:
            return

        self._update_fingering_heading_padding(max(self._fingering_heading_lines, 1))

    def _update_fingering_drop_indicator_palette(self, palette: TablePalette) -> None:
        if self._headless:
            return
        indicator = self._fingering_drop_indicator
        if indicator is None:
            return
        color = palette.selection_background
        indicator.configure(background=color)
        self._fingering_drop_indicator_color = color

    def _show_fingering_drop_indicator(self, position: int) -> None:
        if self._headless:
            return
        indicator = self._fingering_drop_indicator
        if indicator is None:
            return
        position = max(int(position), 0)
        indicator.place(x=position, y=0, width=2, relheight=1.0)
        indicator.lift()

    def _hide_fingering_drop_indicator(self) -> None:
        if self._headless:
            return
        indicator = self._fingering_drop_indicator
        if indicator is None:
            return
        try:
            indicator.place_forget()
        except tk.TclError:
            pass
