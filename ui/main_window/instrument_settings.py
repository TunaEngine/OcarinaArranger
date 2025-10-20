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
    set_active_instrument,
    preferred_note_window,
)
from ocarina_gui.preferences import Preferences, save_preferences
from ocarina_tools.midi_import.models import MidiImportReport
from ui.dialogs.midi_import_issues import show_midi_import_issues

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
    _midi_notice_frame: ttk.Frame | None
    _midi_notice_button: ttk.Button | None
    _last_midi_import_report: MidiImportReport | None

    convert_instrument_var: tk.StringVar
    range_min: tk.StringVar
    range_max: tk.StringVar
    input_path: tk.StringVar
    midi_import_notice: tk.StringVar

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
            set_active_instrument(selected_id)
        except Exception:
            logger.exception(
                "Failed to activate fingering instrument during initialisation",
                extra={"instrument_id": selected_id},
            )
        else:
            try:
                active_id = get_current_instrument_id()
            except Exception:  # pragma: no cover - defensive
                active_id = selected_id
            if active_id and active_id in self._instrument_name_by_id:
                selected_id = active_id
                self._selected_instrument_id = active_id
                state.instrument_id = active_id
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
        refresher = getattr(self, "_refresh_starred_instrument_controls", None)
        if callable(refresher):
            try:
                refresher()
            except Exception:
                logger.debug("Failed to refresh starred instrument controls", exc_info=True)

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

        preferences = getattr(self, "preferences", None)
        if isinstance(preferences, Preferences):
            normalized_instrument_id = instrument_id.strip()
            if normalized_instrument_id and preferences.instrument_id != normalized_instrument_id:
                preferences.instrument_id = normalized_instrument_id
                try:
                    save_preferences(preferences)
                except Exception:
                    logger.warning(
                        "Failed to persist instrument selection", extra={"instrument_id": normalized_instrument_id}
                    )
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

    def _register_midi_import_notice(
        self, frame: ttk.Frame, details_button: ttk.Button
    ) -> None:
        self._midi_notice_frame = frame
        self._midi_notice_button = details_button
        self._last_midi_import_report = None
        try:
            frame.grid_remove()
        except Exception:
            pass
        try:
            details_button.state(["disabled"])
        except Exception:
            pass

    def _update_midi_import_notice(
        self, report: MidiImportReport | None, error: str | None = None
    ) -> None:
        frame = getattr(self, "_midi_notice_frame", None)
        button = getattr(self, "_midi_notice_button", None)
        message_var = getattr(self, "midi_import_notice", None)
        if error is None:
            try:
                error = getattr(self._viewmodel.state, "midi_import_error", None)
            except Exception:
                error = None
        show_notice = bool(
            report
            and isinstance(report, MidiImportReport)
            and str(report.mode).strip().lower() == "lenient"
        )
        show_error = bool(error)
        if not show_notice and not show_error:
            self._last_midi_import_report = None
            if isinstance(message_var, tk.StringVar):
                message_var.set("")
            if frame is not None:
                try:
                    frame.grid_remove()
                except Exception:
                    pass
            if button is not None:
                try:
                    button.state(["disabled"])
                except Exception:
                    pass
            return

        if show_error:
            self._last_midi_import_report = None
            message = f"Preview failed: {error}"
        else:
            assert isinstance(report, MidiImportReport)
            self._last_midi_import_report = report
            issues = report.issues or ()
            track_ids = {issue.track_index for issue in issues}
            issue_count = len(issues)
            track_count = len(track_ids)
            if issue_count and track_count:
                issue_text = "issue" if issue_count == 1 else "issues"
                track_text = "track" if track_count == 1 else "tracks"
                message = (
                    f"Lenient MIDI import recovered {issue_count} {issue_text} "
                    f"across {track_count} {track_text}."
                )
            else:
                message = "Lenient MIDI import salvaged the MIDI file after strict parsing failed."
        if isinstance(message_var, tk.StringVar):
            message_var.set(message)
        if frame is not None:
            try:
                frame.grid()
            except Exception:
                pass
        if button is not None:
            try:
                if show_notice:
                    button.state(["!disabled"])
                else:
                    button.state(["disabled"])
            except Exception:
                pass

    def _on_view_midi_import_details(self) -> None:
        report = getattr(self, "_last_midi_import_report", None)
        if not isinstance(report, MidiImportReport):
            return
        try:
            show_midi_import_issues(self, report)
        except Exception:
            logger.exception("Failed to open MIDI import issues dialog")

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
