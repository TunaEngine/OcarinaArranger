from __future__ import annotations

import tkinter as tk

from .base import logger


class FingeringHeadingEventsMixin:
    """Handlers for fingering table heading interactions."""

    def _set_fingering_heading_cursor(self, cursor: str | None) -> None:
        table = self.fingering_table
        if table is None:
            return

        target = cursor or ""
        if getattr(self, "_fingering_heading_cursor_active", None) == target:
            return

        try:
            table.configure(cursor=target)
        except tk.TclError:
            if cursor == getattr(self, "_fingering_heading_closed_cursor", ""):
                if getattr(self, "_fingering_heading_closed_cursor_supported", None) is not False:
                    self._fingering_heading_closed_cursor_supported = False
                    self._fingering_heading_closed_cursor = getattr(
                        self, "_fingering_heading_open_cursor", ""
                    )
                    self._set_fingering_heading_cursor(
                        getattr(self, "_fingering_heading_open_cursor", None)
                    )
                return
            if cursor == getattr(self, "_fingering_heading_open_cursor", ""):
                try:
                    table.configure(cursor="")
                except tk.TclError:
                    pass
                self._fingering_heading_cursor_active = ""
                return
            return

        self._fingering_heading_cursor_active = target
        if (
            cursor == getattr(self, "_fingering_heading_closed_cursor", "")
            and getattr(self, "_fingering_heading_closed_cursor_supported", None) is None
        ):
            self._fingering_heading_closed_cursor_supported = True

    def _update_fingering_heading_cursor(self, x: int | None, y: int | None) -> None:
        if getattr(self, "_fingering_column_drag_source", None):
            self._set_fingering_heading_cursor(
                getattr(self, "_fingering_heading_closed_cursor", None)
            )
            return

        if not getattr(self, "_fingering_edit_mode", False):
            self._set_fingering_heading_cursor(None)
            return

        table = self.fingering_table
        if table is None or x is None or y is None:
            self._set_fingering_heading_cursor(None)
            return

        region = table.identify_region(x, y)
        if region not in {"heading", "separator"}:
            self._set_fingering_heading_cursor(None)
            return

        column_ref = table.identify_column(x)
        column_id = self._column_id_from_ref(table, column_ref)
        if column_id is None or column_id == "note":
            self._set_fingering_heading_cursor(None)
            return
        self._set_fingering_heading_cursor(
            getattr(self, "_fingering_heading_open_cursor", None)
        )

    def _on_fingering_heading_pointer_motion(self, event: tk.Event) -> None:
        self._update_fingering_heading_cursor(
            getattr(event, "x", None), getattr(event, "y", None)
        )

    def _on_fingering_heading_pointer_leave(self, _event: tk.Event | None = None) -> None:
        if getattr(self, "_fingering_column_drag_source", None):
            return
        self._set_fingering_heading_cursor(None)

    def _on_fingering_table_button_press(self, event: tk.Event) -> None:
        if not self._fingering_edit_mode:
            return
        table = self.fingering_table
        if table is None:
            return
        region = table.identify_region(event.x, event.y)
        if region not in {"heading", "separator"}:
            self._set_fingering_heading_cursor(None)
            self._hide_fingering_drop_indicator()
            return
        column_ref = table.identify_column(event.x)
        column_id = self._column_id_from_ref(table, column_ref)
        if column_id is None or column_id == "note":
            self._set_fingering_heading_cursor(None)
            self._hide_fingering_drop_indicator()
            return
        self._fingering_column_drag_source = column_id
        self._set_fingering_drop_hint(None, insert_after=False)

    def _on_fingering_heading_release(self, event: tk.Event) -> None:
        table = self.fingering_table
        if table is None:
            return
        source = self._fingering_column_drag_source
        self._fingering_column_drag_source = None
        if not self._fingering_edit_mode or not source:
            self._hide_fingering_drop_indicator()
            self._set_fingering_drop_hint(None, insert_after=False)
            return

        display_columns = list(self._get_display_columns(table))
        if not display_columns:
            self._hide_fingering_drop_indicator()
            self._set_fingering_drop_hint(None, insert_after=False)
            return

        column_ref = table.identify_column(event.x)
        target_id = self._column_id_from_ref(table, column_ref)
        region = table.identify_region(event.x, event.y)
        after_hint = getattr(self, "_fingering_drop_insert_after", False)
        used_hint = False
        if target_id is None or target_id not in display_columns:
            hint_id = getattr(self, "_fingering_drop_target_id", None)
            if hint_id and hint_id in display_columns:
                target_id = hint_id
                used_hint = True
                region = "heading"
            else:
                self._hide_fingering_drop_indicator()
                self._set_fingering_drop_hint(None, insert_after=False)
                return

        if used_hint:
            after = after_hint
        else:
            after = self._should_insert_after(event.x, target_id, display_columns, table)

        try:
            display_columns.remove(source)
        except ValueError:
            self._update_fingering_heading_cursor(
                getattr(event, "x", None), getattr(event, "y", None)
            )
            return

        if target_id == "note":
            index = 1
        else:
            try:
                index = display_columns.index(target_id)
            except ValueError:
                self._update_fingering_heading_cursor(
                    getattr(event, "x", None), getattr(event, "y", None)
                )
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
                element_index = self._fingering_column_index.get(column)
                if element_index is None:
                    continue
                if element_index < len(viewmodel.state.holes):
                    hole_order.append(element_index)
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
        self._update_fingering_heading_cursor(
            getattr(event, "x", None), getattr(event, "y", None)
        )

        self._hide_fingering_drop_indicator()
        self._set_fingering_drop_hint(None, insert_after=False)

    def _on_fingering_heading_motion(self, event: tk.Event) -> None:
        table = self.fingering_table
        if table is None:
            return
        source = self._fingering_column_drag_source
        if not self._fingering_edit_mode or not source:
            self._hide_fingering_drop_indicator()
            self._set_fingering_drop_hint(None, insert_after=False)
            return

        region = table.identify_region(event.x, event.y)
        if region not in {"heading", "separator"}:
            self._hide_fingering_drop_indicator()
            self._set_fingering_drop_hint(None, insert_after=False)
            return

        display_columns = self._get_display_columns(table)
        if not display_columns:
            self._hide_fingering_drop_indicator()
            self._set_fingering_drop_hint(None, insert_after=False)
            return

        column_ref = table.identify_column(event.x)
        target_id = self._column_id_from_ref(table, column_ref)
        if target_id is None or target_id not in display_columns:
            self._hide_fingering_drop_indicator()
            self._set_fingering_drop_hint(None, insert_after=False)
            return

        after = self._should_insert_after(event.x, target_id, display_columns, table)
        self._set_fingering_drop_hint(target_id, insert_after=after)

        position = self._column_left_edge(display_columns, target_id, table)
        if after:
            position += self._get_column_width(table, target_id)

        self._show_fingering_drop_indicator(position)

    def _on_fingering_table_motion(self, event: tk.Event) -> None:
        table = self.fingering_table
        if table is None:
            return
        if not self._fingering_edit_mode or self._fingering_column_drag_source:
            return
        region = table.identify_region(event.x, event.y)
        if region not in {"heading", "separator"}:
            self._hide_fingering_drop_indicator()
            self._set_fingering_drop_hint(None, insert_after=False)

    def _on_fingering_table_leave(self, _event: tk.Event) -> None:
        self._hide_fingering_drop_indicator()
        self._set_fingering_drop_hint(None, insert_after=False)
