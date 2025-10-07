from __future__ import annotations

import tkinter as tk

from ui.main_window.tk_support import (
    collect_tk_variables_from_attrs,
    release_tracked_tk_variables,
)

from ._logging import LOGGER


class TkVariableTrackingMixin:
    """Expose helpers to introspect and release Tk variables."""

    def _tk_variables(self) -> tuple[tk.Variable, ...]:
        """Return all Tk variables currently referenced by the window."""

        return collect_tk_variables_from_attrs(self)

    def _release_tk_variables(self, interpreter: object | None = None) -> None:
        release_tracked_tk_variables(self, interpreter, log=LOGGER)


__all__ = ["TkVariableTrackingMixin"]
