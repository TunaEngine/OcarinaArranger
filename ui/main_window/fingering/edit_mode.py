from __future__ import annotations

import copy
import logging
from typing import Optional

from tkinter import messagebox

from ocarina_gui.fingering import (
    get_available_instruments,
    get_current_instrument_id,
    get_instrument,
    update_library_from_config,
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

        if self._fingering_edit_button is not None:
            self._fingering_edit_button.config(text="Edit...")
        if self._fingering_cancel_button is not None:
            self._fingering_cancel_button.pack_forget()
        if self._fingering_edit_controls is not None:
            self._fingering_edit_controls.grid_remove()

        self._populate_fingering_table(current_selection)
        self._update_fingering_note_actions_state()

    def cancel_fingering_edits(self) -> None:
        if not self._fingering_edit_mode:
            return

        backup = self._fingering_edit_backup
        if backup is not None:
            try:
                update_library_from_config(copy.deepcopy(backup), current_instrument_id=get_current_instrument_id())
            except ValueError as exc:
                if not self._headless:
                    messagebox.showerror("Cancel fingering edits", str(exc), parent=self)

        self._exit_fingering_edit_mode()

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
