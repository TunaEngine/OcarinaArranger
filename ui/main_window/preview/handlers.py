from __future__ import annotations

import logging
import os
import time
import tkinter as tk
from tkinter import messagebox

logger = logging.getLogger(__name__)


class PreviewInputHandlersMixin:
    """Tkinter callbacks that respond to preview UI input."""

    def _on_input_path_changed(self, *_args: object) -> None:
        if getattr(self, "_suspend_state_sync", False):
            return
        self._preview_auto_rendered = False
        self._pending_preview_data = None
        for side, playback in self._preview_playback.items():
            try:
                playback.stop()
            except Exception:
                logger.debug("Failed to stop preview playback on input change", exc_info=True)
            try:
                playback.reset_adjustments()
            except Exception:
                logger.debug("Failed to reset preview playback state", exc_info=True)
            try:
                self._preview_applied_settings.pop(side, None)
                if hasattr(self, "_preview_settings_seeded"):
                    self._preview_settings_seeded.discard(side)
            except Exception:
                pass
            self._sync_preview_playback_controls(side)
            self._update_playback_visuals(side)
            self._update_preview_apply_cancel_state(side)
        try:
            self._viewmodel.update_preview_settings({})
        except Exception:
            logger.debug("Unable to clear stored preview settings", exc_info=True)
        path = self.input_path.get().strip()
        if hasattr(self, "_update_reimport_button_state"):
            self._update_reimport_button_state()
        if not path or not os.path.exists(path):
            return
        target_tab = self._preview_frame_for_side("arranged")
        self._select_preview_tab("arranged")
        self._auto_render_preview(target_tab)

    def _on_preview_play_toggle(self, side: str) -> None:
        playback = self._preview_playback.get(side)
        if playback is None:
            return
        was_playing = playback.state.is_playing
        playback.toggle_playback()
        if playback.state.is_playing and not was_playing:
            self._playback_last_ts = time.perf_counter()
        elif not playback.state.is_playing and not was_playing:
            error = playback.state.last_error
            if error:
                try:
                    messagebox.showwarning("Audio unavailable", error)
                except tk.TclError:
                    logging.getLogger(__name__).debug("Unable to show audio warning", exc_info=True)
        self._update_playback_visuals(side)

    def _on_preview_stop(self, side: str) -> None:
        playback = self._preview_playback.get(side)
        if playback is None:
            return
        playback.stop()
        self._update_playback_visuals(side)

    def _on_preview_rewind(self, side: str) -> None:
        playback = self._preview_playback.get(side)
        if playback is None:
            return
        playback.stop()
        playback.seek_to(0)
        self._update_playback_visuals(side)

    def _on_preview_fast_forward(self, side: str) -> None:
        playback = self._preview_playback.get(side)
        if playback is None:
            return
        playback.stop()
        target = playback.state.duration_tick
        loop = getattr(playback.state, "loop", None)
        if loop and getattr(loop, "enabled", False):
            target = getattr(loop, "end_tick", target)
        playback.seek_to(target)
        self._update_playback_visuals(side)

    def _on_preview_cursor_seek(self, side: str, tick: int) -> None:
        playback = self._preview_playback.get(side)
        if playback is None:
            return
        self._handle_loop_range_click(side, tick)
        playback.seek_to(tick)
        force_flags = getattr(self, "_force_autoscroll_once", None)
        if isinstance(force_flags, dict):
            force_flags[side] = True
        self._update_playback_visuals(side)

    def _on_preview_tempo_changed(self, side: str, *_args: object) -> None:
        if side in self._suspend_tempo_update:
            return
        var = self._preview_tempo_vars.get(side)
        if var is None:
            return
        try:
            value = float(var.get())
        except (tk.TclError, ValueError):
            self._update_preview_apply_cancel_state(side, valid=False)
            return
        self._update_preview_apply_cancel_state(side, tempo=value)

    def _on_preview_metronome_toggled(self, side: str, *_args: object) -> None:
        if side in self._suspend_metronome_update:
            return
        var = self._preview_metronome_vars.get(side)
        if var is None:
            return
        try:
            enabled = self._coerce_tk_bool(var.get())
        except (tk.TclError, TypeError, ValueError):
            return
        self._update_preview_apply_cancel_state(side, metronome=enabled)

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
