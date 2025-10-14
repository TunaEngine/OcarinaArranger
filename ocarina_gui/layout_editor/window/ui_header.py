"""Header UI construction helpers for the layout editor window."""

from __future__ import annotations

from typing import Callable

import tkinter as tk
from shared.ttk import ttk


class _LayoutEditorHeaderMixin:
    """Builds and manages the instrument selector and general settings UI."""

    _remove_button: ttk.Button | None
    _instrument_selector: ttk.Combobox
    _preferred_min_combo: ttk.Combobox | None
    _preferred_max_combo: ttk.Combobox | None
    _candidate_min_combo: ttk.Combobox | None
    _candidate_max_combo: ttk.Combobox | None
    _allow_half_var: tk.BooleanVar | None
    _allow_half_check: ttk.Checkbutton | None
    _on_half_toggle: Callable[[], None] | None

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

        allow_half_var = getattr(self, "_allow_half_var", None)
        if allow_half_var is not None:
            check = ttk.Checkbutton(
                general,
                text="Allow half-holes",
                variable=allow_half_var,
                command=self._handle_half_toggle,
            )
            check.grid(row=7, column=0, columnspan=2, sticky="w", padx=4, pady=4)
            self._allow_half_check = check

    def _handle_half_toggle(self) -> None:
        allow_half_var = getattr(self, "_allow_half_var", None)
        viewmodel = getattr(self, "_viewmodel", None)
        instrument_state = getattr(viewmodel, "state", None)
        instrument_id = getattr(instrument_state, "instrument_id", "")

        viewmodel = getattr(self, "_viewmodel", None)
        if allow_half_var is not None and instrument_id and viewmodel is not None:
            try:
                enabled = bool(allow_half_var.get())
            except Exception:
                enabled = False
            viewmodel.set_half_hole_support(enabled)
            self._refresh_state()

        callback = getattr(self, "_on_half_toggle", None)
        if callback is not None:
            callback()
