from __future__ import annotations

import os
import tkinter as tk

from shared.ttk import ttk
from typing import Optional


class PreviewLoopControlsMixin:
    """Loop visualization helpers and automatic rendering triggers."""

    def _update_loop_marker_visuals(self, side: str) -> None:
        roll = self._roll_for_side(side)
        staff = self._staff_for_side(side)
        playback = self._preview_playback.get(side)
        if roll is None or playback is None:
            return
        pulses_per_quarter = max(1, playback.state.pulses_per_quarter)
        loop_start_beats = playback.state.loop.start_tick / pulses_per_quarter
        loop_end_beats = playback.state.loop.end_tick / pulses_per_quarter
        invalid = False
        start_var = self._preview_loop_start_vars.get(side)
        if start_var is not None:
            try:
                loop_start_beats = float(start_var.get())
            except (tk.TclError, ValueError):
                invalid = True
        end_var = self._preview_loop_end_vars.get(side)
        if end_var is not None:
            try:
                loop_end_beats = float(end_var.get())
            except (tk.TclError, ValueError):
                invalid = True
        if invalid:
            roll.set_loop_region(0, 0, False)
            if staff and hasattr(staff, "set_loop_region"):
                try:
                    staff.set_loop_region(0, 0, False)
                except TypeError:
                    staff.set_loop_region(0, 0)
            return
        start_tick = int(round(loop_start_beats * pulses_per_quarter))
        end_tick = int(round(loop_end_beats * pulses_per_quarter))
        visible = loop_end_beats > loop_start_beats
        roll.set_loop_region(start_tick, end_tick, visible)
        if staff and hasattr(staff, "set_loop_region"):
            try:
                staff.set_loop_region(start_tick, end_tick, visible)
            except TypeError:
                staff.set_loop_region(start_tick, end_tick)

    def _auto_render_preview(self, tab: Optional[ttk.Frame]) -> None:
        if self._preview_auto_rendered:
            return
        if tab is not None and tab not in self._preview_tab_frames:
            return
        self._sync_viewmodel_settings()
        path = self._viewmodel.state.input_path.strip()
        if not path or not os.path.exists(path):
            return
        self._preview_auto_rendered = True
        previous = getattr(self, "_suppress_preview_error_dialogs", False)
        try:
            self._suppress_preview_error_dialogs = True
            self.render_previews()
        finally:
            self._suppress_preview_error_dialogs = previous

    def _maybe_auto_render_selected_preview(self) -> None:
        if not self._preview_tab_frames:
            return
        notebook = self._notebook
        if notebook is None:
            return
        try:
            current = notebook.nametowidget(notebook.select())
        except Exception:
            return
        self._auto_render_preview(current)
