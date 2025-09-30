"""UI construction helpers for the instrument layout editor window."""

from __future__ import annotations

from typing import Dict

import tkinter as tk
from tkinter import ttk


class _LayoutEditorUIMixin:
    """Methods responsible purely for constructing and toggling UI widgets."""

    _style_entries: Dict[str, tk.StringVar]
    _remove_button: ttk.Button | None
    _preferred_min_combo: ttk.Combobox | None
    _preferred_max_combo: ttk.Combobox | None
    _candidate_min_combo: ttk.Combobox | None
    _candidate_max_combo: ttk.Combobox | None
    _add_hole_button: ttk.Button | None
    _remove_hole_button: ttk.Button | None
    _hole_entry: ttk.Entry | None
    _preview_frame: ttk.Frame | None
    _preview_toggle: ttk.Button | None
    _json_text: tk.Text | None
    _radius_entry: ttk.Entry

    def _build_header(self, parent: ttk.Frame) -> None:
        selector_frame = ttk.Frame(parent)
        selector_frame.grid(row=0, column=0, sticky="ew")
        selector_frame.columnconfigure(0, weight=1)

        ttk.Label(selector_frame, text="Instrument:").grid(row=0, column=0, sticky="w")
        button_bar = ttk.Frame(selector_frame)
        button_bar.grid(row=0, column=1, sticky="e")
        ttk.Button(button_bar, text="Add...", command=self._add_instrument).pack(side="left", padx=(4, 0))
        remove_button = ttk.Button(button_bar, text="Remove", command=self._remove_instrument)
        remove_button.pack(side="left", padx=(4, 0))
        self._remove_button = remove_button

        self._instrument_selector = ttk.Combobox(
            selector_frame,
            textvariable=self.instrument_var,
            state="readonly",
            width=22,
        )
        self._instrument_selector.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 8))
        self._instrument_selector.bind("<<ComboboxSelected>>", self._on_instrument_change)

        general = ttk.LabelFrame(parent, text="General")
        general.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        general.columnconfigure(1, weight=1)

        ttk.Label(general, text="Identifier:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        id_entry = ttk.Entry(general, textvariable=self._instrument_id_var)
        id_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        id_entry.bind("<FocusOut>", lambda _e: self._apply_instrument_identifier())
        id_entry.bind("<Return>", lambda _e: self._apply_instrument_identifier())

        ttk.Label(general, text="Display name:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        name_entry = ttk.Entry(general, textvariable=self._instrument_name_var)
        name_entry.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        name_entry.bind("<FocusOut>", lambda _e: self._apply_instrument_name())
        name_entry.bind("<Return>", lambda _e: self._apply_instrument_name())

        ttk.Label(general, text="Title:").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        title_entry = ttk.Entry(general, textvariable=self._title_var)
        title_entry.grid(row=2, column=1, sticky="ew", padx=4, pady=4)
        title_entry.bind("<FocusOut>", lambda _e: self._apply_title())
        title_entry.bind("<Return>", lambda _e: self._apply_title())

        ttk.Label(general, text="Canvas width:").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        width_spin = ttk.Spinbox(
            general,
            from_=10,
            to=2000,
            textvariable=self._canvas_width_var,
            width=8,
            increment=5,
        )
        width_spin.grid(row=3, column=1, sticky="w", padx=4, pady=4)
        width_spin.bind("<FocusOut>", lambda _e: self._apply_canvas_size())
        width_spin.bind("<Return>", lambda _e: self._apply_canvas_size())

        ttk.Label(general, text="Canvas height:").grid(row=4, column=0, sticky="w", padx=4, pady=4)
        height_spin = ttk.Spinbox(
            general,
            from_=10,
            to=2000,
            textvariable=self._canvas_height_var,
            width=8,
            increment=5,
        )
        height_spin.grid(row=4, column=1, sticky="w", padx=4, pady=4)
        height_spin.bind("<FocusOut>", lambda _e: self._apply_canvas_size())
        height_spin.bind("<Return>", lambda _e: self._apply_canvas_size())

        ttk.Label(general, text="Available range:").grid(row=5, column=0, sticky="w", padx=4, pady=4)
        candidate_frame = ttk.Frame(general)
        candidate_frame.grid(row=5, column=1, sticky="ew", padx=4, pady=4)
        candidate_frame.columnconfigure(0, weight=1)
        candidate_frame.columnconfigure(2, weight=1)
        candidate_min = ttk.Combobox(candidate_frame, textvariable=self._candidate_min_var, width=10)
        candidate_min.grid(row=0, column=0, sticky="w")
        candidate_min.bind("<<ComboboxSelected>>", lambda _e: self._apply_candidate_range())
        candidate_min.bind("<FocusOut>", lambda _e: self._apply_candidate_range())
        candidate_min.bind("<Return>", lambda _e: self._apply_candidate_range())
        ttk.Label(candidate_frame, text="to").grid(row=0, column=1, padx=4)
        candidate_max = ttk.Combobox(candidate_frame, textvariable=self._candidate_max_var, width=10)
        candidate_max.grid(row=0, column=2, sticky="w")
        candidate_max.bind("<<ComboboxSelected>>", lambda _e: self._apply_candidate_range())
        candidate_max.bind("<FocusOut>", lambda _e: self._apply_candidate_range())
        candidate_max.bind("<Return>", lambda _e: self._apply_candidate_range())
        self._candidate_min_combo = candidate_min
        self._candidate_max_combo = candidate_max

        ttk.Label(general, text="Preferred range:").grid(row=6, column=0, sticky="w", padx=4, pady=4)
        range_frame = ttk.Frame(general)
        range_frame.grid(row=6, column=1, sticky="ew", padx=4, pady=4)
        range_frame.columnconfigure(0, weight=1)
        range_frame.columnconfigure(2, weight=1)
        min_combo = ttk.Combobox(range_frame, textvariable=self._preferred_min_var, width=10, state="readonly")
        min_combo.grid(row=0, column=0, sticky="w")
        min_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_preferred_range())
        min_combo.bind("<FocusOut>", lambda _e: self._apply_preferred_range())
        ttk.Label(range_frame, text="to").grid(row=0, column=1, padx=4)
        max_combo = ttk.Combobox(range_frame, textvariable=self._preferred_max_var, width=10, state="readonly")
        max_combo.grid(row=0, column=2, sticky="w")
        max_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_preferred_range())
        max_combo.bind("<FocusOut>", lambda _e: self._apply_preferred_range())
        self._preferred_min_combo = min_combo
        self._preferred_max_combo = max_combo

    def _build_selection_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Selection")
        frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(1, weight=1)

        info_label = ttk.Label(frame, textvariable=self._selection_info_var, wraplength=220)
        info_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 6))

        ttk.Label(frame, text="Description:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        hole_entry = ttk.Entry(frame, textvariable=self._hole_identifier_var)
        hole_entry.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        hole_entry.bind("<Return>", lambda _e: self._apply_hole_identifier())
        hole_entry.bind("<FocusOut>", lambda _e: self._apply_hole_identifier())
        self._hole_entry = hole_entry

        ttk.Label(frame, text="X:").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        entry_x = ttk.Entry(frame, textvariable=self._selection_x_var)
        entry_x.grid(row=2, column=1, sticky="ew", padx=4, pady=4)
        entry_x.bind("<Return>", lambda _e: self._apply_selection_position())
        entry_x.bind("<FocusOut>", lambda _e: self._apply_selection_position())

        ttk.Label(frame, text="Y:").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        entry_y = ttk.Entry(frame, textvariable=self._selection_y_var)
        entry_y.grid(row=3, column=1, sticky="ew", padx=4, pady=4)
        entry_y.bind("<Return>", lambda _e: self._apply_selection_position())
        entry_y.bind("<FocusOut>", lambda _e: self._apply_selection_position())

        ttk.Label(frame, text="Radius:").grid(row=4, column=0, sticky="w", padx=4, pady=4)
        self._radius_entry = ttk.Entry(frame, textvariable=self._selection_radius_var)
        self._radius_entry.grid(row=4, column=1, sticky="ew", padx=4, pady=4)
        self._radius_entry.bind("<Return>", lambda _e: self._apply_selection_radius())
        self._radius_entry.bind("<FocusOut>", lambda _e: self._apply_selection_radius())

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=2, pady=(4, 2))
        add_button = ttk.Button(buttons, text="Add Hole", command=self._add_hole)
        add_button.pack(side="left", padx=2)
        remove_button = ttk.Button(buttons, text="Remove Hole", command=self._remove_selected_hole)
        remove_button.pack(side="left", padx=2)
        self._add_hole_button = add_button
        self._remove_hole_button = remove_button

        nudge_row = ttk.Frame(frame)
        nudge_row.grid(row=6, column=0, columnspan=2, pady=(4, 2))
        ttk.Button(nudge_row, text="←", width=2, command=lambda: self._nudge_selection(-1, 0)).pack(side="left", padx=2)
        ttk.Button(nudge_row, text="→", width=2, command=lambda: self._nudge_selection(1, 0)).pack(side="left", padx=2)
        ttk.Button(nudge_row, text="↑", width=2, command=lambda: self._nudge_selection(0, -1)).pack(side="left", padx=2)
        ttk.Button(nudge_row, text="↓", width=2, command=lambda: self._nudge_selection(0, 1)).pack(side="left", padx=2)

    def _build_style_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Style")
        frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(1, weight=1)

        self._style_entries = {}
        fields = [
            ("background_color", "Background"),
            ("outline_color", "Outline"),
            ("hole_outline_color", "Hole outline"),
            ("covered_fill_color", "Covered fill"),
        ]
        for row, (attr, label) in enumerate(fields):
            ttk.Label(frame, text=f"{label}:").grid(row=row, column=0, sticky="w", padx=4, pady=2)
            var = tk.StringVar(master=self)
            entry = ttk.Entry(frame, textvariable=var)
            entry.grid(row=row, column=1, sticky="ew", padx=4, pady=2)
            entry.bind("<FocusOut>", lambda _e, key=attr, var=var: self._apply_style_field(key, var.get()))
            entry.bind("<Return>", lambda _e, key=attr, var=var: self._apply_style_field(key, var.get()))
            self._style_entries[attr] = var

    def _build_export_panel(self) -> None:
        footer = ttk.Frame(self)
        footer.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=12, pady=(0, 12))
        footer.columnconfigure(0, weight=1)
        footer.rowconfigure(1, weight=1)

        button_row = ttk.Frame(footer)
        button_row.grid(row=0, column=0, sticky="ew")
        button_row.columnconfigure(0, weight=1)

        ttk.Button(button_row, text="Export Config...", command=self._save_json).pack(side="left", padx=4)
        ttk.Button(button_row, text="Import Config...", command=self._load_json).pack(side="left", padx=4)
        ttk.Button(button_row, text="Export Instrument...", command=self._export_instrument).pack(side="left", padx=4)
        ttk.Button(button_row, text="Import Instrument...", command=self._import_instrument).pack(side="left", padx=4)
        ttk.Label(button_row, textvariable=self._status_var, style="Hint.TLabel").pack(side="left", padx=8)

        toggle = ttk.Button(button_row, text="Show Config Preview", command=self._toggle_preview)
        toggle.pack(side="right", padx=(0, 4))
        self._preview_toggle = toggle

        action_row = ttk.Frame(button_row)
        action_row.pack(side="right")
        ttk.Button(action_row, text="Cancel", command=self._cancel_edits).pack(side="right", padx=(0, 4))
        ttk.Button(action_row, text="Done", command=self._apply_and_close).pack(side="right", padx=(0, 4))

        preview_frame = ttk.Frame(footer)
        preview_frame.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self._json_text = tk.Text(preview_frame, height=10, wrap="word")
        self._json_text.grid(row=0, column=0, sticky="nsew")
        self._json_text.configure(state="disabled", font=("TkFixedFont", 9))

        scrollbar = ttk.Scrollbar(preview_frame, orient="vertical", command=self._json_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._json_text.configure(yscrollcommand=scrollbar.set)

        self._preview_frame = preview_frame
        self._preview_visible = False
        self._hide_preview()

    def _toggle_preview(self) -> None:
        if self._preview_visible:
            self._hide_preview()
        else:
            self._show_preview()

    def _show_preview(self) -> None:
        frame = self._preview_frame
        if frame is None:
            return
        frame.grid()
        self._preview_visible = True
        toggle = self._preview_toggle
        if toggle is not None:
            toggle.configure(text="Hide Config Preview")

    def _hide_preview(self) -> None:
        frame = self._preview_frame
        if frame is None:
            return
        frame.grid_remove()
        self._preview_visible = False
        toggle = self._preview_toggle
        if toggle is not None:
            toggle.configure(text="Show Config Preview")
