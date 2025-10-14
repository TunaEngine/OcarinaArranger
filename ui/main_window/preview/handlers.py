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
        self._pause_preview_playback_for_cursor_seek(side)
        self._handle_loop_range_click(side, tick)
        playback.seek_to(tick)
        force_flags = getattr(self, "_force_autoscroll_once", None)
        if isinstance(force_flags, dict):
            force_flags[side] = True
        self._update_playback_visuals(side)

    def _on_preview_tempo_changed(self, side: str, *_args: object) -> None:
        var = self._preview_tempo_vars.get(side)
        if var is None:
            return
        try:
            value = float(var.get())
        except (tk.TclError, ValueError):
            if hasattr(self, "_refresh_tempo_summary"):
                try:
                    self._refresh_tempo_summary(side, tempo_value=None)
                except Exception:
                    pass
            if side in self._suspend_tempo_update:
                return
            self._update_preview_apply_cancel_state(side, valid=False)
            return
        if hasattr(self, "_refresh_tempo_summary"):
            try:
                self._refresh_tempo_summary(side, tempo_value=value)
            except Exception:
                pass
        if side in self._suspend_tempo_update:
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

    def _on_preview_volume_changed(self, side: str, *_args: object) -> None:
        if side in self._suspend_volume_update:
            return
        var = self._preview_volume_vars.get(side)
        playback = self._preview_playback.get(side)
        if var is None or playback is None:
            return
        try:
            value = float(var.get())
        except (tk.TclError, ValueError):
            return
        clamped = max(0.0, min(100.0, value))
        logger.debug(
            "preview volume var changed: side=%s raw=%s clamped=%.3f",
            side,
            value,
            clamped,
        )
        remember_last = clamped > 0.0
        self._apply_volume_change(side, clamped, remember_last=remember_last)

    def _on_preview_volume_press(self, side: str, event: tk.Event) -> str | None:
        self._begin_volume_adjustment(side)
        self._update_volume_from_slider_event(side, event)
        return "break"

    def _on_preview_volume_drag(self, side: str, event: tk.Event) -> str | None:
        self._update_volume_from_slider_event(side, event)
        return "break"

    def _on_preview_volume_release(self, side: str, event: tk.Event) -> str | None:
        self._update_volume_from_slider_event(side, event)
        self._end_volume_adjustment(side)
        return "break"

    def _handle_preview_volume_button(
        self, side: str, event: tk.Event | None
    ) -> str | None:
        guard = getattr(self, "_preview_volume_button_guard", None)
        if guard is None:
            guard = set()
            self._preview_volume_button_guard = guard

        if event is None:
            guard.add(side)
            logger.debug(
                "preview volume button command: side=%s source=command", side
            )
            try:
                self._toggle_preview_mute(side)
            finally:
                after_idle = getattr(self, "after_idle", None)
                if callable(after_idle):
                    try:
                        after_idle(lambda s=side: guard.discard(s))
                    except tk.TclError:
                        guard.discard(side)
                else:
                    guard.discard(side)
            return None

        if side in guard:
            guard.discard(side)
            logger.debug(
                "preview volume button event suppressed: side=%s (command already handled)",
                side,
            )
            return "break"

        logger.debug(
            "preview volume button event: side=%s type=%s state=%s",  # pragma: no cover - debug aid
            side,
            getattr(event, "type", None),
            getattr(event, "state", None),
        )
        self._toggle_preview_mute(side)
        return "break"

    def _toggle_preview_mute(self, side: str) -> None:
        var = self._preview_volume_vars.get(side)
        playback = self._preview_playback.get(side)
        if var is None or playback is None:
            return

        state_value = max(0.0, min(100.0, playback.state.volume * 100.0))
        try:
            slider_value = float(var.get())
        except (tk.TclError, ValueError):
            slider_value = state_value

        slider_value = max(0.0, min(100.0, slider_value))
        if slider_value <= 1e-6 < state_value:
            slider_value = state_value

        memory = self._preview_volume_memory
        if slider_value > 0.0:
            memory[side] = slider_value

        muted = state_value <= 1e-6 and slider_value <= 1e-6
        logger.debug(
            "toggle preview mute: side=%s state_value=%.3f slider_value=%.3f muted=%s remembered=%.3f",
            side,
            state_value,
            slider_value,
            muted,
            memory.get(side, 0.0),
        )
        if muted:
            restore = slider_value if slider_value > 0.0 else memory.get(side, 100.0)
            if restore <= 0.0:
                restore = 100.0
            target_value = restore
        else:
            remembered = slider_value if slider_value > 0.0 else state_value
            if remembered > 0.0:
                memory[side] = remembered
            target_value = 0.0

        remember_last = target_value > 0.0
        logger.debug(
            "toggle preview mute target: side=%s target_value=%.3f remember_last=%s",
            side,
            target_value,
            remember_last,
        )
        self._apply_volume_change(side, target_value, remember_last=remember_last)
        self._sync_preview_playback_controls(side)

    def _begin_volume_adjustment(self, side: str) -> None:
        if side in self._active_volume_adjustment:
            return
        self._active_volume_adjustment.add(side)
        playback = self._preview_playback.get(side)
        if playback is None:
            self._resume_volume_on_release.pop(side, None)
            return
        resume = bool(playback.state.is_loaded and playback.state.is_playing)
        self._resume_volume_on_release[side] = resume
        logger.debug(
            "begin preview volume adjustment: side=%s resume=%s", side, resume
        )
        if resume:
            playback.toggle_playback()
            self._update_playback_visuals(side)

    def _end_volume_adjustment(self, side: str) -> None:
        self._active_volume_adjustment.discard(side)
        resume = self._resume_volume_on_release.pop(side, False)
        playback = self._preview_playback.get(side)
        if playback is None:
            return
        logger.debug(
            "end preview volume adjustment: side=%s resume=%s is_loaded=%s is_playing=%s",
            side,
            resume,
            getattr(playback.state, "is_loaded", None),
            getattr(playback.state, "is_playing", None),
        )
        if resume and playback.state.is_loaded and not playback.state.is_playing:
            restarted = playback.toggle_playback()
            if restarted:
                self._playback_last_ts = time.perf_counter()
            else:
                error = playback.state.last_error
                if error:
                    try:
                        messagebox.showwarning("Audio unavailable", error)
                    except tk.TclError:
                        logger.debug(
                            "Unable to show audio warning after slider resume",
                            exc_info=True,
                        )
        self._update_playback_visuals(side)

    def _update_volume_from_slider_event(self, side: str, event: tk.Event) -> None:
        widget = getattr(event, "widget", None)
        if widget is None:
            controls = self._preview_volume_controls.get(side, ())
            widget = controls[1] if len(controls) > 1 else None
        if widget is None:
            return
        try:
            width = max(1.0, float(widget.winfo_width()))
        except (tk.TclError, TypeError, ValueError):
            width = 1.0
        x_value = getattr(event, "x", width)
        try:
            x_coord = float(x_value)
        except (TypeError, ValueError):
            x_coord = width
        x_coord = max(0.0, min(width, x_coord))
        try:
            start = float(widget.cget("from"))
        except (tk.TclError, TypeError, ValueError):
            start = 0.0
        try:
            end = float(widget.cget("to"))
        except (tk.TclError, TypeError, ValueError):
            end = 100.0
        ratio = x_coord / width if width else 0.0
        value = start + (end - start) * ratio
        logger.debug(
            "preview volume slider event: side=%s width=%.3f x=%.3f ratio=%.3f value=%.3f",
            side,
            width,
            x_coord,
            ratio,
            value,
        )
        try:
            widget.set(value)
        except (tk.TclError, AttributeError):
            var = self._preview_volume_vars.get(side)
            if var is not None:
                try:
                    var.set(value)
                except tk.TclError:
                    pass

    def _apply_volume_change(
        self, side: str, value: float, *, remember_last: bool
    ) -> float:
        playback = self._preview_playback.get(side)
        if playback is None:
            return self._set_volume_controls_value(side, value)

        clamped = self._set_volume_controls_value(side, value)
        normalized = max(0.0, min(1.0, clamped / 100.0))
        logger.debug(
            "apply preview volume change: side=%s value=%.3f normalized=%.4f remember_last=%s is_playing=%s",
            side,
            clamped,
            normalized,
            remember_last,
            getattr(playback.state, "is_playing", None),
        )
        playback.set_volume(normalized)
        if remember_last and clamped > 0.0:
            self._preview_volume_memory[side] = clamped
        self._update_mute_button_state(side)
        return clamped

    def _set_volume_controls_value(self, side: str, value: float) -> float:
        clamped = max(0.0, min(100.0, float(value)))
        logger.debug(
            "set preview volume controls: side=%s value=%s clamped=%.3f",
            side,
            value,
            clamped,
        )
        self._suspend_volume_update.add(side)
        try:
            var = self._preview_volume_vars.get(side)
            if var is not None:
                try:
                    var.set(clamped)
                except tk.TclError:
                    pass
            controls = self._preview_volume_controls.get(side, ())
            for widget in controls:
                setter = getattr(widget, "set", None)
                if callable(setter):
                    try:
                        setter(clamped)
                    except tk.TclError:
                        continue
        finally:
            self._suspend_volume_update.discard(side)
        return clamped

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
