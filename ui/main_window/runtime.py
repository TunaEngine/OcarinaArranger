from __future__ import annotations

import tkinter as tk


class MainWindowRuntimeMixin:
    """Runtime helpers for :class:`ui.main_window.main_window.MainWindow`."""

    def _on_auto_scroll_mode_changed(self, *_args: object) -> None:
        if getattr(self, "_suspend_auto_scroll_update", False):
            return
        self._apply_auto_scroll_mode(self._auto_scroll_mode.get())

    def update_idletasks(self) -> None:  # type: ignore[override]
        try:
            super().update_idletasks()
        except tk.TclError:
            return
        self._poll_preview_tab_selection()


__all__ = ["MainWindowRuntimeMixin"]
