"""Builder for the fingerings tab."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from ..fingering import (
    FingeringGridView,
    FingeringView,
    get_available_instruments,
    get_current_instrument,
)

if TYPE_CHECKING:  # pragma: no cover - used for type checkers only
    from ..app import App


__all__ = ["build_fingerings_tab"]


def build_fingerings_tab(app: "App", notebook: ttk.Notebook) -> None:
    pad = 8
    tab = ttk.Frame(notebook)
    notebook.add(tab, text="Fingerings")

    header = ttk.Frame(tab)
    header.pack(fill="x", padx=pad, pady=(pad, 0))
    ttk.Label(
        header,
        text="Fingerings are generated from the active instrument configuration.",
        style="Hint.TLabel",
    ).pack(side="left")

    actions = ttk.Frame(header)
    actions.pack(side="right")
    edit_button = ttk.Button(actions, text="Edit...", command=app.toggle_fingering_editing)
    edit_button.pack(side="right")
    app._fingering_edit_button = edit_button
    cancel_button = ttk.Button(actions, text="Cancel", command=app.cancel_fingering_edits)
    app._fingering_cancel_button = cancel_button
    app._fingering_cancel_pad = (0, pad)

    choices = get_available_instruments()
    if choices:
        current = get_current_instrument()
        selector_frame = ttk.Frame(actions)
        selector_frame.pack(side="right", padx=(0, pad))
        ttk.Label(selector_frame, text="Instrument:").pack(side="left", padx=(0, 4))
        instrument_var = tk.StringVar(master=app, value=current.name)
        app.fingering_instrument_var = instrument_var
        instrument_by_name = {choice.name: choice.instrument_id for choice in choices}
        combo = ttk.Combobox(
            selector_frame,
            state="readonly",
            values=[choice.name for choice in choices],
            textvariable=instrument_var,
            width=18,
        )
        combo.pack(side="left")
        app.fingering_selector = combo

        def _on_instrument_change(_event: tk.Event | None = None) -> None:
            selection = instrument_var.get()
            instrument_id = instrument_by_name.get(selection)
            if instrument_id:
                app.set_fingering_instrument(instrument_id)

        combo.bind("<<ComboboxSelected>>", _on_instrument_change)

    content = ttk.Frame(tab)
    content.pack(fill="both", expand=True, padx=pad, pady=(pad, pad))
    content.columnconfigure(0, weight=1)
    content.rowconfigure(0, weight=1)

    panes = ttk.Panedwindow(content, orient="vertical")
    panes.grid(row=0, column=0, sticky="nsew")

    top_section = ttk.Frame(panes)
    top_section.columnconfigure(1, weight=1)
    top_section.rowconfigure(0, weight=1)

    preview_frame = ttk.Frame(top_section)
    preview_frame.grid(row=0, column=0, sticky="n", padx=(0, pad))
    ttk.Label(preview_frame, text="Selected fingering").pack(anchor="w")
    preview = FingeringView(preview_frame)
    preview.pack(pady=(4, 0))
    register_preview = getattr(app, "_register_fingering_preview", None)
    if callable(register_preview):
        register_preview(preview)
    else:  # pragma: no cover - legacy path
        app.fingering_preview = preview

    table_frame = ttk.Frame(top_section)
    table_frame.grid(row=0, column=1, sticky="nsew")
    table_frame.columnconfigure(0, weight=1)
    table_frame.rowconfigure(0, weight=1)

    tree = ttk.Treeview(table_frame, show="headings", selectmode="browse")
    tree.grid(row=0, column=0, sticky="nsew")
    register = getattr(app, "_register_fingering_table", None)
    if callable(register):
        register(tree)
    else:  # pragma: no cover - legacy path
        app.fingering_table = tree
    yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    yscroll.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=yscroll.set)

    tree.bind("<ButtonPress-1>", app._on_fingering_table_button_press, add=True)
    tree.bind("<B1-Motion>", app._on_fingering_heading_motion, add=True)
    tree.bind("<<TreeviewSelect>>", app._on_fingering_table_select)
    tree.bind("<ButtonRelease-1>", app._on_fingering_cell_click, add=True)

    panes.add(top_section, weight=3)

    grid_section = ttk.LabelFrame(panes, text="All fingerings")
    grid_section.columnconfigure(0, weight=1)
    grid_section.rowconfigure(0, weight=1)

    fingering_grid = FingeringGridView(grid_section)
    fingering_grid.grid(row=0, column=0, sticky="nsew")
    app.fingering_grid = fingering_grid
    app._populate_fingering_table()

    grid_section.configure(padding=(0, pad, 0, 0))
    panes.add(grid_section, weight=2)

    controls = ttk.Frame(content)
    controls.grid(row=1, column=0, sticky="ew", pady=(pad, 0))
    controls.columnconfigure(0, weight=1)
    controls.grid_remove()
    app._fingering_edit_controls = controls

    buttons = ttk.Frame(controls)
    buttons.grid(row=0, column=0, sticky="w", pady=(pad // 2, 0))

    ttk.Button(buttons, text="Add note", command=app.add_fingering_note).pack(side="left", padx=(0, pad))
    ttk.Button(buttons, text="Rename", command=app.rename_fingering_note).pack(side="left", padx=(0, pad))
    ttk.Button(buttons, text="Remove", command=app.remove_fingering_note).pack(side="left", padx=(0, pad))
