from __future__ import annotations

import tkinter as tk


class PreviewLoopHandlersMixin:
    def _on_preview_loop_enabled(self, side: str, *_args: object) -> None:
        if side in self._suspend_loop_update:
            return
        var = self._preview_loop_enabled_vars.get(side)
        if var is None:
            return
        try:
            enabled = self._coerce_tk_bool(var.get())
        except (tk.TclError, TypeError, ValueError):
            return
        self._update_preview_apply_cancel_state(side, loop_enabled=enabled)
        self._update_loop_marker_visuals(side)

    def _on_preview_loop_start_changed(self, side: str, *_args: object) -> None:
        if side in self._suspend_loop_update:
            return
        var = self._preview_loop_start_vars.get(side)
        if var is None:
            return
        try:
            value = float(var.get())
        except (tk.TclError, ValueError):
            self._update_preview_apply_cancel_state(side, valid=False)
            return
        self._update_preview_apply_cancel_state(side, loop_start=value)
        self._update_loop_marker_visuals(side)

    def _on_preview_loop_end_changed(self, side: str, *_args: object) -> None:
        if side in self._suspend_loop_update:
            return
        var = self._preview_loop_end_vars.get(side)
        if var is None:
            return
        try:
            value = float(var.get())
        except (tk.TclError, ValueError):
            self._update_preview_apply_cancel_state(side, valid=False)
            return
        self._update_preview_apply_cancel_state(side, loop_end=value)
        self._update_loop_marker_visuals(side)

    def _begin_loop_range_selection(self, side: str) -> None:
        playback = self._preview_playback.get(side)
        if playback is None or not playback.state.is_loaded:
            self._cancel_loop_range_selection(side)
            return
        self._loop_range_active.add(side)
        self._loop_range_first_tick[side] = None

    def _cancel_loop_range_selection(self, side: str) -> None:
        self._loop_range_active.discard(side)
        self._loop_range_first_tick[side] = None

    def _handle_loop_range_click(self, side: str, tick: int) -> None:
        if side not in self._loop_range_active:
            return
        playback = self._preview_playback.get(side)
        loop_start_var = self._preview_loop_start_vars.get(side)
        loop_end_var = self._preview_loop_end_vars.get(side)
        if playback is None or loop_start_var is None or loop_end_var is None:
            self._cancel_loop_range_selection(side)
            return
        pulses_per_quarter = max(1, playback.state.pulses_per_quarter)
        first_tick = self._loop_range_first_tick.get(side)
        if first_tick is None:
            try:
                loop_start_var.set(tick / pulses_per_quarter)
            except tk.TclError:
                pass
            self._loop_range_first_tick[side] = tick
            self._update_loop_marker_visuals(side)
            return
        start_tick = min(first_tick, tick)
        end_tick = max(first_tick, tick)
        try:
            loop_start_var.set(start_tick / pulses_per_quarter)
            loop_end_var.set(end_tick / pulses_per_quarter)
        except tk.TclError:
            pass
        loop_enabled_var = self._preview_loop_enabled_vars.get(side)
        if loop_enabled_var is not None:
            try:
                loop_enabled_var.set(True)
            except tk.TclError:
                pass
        self._cancel_loop_range_selection(side)
        self._update_loop_marker_visuals(side)
