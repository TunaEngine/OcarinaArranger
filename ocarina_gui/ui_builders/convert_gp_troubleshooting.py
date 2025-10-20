"""Shared troubleshooting helpers for the GP arranger panel."""

from __future__ import annotations

from tkinter import messagebox

from shared.ttk import ttk

from ui.widgets import attach_tooltip


TROUBLESHOOTING_TIPS = """Troubleshooting
1. Try to use default settings first (reset to default if already changed).
2. If you don't like the output, change to "Use ranked candidate" first and re-arrange.
3. If it still doesn't look good, expand "Show advanced arranger controls" and change "Range clamp penalty" to 5, re-arrange. This may cause the notes to be out of instrument range. Use manual transposition to move the song up/down as needed."""


def add_troubleshooting_button(parent: ttk.Widget, pad: int) -> ttk.Button:
    """Attach the troubleshooting button to ``parent`` and return it."""

    def _show_troubleshooting() -> None:
        messagebox.showinfo(
            "GP arranger troubleshooting",
            TROUBLESHOOTING_TIPS,
            parent=parent.winfo_toplevel(),
        )

    button = ttk.Button(parent, text="Troubleshooting tips", command=_show_troubleshooting)
    button.grid(row=1, column=0, sticky="w", pady=(pad // 2, 0))
    attach_tooltip(button, "Open arranger troubleshooting guidance.")
    return button


__all__ = ["add_troubleshooting_button", "TROUBLESHOOTING_TIPS"]
