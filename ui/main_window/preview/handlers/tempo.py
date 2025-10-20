from __future__ import annotations

import tkinter as tk


class PreviewTempoHandlersMixin:
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
