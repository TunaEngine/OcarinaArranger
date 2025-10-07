from __future__ import annotations

import tkinter as tk

from ocarina_gui.headless import install_headless_photoimage
from shared.ttk import ttk

from ._logging import LOGGER


class TkRootMixin:
    """Mixin providing Tk/ttkbootstrap root initialisation."""

    def _initialise_tk_root(self, themename: str | None = None) -> bool:
        init_kwargs: dict[str, object] = {}
        if hasattr(ttk, "Window") and themename:
            init_kwargs["themename"] = themename
        try:
            super().__init__(**init_kwargs)  # type: ignore[misc]
        except tk.TclError:
            tk.Tk.__init__(self, useTk=False)  # type: ignore[misc]
            install_headless_photoimage()
            return True
        except Exception:  # pragma: no cover - defensive fallback
            LOGGER.warning(
                "ttkbootstrap Window initialisation failed; falling back to Tk",
                exc_info=True,
            )
            tk.Tk.__init__(self)  # type: ignore[misc]
            return False
        return False


__all__ = ["TkRootMixin"]
