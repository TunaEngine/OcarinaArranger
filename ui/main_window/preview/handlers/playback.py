from __future__ import annotations

import logging
import time
import tkinter as tk
from tkinter import messagebox

logger = logging.getLogger(__name__)


class PreviewPlaybackHandlersMixin:
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
                    logger.debug("Unable to show audio warning", exc_info=True)
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
        target = playback.state.track_end_tick or playback.state.duration_tick
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
