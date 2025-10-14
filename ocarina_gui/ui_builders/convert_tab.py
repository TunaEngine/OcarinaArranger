"""Builder for the "Convert" tab."""

from __future__ import annotations

from shared.ttk import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - used for type checkers only
    from ..app import App

from ui.main_window.initialisation.arranger_results import build_arranger_results_panel


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

    left_column = ttk.Frame(container)
    left_column.grid(row=0, column=0, sticky="nsew", padx=(0, pad))
    left_column.columnconfigure(0, weight=1)
    left_column.rowconfigure(0, weight=0)
    left_column.rowconfigure(1, weight=0)
    left_column.rowconfigure(2, weight=1)

    right_column = ttk.Frame(container)
    right_column.grid(row=0, column=1, sticky="nsew")
    right_column.columnconfigure(0, weight=1)

    # 1. Instrument & Range
    instrument_section = ttk.LabelFrame(left_column, text="1. Instrument & Range", padding=pad, style="Panel.TLabelframe")
    instrument_section.grid(row=0, column=0, sticky="nsew")
    instrument_section.columnconfigure(1, weight=1)

    ttk.Label(instrument_section, text="Instrument").grid(row=0, column=0, sticky="w")
    instrument_combo = ttk.Combobox(
        instrument_section,
        textvariable=app.convert_instrument_var,
        state="readonly",
        width=24,
    )
    instrument_combo.grid(row=0, column=1, sticky="ew")
    app._register_convert_instrument_combo(instrument_combo)

    ttk.Label(
        instrument_section,
        text="Select the target ocarina type.",
        style="Hint.TLabel",
        wraplength=280,
    ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

    ttk.Label(instrument_section, text="Desired Range").grid(row=2, column=0, sticky="w", pady=(pad, 0))
    range_frame = ttk.Frame(instrument_section)
    range_frame.grid(row=2, column=1, sticky="ew", pady=(pad, 0))
    range_frame.columnconfigure(0, weight=1)
    range_frame.columnconfigure(2, weight=1)

    range_min_combo = ttk.Combobox(range_frame, width=8, textvariable=app.range_min)
    range_min_combo.grid(row=0, column=0, sticky="ew")
    ttk.Label(range_frame, text="to").grid(row=0, column=1, padx=(pad // 2, pad // 2))
    range_max_combo = ttk.Combobox(range_frame, width=8, textvariable=app.range_max)
    range_max_combo.grid(row=0, column=2, sticky="ew")
    app._register_range_comboboxes(range_min_combo, range_max_combo)

    ttk.Label(
        instrument_section,
        text="Automatically set based on instrument, or override manually.",
        style="Hint.TLabel",
        wraplength=280,
    ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))

    # 2. Arranger Version
    mode_section = ttk.LabelFrame(
        left_column,
        text="2. Arranger Version",
        padding=pad,
        style="Panel.TLabelframe",
    )
    mode_section.grid(row=1, column=0, sticky="nsew", pady=(pad, 0))
    mode_section.columnconfigure(0, weight=1)
    mode_section.rowconfigure(2, weight=1)

    ttk.Label(mode_section, text="Select which arranger experience to use.").grid(
        row=0, column=0, sticky="w"
    )
    mode_selector = ttk.Frame(mode_section)
    mode_selector.grid(row=1, column=0, sticky="w", pady=(4, pad))
    for index, (value, label) in enumerate(
        (("classic", "Classic v1"), ("best_effort", "Best-Effort v2"))
    ):
        padding_x = (0, pad) if index == 0 else (0, 0)
        ttk.Radiobutton(
            mode_selector,
            text=label,
            variable=app.arranger_mode,
            value=value,
            style="Segmented.TRadiobutton",
        ).pack(side="left", padx=padding_x)

    mode_stack = ttk.Frame(mode_section)
    mode_stack.grid(row=2, column=0, sticky="nsew")
    mode_stack.columnconfigure(0, weight=1)
    mode_stack.rowconfigure(0, weight=1)

    classic_panel = ttk.Frame(mode_stack)
    classic_panel.grid(row=0, column=0, sticky="nsew")
    classic_panel.columnconfigure(0, weight=1)

    classic_section = ttk.LabelFrame(
        classic_panel,
        text="Classic Arranger Algorithm",
        padding=pad,
        style="Panel.TLabelframe",
    )
    classic_section.grid(row=0, column=0, sticky="nsew")
    classic_section.columnconfigure(0, weight=1)

    ttk.Label(classic_section, text="Target Mode").grid(row=0, column=0, sticky="w")
    target_mode_frame = ttk.Frame(classic_section)
    target_mode_frame.grid(row=1, column=0, sticky="w", pady=(4, pad))
    ttk.Radiobutton(
        target_mode_frame,
        text="Auto",
        variable=app.prefer_mode,
        value="auto",
    ).pack(side="left", padx=(0, pad))
    ttk.Radiobutton(
        target_mode_frame,
        text="Force C Major",
        variable=app.prefer_mode,
        value="major",
    ).pack(side="left", padx=(0, pad))
    ttk.Radiobutton(
        target_mode_frame,
        text="Force A Minor",
        variable=app.prefer_mode,
        value="minor",
    ).pack(side="left")

    preferences_frame = ttk.Frame(classic_section)
    preferences_frame.grid(row=2, column=0, sticky="w", pady=(0, pad))
    ttk.Checkbutton(
        preferences_frame,
        text="Prefer flats for accidentals",
        variable=app.prefer_flats,
    ).pack(anchor="w")
    ttk.Checkbutton(
        preferences_frame,
        text="Collapse chords to single melody line",
        variable=app.collapse_chords,
    ).pack(anchor="w", pady=(4, 0))
    ttk.Checkbutton(
        preferences_frame,
        text="Favor lower register (drop notes by octave when safe)",
        variable=app.favor_lower,
    ).pack(anchor="w", pady=(4, 0))

    manual_frame = ttk.Frame(classic_section)
    manual_frame.grid(row=3, column=0, sticky="w")
    ttk.Label(manual_frame, text="Manual transpose:").grid(row=0, column=0, sticky="w")
    spin = ttk.Spinbox(
        manual_frame, from_=-12, to=12, width=4, textvariable=app.transpose_offset
    )
    spin.grid(row=0, column=1, padx=(pad // 2, pad // 2))
    app._register_transpose_spinbox(spin)
    ttk.Label(manual_frame, text="semitones").grid(row=0, column=2, sticky="w")

    ttk.Label(
        classic_section,
        text="Apply an additional transposition after the automatic arrangement.",
        style="Hint.TLabel",
        wraplength=360,
    ).grid(row=4, column=0, sticky="w", pady=(4, 0))

    best_effort_panel = ttk.Frame(mode_stack)
    best_effort_panel.columnconfigure(0, weight=1)

    best_effort_section = ttk.LabelFrame(
        best_effort_panel,
        text="Best-Effort Arranger Preview",
        padding=pad,
        style="Panel.TLabelframe",
    )
    best_effort_section.grid(row=0, column=0, sticky="nsew")
    best_effort_section.columnconfigure(0, weight=1)
    best_effort_section.rowconfigure(0, weight=0)
    best_effort_section.rowconfigure(1, weight=1)
    best_effort_section.rowconfigure(2, weight=0)
    best_effort_section.rowconfigure(3, weight=0)

    target_section = ttk.LabelFrame(
        best_effort_section,
        text="Target Instruments",
        padding=pad,
        style="Panel.TLabelframe",
    )
    target_section.grid(row=0, column=0, sticky="nsew")
    target_section.columnconfigure(0, weight=1)
    target_section.rowconfigure(2, weight=1)

    ttk.Label(
        target_section,
        text="Choose how arranger v2 selects instruments for comparison.",
        style="Hint.TLabel",
        wraplength=360,
    ).grid(row=0, column=0, sticky="w")

    strategy_frame = ttk.Frame(target_section)
    strategy_frame.grid(row=1, column=0, sticky="w", pady=(4, pad))
    strategy_options = (
        ("current", "Current instrument only"),
        ("starred-best", "Starred instruments (pick best)"),
    )
    app._arranger_strategy_buttons = {}
    for index, (value, label) in enumerate(strategy_options):
        button = ttk.Radiobutton(
            strategy_frame,
            text=label,
            variable=app.arranger_strategy,
            value=value,
            style="Segmented.TRadiobutton",
        )
        button.pack(side="left", padx=(0, pad if index == 0 else 0))
        app._arranger_strategy_buttons[value] = button

    starred_section = ttk.Frame(target_section)
    starred_section.grid(row=2, column=0, sticky="nsew")
    starred_section.columnconfigure(0, weight=1)
    ttk.Label(
        starred_section,
        text="Star instruments to include them when using the starred strategy.",
        style="Hint.TLabel",
        wraplength=360,
    ).grid(row=0, column=0, sticky="w")
    starred_list = ttk.Frame(starred_section)
    starred_list.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
    starred_section.rowconfigure(1, weight=1)
    app._register_starred_container(starred_list)

    summary_section = ttk.LabelFrame(
        best_effort_section,
        text="Arrangement Summary",
        padding=pad,
        style="Panel.TLabelframe",
    )
    summary_section.grid(row=1, column=0, sticky="nsew", pady=(pad, 0))
    summary_section.columnconfigure(0, weight=1)
    summary_section.rowconfigure(0, weight=1)
    summary_container = ttk.Frame(summary_section)
    summary_container.grid(row=0, column=0, sticky="nsew")
    app._register_arranger_summary_container(summary_container)

    advanced_toggle = ttk.Frame(best_effort_section)
    advanced_toggle.grid(row=2, column=0, sticky="ew", pady=(pad, 0))
    advanced_toggle.columnconfigure(0, weight=1)
    ttk.Checkbutton(
        advanced_toggle,
        text="Show advanced arranger controls",
        variable=app.arranger_show_advanced,
    ).grid(row=0, column=0, sticky="w")

    advanced_section = ttk.LabelFrame(
        best_effort_section,
        text="Advanced Settings",
        padding=pad,
        style="Panel.TLabelframe",
    )
    advanced_section.grid(row=3, column=0, sticky="nsew", pady=(pad, 0))
    advanced_section.columnconfigure(0, weight=1)

    ttk.Checkbutton(
        advanced_section,
        text="Enable DP-with-slack (preview)",
        variable=app.arranger_dp_slack,
    ).grid(row=0, column=0, sticky="w")
    ttk.Label(
        advanced_section,
        text="Uses the experimental octave-folding dynamic program; defaults to off.",
        style="Hint.TLabel",
        wraplength=360,
    ).grid(row=1, column=0, sticky="w", pady=(4, pad))

    budgets_group = ttk.LabelFrame(
        advanced_section,
        text="Salvage Edit Budgets",
        padding=pad,
        style="Panel.TLabelframe",
    )
    budgets_group.grid(row=2, column=0, sticky="nsew")
    budgets_group.columnconfigure(1, weight=1)

    budget_rows = (
        ("Octave shifts", app.arranger_budget_octave, "per span"),
        ("Rhythm simplifications", app.arranger_budget_rhythm, "per span"),
        ("Substitutions", app.arranger_budget_substitution, "per span"),
        ("Total edit steps", app.arranger_budget_total, "minimum 1"),
    )
    for idx, (label, variable, suffix) in enumerate(budget_rows):
        ttk.Label(budgets_group, text=label).grid(row=idx, column=0, sticky="w", pady=(0, 2))
        spin = ttk.Spinbox(
            budgets_group,
            from_=0,
            to=9,
            width=4,
            textvariable=variable,
        )
        if label == "Total edit steps":
            spin.configure(from_=1, to=12)
        spin.grid(row=idx, column=1, sticky="w", padx=(pad // 2, pad // 2))
        ttk.Label(budgets_group, text=suffix, style="Hint.TLabel").grid(
            row=idx,
            column=2,
            sticky="w",
        )

    ttk.Button(
        advanced_section,
        text="Reset budgets to defaults",
        command=app.reset_arranger_budgets,
    ).grid(row=3, column=0, sticky="w", pady=(pad, 0))

    app._register_arranger_advanced_frame(advanced_section)

    right_column.rowconfigure(0, weight=1)
    right_column.rowconfigure(1, weight=0)
    right_column.rowconfigure(2, weight=0)

    results_section = build_arranger_results_panel(app, right_column, pad)
    results_section.grid(row=0, column=0, sticky="nsew")
    app._arranger_results_section = results_section

    # Import & Export
    import_section = ttk.LabelFrame(
        right_column, text="Import & Export", padding=pad, style="Panel.TLabelframe"
    )
    import_section.grid(row=1, column=0, sticky="nsew")
    import_section.columnconfigure(0, weight=1)

    ttk.Label(import_section, text="Input MusicXML/MXL").grid(row=0, column=0, sticky="w")
    path_row = ttk.Frame(import_section)
    path_row.grid(row=1, column=0, sticky="ew", pady=(4, pad))
    path_row.columnconfigure(0, weight=1)
    ttk.Entry(path_row, textvariable=app.input_path).grid(row=0, column=0, sticky="ew")
    ttk.Button(path_row, text="Browse...", command=app.browse).grid(row=0, column=1, padx=(pad // 2, 0))

    actions_frame = ttk.Frame(import_section)
    actions_frame.grid(row=2, column=0, sticky="ew")
    actions_frame.columnconfigure(0, weight=1)
    actions_frame.columnconfigure(1, weight=1)

    reimport_button = ttk.Button(
        actions_frame,
        text="Re-import and Arrange",
        command=app.reimport_and_arrange,
    )
    reimport_button.grid(row=0, column=0, sticky="ew", padx=(0, pad // 2))
    app._register_reimport_button(reimport_button)

    ttk.Button(
        actions_frame,
        text="Convert and Save...",
        command=app.convert,
    ).grid(row=0, column=1, sticky="ew")

    ttk.Label(
        import_section,
        textvariable=app.status,
        anchor="center",
        style="Hint.TLabel",
    ).grid(row=3, column=0, sticky="ew", pady=(pad, 0))

    # Playback
    playback_section = ttk.LabelFrame(
        right_column, text="Playback", padding=pad, style="Panel.TLabelframe"
    )
    playback_section.grid(row=2, column=0, sticky="nsew", pady=(pad, 0))
    playback_section.columnconfigure(0, weight=1)

    playback_buttons = ttk.Frame(playback_section)
    playback_buttons.grid(row=0, column=0, sticky="ew")
    playback_buttons.columnconfigure(0, weight=1)
    playback_buttons.columnconfigure(1, weight=1)

    ttk.Button(
        playback_buttons,
        text="Play Original",
        command=app.play_original,
    ).grid(row=0, column=0, sticky="ew", padx=(0, pad // 2))

    ttk.Button(
        playback_buttons,
        text="Play Arranged",
        command=app.play_arranged,
    ).grid(row=0, column=1, sticky="ew", padx=(pad // 2, 0))

    app._arranger_mode_frames = {
        "classic": {"left": classic_panel},
        "best_effort": {"left": best_effort_panel},
    }

    def _update_arranger_mode_layout() -> None:
        mode = (app.arranger_mode.get() or "classic").strip().lower()
        classic_frame = app._arranger_mode_frames["classic"]["left"]
        best_effort_frame = app._arranger_mode_frames["best_effort"]["left"]
        if mode == "best_effort":
            classic_frame.grid_remove()
            best_effort_frame.grid(row=0, column=0, sticky="nsew")
            results_section.grid(row=0, column=0, sticky="nsew")
            import_section.grid_configure(pady=(pad, 0))
        else:
            best_effort_frame.grid_remove()
            classic_frame.grid(row=0, column=0, sticky="nsew")
            results_section.grid_remove()
            import_section.grid_configure(pady=(0, 0))
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
    
    # Apply Panel styles after widgets are created to ensure proper theming
    def _ensure_convert_tab_panel_styles():
        from shared.tk_style import apply_theme_to_panel_widgets
        try:
            apply_theme_to_panel_widgets(app)
        except Exception:
            pass
    
    # Schedule Panel style application after widget creation
    app.after(1, _ensure_convert_tab_panel_styles)
