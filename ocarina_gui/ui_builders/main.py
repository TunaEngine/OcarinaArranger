"""High-level orchestration for building the ocarina arranger UI."""

from __future__ import annotations

import tkinter as tk
from shared.ttk import ttk
from typing import TYPE_CHECKING

from .convert_tab import build_convert_tab
from .fingerings_tab import build_fingerings_tab
from .preview import build_preview_tabs

if TYPE_CHECKING:  # pragma: no cover - used for type checkers only
    from ..app import App


__all__ = ["build_ui"]


def build_ui(app: "App") -> None:
    """Build the full UI into ``app``."""

    notebook = ttk.Notebook(app)
    notebook.pack(fill="both", expand=True)
    app._notebook = notebook

    build_convert_tab(app, notebook)
    build_fingerings_tab(app, notebook)
    build_preview_tabs(app, notebook)

    def _maybe_render_preview(event: tk.Event) -> None:
        if not getattr(app, "_preview_tab_frames", ()):  # pragma: no cover - defensive
            return
        try:
            selected = event.widget.nametowidget(event.widget.select())
        except Exception:  # pragma: no cover - Tk can raise on teardown
            return
        side = getattr(app, "_preview_sides_by_frame", {}).get(selected)
        if side:
            app._ensure_preview_tab_initialized(side)
        if selected in app._preview_tab_frames:
            app._auto_render_preview(selected)

    notebook.bind("<<NotebookTabChanged>>", _maybe_render_preview)
