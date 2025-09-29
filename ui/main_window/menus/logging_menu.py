"""Logging-related helpers for :class:`MenuActionsMixin`."""

from __future__ import annotations

from tkinter import messagebox
from typing import Callable

from ocarina_gui.preferences import Preferences
from shared.logging_config import LogVerbosity
from ui.logging_preferences import (
    apply_log_verbosity,
    persist_log_verbosity,
    restore_log_verbosity_preference,
)

from ._logger import logger


class LoggingMenuMixin:
    _headless: bool
    _log_verbosity: object  # Tk variable

    def _make_log_verbosity_callback(self, verbosity: LogVerbosity) -> Callable[[], None]:
        def _callback() -> None:
            self._apply_log_verbosity(verbosity)

        return _callback

    def _apply_log_verbosity(self, verbosity: LogVerbosity) -> None:
        def _on_failure(_verbosity: LogVerbosity, _exc: Exception) -> None:
            if self._headless:
                return
            try:
                messagebox.showerror(
                    "Logging",
                    "Unable to update the log file verbosity.",
                    parent=self,
                )
            except Exception:  # pragma: no cover - defensive against Tk failures
                pass

        if not apply_log_verbosity(verbosity, on_failure=_on_failure):
            return
        self._log_verbosity.set(verbosity.value)
        if verbosity is LogVerbosity.DISABLED:
            logger.warning("File logging disabled by user request")
        else:
            logger.info("File logging verbosity set to %s", verbosity.value)
        persist_log_verbosity(verbosity)

    def _restore_log_verbosity_preference(self, preferences: Preferences) -> None:
        restored = restore_log_verbosity_preference(preferences)
        if restored is not None:
            self._log_verbosity.set(restored.value)
