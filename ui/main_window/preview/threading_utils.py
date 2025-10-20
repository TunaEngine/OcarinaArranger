from __future__ import annotations

import logging
import threading
import tkinter as tk
from typing import Callable


logger = logging.getLogger(__name__)


def dispatch_to_ui(
    root: tk.Misc,
    callback: Callable[..., object],
    *args: object,
    **kwargs: object,
) -> None:
    """Invoke *callback* on the Tk UI thread."""

    if threading.current_thread() is threading.main_thread():
        try:
            callback(*args, **kwargs)
        except Exception:  # pragma: no cover - defensive UI guard
            logger.exception("UI callback raised on main thread")
        return

    def _invoke() -> None:
        try:
            callback(*args, **kwargs)
        except Exception:  # pragma: no cover - defensive UI guard
            logger.exception("UI callback raised from scheduled task")

    try:
        root.after(0, _invoke)
    except Exception:  # pragma: no cover - fallback if Tk is tearing down
        logger.exception("Failed to schedule UI callback; running immediately")
        try:
            callback(*args, **kwargs)
        except Exception:
            logger.exception("Fallback UI callback raised")
