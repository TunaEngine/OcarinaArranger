"""Preview rendering progress overlay."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - used for type checkers only
    from ..app import App


__all__ = ["build_preview_progress_overlay"]


def build_preview_progress_overlay(app: "App", tab: ttk.Frame, side: str) -> None:
    """Create a modal-like overlay that blocks the preview tab while rendering."""

    try:
        background = tab.winfo_toplevel().cget("background")
    except Exception:  # pragma: no cover - headless fallback
        background = "#000000"

    overlay = tk.Frame(tab, background=background, cursor="watch")
    overlay.pack_propagate(False)

    card = ttk.Frame(overlay, padding=16)
    card.pack(expand=True, fill="both")

    ttk.Label(card, text="Preparing preview…").pack(pady=(0, 8))
    ttk.Progressbar(
        card,
        orient="horizontal",
        mode="determinate",
        maximum=100,
        variable=app._preview_render_progress_vars[side],
    ).pack(fill="x")
    ttk.Label(card, textvariable=app._preview_render_progress_labels[side]).pack(pady=(8, 0))

    overlay.bind("<Button>", lambda event: "break")
    overlay.bind("<ButtonRelease>", lambda event: "break")
    overlay.bind("<Key>", lambda event: "break")
    overlay.bind("<MouseWheel>", lambda event: "break")
    overlay.bind("<Button-4>", lambda event: "break")  # X11 scroll up
    overlay.bind("<Button-5>", lambda event: "break")  # X11 scroll down

    app._register_preview_progress_frame(
        side,
        overlay,
        place={"relx": 0.0, "rely": 0.0, "relwidth": 1.0, "relheight": 1.0},
    )
