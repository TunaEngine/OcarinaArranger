from __future__ import annotations

import tkinter as tk

from .base import FingeringEventBaseMixin, logger


class FingeringTableEventsMixin(FingeringEventBaseMixin):
    """Handlers for treeview interactions in the fingering editor."""

    def _on_fingering_cell_click(self, event: tk.Event) -> None:
        if not self._fingering_edit_mode:
            return
        table = self.fingering_table
        if table is None:
            return

        region = table.identify_region(event.x, event.y)
        if region in {"heading", "separator"}:
            self._on_fingering_heading_release(event)
            return
        if self._fingering_column_drag_source:
            self._fingering_column_drag_source = None
            self._hide_fingering_drop_indicator()
        if region != "cell":
            return

        column_ref = table.identify_column(event.x)
        column_id = self._column_id_from_ref(table, column_ref)
        if column_id is None or column_id == "note":
            return

        element_index = self._fingering_column_index.get(column_id)
        if element_index is None:
            return

        note = table.identify_row(event.y)
        if not note or note == "_empty":
            return

        logger.debug(
            "Fingering cell click",
            extra={
                "clicked_note": note,
                "focused_note": table.focus(),
                "selection": list(table.selection()),
                "column_index": self._display_column_index(table, column_id),
                "column_id": column_id,
                "click_guard_note": self._fingering_click_guard_note,
            },
        )

        selection = set(table.selection())
        focused_note = table.focus()
        active_note = self._fingering_last_selected_note

        if note not in selection:
            logger.debug(
                "Selecting row before toggling",
                extra={
                    "clicked_note": note,
                    "focused_note": focused_note,
                    "selection": list(selection),
                },
            )
            table.selection_set(note)
            if focused_note != note:
                table.focus(note)
            return

        if focused_note != note:
            logger.debug(
                "Restoring focus before toggling",
                extra={
                    "clicked_note": note,
                    "focused_note": focused_note,
                    "selection": list(selection),
                },
            )
            table.focus(note)
            focused_note = note

        if active_note != note:
            logger.debug(
                "Clicked non-active fingering row",
                extra={
                    "clicked_note": note,
                    "active_note": active_note,
                    "selection": list(selection),
                },
            )
            return

        if self._fingering_click_guard_note == note:
            logger.debug(
                "Ignoring guard click",
                extra={
                    "clicked_note": note,
                    "click_guard_note": self._fingering_click_guard_note,
                },
            )
            self._fingering_click_guard_note = None
            return

        self._fingering_click_guard_note = None
        logger.debug(
            "Toggling hole on active row",
            extra={
                "clicked_note": note,
                "column_index": self._display_column_index(table, column_id),
                "element_index": element_index,
            },
        )
        self._cycle_fingering_state(note, element_index)
