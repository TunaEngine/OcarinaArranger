from __future__ import annotations

import tkinter as tk

from shared.ttk import ttk
from typing import Callable, Dict


class PreviewWidgetRegistrationMixin:
    """Register preview widgets and reset their initial state."""

    def _register_transpose_spinbox(
        self,
        spinbox: ttk.Spinbox,
        *,
        apply_button: object | None = None,
        cancel_button: object | None = None,
    ) -> None:
        self._transpose_spinboxes.append(spinbox)
        if apply_button is not None and cancel_button is not None:
            self._transpose_apply_button = apply_button
            self._transpose_cancel_button = cancel_button
            for widget in (apply_button, cancel_button):
                try:
                    widget.state(["disabled"])
                except Exception:
                    continue
        self._update_transpose_apply_cancel_state()

    def _register_preview_control_buttons(
        self,
        side: str,
        apply_button: ttk.Button,
        cancel_button: ttk.Button,
        *,
        additional: bool = False,
    ) -> None:
        if additional:
            self._preview_linked_apply_buttons.setdefault(side, []).append(apply_button)
            self._preview_linked_cancel_buttons.setdefault(side, []).append(cancel_button)
            if side not in self._preview_apply_buttons:
                self._preview_apply_buttons[side] = apply_button
                self._preview_cancel_buttons[side] = cancel_button
        else:
            self._preview_apply_buttons[side] = apply_button
            self._preview_cancel_buttons[side] = cancel_button
            self._preview_linked_apply_buttons[side] = [apply_button]
            self._preview_linked_cancel_buttons[side] = [cancel_button]
        for button in (apply_button, cancel_button):
            try:
                button.state(["disabled"])
            except tk.TclError:
                continue
        self._update_preview_apply_cancel_state(side)

    def _register_preview_adjust_widgets(
        self, side: str, tempo_widget: object, metronome_widget: object
    ) -> None:
        self._preview_tempo_controls[side] = tempo_widget
        self._preview_metronome_controls[side] = metronome_widget
        self._set_preview_controls_enabled(side, False)

    def _register_preview_loop_widgets(self, side: str, *widgets: object) -> None:
        filtered = tuple(widget for widget in widgets if widget is not None)
        self._preview_loop_controls[side] = filtered
        self._set_preview_controls_enabled(side, False)

    def _register_preview_loop_range_button(self, side: str, button: object) -> None:
        self._preview_loop_range_buttons[side] = button

    def _register_preview_progress_frame(
        self, side: str, frame: tk.Widget, *, place: Dict[str, float] | None = None
    ) -> None:
        self._preview_progress_frames[side] = frame
        if place is not None:
            self._preview_progress_places[side] = place
        try:
            manager = frame.winfo_manager()
        except tk.TclError:
            manager = ""
        if manager == "place":
            try:
                frame.place_forget()
            except tk.TclError:
                pass
        elif manager:
            try:
                frame.pack_forget()
            except tk.TclError:
                pass

    def _register_preview_tab_initializer(
        self, side: str, builder: Callable[[], None]
    ) -> None:
        self._preview_tab_builders[side] = builder
