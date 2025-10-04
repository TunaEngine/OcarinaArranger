from __future__ import annotations

import tkinter as tk


class PreviewProgressMixin:
    """Track render progress state for preview playback."""

    def _set_preview_initial_loading(
        self, side: str, loading: bool, *, message: str | None = None
    ) -> None:
        if loading:
            self._preview_initial_loading.add(side)
            if message is not None:
                self._preview_progress_messages[side] = message
        else:
            self._preview_initial_loading.discard(side)
            self._preview_progress_messages.pop(side, None)
        progress_var = self._preview_render_progress_vars.get(side)
        label_var = self._preview_render_progress_labels.get(side)
        if progress_var is not None:
            try:
                if loading:
                    progress_var.set(0.0)
            except (tk.TclError, RuntimeError, AttributeError):
                pass
        if label_var is not None and message is not None:
            try:
                label_var.set(
                    f"{message} {self._format_progress_percentage(0.0)}"
                )
            except (tk.TclError, RuntimeError, AttributeError):
                pass
        self._update_preview_render_progress(side)
        if hasattr(self, "_update_reimport_button_state"):
            self._update_reimport_button_state()

    @staticmethod
    def _format_progress_percentage(percent: float) -> str:
        clamped = max(0.0, min(100.0, percent))
        if clamped <= 0.0:
            return "0%"
        if clamped >= 100.0:
            return "100%"
        if clamped < 10.0:
            return f"{clamped:.1f}%"
        return f"{clamped:.0f}%"

    def _update_preview_render_progress(self, side: str) -> None:
        playback = self._preview_playback.get(side)
        if playback is None:
            return
        progress_var = self._preview_render_progress_vars.get(side)
        label_var = self._preview_render_progress_labels.get(side)
        frame = self._preview_progress_frames.get(side)
        if progress_var is None or label_var is None or frame is None:
            return
        try:
            manager = frame.winfo_manager()
        except (tk.TclError, RuntimeError, AttributeError):
            manager = ""
        initial_loading = side in self._preview_initial_loading
        base_message = self._preview_progress_messages.get(side)
        try:
            if playback.state.is_rendering:
                progress = max(0.0, min(1.0, playback.state.render_progress))
                percent = max(0.0, min(100.0, progress * 100.0))
                progress_var.set(percent)
                formatted = self._format_progress_percentage(percent)
                if base_message:
                    label_var.set(f"{base_message} {formatted}")
                else:
                    label_var.set(formatted)
                place = self._preview_progress_places.get(side)
                if manager != "place":
                    if place is not None:
                        frame.place(**place)
                    else:
                        frame.pack(fill="x", pady=(0, 4))
                frame.lift()
                try:
                    frame.focus_set()
                except (tk.TclError, RuntimeError):
                    pass
            elif initial_loading:
                progress_var.set(0.0)
                if base_message:
                    label_var.set(
                        f"{base_message} {self._format_progress_percentage(0.0)}"
                    )
                place = self._preview_progress_places.get(side)
                if manager != "place":
                    if place is not None:
                        frame.place(**place)
                    else:
                        frame.pack(fill="x", pady=(0, 4))
                frame.lift()
                try:
                    frame.focus_set()
                except (tk.TclError, RuntimeError):
                    pass
            else:
                progress_var.set(0.0)
                label_var.set("")
                if manager == "place":
                    frame.place_forget()
                elif manager:
                    frame.pack_forget()
        except (tk.TclError, RuntimeError, AttributeError):
            return
        self._update_preview_apply_cancel_state(side)
