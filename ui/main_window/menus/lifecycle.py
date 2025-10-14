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
        # Reapply Panel styles after widget updates to handle ttkbootstrap resets
        self._reapply_panel_styles_if_needed()

    def _reapply_panel_styles_if_needed(self) -> None:
        """Reapply Panel styles if they may have been reset by ttkbootstrap."""
        style = getattr(self, '_style', None)
        if style is None:
            return
        
        theme = getattr(self, '_theme', None)
        if theme is None:
            return
            
        try:
            from shared.tk_style import configure_panel_styles
            configure_panel_styles(style, theme.palette.window_background, theme.palette.text_primary)
        except Exception:
            # Don't fail if Panel style reapplication fails
            pass

    def destroy(self) -> None:  # type: ignore[override]
        """Tear down subscriptions and playback before destroying the window."""

        logger.info("Destroying main window")
        if getattr(self, "_fingering_edit_mode", False):
            cancel_edits = getattr(self, "cancel_fingering_edits", None)
            if callable(cancel_edits):
                try:
                    cancel_edits(show_errors=False)
                except Exception:  # pragma: no cover - defensive safeguard
                    logger.exception("Failed to cancel fingering edits during destroy")

        teardown_linux = getattr(self, "_teardown_linux_automation", None)
        if callable(teardown_linux):
            try:
                teardown_linux()
            except Exception:
                logger.debug("Linux automation teardown raised", exc_info=True)

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
