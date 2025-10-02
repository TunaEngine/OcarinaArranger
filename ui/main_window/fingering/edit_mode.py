from __future__ import annotations

import copy
import logging
from typing import Optional

from tkinter import messagebox
from typing import Iterable

from ocarina_gui.fingering import (
    get_available_instruments,
    get_current_instrument_id,
    get_instrument,
    update_library_from_config,
)
from ocarina_gui.fingering.half_holes import (
    instrument_allows_half_holes,
    set_instrument_half_holes,
)

from viewmodels.instrument_layout_editor_viewmodel import InstrumentLayoutEditorViewModel

logger = logging.getLogger(__name__)


class FingeringEditModeMixin:
    """Manage lifecycle of the fingering editor view-model and edit state."""

    def _ensure_fingering_editor_viewmodel(self) -> InstrumentLayoutEditorViewModel | None:
        if self._headless:
            return None

        choices = get_available_instruments()
        if not choices:
            return None

        instruments = [get_instrument(choice.instrument_id) for choice in choices]
        viewmodel = InstrumentLayoutEditorViewModel(instruments)

        try:
            current_id = get_current_instrument_id()
        except Exception:
            current_id = instruments[0].instrument_id

        try:
            viewmodel.select_instrument(current_id)
        except ValueError:
            viewmodel.select_instrument(instruments[0].instrument_id)

        self._fingering_edit_vm = viewmodel
        return viewmodel

    def toggle_fingering_editing(self) -> None:
        if self._headless:
            return
        if self._fingering_edit_mode:
            self._exit_fingering_edit_mode()
        else:
            self._enter_fingering_edit_mode()

    def _enter_fingering_edit_mode(self) -> None:
        current_selection = self._selected_fingering_note()
        viewmodel = self._ensure_fingering_editor_viewmodel()
        if viewmodel is None:
            return

        self._fingering_edit_backup = copy.deepcopy(viewmodel.build_config())
        self._fingering_edit_mode = True
        self._fingering_click_guard_note = None
        self._fingering_display_columns_override = None
        self._hide_fingering_drop_indicator()
        self._set_fingering_drop_hint(None, insert_after=False)

        self._set_instrument_switching_enabled(False)

        if self._fingering_edit_button is not None:
            self._fingering_edit_button.config(text="Done")
        if self._fingering_cancel_button is not None and self._fingering_cancel_pad is not None:
            self._fingering_cancel_button.pack(side="right", padx=self._fingering_cancel_pad)
        if self._fingering_edit_controls is not None:
            self._fingering_edit_controls.grid()

        self._populate_fingering_table(current_selection)
        self._update_fingering_note_actions_state()

    def _exit_fingering_edit_mode(self) -> None:
        current_selection = self._selected_fingering_note()
        self._fingering_edit_mode = False
        self._fingering_edit_vm = None
        self._fingering_edit_backup = None
        self._fingering_click_guard_note = None
        self._fingering_display_columns_override = None
        self._fingering_column_drag_source = None
        self._hide_fingering_drop_indicator()
        self._set_fingering_drop_hint(None, insert_after=False)

        self._set_instrument_switching_enabled(True)

        if self._fingering_edit_button is not None:
            self._fingering_edit_button.config(text="Edit...")
        if self._fingering_cancel_button is not None:
            self._fingering_cancel_button.pack_forget()
        if self._fingering_edit_controls is not None:
            self._fingering_edit_controls.grid_remove()

        self._populate_fingering_table(current_selection)
        self._update_fingering_note_actions_state()

    def cancel_fingering_edits(self, *, show_errors: bool = True) -> None:
        if not self._fingering_edit_mode:
            return

        self._restore_fingering_backup(show_errors=show_errors)
        self._exit_fingering_edit_mode()

    def _restore_fingering_backup(self, *, show_errors: bool) -> None:
        backup = self._fingering_edit_backup
        if backup is None:
            return

        try:
            update_library_from_config(
                copy.deepcopy(backup),
                current_instrument_id=get_current_instrument_id(),
            )
        except ValueError as exc:
            if show_errors and not self._headless:
                messagebox.showerror("Cancel fingering edits", str(exc), parent=self)

    def _selected_fingering_note(self) -> Optional[str]:
        table = self.fingering_table
        if table is None:
            return None
        selection = table.selection()
        if not selection:
            return None
        note = selection[0]
        if note == "_empty":
            return None
        return note

    def _apply_fingering_editor_changes(self, focus_note: Optional[str] = None) -> None:
        viewmodel = self._fingering_edit_vm
        if viewmodel is None:
            return

        config = viewmodel.build_config()
        current_id = viewmodel.state.instrument_id
        try:
            update_library_from_config(config, current_instrument_id=current_id)
        except ValueError as exc:
            if not self._headless:
                messagebox.showerror("Update fingering", str(exc), parent=self)
            return

        self._refresh_fingering_instrument_choices(current_id)
        self._populate_fingering_table(focus_note)
        self._fingering_click_guard_note = None

        if focus_note:
            table = self.fingering_table
            if table is not None and table.exists(focus_note):
                self._fingering_ignore_next_select = True
                logger.debug(
                    "Re-selecting note after applying fingering edits",
                    extra={
                        "focus_note": focus_note,
                        "ignore_next_select": self._fingering_ignore_next_select,
                    },
                )
                table.selection_set(focus_note)
                table.focus(focus_note)
                self._on_fingering_table_select()
        self._update_fingering_note_actions_state()

    def _half_notes_enabled(self) -> bool:
        value = getattr(self, "_fingering_half_notes_enabled", False)
        var = getattr(self, "_fingering_allow_half_var", None)
        if var is not None:
            try:
                value = bool(var.get())
            except Exception:  # pragma: no cover - defensive
                value = False
        self._fingering_half_notes_enabled = value
        return value

    def _set_instrument_switching_enabled(self, enabled: bool) -> None:
        combos: Iterable[object] = (
            combo
            for combo in (
                getattr(self, "fingering_selector", None),
                getattr(self, "_convert_instrument_combo", None),
            )
            if combo is not None
        )

        state = "readonly" if enabled else "disabled"
        for combo in combos:
            if self._set_combobox_state_via_item(combo, state):
                self._normalise_combobox_state_accessor(combo)
                continue

            if self._set_combobox_state_via_configure(combo, state):
                self._normalise_combobox_state_accessor(combo)
                continue

            if self._set_combobox_state_via_state_method(combo, enabled, state):
                self._normalise_combobox_state_accessor(combo)

    @staticmethod
    def _set_combobox_state_via_item(combo: object, state: str) -> bool:
        try:
            combo["state"] = state
        except Exception:
            return False
        return True

    @staticmethod
    def _set_combobox_state_via_configure(combo: object, state: str) -> bool:
        try:
            combo.configure(state=str(state))
        except Exception:
            return False
        return True

    @staticmethod
    def _set_combobox_state_via_state_method(
        combo: object, enabled: bool, state: str
    ) -> bool:
        try:
            if enabled:
                combo.state(["!disabled"])
                combo.state([state])
            else:
                combo.state(["disabled"])
        except Exception:
            return False
        return True

    @staticmethod
    def _normalise_combobox_state_accessor(combo: object) -> None:
        if getattr(combo, "_state_cget_normalised", False):
            return

        original_cget = getattr(combo, "cget", None)
        if original_cget is None:
            return

        def _normalised_cget(option: str, _orig=original_cget):
            value = _orig(option)
            if option == "state" and not isinstance(value, str):
                try:
                    return str(value)
                except Exception:
                    return value
            return value

        try:
            setattr(combo, "cget", _normalised_cget)
            setattr(combo, "_state_cget_normalised", True)
        except Exception:
            pass

    def _apply_half_note_default(self, instrument_id: str) -> None:
        enabled = self._should_enable_half_holes(instrument_id)
        self._fingering_half_notes_enabled = enabled
        set_instrument_half_holes(instrument_id, enabled)
        viewmodel = getattr(self, "_fingering_edit_vm", None)
        if viewmodel is not None:
            try:
                viewmodel.set_half_hole_support(enabled)
            except Exception:
                pass
        var = getattr(self, "_fingering_allow_half_var", None)
        if var is None:
            return
        try:
            if bool(var.get()) != enabled:
                var.set(enabled)
        except Exception:
            pass

    @staticmethod
    def _should_enable_half_holes(instrument_id: str) -> bool:
        return instrument_allows_half_holes(instrument_id)

    def _on_fingering_half_notes_toggle(self) -> None:
        allow_half = self._half_notes_enabled()
        current_id = getattr(self, "_selected_instrument_id", "")
        if current_id:
            set_instrument_half_holes(current_id, allow_half)
        logger.debug(
            "Toggled fingering half-note support",
            extra={"enabled": allow_half},
        )
        viewmodel = self._fingering_edit_vm
        if viewmodel is not None:
            viewmodel.set_half_hole_support(allow_half)
        if viewmodel is None or allow_half:
            self._update_fingering_note_actions_state()
            return

        hole_count = len(viewmodel.state.holes)
        if hole_count <= 0:
            self._update_fingering_note_actions_state()
            return

        changed = False
        for note, pattern in list(viewmodel.state.note_map.items()):
            normalized = list(pattern)
            limit = min(len(normalized), hole_count)
            note_changed = False
            for index in range(limit):
                if int(normalized[index]) == 1:
                    normalized[index] = 2
                    note_changed = True
            if note_changed:
                viewmodel.set_note_pattern(note, normalized)
                changed = True

        if changed:
            focus = self._selected_fingering_note()
            self._apply_fingering_editor_changes(focus)
        else:
            self._update_fingering_note_actions_state()
