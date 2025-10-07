from __future__ import annotations

import tkinter as tk
from typing import Dict

from shared.ttk import ttk

from ocarina_gui.constants import DEFAULT_MAX, DEFAULT_MIN


class ConvertControlsMixin:
    """Initialise conversion-related Tk variables and helpers."""

    def _create_convert_controls(self, state) -> None:
        self.input_path = tk.StringVar(master=self, value=state.input_path)
        self.prefer_mode = tk.StringVar(master=self, value=state.prefer_mode)
        self.prefer_flats = tk.BooleanVar(master=self, value=state.prefer_flats)
        self.collapse_chords = tk.BooleanVar(master=self, value=state.collapse_chords)
        self.favor_lower = tk.BooleanVar(master=self, value=state.favor_lower)
        self.transpose_offset = tk.IntVar(master=self, value=state.transpose_offset)
        self.convert_instrument_var = tk.StringVar(
            master=self,
            value=self._instrument_name_by_id.get(self._selected_instrument_id, ""),
        )
        self.range_min = tk.StringVar(master=self, value=state.range_min or DEFAULT_MIN)
        self.range_max = tk.StringVar(master=self, value=state.range_max or DEFAULT_MAX)
        self.status = tk.StringVar(master=self, value=state.status_message)
        self._reimport_button: ttk.Button | None = None
        self._last_imported_path: str | None = None
        self._last_import_settings: Dict[str, object] = {}
        self._convert_setting_traces: list[tuple[tk.Variable, str]] = []
        self._register_convert_setting_var(self.prefer_mode)
        self._register_convert_setting_var(self.prefer_flats)
        self._register_convert_setting_var(self.collapse_chords)
        self._register_convert_setting_var(self.favor_lower)
        self._register_convert_setting_var(self.range_min)
        self._register_convert_setting_var(self.range_max)
        self._register_convert_setting_var(self.convert_instrument_var)
        self._register_convert_setting_var(self.transpose_offset)
        if self._selected_instrument_id:
            self._on_library_instrument_changed(
                self._selected_instrument_id, update_range=False
            )


__all__ = ["ConvertControlsMixin"]
