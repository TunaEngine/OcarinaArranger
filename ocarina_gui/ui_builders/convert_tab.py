"""Builder for the "Convert" tab."""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

from shared.ttk import ttk

from ui.main_window.initialisation.arranger_results import build_arranger_results_panel
from .convert_tab_sections import (
    build_arranger_mode_section,
    build_import_export_section,
    build_instrument_section,
    build_playback_section,
)

if TYPE_CHECKING:  # pragma: no cover - used for type checkers only
    from ..app import App


__all__ = ["build_convert_tab"]


def build_convert_tab(app: "App", notebook: ttk.Notebook) -> None:
    pad = 8
    tab = ttk.Frame(notebook)
    notebook.add(tab, text="Convert")

    container = ttk.Frame(tab, padding=pad)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=2)
    container.columnconfigure(1, weight=1)
    container.rowconfigure(0, weight=1)

    left_pane = ttk.Frame(container)
    left_pane.grid(row=0, column=0, sticky="nsew", padx=(0, pad))
    left_pane.columnconfigure(0, weight=1)
    left_pane.rowconfigure(0, weight=1)

    left_canvas = tk.Canvas(left_pane, highlightthickness=0)
    left_canvas.grid(row=0, column=0, sticky="nsew")
    left_scrollbar = ttk.Scrollbar(left_pane, orient="vertical", command=left_canvas.yview)
    left_scrollbar.grid(row=0, column=1, sticky="ns")
    left_canvas.configure(yscrollcommand=left_scrollbar.set)

    left_column = ttk.Frame(left_canvas)
    left_window = left_canvas.create_window((0, 0), window=left_column, anchor="nw")

    def _update_left_scrollregion(_event: tk.Event) -> None:
        left_canvas.configure(scrollregion=left_canvas.bbox("all"))

    left_column.bind("<Configure>", _update_left_scrollregion)

    def _sync_left_content_width(event: tk.Event) -> None:
        left_canvas.itemconfigure(left_window, width=event.width)

    left_canvas.bind("<Configure>", _sync_left_content_width)

    left_column.columnconfigure(0, weight=1)
    left_column.rowconfigure(0, weight=0)
    left_column.rowconfigure(1, weight=1)

    right_column = ttk.Frame(container)
    right_column.grid(row=0, column=1, sticky="nsew")
    right_column.columnconfigure(0, weight=1)
    right_column.rowconfigure(0, weight=0)
    right_column.rowconfigure(1, weight=0)
    right_column.rowconfigure(2, weight=1)

    build_instrument_section(app, left_column, pad)
    mode_panels = build_arranger_mode_section(app, left_column, pad)

    results_section = build_arranger_results_panel(app, right_column, pad)
    results_section.grid(row=2, column=0, sticky="nsew", pady=(pad, 0))
    app._arranger_results_section = results_section

    import_section = build_import_export_section(app, right_column, pad)
    build_playback_section(app, right_column, pad)

    app._arranger_mode_frames = {
        "classic": {"left": mode_panels["classic"]},
        "best_effort": {"left": mode_panels["best_effort"]},
        "gp": {"left": mode_panels["gp"]},
    }

    def _update_arranger_mode_layout() -> None:
        mode = (app.arranger_mode.get() or "classic").strip().lower()
        classic_frame = app._arranger_mode_frames["classic"]["left"]
        best_effort_frame = app._arranger_mode_frames["best_effort"]["left"]
        gp_frame = app._arranger_mode_frames["gp"]["left"]
        if mode == "best_effort":
            classic_frame.grid_remove()
            gp_frame.grid_remove()
            best_effort_frame.grid(row=0, column=0, sticky="nsew")
            results_section.grid(row=2, column=0, sticky="nsew", pady=(pad, 0))
        elif mode == "gp":
            classic_frame.grid_remove()
            best_effort_frame.grid_remove()
            gp_frame.grid(row=0, column=0, sticky="nsew")
            results_section.grid(row=2, column=0, sticky="nsew", pady=(pad, 0))
        else:
            best_effort_frame.grid_remove()
            gp_frame.grid_remove()
            classic_frame.grid(row=0, column=0, sticky="nsew")
            results_section.grid_remove()
        if hasattr(app, "_update_arranger_advanced_visibility"):
            try:
                app._update_arranger_advanced_visibility()
            except Exception:
                pass

    app._update_arranger_mode_layout = _update_arranger_mode_layout
    _update_arranger_mode_layout()

    footer = ttk.Label(
        container,
        text="Outputs .musicxml + .mxl | Part named 'Ocarina' | GM Program 80",
        style="Hint.TLabel",
    )
    footer.grid(row=1, column=0, columnspan=2, sticky="w", pady=(pad, 0))

    def _ensure_convert_tab_panel_styles() -> None:
        from shared.tk_style import apply_theme_to_panel_widgets

        try:
            apply_theme_to_panel_widgets(app)
        except Exception:
            pass

    app.after(1, _ensure_convert_tab_panel_styles)
