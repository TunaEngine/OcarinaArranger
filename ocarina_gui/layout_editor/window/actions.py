"""User interaction handlers for the layout editor window."""

from __future__ import annotations

from typing import Optional

import tkinter as tk
from tkinter import messagebox, simpledialog

from viewmodels.instrument_layout_editor_viewmodel import SelectionKind

from ..labels import friendly_label


class _LayoutEditorActionsMixin:
    """Methods handling direct user interactions with the editor."""

    def _on_instrument_change(self, _event: tk.Event) -> None:
        if self._updating:
            return
        selection = self.instrument_var.get()
        instrument_id = self._instrument_name_to_id.get(selection)
        if not instrument_id:
            return
        self._viewmodel.select_instrument(instrument_id)
        self._refresh_state()

    def _apply_instrument_identifier(self) -> None:
        if self._updating:
            return
        new_identifier = self._instrument_id_var.get()
        if new_identifier == self._viewmodel.state.instrument_id:
            return
        try:
            self._viewmodel.update_instrument_metadata(instrument_id=new_identifier)
        except ValueError as exc:
            messagebox.showerror("Invalid identifier", str(exc), parent=self)
            self._instrument_id_var.set(self._viewmodel.state.instrument_id)
            return
        self._refresh_all()

    def _apply_instrument_name(self) -> None:
        if self._updating:
            return
        new_name = self._instrument_name_var.get()
        if new_name == self._viewmodel.state.name:
            return
        try:
            self._viewmodel.update_instrument_metadata(name=new_name)
        except ValueError as exc:
            messagebox.showerror("Invalid name", str(exc), parent=self)
            self._instrument_name_var.set(self._viewmodel.state.name)
            return
        self._refresh_all()

    def _add_instrument(self) -> None:
        identifier = simpledialog.askstring(
            "Add instrument",
            "Enter a unique instrument identifier:",
            parent=self,
        )
        if not identifier:
            return
        name = simpledialog.askstring(
            "Add instrument",
            "Enter a display name:",
            initialvalue=identifier,
            parent=self,
        )
        if name is None:
            return
        try:
            self._viewmodel.add_instrument(identifier, name)
        except ValueError as exc:
            messagebox.showerror("Add instrument", str(exc), parent=self)
            return
        self._refresh_all()
        self._status_var.set(f"Added instrument '{self._viewmodel.state.name}'")

    def _remove_instrument(self) -> None:
        if len(self._viewmodel.choices()) <= 1:
            messagebox.showerror(
                "Remove instrument",
                "At least one instrument must remain.",
                parent=self,
            )
            return
        state = self._viewmodel.state
        removed_name = state.name
        if not messagebox.askyesno(
            "Remove instrument",
            f"Remove instrument '{removed_name}'?",
            parent=self,
        ):
            return
        try:
            self._viewmodel.remove_current_instrument()
        except ValueError as exc:
            messagebox.showerror("Remove instrument", str(exc), parent=self)
            return
        self._refresh_all()
        self._status_var.set(f"Removed instrument '{removed_name}'")

    def _apply_title(self) -> None:
        if self._updating:
            return
        self._viewmodel.set_title(self._title_var.get())
        self._refresh_state()

    def _apply_canvas_size(self) -> None:
        if self._updating:
            return
        try:
            width = self._canvas_width_var.get()
            height = self._canvas_height_var.get()
        except tk.TclError:
            return
        self._viewmodel.set_canvas_size(width, height)
        self._refresh_state()

    def _apply_preferred_range(self) -> None:
        if self._updating:
            return
        minimum = self._preferred_min_var.get()
        maximum = self._preferred_max_var.get()
        try:
            self._viewmodel.set_preferred_range(minimum, maximum)
        except ValueError as exc:
            messagebox.showerror("Preferred range", str(exc), parent=self)
            self._refresh_state()
            return
        self._refresh_state()

    def _apply_candidate_range(self) -> None:
        if self._updating:
            return
        minimum = self._candidate_min_var.get()
        maximum = self._candidate_max_var.get()
        if not minimum or not maximum:
            # Allow users to tab between fields without triggering validation
            # errors while they type in the remaining endpoint.
            return
        try:
            self._viewmodel.set_candidate_range(minimum, maximum)
        except ValueError as exc:
            messagebox.showerror("Available range", str(exc), parent=self)
            self._refresh_state()
            return
        self._refresh_state()

    def _apply_selection_position(self) -> None:
        if self._updating:
            return
        selection = self._viewmodel.state.selection
        if selection is None:
            return
        try:
            x_value = self._selection_x_var.get()
            y_value = self._selection_y_var.get()
        except tk.TclError:
            return
        self._viewmodel.set_selected_position(x_value, y_value)
        self._refresh_state()

    def _apply_selection_radius(self) -> None:
        if self._updating:
            return
        selection = self._viewmodel.state.selection
        if selection is None or selection.kind == SelectionKind.OUTLINE:
            return
        try:
            current = self._selection_radius_var.get()
        except tk.TclError:
            return
        state = self._viewmodel.state
        if selection.kind != SelectionKind.HOLE:
            return
        radius = state.holes[selection.index].radius
        self._viewmodel.adjust_selected_radius(current - radius)
        self._refresh_state()

    def _apply_hole_identifier(self) -> None:
        if self._updating:
            return
        selection = self._viewmodel.state.selection
        if selection is None or selection.kind != SelectionKind.HOLE:
            return
        new_identifier = self._hole_identifier_var.get()
        try:
            self._viewmodel.update_hole_identifier(selection.index, new_identifier)
        except (ValueError, IndexError) as exc:
            messagebox.showerror("Invalid hole description", str(exc), parent=self)
            state = self._viewmodel.state
            hole = state.holes[selection.index]
            self._hole_identifier_var.set(hole.identifier)
            return
        self._refresh_state()

    def _apply_style_field(self, key: str, value: str) -> None:
        if self._updating:
            return
        self._viewmodel.update_style(**{key: value})
        self._refresh_state()

    def _nudge_selection(self, dx: float, dy: float) -> None:
        if self._viewmodel.state.selection is None:
            return
        try:
            x = self._selection_x_var.get() + dx
            y = self._selection_y_var.get() + dy
        except tk.TclError:
            return
        self._viewmodel.set_selected_position(x, y)
        self._refresh_state()

    def _add_hole(self) -> None:
        new_hole = self._viewmodel.add_hole()
        self._refresh_state()
        label = friendly_label(new_hole.identifier, "Hole")
        self._status_var.set(f"Added hole '{label}'")

    def _remove_selected_hole(self) -> None:
        selection = self._viewmodel.state.selection
        if selection is None or selection.kind != SelectionKind.HOLE:
            messagebox.showinfo("Remove hole", "Select a hole to remove first.", parent=self)
            return
        state = self._viewmodel.state
        hole = state.holes[selection.index]
        try:
            self._viewmodel.remove_hole(selection.index)
        except IndexError as exc:
            messagebox.showerror("Remove hole", str(exc), parent=self)
            return
        self._refresh_state()
        label = friendly_label(hole.identifier, "Hole")
        self._status_var.set(f"Removed hole '{label}'")

    def _on_canvas_select(self, kind: SelectionKind, index: Optional[int]) -> None:
        self._viewmodel.select_element(kind, index)
        self._refresh_state()

    def _on_canvas_move(self, kind: SelectionKind, index: int, x: float, y: float) -> None:
        selection = self._viewmodel.state.selection
        if selection is None or selection.kind != kind or selection.index != index:
            self._viewmodel.select_element(kind, index)
        self._viewmodel.set_selected_position(x, y)
        self.canvas.render(self._viewmodel.state)
        self._update_selection_vars(self._viewmodel.state)
        self._update_dirty_indicator()
        self._refresh_json_preview()
