"""Tk style helpers for the piano roll widget."""

from __future__ import annotations

import tkinter as tk
from types import MethodType


def install_canvas_background_accessor(widget: tk.Canvas, color: str) -> None:
    """Expose a virtual ``background`` value for canvas widgets.

    Tk canvases do not always report the assigned ``background`` colour when
    queried through ``__getitem__``.  The existing widget implementation relies
    on retrieving the colour later when re-applying palettes, so we install a
    lightweight proxy that stores the colour alongside the canvas instance.
    ``MethodType`` is used so that the override participates in the Tk widget's
    descriptor protocol correctly.
    """

    try:
        setattr(widget, "_piano_roll_background", color)
        original = getattr(widget, "_piano_roll_original_getitem", None)
        if original is None:
            original = widget.__getitem__
            setattr(widget, "_piano_roll_original_getitem", original)

            def _cget(self: tk.Canvas, key: str, _orig=original):
                if key == "background":
                    return getattr(self, "_piano_roll_background", _orig(key))
                return _orig(key)

            widget.__getitem__ = MethodType(_cget, widget)
    except Exception:
        pass

