from __future__ import annotations

import logging
import textwrap
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from typing import Dict, List, Optional, Sequence

from ocarina_gui.fingering import (
    collect_instrument_note_names,
    get_current_instrument,
)

logger = logging.getLogger(__name__)


class FingeringTableMixin:
    """Population and selection handling for the fingering table."""

    def _on_fingering_table_select(self, _event: Optional[tk.Event] = None) -> None:
        table = self.fingering_table
        if not table:
            return

        selection = table.selection()
        if not selection:
            if self._fingering_ignore_next_select:
                logger.debug(
                    "Skipping fingering clear during programmatic update",
                    extra={
                        "ignore_next_select": True,
                        "last_selected": self._fingering_last_selected_note,
                    },
                )
                return

            if self.fingering_preview:
                self.fingering_preview.clear()
            self._fingering_ignore_next_select = False
            self._fingering_last_selected_note = None
            self._fingering_click_guard_note = None
            logger.debug(
                "Fingering selection cleared",
                extra={
                    "click_guard_note": None,
                    "ignore_next_select": False,
                },
            )
            self._update_fingering_note_actions_state()
            return

        note_name = selection[0]
        if note_name == "_empty":
            if self.fingering_preview:
                self.fingering_preview.clear()
            self._fingering_ignore_next_select = False
            self._fingering_last_selected_note = None
            self._fingering_click_guard_note = None
            logger.debug("Fingering placeholder row selected")
            self._update_fingering_note_actions_state()
            return

        try:
            table.see(note_name)
        except tk.TclError:
            return

        previous_selection = self._fingering_last_selected_note
        self._fingering_last_selected_note = note_name

        if self._fingering_ignore_next_select:
            self._fingering_ignore_next_select = False
            self._fingering_click_guard_note = None
            logger.debug(
                "Ignoring select triggered by programmatic focus",
                extra={
                    "note": note_name,
                    "previous_selection": previous_selection,
                },
            )
        else:
            if previous_selection != note_name:
                self._fingering_click_guard_note = note_name
            else:
                self._fingering_click_guard_note = None
            logger.debug(
                "Fingering selection updated",
                extra={
                    "note": note_name,
                    "previous_selection": previous_selection,
                    "click_guard_note": self._fingering_click_guard_note,
                },
            )

        if self.fingering_preview:
            try:
                instrument = get_current_instrument()
            except Exception:
                self.fingering_preview.clear()
            else:
                mapping = instrument.note_map.get(note_name)
                if mapping is None:
                    self.fingering_preview.clear()
                else:
                    midi = self._fingering_note_to_midi.get(note_name)
                    self.fingering_preview.show_fingering(note_name, midi)
        self._update_fingering_note_actions_state()

    def _wrap_table_heading(self, heading: str, *, width: int = 10) -> str:
        if "\n" in heading:
            return heading
        lines = textwrap.wrap(heading, width=width)
        if not lines:
            return heading
        return "\n".join(lines)

    def _symbol_for_fingering_state(self, value: int) -> str:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return "○"
        if number >= 2:
            return "●"
        if number == 1:
            if not self._half_notes_enabled():
                return "●"
            return "◐"
        return "○"

    def _populate_fingering_table(self, focus_note: Optional[str] = None) -> None:
        table = self.fingering_table
        if table is None:
            return

        instrument = get_current_instrument()
        holes = list(instrument.holes)
        windways = list(instrument.windways)

        raw_note_names = collect_instrument_note_names(instrument)
        note_names: List[str] = []
        seen: set[str] = set()

        for name in instrument.note_order:
            if name in instrument.note_map and name not in seen:
                note_names.append(name)
                seen.add(name)

        for name in raw_note_names:
            if name in instrument.note_map and name not in seen:
                note_names.append(name)
                seen.add(name)

        for name in instrument.note_map.keys():
            if name not in seen:
                note_names.append(name)
                seen.add(name)

        columns: List[str] = ["note"]
        headings: Dict[str, str] = {"note": "Note"}
        seen: set[str] = set(columns)
        for index, hole in enumerate(holes):
            base_id = hole.identifier or f"hole_{index + 1}"
            column_id = base_id
            suffix = 1
            while column_id in seen:
                suffix += 1
                column_id = f"{base_id}_{suffix}"
            seen.add(column_id)
            columns.append(column_id)
            if hole.identifier:
                heading = hole.identifier.replace("_", " ").title()
            else:
                heading = f"Hole {index + 1}"
            headings[column_id] = heading

        for index, windway in enumerate(windways):
            base = windway.identifier or f"windway_{index + 1}"
            column_id = base
            suffix = 1
            while column_id in seen:
                suffix += 1
                column_id = f"{base}_{suffix}"
            seen.add(column_id)
            columns.append(column_id)
            if windway.identifier:
                heading = windway.identifier.replace("_", " ").title()
            else:
                heading = f"Windway {index + 1}"
            headings[column_id] = heading

        wrapped_headings = {column_id: self._wrap_table_heading(text) for column_id, text in headings.items()}

        display_columns: List[str]
        if self._fingering_edit_mode:
            if self._fingering_display_columns_override is None:
                self._fingering_display_columns_override = list(columns[1:])
            display_columns = ["note"]
            seen_display: set[str] = set(display_columns)
            for column_id in self._fingering_display_columns_override:
                if column_id in seen_display or column_id not in columns:
                    continue
                display_columns.append(column_id)
                seen_display.add(column_id)
            for column_id in columns[1:]:
                if column_id not in seen_display:
                    display_columns.append(column_id)
                    seen_display.add(column_id)
        else:
            display_columns = list(columns)
            self._fingering_display_columns_override = None

        table.configure(columns=columns, displaycolumns=display_columns)
        self._fingering_display_columns = tuple(display_columns)
        self._fingering_column_index = {
            column_id: index for index, column_id in enumerate(columns[1:])
        }

        try:
            heading_font = tkfont.nametofont("TkHeadingFont")
        except tk.TclError:
            heading_font = tkfont.nametofont("TkDefaultFont")

        try:
            body_font_name = str(table.cget("font"))
        except tk.TclError:
            body_font_name = ""

        if not body_font_name:
            style = self._style or ttk.Style(table)
            body_font_name = style.lookup("Treeview", "font") or ""

        if not body_font_name:
            body_font_name = "TkDefaultFont"

        try:
            body_font = tkfont.nametofont(body_font_name)
        except tk.TclError:
            try:
                body_font = tkfont.Font(font=body_font_name)
            except Exception:
                body_font = tkfont.nametofont("TkDefaultFont")

        heading_line_counts: Dict[str, int] = {
            column_id: max(len([line for line in text.split("\n") if line]), 1)
            for column_id, text in wrapped_headings.items()
        }

        self._update_fingering_heading_padding(
            max(heading_line_counts.values(), default=1), heading_font
        )

        column_widths: Dict[str, int] = {}
        for column_id in columns:
            text = wrapped_headings[column_id]
            lines = [line for line in text.split("\n") if line]
            if not lines:
                heading_width = heading_font.measure("")
            else:
                heading_width = max(heading_font.measure(line) for line in lines)
            column_widths[column_id] = heading_width

        placeholder_text = "No note mappings configured"
        display_notes: Sequence[str] = note_names if note_names else (placeholder_text,)
        if display_notes:
            widest_note = max(body_font.measure(note) for note in display_notes)
            column_widths["note"] = max(column_widths["note"], widest_note)

        symbol_width = max(body_font.measure(symbol) for symbol in ("●", "◐", "○", "–"))
        for column_id in columns[1:]:
            column_widths[column_id] = max(column_widths[column_id], symbol_width)

        padding = 16
        for column_id in columns:
            width = column_widths[column_id] + padding
            anchor = "w" if column_id == "note" else "center"
            table.heading(column_id, text=wrapped_headings[column_id], anchor="center")
            table.column(column_id, anchor=anchor, width=width, minwidth=width, stretch="0")

        for row in table.get_children():
            table.delete(row)

        self._fingering_note_to_midi.clear()

        if not note_names:
            placeholder = (placeholder_text,) + ("",) * (len(columns) - 1)
            table.insert("", "end", iid="_empty", values=placeholder, tags=("even",))
            if self.fingering_preview:
                self.fingering_preview.clear()
            if self.fingering_grid:
                self.fingering_grid.set_notes(())
            return

        for row_index, note_name in enumerate(note_names):
            midi: Optional[int]
            try:
                midi = self._parse_note_safe(note_name)
            except Exception:
                midi = None

            mapping = instrument.note_map.get(note_name)

            total_elements = len(holes) + len(windways)
            if mapping is None:
                hole_display = ["–"] * len(holes)
                windway_display = ["–"] * len(windways)
            else:
                sequence = list(mapping)
                if len(sequence) < total_elements:
                    sequence.extend([0] * (total_elements - len(sequence)))
                elif len(sequence) > total_elements:
                    sequence = sequence[:total_elements]
                hole_display = [
                    self._symbol_for_fingering_state(value)
                    for value in sequence[: len(holes)]
                ]
                windway_display = [
                    self._symbol_for_fingering_state(value)
                    for value in sequence[len(holes) : len(holes) + len(windways)]
                ]

            values = [note_name] + hole_display + windway_display
            tags = ("even",) if row_index % 2 == 0 else ("odd",)
            table.insert("", "end", iid=note_name, values=values, tags=tags)
            self._fingering_note_to_midi[note_name] = midi

        if self.fingering_grid:
            self.fingering_grid.set_notes(note_names, self._fingering_note_to_midi)

        selected: Optional[str] = None
        if focus_note and table.exists(focus_note):
            selected = focus_note
        else:
            children = table.get_children()
            if children:
                selected = children[0]

        if selected:
            self._fingering_ignore_next_select = True
            table.selection_set(selected)
            table.focus(selected)
            self._on_fingering_table_select()
        elif self.fingering_preview:
            self.fingering_preview.clear()
