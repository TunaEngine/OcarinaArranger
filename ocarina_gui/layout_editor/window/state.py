"""State refresh helpers for the layout editor window."""

from __future__ import annotations

import json
import tkinter as tk

from ocarina_gui.fingering.half_holes import instrument_allows_half_holes
from viewmodels.instrument_layout_editor_viewmodel import InstrumentLayoutState, SelectionKind


class _LayoutEditorStateMixin:
    """Shared behaviour for synchronising the UI with the view model."""

    canvas: object

    def _refresh_all(self) -> None:
        self._populate_instrument_choices()
        self._update_instrument_controls()
        self._refresh_state()

    def _populate_instrument_choices(self) -> None:
        choices = self._viewmodel.choices()
        self._instrument_name_to_id = {name: identifier for identifier, name in choices}
        names = [name for _, name in choices]
        self._instrument_selector.configure(values=names)
        state = self._viewmodel.state
        self.instrument_var.set(state.name)

    def _update_instrument_controls(self) -> None:
        button = self._remove_button
        if button is None:
            return
        if len(self._viewmodel.choices()) <= 1:
            button.state(["disabled"])
        else:
            button.state(["!disabled"])

    def _refresh_state(self) -> None:
        state = self._viewmodel.state
        previous_instrument = getattr(self, "_last_instrument_id", None)
        self._updating = True
        try:
            self._instrument_id_var.set(state.instrument_id)
            self._instrument_name_var.set(state.name)
            self._title_var.set(state.title)
            self._canvas_width_var.set(state.canvas_width)
            self._canvas_height_var.set(state.canvas_height)
            self.instrument_var.set(state.name)
            note_choices = self._viewmodel.candidate_note_names()
            if self._candidate_min_combo is not None:
                self._candidate_min_combo.configure(values=note_choices)
            if self._candidate_max_combo is not None:
                self._candidate_max_combo.configure(values=note_choices)
            if self._preferred_min_combo is not None:
                self._preferred_min_combo.configure(values=note_choices)
            if self._preferred_max_combo is not None:
                self._preferred_max_combo.configure(values=note_choices)
            self._candidate_min_var.set(state.candidate_range_min)
            self._candidate_max_var.set(state.candidate_range_max)
            self._preferred_min_var.set(state.preferred_range_min)
            self._preferred_max_var.set(state.preferred_range_max)
            if state.selection is None:
                self._selection_x_var.set(0.0)
                self._selection_y_var.set(0.0)
                self._selection_radius_var.set(0.0)
                self._selection_width_var.set(0.0)
                self._selection_height_var.set(0.0)
                self._selection_info_var.set("No element selected")
                self._hole_identifier_var.set("")
            else:
                self._update_selection_vars(state)
        finally:
            self._updating = False

        self.canvas.render(state)
        self._update_dirty_indicator()
        self._refresh_json_preview()
        self._update_size_entry_state()
        self._update_element_controls()

        self._update_half_hole_var(state.instrument_id)
        if previous_instrument != state.instrument_id:
            self._remember_last_instrument(state.instrument_id)
            self._last_instrument_id = state.instrument_id

    def _update_selection_vars(self, state: InstrumentLayoutState) -> None:
        selection = state.selection
        if selection is None:
            return
        if selection.kind == SelectionKind.HOLE:
            hole = state.holes[selection.index]
            self._selection_x_var.set(hole.x)
            self._selection_y_var.set(hole.y)
            self._selection_radius_var.set(hole.radius)
            self._selection_width_var.set(0.0)
            self._selection_height_var.set(0.0)
            self._hole_identifier_var.set(hole.identifier)
        elif selection.kind == SelectionKind.WINDWAY:
            windway = state.windways[selection.index]
            self._selection_x_var.set(windway.x)
            self._selection_y_var.set(windway.y)
            self._selection_radius_var.set(0.0)
            self._selection_width_var.set(windway.width)
            self._selection_height_var.set(windway.height)
            self._hole_identifier_var.set(windway.identifier)
        elif selection.kind == SelectionKind.OUTLINE:
            point = state.outline_points[selection.index]
            self._selection_x_var.set(point.x)
            self._selection_y_var.set(point.y)
            self._selection_radius_var.set(0.0)
            self._selection_width_var.set(0.0)
            self._selection_height_var.set(0.0)
            self._hole_identifier_var.set("")
        self._selection_info_var.set(self._describe_selection(state))

    def _update_size_entry_state(self) -> None:
        state = self._viewmodel.state
        selection = state.selection
        radius_state = "disabled"
        width_state = "disabled"
        height_state = "disabled"
        if selection is not None:
            if selection.kind == SelectionKind.HOLE:
                radius_state = "normal"
            elif selection.kind == SelectionKind.WINDWAY:
                width_state = "normal"
                height_state = "normal"

        self._radius_entry.configure(state=radius_state)
        if self._width_entry is not None:
            self._width_entry.configure(state=width_state)
        if self._height_entry is not None:
            self._height_entry.configure(state=height_state)

    def _update_element_controls(self) -> None:
        state = self._viewmodel.state
        entry = self._hole_entry
        remove_button = self._remove_element_button
        add_button = self._add_hole_button
        add_windway = self._add_windway_button
        if add_button is not None:
            add_button.state(["!disabled"])
        if add_windway is not None:
            add_windway.state(["!disabled"])

        selection = state.selection
        if selection is not None and selection.kind in (SelectionKind.HOLE, SelectionKind.WINDWAY):
            if entry is not None:
                entry.configure(state="normal")
            if remove_button is not None:
                remove_button.state(["!disabled"])
        else:
            if entry is not None:
                entry.configure(state="disabled")
            if remove_button is not None:
                remove_button.state(["disabled"])
            if selection is None or selection.kind not in (
                SelectionKind.HOLE,
                SelectionKind.WINDWAY,
            ):
                self._hole_identifier_var.set("")

    def _update_half_hole_var(self, instrument_id: str) -> None:
        var = getattr(self, "_allow_half_var", None)
        if var is None:
            return

        expected = instrument_allows_half_holes(instrument_id)
        viewmodel = getattr(self, "_viewmodel", None)
        if viewmodel is not None:
            try:
                expected = bool(getattr(viewmodel.state, "allow_half_holes", expected))
            except Exception:
                pass
        try:
            current = bool(var.get())
        except Exception:
            current = False

        if current == expected:
            return

        try:
            var.set(expected)
        except Exception:
            pass

    @staticmethod
    def _format_number(value: float) -> str:
        text = f"{value:.2f}".rstrip("0").rstrip(".")
        return text or "0"

    def _update_dirty_indicator(self) -> None:
        if self._viewmodel.is_dirty():
            self._status_var.set("Unsaved changes")
        elif self._status_var.get() == "Unsaved changes":
            self._status_var.set("")

    def _refresh_json_preview(self) -> None:
        config = self._viewmodel.build_config()
        text = json.dumps(config, indent=2)
        widget = self._json_text
        if widget is None:
            return
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _describe_selection(self, state: InstrumentLayoutState) -> str:
        selection = state.selection
        if selection is None:
            return "No element selected"

        fmt = self._format_number
        if selection.kind == SelectionKind.HOLE:
            hole = state.holes[selection.index]
            label = getattr(hole, "identifier", "") or f"Hole #{selection.index + 1}"
            return (
                f"{label} (x={fmt(hole.x)}, y={fmt(hole.y)}, radius={fmt(hole.radius)})"
            )
        if selection.kind == SelectionKind.WINDWAY:
            windway = state.windways[selection.index]
            label = getattr(windway, "identifier", "") or f"Windway #{selection.index + 1}"
            return (
                f"{label} (x={fmt(windway.x)}, y={fmt(windway.y)}, "
                f"width={fmt(windway.width)}, height={fmt(windway.height)})"
            )
        if selection.kind == SelectionKind.OUTLINE:
            point = state.outline_points[selection.index]
            return f"Outline point #{selection.index + 1} (x={fmt(point.x)}, y={fmt(point.y)})"
        return "No element selected"
