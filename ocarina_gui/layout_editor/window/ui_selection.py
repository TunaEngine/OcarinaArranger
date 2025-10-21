"""Selection panel helpers for the layout editor window."""

from __future__ import annotations

from shared.ttk import ttk


class _LayoutEditorSelectionMixin:
    """Builds the selection editor controls."""

    _hole_entry: ttk.Entry | None
    _width_entry: ttk.Entry | None
    _height_entry: ttk.Entry | None
    _radius_entry: ttk.Entry
    _add_hole_button: ttk.Button | None
    _add_windway_button: ttk.Button | None
    _remove_element_button: ttk.Button | None
    _hole_subhole_check: ttk.Checkbutton | None

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

        subhole_check = ttk.Checkbutton(
            frame,
            text="Subhole",
            variable=self._hole_subhole_var,
            command=self._apply_subhole_flag,
        )
        subhole_check.grid(row=5, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 4))
        self._hole_subhole_check = subhole_check

        ttk.Label(frame, text="Width:").grid(row=6, column=0, sticky="w", padx=4, pady=4)
        width_entry = ttk.Entry(frame, textvariable=self._selection_width_var)
        width_entry.grid(row=6, column=1, sticky="ew", padx=4, pady=4)
        width_entry.bind("<Return>", lambda _e: self._apply_windway_size())
        width_entry.bind("<FocusOut>", lambda _e: self._apply_windway_size())
        self._width_entry = width_entry

        ttk.Label(frame, text="Height:").grid(row=7, column=0, sticky="w", padx=4, pady=4)
        height_entry = ttk.Entry(frame, textvariable=self._selection_height_var)
        height_entry.grid(row=7, column=1, sticky="ew", padx=4, pady=4)
        height_entry.bind("<Return>", lambda _e: self._apply_windway_size())
        height_entry.bind("<FocusOut>", lambda _e: self._apply_windway_size())
        self._height_entry = height_entry

        buttons = ttk.Frame(frame)
        buttons.grid(row=8, column=0, columnspan=2, pady=(4, 2))
        add_hole_button = ttk.Button(buttons, text="Add Hole", command=self._add_hole)
        add_hole_button.pack(side="left", padx=2)
        add_windway_button = ttk.Button(
            buttons, text="Add Windway", command=self._add_windway
        )
        add_windway_button.pack(side="left", padx=2)
        remove_button = ttk.Button(
            buttons, text="Remove", command=self._remove_selected_element
        )
        remove_button.pack(side="left", padx=2)
        self._add_hole_button = add_hole_button
        self._add_windway_button = add_windway_button
        self._remove_element_button = remove_button

        nudge_row = ttk.Frame(frame)
        nudge_row.grid(row=9, column=0, columnspan=2, pady=(4, 2))
        ttk.Button(nudge_row, text="←", width=2, command=lambda: self._nudge_selection(-1, 0)).pack(
            side="left", padx=2
        )
        ttk.Button(nudge_row, text="→", width=2, command=lambda: self._nudge_selection(1, 0)).pack(
            side="left", padx=2
        )
        ttk.Button(nudge_row, text="↑", width=2, command=lambda: self._nudge_selection(0, -1)).pack(
            side="left", padx=2
        )
        ttk.Button(nudge_row, text="↓", width=2, command=lambda: self._nudge_selection(0, 1)).pack(
            side="left", padx=2
        )
