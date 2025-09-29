from __future__ import annotations

import time
import tkinter as tk
from typing import Optional

from app.config import PlaybackTiming, get_playback_timing
from ocarina_gui.fingering import FingeringView
from ocarina_gui.piano_roll import PianoRoll
from ocarina_gui.staff import StaffView
from viewmodels.preview_playback_viewmodel import PreviewPlaybackViewModel


class PreviewPlaybackControlMixin:
    """Coordinate playback timers and sync widget state for previews."""

    _PLAYBACK_TIMING: PlaybackTiming = get_playback_timing()

    def _schedule_playback_loop(self) -> None:
        if self._headless:
            return
        self._playback_last_ts = time.perf_counter()
        interval = self._next_playback_interval_ms()
        self._playback_job = self.after(interval, self._playback_step)

    def _bind_preview_render_observers(self) -> None:
        for side in ("original", "arranged"):
            self._bind_preview_render_observer(side)

    def _bind_preview_render_observer(self, side: str) -> None:
        playback = self._preview_playback.get(side)
        if playback is None:
            return

        def _notify() -> None:
            self._on_preview_render_state_changed(side)

        playback.set_render_observer(_notify)
        self._on_preview_render_state_changed(side)

    def _cancel_playback_loop(self) -> None:
        job = self._playback_job
        if job is not None:
            try:
                self.after_cancel(job)
            except Exception:
                pass
        self._playback_job = None
        self._playback_last_ts = None

    def _playback_step(self) -> None:
        if self._headless:
            return
        now = time.perf_counter()
        last = self._playback_last_ts or now
        elapsed = max(0.0, now - last)
        self._playback_last_ts = now
        for side in ("original", "arranged"):
            playback = self._preview_playback.get(side)
            if playback is None:
                continue
            playback.advance(elapsed)
            self._update_playback_visuals(side)
        interval = self._next_playback_interval_ms()
        self._playback_job = self.after(interval, self._playback_step)

    def _next_playback_interval_ms(self) -> int:
        if self._headless:
            return self._PLAYBACK_TIMING.idle_interval_ms
        for playback in self._preview_playback.values():
            if playback is None:
                continue
            state = getattr(playback, "state", None)
            if state is not None and getattr(state, "is_playing", False):
                return self._PLAYBACK_TIMING.active_interval_ms
        return self._PLAYBACK_TIMING.idle_interval_ms

    def _update_playback_visuals(self, side: str) -> None:
        playback = self._preview_playback.get(side)
        if playback is None:
            return
        roll = self._roll_for_side(side)
        force_flags = getattr(self, "_force_autoscroll_once", None)
        allow_autoscroll = playback.state.is_playing or (
            force_flags.get(side, False) if isinstance(force_flags, dict) else False
        )
        if roll:
            roll.set_cursor(playback.state.position_tick, allow_autoscroll=allow_autoscroll)
            self._update_loop_marker_visuals(side)
        staff = self._staff_for_side(side)
        if staff and hasattr(staff, "set_cursor"):
            try:
                staff.set_cursor(playback.state.position_tick, allow_autoscroll=allow_autoscroll)
            except TypeError:
                staff.set_cursor(playback.state.position_tick)  # Backwards compatibility
        if isinstance(force_flags, dict):
            force_flags[side] = False
        text_var = self._preview_play_vars.get(side)
        if text_var is not None:
            text_var.set("Pause" if playback.state.is_playing else "Play")
        self._update_preview_render_progress(side)
        controls_enabled = (
            playback.state.is_loaded
            and not playback.state.is_playing
            and not playback.state.is_rendering
        )
        self._set_preview_controls_enabled(side, controls_enabled)
        self._update_preview_fingering(side)

    def _sync_preview_playback_controls(self, side: str) -> None:
        playback = self._preview_playback.get(side)
        if playback is None:
            return
        self._cancel_loop_range_selection(side)
        tempo_var = self._preview_tempo_vars.get(side)
        if tempo_var is not None:
            self._suspend_tempo_update.add(side)
            try:
                tempo_var.set(float(playback.state.tempo_bpm))
            except tk.TclError:
                pass
            finally:
                self._suspend_tempo_update.discard(side)
        met_var = self._preview_metronome_vars.get(side)
        if met_var is not None:
            self._suspend_metronome_update.add(side)
            try:
                met_var.set(bool(playback.state.metronome_enabled))
            except tk.TclError:
                pass
            finally:
                self._suspend_metronome_update.discard(side)
        loop_enabled_var = self._preview_loop_enabled_vars.get(side)
        loop_start_var = self._preview_loop_start_vars.get(side)
        loop_end_var = self._preview_loop_end_vars.get(side)
        start_beats, end_beats = self._loop_bounds_in_beats(playback)
        if (
            loop_enabled_var is not None
            and loop_start_var is not None
            and loop_end_var is not None
        ):
            self._suspend_loop_update.add(side)
            try:
                loop_enabled_var.set(bool(playback.state.loop.enabled))
                loop_start_var.set(start_beats)
                loop_end_var.set(end_beats)
            except tk.TclError:
                pass
            finally:
                self._suspend_loop_update.discard(side)
        applied_snapshot = self._preview_applied_settings.get(side, {})
        tempo_to_apply = playback.state.tempo_bpm
        desired_tempo = applied_snapshot.get("tempo") if isinstance(applied_snapshot, dict) else None
        if desired_tempo is not None:
            tempo_to_apply = float(desired_tempo)
            playback.state.tempo_bpm = tempo_to_apply
        else:
            preview_data = getattr(self, "_pending_preview_data", None)
            if (
                preview_data is not None
                and hasattr(preview_data, "tempo_bpm")
                and abs(float(preview_data.tempo_bpm) - tempo_to_apply) > 1e-6
            ):
                tempo_to_apply = float(preview_data.tempo_bpm)
                playback.state.tempo_bpm = tempo_to_apply
        self._preview_applied_settings[side] = {
            "tempo": tempo_to_apply,
            "metronome": playback.state.metronome_enabled,
            "loop_enabled": playback.state.loop.enabled,
            "loop_start": start_beats,
            "loop_end": end_beats,
        }
        self._update_preview_apply_cancel_state(side)
        self._update_loop_marker_visuals(side)

    def _loop_bounds_in_beats(self, playback: PreviewPlaybackViewModel) -> tuple[float, float]:
        pulses_per_quarter = max(1, playback.state.pulses_per_quarter)
        start = playback.state.loop.start_tick / pulses_per_quarter
        end = playback.state.loop.end_tick / pulses_per_quarter
        return (start, end)

    def _on_preview_render_state_changed(self, side: str) -> None:
        def _refresh() -> None:
            playback = self._preview_playback.get(side)
            if playback is None:
                return
            self._update_preview_render_progress(side)
            controls_enabled = (
                playback.state.is_loaded
                and not playback.state.is_playing
                and not playback.state.is_rendering
            )
            self._set_preview_controls_enabled(side, controls_enabled)

        if self._headless:
            _refresh()
            return
        try:
            self.after_idle(_refresh)
        except Exception:
            _refresh()

    def _roll_for_side(self, side: str) -> Optional[PianoRoll]:
        if side == "original":
            return self.roll_orig
        if side == "arranged":
            return self.roll_arr
        return None

    def _staff_for_side(self, side: str) -> Optional[StaffView]:
        if side == "original":
            return self.staff_orig
        if side == "arranged":
            return self.staff_arr
        return None

    def _side_fingering_for_side(self, side: str) -> Optional[FingeringView]:
        if side == "original":
            return self.side_fing_orig
        if side == "arranged":
            return self.side_fing_arr
        return None
