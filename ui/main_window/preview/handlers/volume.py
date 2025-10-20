from __future__ import annotations

import logging
import time
import tkinter as tk
from tkinter import messagebox

from services.project_service import PreviewPlaybackSnapshot

logger = logging.getLogger(__name__)


class PreviewVolumeHandlersMixin:
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
        clamped = self._set_volume_controls_value(side, value)

        applied_store = getattr(self, "_preview_applied_settings", None)
        if not isinstance(applied_store, dict):
            applied_store = {}
            self._preview_applied_settings = applied_store
        applied = applied_store.setdefault(side, {})
        applied["volume"] = clamped
        if hasattr(self, "_preview_settings_seeded"):
            self._preview_settings_seeded.add(side)

        preview_state = getattr(getattr(self, "_viewmodel", None), "state", None)
        if preview_state is not None:
            settings: dict[str, PreviewPlaybackSnapshot] = dict(
                getattr(preview_state, "preview_settings", {})
            )
            existing_snapshot = settings.get(side)
            if isinstance(existing_snapshot, PreviewPlaybackSnapshot):
                snapshot = PreviewPlaybackSnapshot(
                    tempo_bpm=float(existing_snapshot.tempo_bpm),
                    metronome_enabled=bool(existing_snapshot.metronome_enabled),
                    loop_enabled=bool(existing_snapshot.loop_enabled),
                    loop_start_beat=float(existing_snapshot.loop_start_beat),
                    loop_end_beat=float(existing_snapshot.loop_end_beat),
                    volume=clamped / 100.0,
                )
            else:
                tempo = float(applied.get("tempo", 120.0))
                loop_enabled = bool(applied.get("loop_enabled", False))
                loop_start = float(applied.get("loop_start", 0.0))
                loop_end = float(applied.get("loop_end", loop_start))
                snapshot = PreviewPlaybackSnapshot(
                    tempo_bpm=tempo,
                    metronome_enabled=bool(applied.get("metronome", False)),
                    loop_enabled=loop_enabled,
                    loop_start_beat=loop_start,
                    loop_end_beat=loop_end,
                    volume=clamped / 100.0,
                )
            settings[side] = snapshot
            self._viewmodel.update_preview_settings(settings)

        playback = self._preview_playback.get(side)
        if playback is None:
            return clamped

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
        self._update_preview_apply_cancel_state(side, volume=clamped)
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
