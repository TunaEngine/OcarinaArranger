"""Lifecycle hooks for :class:`MenuActionsMixin`."""

from __future__ import annotations

from typing import Callable

import tkinter as tk

from ._logger import logger


class LifecycleMixin:
    _headless: bool
    _theme_unsubscribe: Callable[[], None] | None
    _input_path_trace_id: str | None
    _layout_editor_window: tk.Misc | None

    def withdraw(self) -> None:  # type: ignore[override]
        if self._headless:
            return
        super().withdraw()

    def update_idletasks(self) -> None:  # type: ignore[override]
        if self._headless:
            return
        super().update_idletasks()
        self._maybe_auto_render_selected_preview()

    def destroy(self) -> None:  # type: ignore[override]
        """Tear down subscriptions and playback before destroying the window."""

        logger.info("Destroying main window")
        if self._theme_unsubscribe is not None:
            self._theme_unsubscribe()
            self._theme_unsubscribe = None

        interpreter = getattr(self, "tk", None)

        if self._input_path_trace_id is not None:
            try:
                self.input_path.trace_remove("write", self._input_path_trace_id)
            except tk.TclError:
                pass
            self._input_path_trace_id = None

        if self._layout_editor_window is not None:
            try:
                self._layout_editor_window.destroy()
            except Exception:
                pass
            finally:
                self._layout_editor_window = None

        try:
            self._teardown_playback()
        finally:
            try:
                if not self._headless:
                    super().destroy()
            except tk.TclError:
                pass
            finally:
                try:
                    self._release_tk_variables(interpreter)
                except Exception:
                    logger.debug("Failed clearing Tk variable interpreters", exc_info=True)
        logger.info("Main window destroyed")
