from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox

logger = logging.getLogger(__name__)


class FingeringEventMixin:
    """Event handlers for fingering editor interactions."""

    def _cycle_fingering_state(self, note: str, hole_index: int) -> None:
        viewmodel = self._fingering_edit_vm
        if viewmodel is None:
            return

        state = viewmodel.state
        hole_count = len(state.holes)
        if hole_index < 0 or hole_index >= hole_count:
            logger.debug(
                "Ignoring hole toggle outside range",
                extra={
                    "fingering_note": note,
                    "hole_index": hole_index,
                    "hole_count": hole_count,
                },
            )
            return

        pattern = list(state.note_map.get(note, [0] * hole_count))
        current = int(pattern[hole_index]) if hole_index < len(pattern) else 0
        next_value = (current + 1) % 3
        if hole_index >= len(pattern):
            pattern.extend([0] * (hole_index - len(pattern) + 1))
        pattern[hole_index] = next_value
        logger.debug(
            "Cycling fingering hole",
            extra={
                "fingering_note": note,
                "hole_index": hole_index,
                "previous_state": current,
                "next_state": next_value,
                "pattern_before": state.note_map.get(note, [0] * hole_count),
            },
        )
        try:
            viewmodel.set_note_pattern(note, pattern)
        except ValueError as exc:
            messagebox.showerror("Update fingering", str(exc), parent=self)
            return

        self._apply_fingering_editor_changes(note)

    def _on_fingering_preview_hole_click(self, hole_index: int) -> None:
        if not self._fingering_edit_mode:
            return

        note = self._fingering_last_selected_note
        if not note:
            return

        logger.debug(
            "Fingering preview hole click",
            extra={
                "clicked_note": note,
                "hole_index": hole_index,
            },
        )
        self._cycle_fingering_state(note, hole_index)

    def _on_fingering_cell_click(self, event: tk.Event) -> None:
        if not self._fingering_edit_mode:
            return
        table = self.fingering_table
        if table is None:
            return

        region = table.identify_region(event.x, event.y)
        if region == "heading":
            self._on_fingering_heading_release(event)
            return
        if region != "cell":
            return

        column_ref = table.identify_column(event.x)
        column_id = self._column_id_from_ref(table, column_ref)
        if column_id is None or column_id == "note":
            return

        hole_index = self._fingering_column_hole_index.get(column_id)
        if hole_index is None:
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
                "hole_index": hole_index,
            },
        )
        self._cycle_fingering_state(note, hole_index)

    def _on_fingering_table_button_press(self, event: tk.Event) -> None:
        if not self._fingering_edit_mode:
            return
        table = self.fingering_table
        if table is None:
            return
        region = table.identify_region(event.x, event.y)
        if region not in {"heading", "separator"}:
            self._hide_fingering_drop_indicator()
            return
        column_ref = table.identify_column(event.x)
        column_id = self._column_id_from_ref(table, column_ref)
        if column_id is None or column_id == "note":
            self._hide_fingering_drop_indicator()
            return
        self._fingering_column_drag_source = column_id

    def _on_fingering_heading_release(self, event: tk.Event) -> None:
        table = self.fingering_table
        if table is None:
            return
        source = self._fingering_column_drag_source
        self._fingering_column_drag_source = None
        if not self._fingering_edit_mode or not source:
            self._hide_fingering_drop_indicator()
            return

        display_columns = list(self._get_display_columns(table))
        if not display_columns:
            return

        column_ref = table.identify_column(event.x)
        target_id = self._column_id_from_ref(table, column_ref)
        if target_id is None or target_id not in display_columns:
            return

        after = self._should_insert_after(event.x, target_id, display_columns, table)

        try:
            display_columns.remove(source)
        except ValueError:
            return

        if target_id == "note":
            index = 1
        else:
            try:
                index = display_columns.index(target_id)
            except ValueError:
                return
            if after:
                index += 1
        index = max(1, index)

        display_columns.insert(index, source)
        self._apply_fingering_display_columns(display_columns)

        viewmodel = self._fingering_edit_vm
        if viewmodel is not None:
            hole_order: list[int] = []
            for column in display_columns:
                if column == "note":
                    continue
                hole_index = self._fingering_column_hole_index.get(column)
                if hole_index is not None:
                    hole_order.append(hole_index)
            if hole_order:
                focus_note = self._selected_fingering_note()
                try:
                    viewmodel.reorder_holes(hole_order)
                except Exception:
                    logger.debug("Failed to reorder holes", exc_info=True)
                else:
                    self._apply_fingering_editor_changes(focus_note)

        logger.debug(
            "Reordered fingering columns",
            extra={
                "source_column": source,
                "target_column": target_id,
                "insert_after_target": after,
                "display_columns": list(display_columns),
            },
        )

    def _on_fingering_heading_motion(self, event: tk.Event) -> None:
        table = self.fingering_table
        if table is None:
            return
        source = self._fingering_column_drag_source
        if not self._fingering_edit_mode or not source:
            self._hide_fingering_drop_indicator()
            return

        region = table.identify_region(event.x, event.y)
        if region not in {"heading", "separator"}:
            self._hide_fingering_drop_indicator()
            return

        display_columns = self._get_display_columns(table)
        if not display_columns:
            self._hide_fingering_drop_indicator()
            return

        column_ref = table.identify_column(event.x)
        target_id = self._column_id_from_ref(table, column_ref)
        if target_id is None or target_id not in display_columns:
            self._hide_fingering_drop_indicator()
            return

        after = self._should_insert_after(event.x, target_id, display_columns, table)

        position = self._column_left_edge(display_columns, target_id, table)
        if after:
            position += self._get_column_width(table, target_id)

        self._show_fingering_drop_indicator(position)
