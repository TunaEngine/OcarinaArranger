from __future__ import annotations

import logging
import os
import tkinter as tk

from shared.ttk import ttk
from typing import TYPE_CHECKING, Dict, List, Optional

from ocarina_gui.constants import DEFAULT_MAX, DEFAULT_MIN
from ocarina_gui.fingering import (
    collect_instrument_note_names,
    get_available_instruments,
    get_current_instrument_id,
    get_instrument,
    preferred_note_window,
)

if TYPE_CHECKING:
    from viewmodels.main_viewmodel import MainViewModel, MainViewModelState

logger = logging.getLogger(__name__)


class InstrumentSettingsMixin:
    """Helpers for managing instrument selection and conversion settings."""

    _instrument_name_by_id: Dict[str, str]
    _instrument_id_by_name: Dict[str, str]
    _instrument_display_names: List[str]
    _range_note_options: list[str]
    _convert_instrument_combo: Optional[ttk.Combobox]
    _range_min_combo: Optional[ttk.Combobox]
    _range_max_combo: Optional[ttk.Combobox]
    _suspend_instrument_updates: bool
    _selected_instrument_id: str
    _viewmodel: "MainViewModel"
    _last_imported_path: Optional[str]
    _last_import_settings: Dict[str, object]
    _convert_setting_traces: list[tuple[tk.Variable, str]]
    _reimport_button: ttk.Button | None
    _preview_initial_loading: set[str]

    convert_instrument_var: tk.StringVar
    range_min: tk.StringVar
    range_max: tk.StringVar
    input_path: tk.StringVar

    def _initialize_instrument_state(self, state: "MainViewModelState") -> None:
        self._reload_instrument_choices()
        selected_id = state.instrument_id or self._safe_current_instrument_id()
        if selected_id and selected_id not in self._instrument_name_by_id:
            selected_id = ""
        if not selected_id and self._instrument_name_by_id:
            selected_id = next(iter(self._instrument_name_by_id))
        self._selected_instrument_id = selected_id
        if not selected_id:
            self._range_note_options = []
            return

        state.instrument_id = selected_id
        try:
            spec = get_instrument(selected_id)
        except Exception:
            logger.exception(
                "Failed to load instrument specification",
                extra={"instrument_id": selected_id},
            )
            self._range_note_options = []
            return

        self._range_note_options = collect_instrument_note_names(spec)
        if state.range_min == DEFAULT_MIN and state.range_max == DEFAULT_MAX:
            try:
                preferred_min, preferred_max = preferred_note_window(spec)
            except ValueError:
                preferred_min, preferred_max = state.range_min, state.range_max
            state.range_min = preferred_min
            state.range_max = preferred_max

    def _reload_instrument_choices(self) -> None:
        choices = get_available_instruments()
        self._instrument_name_by_id = {
            choice.instrument_id: choice.name for choice in choices
        }
        self._instrument_id_by_name = {
            choice.name: choice.instrument_id for choice in choices
        }
        self._instrument_display_names = [choice.name for choice in choices]

    def _safe_current_instrument_id(self) -> str:
        try:
            current = get_current_instrument_id()
        except Exception:  # pragma: no cover - defensive guard
            current = ""
        if current and current in self._instrument_name_by_id:
            return current
        return ""

    def _refresh_instrument_combo_values(self) -> None:
        if self._convert_instrument_combo is not None:
            self._convert_instrument_combo.configure(values=self._instrument_display_names)
        if hasattr(self, "convert_instrument_var"):
            name = self._instrument_name_by_id.get(self._selected_instrument_id, "")
            self._suspend_instrument_updates = True
            try:
                self.convert_instrument_var.set(name)
            finally:
                self._suspend_instrument_updates = False

    def _refresh_range_combobox_values(self) -> None:
        if self._range_min_combo is not None:
            self._range_min_combo.configure(values=self._range_note_options)
        if self._range_max_combo is not None:
            self._range_max_combo.configure(values=self._range_note_options)

    def _register_convert_instrument_combo(self, combo: ttk.Combobox) -> None:
        self._convert_instrument_combo = combo
        self._refresh_instrument_combo_values()
        combo.bind("<<ComboboxSelected>>", self._on_convert_instrument_selected)
        self._update_reimport_button_state()

    def _register_range_comboboxes(
        self, min_combo: ttk.Combobox, max_combo: ttk.Combobox
    ) -> None:
        self._range_min_combo = min_combo
        self._range_max_combo = max_combo
        self._refresh_range_combobox_values()

    def _on_library_instrument_changed(
        self, instrument_id: str, *, update_range: bool
    ) -> None:
        if not instrument_id:
            return
        self._reload_instrument_choices()
        if instrument_id not in self._instrument_name_by_id:
            instrument_id = self._safe_current_instrument_id()
            if not instrument_id:
                return
        self._selected_instrument_id = instrument_id
        self._viewmodel.state.instrument_id = instrument_id
        self._apply_half_note_default(instrument_id)
        try:
            spec = get_instrument(instrument_id)
        except Exception:
            logger.exception(
                "Failed to refresh instrument selection",
                extra={"instrument_id": instrument_id},
            )
            return
        self._range_note_options = collect_instrument_note_names(spec)
        if update_range:
            try:
                preferred_min, preferred_max = preferred_note_window(spec)
            except ValueError:
                preferred_min = self.range_min.get()
                preferred_max = self.range_max.get()
            if hasattr(self, "range_min"):
                self.range_min.set(preferred_min)
            if hasattr(self, "range_max"):
                self.range_max.set(preferred_max)
            self._viewmodel.state.range_min = preferred_min
            self._viewmodel.state.range_max = preferred_max
        self._refresh_instrument_combo_values()
        self._refresh_range_combobox_values()
        self._on_convert_setting_changed()

    def _on_convert_instrument_selected(
        self, _event: tk.Event | None = None
    ) -> None:
        if self._suspend_instrument_updates:
            return
        name = self.convert_instrument_var.get()
        instrument_id = self._instrument_id_by_name.get(name, "")
        if not instrument_id:
            logger.warning("Unknown instrument selection", extra={"name": name})
            return
        logger.info(
            "Convert tab instrument changed",
            extra={"instrument_id": instrument_id},
        )
        self.set_fingering_instrument(instrument_id)
        self._on_convert_setting_changed()

    def _register_reimport_button(self, button: ttk.Button) -> None:
        self._reimport_button = button
        try:
            button.state(["disabled"])
        except Exception:
            pass
        self._update_reimport_button_state()

    def _register_convert_setting_var(self, var: tk.Variable) -> None:
        try:
            token = var.trace_add("write", lambda *_args: self._on_convert_setting_changed())
        except Exception:
            return
        self._convert_setting_traces.append((var, token))

    def _on_convert_setting_changed(self) -> None:
        if getattr(self, "_suspend_state_sync", False):
            return
        self._update_reimport_button_state()

    def _update_reimport_button_state(self) -> None:
        button = self._reimport_button
        if button is None:
            return
        path = self.input_path.get().strip()
        if not path:
            try:
                button.state(["disabled"])
            except Exception:
                pass
            return
        if getattr(self, "_preview_initial_loading", set()):
            try:
                button.state(["disabled"])
            except Exception:
                pass
            return
        normalized = os.path.abspath(path)
        if not self._last_imported_path or normalized != self._last_imported_path:
            try:
                button.state(["disabled"])
            except Exception:
                pass
            return
        current = self._current_convert_settings_snapshot()
        if not self._last_import_settings:
            try:
                button.state(["disabled"])
            except Exception:
                pass
            return
        if current == self._last_import_settings:
            try:
                button.state(["!disabled"])
            except Exception:
                pass
            return
        try:
            button.state(["!disabled"])
        except Exception:
            pass


__all__ = ["InstrumentSettingsMixin"]
