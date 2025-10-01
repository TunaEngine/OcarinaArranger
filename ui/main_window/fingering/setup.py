from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from ocarina_gui.fingering import (
    get_available_instruments,
    get_current_instrument_id,
    set_active_instrument,
)
from ocarina_gui.themes import get_current_theme

logger = logging.getLogger(__name__)


class FingeringSetupMixin:
    """Widget registration and instrument selection helpers."""

    def _register_fingering_table(self, tree: ttk.Treeview) -> None:
        self.fingering_table = tree
        if self._headless:
            return

        if self._style is None:
            self._style = ttk.Style(tree)

        style = self._style
        style_name = "Fingerings.Treeview"
        try:
            tree.configure(style=style_name)
        except tk.TclError:
            self._fingering_table_style = None
        else:
            self._fingering_table_style = style_name

        heading_style = f"{style_name}.Heading" if self._fingering_table_style else "Treeview.Heading"
        base_padding = self._normalize_style_padding(style.configure(heading_style, "padding"))
        if base_padding is None:
            base_padding = self._normalize_style_padding(style.configure("Treeview.Heading", "padding"))
        if base_padding is None:
            base_padding = (4, 2, 4, 2)
        self._fingering_heading_base_padding = base_padding

        self._refresh_fingering_heading_style()

        if self._fingering_drop_indicator is None:
            indicator = tk.Frame(tree, width=2, background="")
            indicator.place_forget()
            self._fingering_drop_indicator = indicator

        theme = self._theme or get_current_theme()
        self._update_fingering_drop_indicator_palette(theme.palette.table)
        self._hide_fingering_drop_indicator()

    def _register_fingering_preview(self, preview) -> None:
        self.fingering_preview = preview
        setter = getattr(preview, "set_hole_click_handler", None)
        if callable(setter):
            setter(self._on_fingering_preview_hole_click)
        windway_setter = getattr(preview, "set_windway_click_handler", None)
        if callable(windway_setter):
            windway_setter(self._on_fingering_preview_windway_click)

    def _refresh_fingering_after_layout_save(self, preferred_id: str) -> None:
        try:
            current_id = get_current_instrument_id()
        except Exception:  # pragma: no cover - defensive
            current_id = ""
        if preferred_id and preferred_id != current_id:
            try:
                set_active_instrument(preferred_id)
            except ValueError:
                pass
        active_id = get_current_instrument_id()
        self._refresh_fingering_instrument_choices(active_id)
        self._populate_fingering_table()
        self._on_fingering_table_select()

    def _refresh_fingering_instrument_choices(self, target_id: str | None) -> None:
        choices = get_available_instruments()
        if not choices:
            return
        name_by_id = {choice.instrument_id: choice.name for choice in choices}
        names = [choice.name for choice in choices]
        selected_id = target_id if target_id in name_by_id else choices[0].instrument_id
        selected_name = name_by_id[selected_id]

        if self.fingering_selector is not None:
            self.fingering_selector.configure(values=names)
            self.fingering_selector.set(selected_name)
        if self.fingering_instrument_var is not None:
            self.fingering_instrument_var.set(selected_name)

    def set_fingering_instrument(self, instrument_id: str) -> None:
        logger.info("Setting fingering instrument", extra={"instrument_id": instrument_id})
        try:
            set_active_instrument(instrument_id)
        except ValueError as exc:
            messagebox.showerror("Instrument", str(exc), parent=self)
            return

        if hasattr(self, "_on_library_instrument_changed"):
            self._on_library_instrument_changed(instrument_id, update_range=True)
        self._refresh_fingering_instrument_choices(instrument_id)
        self._populate_fingering_table()
        self._on_fingering_table_select()
