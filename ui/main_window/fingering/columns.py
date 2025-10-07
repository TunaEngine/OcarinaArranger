from __future__ import annotations

import tkinter as tk
from shared.ttk import ttk
from typing import List, Sequence


class FingeringColumnLayoutMixin:
    """Helpers for reordering and persisting fingering table columns."""

    def _display_column_index(self, table: ttk.Treeview, column_id: str) -> int:
        display = self._get_display_columns(table)
        try:
            return display.index(column_id)
        except ValueError:
            return -1

    def _column_id_from_ref(self, table: ttk.Treeview, column_ref: str | None) -> str | None:
        if not column_ref or column_ref == "#0":
            return None
        try:
            index = int(str(column_ref).lstrip("#")) - 1
        except ValueError:
            return None
        display = self._get_display_columns(table)
        if index < 0 or index >= len(display):
            return None
        return display[index]

    def _get_display_columns(self, table: ttk.Treeview) -> tuple[str, ...]:
        if self._fingering_display_columns:
            return self._fingering_display_columns
        columns = table["displaycolumns"]
        if isinstance(columns, str):
            if columns in {"", "#all"}:
                raw_columns = table["columns"]
                if isinstance(raw_columns, str):
                    return (raw_columns,)
                return tuple(raw_columns)
            return (columns,)
        return tuple(columns)

    def _apply_fingering_display_columns(self, columns: Sequence[str]) -> None:
        table = self.fingering_table
        if table is None:
            return

        normalized: List[str] = []
        seen: set[str] = set()
        for column_id in columns:
            if column_id not in seen:
                normalized.append(column_id)
                seen.add(column_id)
        if "note" not in seen:
            normalized.insert(0, "note")
            seen.add("note")

        base_columns = table["columns"]
        if isinstance(base_columns, str):
            base_list = [base_columns]
        else:
            base_list = list(base_columns)
        for column_id in base_list:
            if column_id not in seen:
                normalized.append(column_id)
                seen.add(column_id)

        table.configure(displaycolumns=normalized)
        self._fingering_display_columns = tuple(normalized)
        if self._fingering_edit_mode:
            self._fingering_display_columns_override = [
                column_id for column_id in normalized if column_id != "note"
            ]

    def _should_insert_after(
        self,
        event_x: int,
        target_id: str,
        display_columns: Sequence[str],
        table: ttk.Treeview,
    ) -> bool:
        if target_id == "note":
            return True
        width = self._get_column_width(table, target_id)
        if width <= 0:
            return False
        left = self._column_left_edge(display_columns, target_id, table)
        return event_x >= left + width / 2

    def _get_column_width(self, table: ttk.Treeview, column_id: str) -> int:
        try:
            raw = table.column(column_id, "width")
        except tk.TclError:
            return 0
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            return 0

    def _column_left_edge(
        self,
        display_columns: Sequence[str],
        target_id: str,
        table: ttk.Treeview,
    ) -> int:
        total = 0
        for column_id in display_columns:
            if column_id == target_id:
                break
            total += self._get_column_width(table, column_id)
        return total
