from __future__ import annotations

import importlib
import logging

logger = logging.getLogger(__name__)


class FingeringNoteActionsMixin:
    """Commands for adding, renaming, and removing fingering notes."""

    def add_fingering_note(self) -> None:
        if not self._fingering_edit_mode:
            return
        viewmodel = self._fingering_edit_vm
        if viewmodel is None:
            return

        candidates = viewmodel.candidate_note_names()
        logger.debug(
            "Computed fingering note candidates",
            extra={
                "instrument_id": viewmodel.state.instrument_id,
                "candidate_count": len(candidates),
                "candidates": candidates,
            },
        )
        if not candidates:
            logger.debug(
                "No fingering candidates available",
                extra={"instrument_id": viewmodel.state.instrument_id},
            )
            _messagebox().showinfo(
                "Add fingering",
                "No note choices are available for this instrument.",
                parent=self,
            )
            return

        existing = set(viewmodel.state.note_map.keys())
        if not any(choice not in existing for choice in candidates):
            logger.debug(
                "All candidate notes already have fingerings",
                extra={
                    "instrument_id": viewmodel.state.instrument_id,
                    "existing_notes": sorted(existing),
                    "candidate_count": len(candidates),
                },
            )
            _messagebox().showinfo(
                "Add fingering",
                "All available notes already have fingerings.",
                parent=self,
            )
            return

        note = _prompt_for_note_name(
            self,
            candidates,
            disabled=existing,
            title="Add Fingering",
        )
        if note is None:
            return
        normalized = note.strip()

        pattern = viewmodel.initial_pattern_for_note(normalized)
        try:
            viewmodel.set_note_pattern(normalized, pattern)
        except ValueError as exc:
            _messagebox().showerror("Add fingering", str(exc), parent=self)
            return

        self._apply_fingering_editor_changes(normalized)

    def remove_fingering_note(self) -> None:
        if not self._fingering_edit_mode:
            return
        viewmodel = self._fingering_edit_vm
        if viewmodel is None:
            return

        note = self._selected_fingering_note()
        if not note:
            _messagebox().showinfo("Remove fingering", "Select a note to remove first.", parent=self)
            return

        if not _messagebox().askyesno("Remove fingering", f"Remove fingering for '{note}'?", parent=self):
            return

        try:
            viewmodel.remove_note(note)
        except ValueError as exc:
            _messagebox().showerror("Remove fingering", str(exc), parent=self)
            return

        self._apply_fingering_editor_changes()
        table = self.fingering_table
        if table is not None:
            table.selection_remove(table.selection())
        self._on_fingering_table_select()

    def _update_fingering_note_actions_state(self) -> None:
        button = self.__dict__.get("_fingering_remove_button")
        if button is None:
            return
        if not self._fingering_edit_mode:
            button.state(["disabled"])
            return

        note = self._selected_fingering_note()
        viewmodel = self._fingering_edit_vm
        if viewmodel is None or not note or note not in viewmodel.state.note_map:
            button.state(["disabled"])
        else:
            button.state(["!disabled"])


def _messagebox():
    """Return the messagebox module exported from ui.main_window."""

    module = importlib.import_module("ui.main_window")
    return module.messagebox


def _prompt_for_note_name(*args, **kwargs):
    """Delegate to the prompt_for_note_name re-export for monkeypatch compatibility."""

    module = importlib.import_module("ui.main_window")
    return module.prompt_for_note_name(*args, **kwargs)
