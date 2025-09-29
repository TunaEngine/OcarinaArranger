"""Helpers for positioning Tk windows consistently."""

from __future__ import annotations

import tkinter as tk


def center_window_over_parent(
    window: tk.Toplevel, parent: tk.Misc | None = None
) -> None:
    """Center ``window`` over ``parent`` or the screen if no parent is mapped."""

    try:
        window.update_idletasks()
    except tk.TclError:
        return

    if parent is None:
        master = getattr(window, "master", None)
        if isinstance(master, tk.Misc):
            parent = master

    if parent is not None:
        try:
            parent.update_idletasks()
        except tk.TclError:
            parent = None

    width = window.winfo_width()
    height = window.winfo_height()
    if width <= 1 or height <= 1:
        width = max(width, window.winfo_reqwidth())
        height = max(height, window.winfo_reqheight())

    x: int | None = None
    y: int | None = None

    if parent is not None:
        try:
            if parent.winfo_ismapped():
                parent_width = parent.winfo_width()
                parent_height = parent.winfo_height()
                if parent_width <= 1:
                    parent_width = parent.winfo_reqwidth()
                if parent_height <= 1:
                    parent_height = parent.winfo_reqheight()

                x = parent.winfo_rootx() + (parent_width - width) // 2
                y = parent.winfo_rooty() + (parent_height - height) // 2
        except tk.TclError:
            x = None
            y = None

    if x is None or y is None:
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2

    window.geometry(f"+{max(int(x), 0)}+{max(int(y), 0)}")


__all__ = ["center_window_over_parent"]
