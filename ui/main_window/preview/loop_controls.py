from __future__ import annotations

import os
import tkinter as tk

from shared.tempo import align_duration_to_measure
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
        track_end_tick = playback.state.track_end_tick
        if track_end_tick <= 0:
            track_end_tick = align_duration_to_measure(
                playback.state.duration_tick,
                playback.state.pulses_per_quarter,
                playback.state.beats_per_measure,
                playback.state.beat_unit,
            )
        duration_beats = track_end_tick / pulses_per_quarter

        loop_state = playback.state.loop
        loop_state_enabled = bool(
            loop_state.enabled and loop_state.end_tick > loop_state.start_tick
        )
        default_start_beats = (
            loop_state.start_tick / pulses_per_quarter if loop_state_enabled else 0.0
        )
        default_end_beats = (
            loop_state.end_tick / pulses_per_quarter
            if loop_state_enabled
            else duration_beats
        )

        loop_enabled_var = self._preview_loop_enabled_vars.get(side)
        if loop_enabled_var is not None:
            try:
                loop_enabled = self._coerce_tk_bool(
                    loop_enabled_var.get(), default=loop_state_enabled
                )
            except (tk.TclError, TypeError, ValueError):
                loop_enabled = loop_state_enabled
        else:
            loop_enabled = loop_state_enabled

        loop_start_beats = default_start_beats
        loop_end_beats = default_end_beats
        invalid = False
        if loop_enabled:
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
        visible = loop_enabled and loop_end_beats > loop_start_beats
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
