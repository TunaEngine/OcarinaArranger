from __future__ import annotations

import tkinter as tk

from ocarina_gui import themes


class PreviewTabManagementMixin:
    """Ensure preview tabs are created lazily and track selection."""

    def _ensure_preview_tab_initialized(self, side: str) -> None:
        if not side:
            return
        if side in self._preview_tab_initialized:
            return
        builder = self._preview_tab_builders.pop(side, None)
        if builder is not None:
            builder()
            if side == "original":
                target = getattr(self, "roll_orig", None)
            elif side == "arranged":
                target = getattr(self, "roll_arr", None)
            else:
                target = None
            if target is not None:
                try:
                    target.apply_palette(themes.get_current_theme().palette.piano_roll)
                except Exception:
                    pass
        self._preview_tab_initialized.add(side)
        self._load_pending_preview_playback(side)
        pending = getattr(self, "_pending_preview_data", None)
        if pending is not None:
            self._apply_preview_data_for_side(side, pending)
        self._sync_preview_playback_controls(side)
        self._update_playback_visuals(side)
        self._update_preview_render_progress(side)

    def _poll_preview_tab_selection(self) -> None:
        if getattr(self, "_headless", False):
            return
        notebook = getattr(self, "_notebook", None)
        if notebook is None:
            return
        try:
            current = notebook.nametowidget(notebook.select())
        except Exception:
            return
        side = getattr(self, "_preview_sides_by_frame", {}).get(current)
        if not side:
            return
        if getattr(self, "_preview_selected_side", None) != side:
            self._preview_selected_side = side
        if side not in self._preview_tab_initialized:
            self._ensure_preview_tab_initialized(side)

    def _preview_frame_for_side(self, side: str) -> tk.Widget | None:
        frames_by_side = getattr(self, "_preview_frames_by_side", {})
        frame = frames_by_side.get(side)
        if frame is not None:
            return frame
        if not self._preview_tab_frames:
            return None
        index: int
        if side == "original":
            index = 0
        elif side == "arranged":
            index = 1
        else:
            return None
        try:
            return self._preview_tab_frames[index]
        except IndexError:
            return None

    def _select_preview_tab(self, side: str) -> None:
        self._preview_selected_side = side
        notebook = getattr(self, "_notebook", None)
        frame = self._preview_frame_for_side(side)
        if notebook is None or frame is None:
            return
        try:
            notebook.select(frame)
        except Exception:
            pass
