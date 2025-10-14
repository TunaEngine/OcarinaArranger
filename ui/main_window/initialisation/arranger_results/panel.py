"""Builder for arranger v2 results panel widgets."""

from shared.ttk import ttk


def build_arranger_results_panel(app, parent: ttk.Frame, pad: int) -> ttk.LabelFrame:
    """Create the arranger results section and register UI bindings."""

    section = ttk.LabelFrame(
        parent,
        text="Arrangement Details",
        padding=pad,
        style="Panel.TLabelframe",
    )
    section.columnconfigure(0, weight=1)
    section.rowconfigure(0, weight=1)

    notebook = ttk.Notebook(section)
    notebook.grid(row=0, column=0, sticky="nsew")
    app._register_arranger_results_notebook(notebook)

    summary_tab = ttk.Frame(notebook, padding=pad)
    summary_tab.columnconfigure(0, weight=1)
    notebook.add(summary_tab, text="Summary")

    ttk.Label(
        summary_tab,
        textvariable=app.arranger_summary_status,
        wraplength=320,
        justify="left",
    ).grid(row=0, column=0, sticky="w")

    progress_frame = ttk.Frame(summary_tab)
    progress_frame.columnconfigure(0, weight=1)
    progress_frame.grid(row=1, column=0, sticky="ew", pady=(pad // 2, 0))
    progress = ttk.Progressbar(progress_frame, mode="indeterminate")
    progress.grid(row=0, column=0, sticky="ew")
    app._register_arranger_progress_widgets(progress_frame, progress)
    app._set_arranger_results_loading(False, restore_status=False)

    difficulty_group = ttk.LabelFrame(
        summary_tab,
        text="Difficulty metrics",
        padding=pad,
        style="Panel.TLabelframe",
    )
    difficulty_group.grid(row=2, column=0, sticky="ew", pady=(pad, 0))
    difficulty_group.columnconfigure(1, weight=1)
    for row_index, (label, variable) in enumerate(
        (
            ("Transposition", app.arranger_summary_transposition),
            ("Easy", app.arranger_summary_easy),
            ("Medium", app.arranger_summary_medium),
            ("Hard", app.arranger_summary_hard),
            ("Very hard", app.arranger_summary_very_hard),
            ("Tessitura distance", app.arranger_summary_tessitura),
            ("Starting difficulty", app.arranger_summary_starting),
            ("Final difficulty", app.arranger_summary_final),
            ("Difficulty threshold", app.arranger_summary_threshold),
            ("Δ difficulty", app.arranger_summary_delta),
        )
    ):
        ttk.Label(difficulty_group, text=label).grid(
            row=row_index,
            column=0,
            sticky="w",
            pady=(0, 2),
        )
        ttk.Label(difficulty_group, textvariable=variable).grid(
            row=row_index,
            column=1,
            sticky="e",
        )

    edits_group = ttk.LabelFrame(
        summary_tab,
        text="Salvage edits",
        padding=pad,
        style="Panel.TLabelframe",
    )
    edits_group.grid(row=3, column=0, sticky="ew", pady=(pad, 0))
    edits_group.columnconfigure(1, weight=1)
    for row_index, (label, variable) in enumerate(
        (
            ("Total", app.arranger_edits_total),
            ("Octave shifts", app.arranger_edits_octave),
            ("Rhythm edits", app.arranger_edits_rhythm),
            ("Substitutions", app.arranger_edits_substitution),
        )
    ):
        ttk.Label(edits_group, text=label).grid(
            row=row_index,
            column=0,
            sticky="w",
            pady=(0, 2),
        )
        ttk.Label(edits_group, textvariable=variable).grid(
            row=row_index,
            column=1,
            sticky="e",
        )

    ttk.Label(summary_tab, text="Applied steps").grid(
        row=4,
        column=0,
        sticky="w",
        pady=(pad, 0),
    )
    ttk.Label(
        summary_tab,
        textvariable=app.arranger_applied_steps,
        wraplength=320,
        justify="left",
    ).grid(row=5, column=0, sticky="w")

    explanations_tab = ttk.Frame(notebook, padding=pad)
    explanations_tab.columnconfigure(0, weight=1)
    explanations_tab.rowconfigure(1, weight=1)
    notebook.add(explanations_tab, text="Explanations")

    filter_row = ttk.Frame(explanations_tab)
    filter_row.grid(row=0, column=0, sticky="ew")
    ttk.Label(filter_row, text="Filter by reason code").grid(
        row=0, column=0, sticky="w"
    )
    reason_filter = ttk.Combobox(
        filter_row,
        textvariable=app.arranger_explanation_filter,
        width=28,
    )
    reason_filter.grid(row=0, column=1, sticky="e", padx=(pad // 2, 0))
    app._register_arranger_explanation_filter(reason_filter)

    tree_container = ttk.Frame(explanations_tab)
    tree_container.grid(row=1, column=0, sticky="nsew")
    tree_container.columnconfigure(0, weight=1)
    tree_container.rowconfigure(0, weight=1)
    columns = ("bar", "action", "reason", "delta", "notes")
    tree = ttk.Treeview(
        tree_container,
        columns=columns,
        show="headings",
        selectmode="browse",
        height=8,
    )
    tree.heading("bar", text="Bar")
    tree.heading("action", text="Action")
    tree.heading("reason", text="Reason")
    tree.heading("delta", text="Δ difficulty")
    tree.heading("notes", text="Notes")
    tree.column("bar", width=40, anchor="center", stretch=False)
    tree.column("action", width=120, anchor="w", stretch=False)
    tree.column("reason", width=180, anchor="w", stretch=False)
    tree.column("delta", width=100, anchor="e", stretch=False)
    tree.column("notes", width=140, anchor="center", stretch=False)
    tree.grid(row=0, column=0, sticky="nsew")
    scrollbar = ttk.Scrollbar(
        tree_container, orient="vertical", command=tree.yview
    )
    scrollbar.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=scrollbar.set)
    app._register_arranger_explanations_tree(tree)

    ttk.Label(
        explanations_tab,
        textvariable=app.arranger_explanation_detail,
        style="Hint.TLabel",
        wraplength=320,
        justify="left",
        anchor="w",
    ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(pad, 0))

    telemetry_tab = ttk.Frame(notebook, padding=pad)
    telemetry_tab.columnconfigure(0, weight=1)
    telemetry_tab.rowconfigure(0, weight=1)
    notebook.add(telemetry_tab, text="Telemetry")

    telemetry_container = ttk.Frame(telemetry_tab)
    telemetry_container.grid(row=0, column=0, sticky="nsew")
    telemetry_container.columnconfigure(0, weight=1)
    app._register_arranger_telemetry_container(telemetry_container)

    return section


__all__ = [
    "ArrangerResultsMixin",
    "build_arranger_results_panel",
]
