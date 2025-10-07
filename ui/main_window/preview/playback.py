from __future__ import annotations

import time
import tkinter as tk
from typing import Optional

from app.config import PlaybackTiming, get_playback_timing
from ocarina_gui.color_utils import hex_to_rgb
from ocarina_gui.fingering import FingeringView
from ocarina_gui.piano_roll import PianoRoll
from ocarina_gui.staff import StaffView
from shared.ttk import ttk
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
        play_buttons = getattr(self, "_preview_play_buttons", None)
        if isinstance(play_buttons, dict):
            play_btn = play_buttons.get(side)
        else:
            play_btn = None
        if play_btn is not None:
            icon_sets = getattr(self, "_preview_play_icons", None)
            icons = icon_sets.get(side) if isinstance(icon_sets, dict) else None
            desired_key = "pause" if playback.state.is_playing else "play"
            image = icons.get(desired_key) if isinstance(icons, dict) else None
            if image is not None:
                play_btn.configure(image=image, compound="left")
            else:
                play_btn.configure(image="", compound="none")
            self._apply_icon_button_style(play_btn)
        position_var = getattr(self, "_preview_position_vars", {}).get(side)
        duration_var = getattr(self, "_preview_duration_vars", {}).get(side)
        if position_var is not None or duration_var is not None:
            if playback.state.is_loaded:
                position_label = self._format_preview_time_label(
                    playback, playback.state.position_tick
                )
                duration_label = self._format_preview_time_label(
                    playback, playback.state.duration_tick
                )
            else:
                position_label = "0:00.000"
                duration_label = "0:00.000"
            if position_var is not None:
                position_var.set(position_label)
            if duration_var is not None:
                duration_var.set(duration_label)
        self._update_preview_render_progress(side)
        controls_enabled = (
            playback.state.is_loaded
            and not playback.state.is_playing
            and not playback.state.is_rendering
        )
        self._set_preview_controls_enabled(side, controls_enabled)
        self._update_preview_fingering(side)

    def _register_arranged_icon_target(self, name: str, widget: tk.Widget) -> None:
        registry = getattr(self, "_arranged_icon_targets", None)
        if registry is None:
            registry = {}
            self._arranged_icon_targets = registry
        registry.setdefault(name, []).append(widget)
        self._apply_icon_button_style(widget)

    def _apply_icon_button_style(self, widget: tk.Widget) -> None:
        if not isinstance(widget, ttk.Button):
            return

        emphasize = False
        play_buttons = getattr(self, "_preview_play_buttons", None)
        if isinstance(play_buttons, dict) and widget in play_buttons.values():
            emphasize = True

        bootstyle = ("primary", "outline") if emphasize else ("info", "outline")

        try:
            widget.configure(bootstyle=bootstyle)
        except (tk.TclError, TypeError):
            try:
                widget.configure(style="Toolbutton")
            except tk.TclError:
                return

    def _refresh_preview_theme_assets(self) -> None:
        self._refresh_arranged_icon_theme()

    def _refresh_arranged_icon_theme(self) -> None:
        cache = getattr(self, "_arranged_icon_cache", None)
        if not cache:
            return

        variant = "dark" if self._is_preview_theme_dark() else "light"

        icon_targets = getattr(self, "_arranged_icon_targets", {})
        if isinstance(icon_targets, dict):
            for name, widgets in icon_targets.items():
                entry = cache.get(name)
                if not isinstance(entry, dict):
                    continue
                icon = entry.get(variant) or entry.get("light")
                if icon is None:
                    continue
                for widget in widgets:
                    try:
                        widget.configure(image=icon)
                    except tk.TclError:
                        continue

        play_icons = getattr(self, "_preview_play_icons", {})
        play_buttons = getattr(self, "_preview_play_buttons", {})
        if isinstance(play_icons, dict):
            for side, icon_map in play_icons.items():
                if not isinstance(icon_map, dict):
                    continue
                for role in ("play", "pause"):
                    entry = cache.get(role)
                    icon = None
                    if isinstance(entry, dict):
                        icon = entry.get(variant) or entry.get("light")
                    icon_map[role] = icon
                if side in play_buttons:
                    self._update_playback_visuals(side)

    def _is_preview_theme_dark(self) -> bool:
        theme = getattr(self, "_theme", None)
        if theme is None:
            return False

        background = getattr(getattr(theme, "palette", None), "window_background", "")
        try:
            red, green, blue = hex_to_rgb(background)
        except ValueError:
            identifier = getattr(theme, "theme_id", "")
            return "dark" in str(identifier).lower()

        luminance = (0.299 * red + 0.587 * green + 0.114 * blue) / 255.0
        return luminance < 0.5

    @staticmethod
    def _format_preview_time_label(
        playback: PreviewPlaybackViewModel, ticks: int
    ) -> str:
        pulses = max(1, getattr(playback.state, "pulses_per_quarter", 1))
        tempo = getattr(playback.state, "tempo_bpm", 60.0) or 60.0
        tempo = max(tempo, 1e-6)
        seconds = max(0.0, (ticks / pulses) * 60.0 / tempo)
        minutes, remainder = divmod(seconds, 60.0)
        return f"{int(minutes)}:{remainder:06.3f}"

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
