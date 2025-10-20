"""Builder for the GP arranger tuning panel shown on the Convert tab."""

from __future__ import annotations

import tkinter as tk

from shared.ttk import ttk

from viewmodels.arranger_models import (
    GP_APPLY_LABELS,
    GP_APPLY_RANKED,
    GP_APPLY_SESSION_WINNER,
)

from ui.widgets import attach_tooltip

from .convert_gp_troubleshooting import add_troubleshooting_button


__all__ = ["build_gp_panel"]


def build_gp_panel(app, mode_stack: ttk.Frame, pad: int) -> ttk.Frame:
    gp_panel = ttk.Frame(mode_stack)
    gp_panel.columnconfigure(0, weight=1)

    gp_section = ttk.LabelFrame(
        gp_panel,
        text="GP Arranger Preview",
        padding=pad,
        style="Panel.TLabelframe",
    )
    gp_section.grid(row=0, column=0, sticky="nsew")
    gp_section.columnconfigure(0, weight=1)

    ttk.Label(
        gp_section,
        text=(
            "Runs an experimental genetic-programming search to suggest a "
            "playable arrangement for the selected instrument."
        ),
        style="Hint.TLabel",
        wraplength=360,
    ).grid(row=0, column=0, sticky="w")

    add_troubleshooting_button(gp_section, pad)

    gp_config = ttk.Frame(gp_section)
    gp_config.grid(row=2, column=0, sticky="nsew", pady=(pad, 0))
    for column in range(3):
        gp_config.columnconfigure(column * 2, weight=0)
        gp_config.columnconfigure(column * 2 + 1, weight=1)

    ttk.Label(gp_config, text="Generations").grid(row=0, column=0, sticky="w")
    generations_spin = ttk.Spinbox(
        gp_config,
        from_=1,
        to=250,
        width=4,
        textvariable=app.arranger_gp_generations,
    )
    generations_spin.grid(row=0, column=1, sticky="w", padx=(pad // 2, pad))
    attach_tooltip(
        generations_spin,
        "Number of evolutionary iterations to run before programs are ranked.",
    )

    ttk.Label(gp_config, text="Population").grid(row=0, column=2, sticky="w")
    population_spin = ttk.Spinbox(
        gp_config,
        from_=1,
        to=640,
        width=4,
        textvariable=app.arranger_gp_population,
    )
    population_spin.grid(row=0, column=3, sticky="w", padx=(pad // 2, pad))
    attach_tooltip(
        population_spin,
        "Number of candidate programs maintained in each generation.",
    )

    ttk.Label(gp_config, text="Time budget (s)").grid(row=0, column=4, sticky="w")
    time_budget_entry = ttk.Entry(
        gp_config,
        width=6,
        textvariable=app.arranger_gp_time_budget,
    )
    time_budget_entry.grid(row=0, column=5, sticky="w")
    attach_tooltip(
        time_budget_entry,
        "Optional wall-clock limit in seconds; the GP search stops early when reached.",
    )

    apply_container = ttk.Frame(gp_section)
    apply_container.grid(row=3, column=0, sticky="w", pady=(pad // 2, 0))
    apply_container.columnconfigure(1, weight=1)
    ttk.Label(apply_container, text="Apply program").grid(row=0, column=0, sticky="w")
    apply_frame = ttk.Frame(apply_container)
    apply_frame.grid(row=0, column=1, sticky="w", padx=(pad // 2, 0))
    apply_frame.columnconfigure(0, weight=0)
    apply_frame.columnconfigure(1, weight=0)
    ranked_radio = ttk.Radiobutton(
        apply_frame,
        text=GP_APPLY_LABELS[GP_APPLY_RANKED],
        value=GP_APPLY_RANKED,
        variable=app.arranger_gp_apply_preference,
    )
    ranked_radio.grid(row=0, column=0, sticky="w", padx=(0, pad))
    attach_tooltip(
        ranked_radio,
        "Preview the candidate chosen after scoring. Try this option first before diving into advanced settings.",
    )
    winner_radio = ttk.Radiobutton(
        apply_frame,
        text=GP_APPLY_LABELS[GP_APPLY_SESSION_WINNER],
        value=GP_APPLY_SESSION_WINNER,
        variable=app.arranger_gp_apply_preference,
    )
    winner_radio.grid(row=0, column=1, sticky="w")
    attach_tooltip(
        winner_radio,
        "Preview the raw GP session winner even if scoring prefers another program (default).",
    )

    warning_var = getattr(app, "arranger_gp_warning", None)
    if warning_var is None:
        warning_var = tk.StringVar(master=gp_section, value="")
        setattr(app, "arranger_gp_warning", warning_var)

    warning_label = ttk.Label(
        gp_section,
        textvariable=warning_var,
        style="Hint.TLabel",
        wraplength=360,
        justify="left",
    )
    warning_label.grid(row=4, column=0, sticky="w", pady=(pad // 2, 0))

    advanced_toggle = ttk.Frame(gp_section)
    advanced_toggle.grid(row=5, column=0, sticky="ew", pady=(pad, 0))
    advanced_toggle.columnconfigure(0, weight=1)
    ttk.Checkbutton(
        advanced_toggle,
        text="Show advanced arranger controls",
        variable=app.arranger_show_advanced,
    ).grid(row=0, column=0, sticky="w")

    advanced_section = ttk.LabelFrame(
        gp_section,
        text="Advanced Settings",
        padding=pad,
        style="Panel.TLabelframe",
    )
    advanced_section.grid(row=6, column=0, sticky="nsew", pady=(pad, 0))
    gp_section.rowconfigure(6, weight=1)
    advanced_section.columnconfigure(0, weight=1)
    advanced_section.rowconfigure(1, weight=1)
    advanced_section.rowconfigure(2, weight=1)

    session_group = ttk.LabelFrame(
        advanced_section,
        text="Session tuning",
        padding=pad,
        style="Panel.TLabelframe",
    )
    session_group.grid(row=0, column=0, sticky="nsew")
    session_group.columnconfigure(1, weight=1)
    session_group.columnconfigure(3, weight=1)

    ttk.Label(session_group, text="Archive size").grid(row=0, column=0, sticky="w")
    archive_spin = ttk.Spinbox(
        session_group,
        from_=1,
        to=640,
        width=4,
        textvariable=app.arranger_gp_archive_size,
    )
    archive_spin.grid(row=0, column=1, sticky="w", padx=(pad // 2, pad))
    attach_tooltip(
        archive_spin,
        "Number of top-performing programs preserved between generations.",
    )

    ttk.Label(session_group, text="Random programs").grid(
        row=0, column=2, sticky="w"
    )
    random_programs_spin = ttk.Spinbox(
        session_group,
        from_=0,
        to=640,
        width=4,
        textvariable=app.arranger_gp_random_programs,
    )
    random_programs_spin.grid(row=0, column=3, sticky="w")
    attach_tooltip(
        random_programs_spin,
        "Fresh random programs injected each generation to keep exploration diverse.",
    )

    ttk.Label(session_group, text="Crossover rate").grid(row=1, column=0, sticky="w")
    crossover_spin = ttk.Spinbox(
        session_group,
        from_=0.0,
        to=1.0,
        increment=0.05,
        width=5,
        textvariable=app.arranger_gp_crossover,
    )
    crossover_spin.grid(row=1, column=1, sticky="w", padx=(pad // 2, pad))
    attach_tooltip(
        crossover_spin,
        "Probability that two parent programs exchange operations during breeding.",
    )

    ttk.Label(session_group, text="Mutation rate").grid(row=1, column=2, sticky="w")
    mutation_spin = ttk.Spinbox(
        session_group,
        from_=0.0,
        to=1.0,
        increment=0.05,
        width=5,
        textvariable=app.arranger_gp_mutation,
    )
    mutation_spin.grid(row=1, column=3, sticky="w")
    attach_tooltip(
        mutation_spin,
        "Probability that a program receives a random edit after each generation.",
    )

    ttk.Label(session_group, text="Log best programs").grid(
        row=3, column=0, sticky="w"
    )
    log_best_spin = ttk.Spinbox(
        session_group,
        from_=1,
        to=320,
        width=4,
        textvariable=app.arranger_gp_log_best,
    )
    log_best_spin.grid(row=3, column=1, sticky="w", padx=(pad // 2, pad))
    attach_tooltip(
        log_best_spin,
        "How many of the best programs to include in the debug log output.",
    )

    ttk.Label(session_group, text="Random seed").grid(row=2, column=2, sticky="w")
    random_seed_entry = ttk.Entry(
        session_group,
        width=8,
        textvariable=app.arranger_gp_random_seed,
    )
    random_seed_entry.grid(row=3, column=3, sticky="w")
    attach_tooltip(
        random_seed_entry,
        "Seed for the random generator; change it to explore different GP runs.",
    )

    fitness_group = ttk.LabelFrame(
        advanced_section,
        text="Fitness weights",
        padding=pad,
        style="Panel.TLabelframe",
    )
    fitness_group.grid(row=1, column=0, sticky="nsew", pady=(pad, 0))
    for column in range(4):
        fitness_group.columnconfigure(column, weight=1)

    ttk.Label(fitness_group, text="Playability").grid(row=0, column=0, sticky="w")
    playability_entry = ttk.Entry(
        fitness_group,
        width=6,
        textvariable=app.arranger_gp_playability_weight,
    )
    playability_entry.grid(row=0, column=1, sticky="w", padx=(pad // 2, pad // 2))
    attach_tooltip(
        playability_entry,
        "Weight applied to difficulty penalties when scoring candidates.",
    )

    ttk.Label(fitness_group, text="Fidelity").grid(row=0, column=2, sticky="w")
    fidelity_entry = ttk.Entry(
        fitness_group,
        width=6,
        textvariable=app.arranger_gp_fidelity_weight,
    )
    fidelity_entry.grid(row=0, column=3, sticky="w")
    attach_tooltip(
        fidelity_entry,
        "Weight applied to melody-matching penalties; raise to resist pitch drift.",
    )

    ttk.Label(fitness_group, text="Tessitura").grid(row=1, column=0, sticky="w")
    tessitura_entry = ttk.Entry(
        fitness_group,
        width=6,
        textvariable=app.arranger_gp_tessitura_weight,
    )
    tessitura_entry.grid(row=1, column=1, sticky="w", padx=(pad // 2, pad // 2))
    attach_tooltip(
        tessitura_entry,
        "Weight applied to tessitura penalties; higher keeps phrases near the comfort zone.",
    )

    ttk.Label(fitness_group, text="Program size").grid(row=1, column=2, sticky="w")
    program_size_entry = ttk.Entry(
        fitness_group,
        width=6,
        textvariable=app.arranger_gp_program_size_weight,
    )
    program_size_entry.grid(row=1, column=3, sticky="w")
    attach_tooltip(
        program_size_entry,
        "Weight penalising longer GP programs; higher prefers simpler transformations.",
    )

    ttk.Label(fitness_group, text="Contour weight").grid(row=2, column=0, sticky="w")
    contour_entry = ttk.Entry(
        fitness_group,
        width=6,
        textvariable=app.arranger_gp_contour_weight,
    )
    contour_entry.grid(row=2, column=1, sticky="w", padx=(pad // 2, pad // 2))
    attach_tooltip(
        contour_entry,
        "Relative share of melodic contour differences within the fidelity calculation.",
    )

    ttk.Label(fitness_group, text="LCS weight").grid(row=2, column=2, sticky="w")
    lcs_entry = ttk.Entry(
        fitness_group,
        width=6,
        textvariable=app.arranger_gp_lcs_weight,
    )
    lcs_entry.grid(row=2, column=3, sticky="w")
    attach_tooltip(
        lcs_entry,
        "Relative share of longest-common-subsequence matches within the fidelity score.",
    )

    ttk.Label(fitness_group, text="Pitch weight").grid(row=3, column=0, sticky="w")
    pitch_entry = ttk.Entry(
        fitness_group,
        width=6,
        textvariable=app.arranger_gp_pitch_weight,
    )
    pitch_entry.grid(row=3, column=1, sticky="w", padx=(pad // 2, pad // 2))
    attach_tooltip(
        pitch_entry,
        "Relative share of pitch drift considered when comparing melodies.",
    )

    penalty_group = ttk.LabelFrame(
        advanced_section,
        text="Penalty tuning",
        padding=pad,
        style="Panel.TLabelframe",
    )
    penalty_group.grid(row=2, column=0, sticky="nsew", pady=(pad, 0))
    for column in range(4):
        penalty_group.columnconfigure(column, weight=1)

    ttk.Label(penalty_group, text="Range clamp penalty").grid(
        row=0, column=0, sticky="w"
    )
    range_penalty_entry = ttk.Entry(
        penalty_group,
        width=6,
        textvariable=app.arranger_gp_range_clamp_penalty,
    )
    range_penalty_entry.grid(row=0, column=1, sticky="w", padx=(pad // 2, pad // 2))
    attach_tooltip(
        range_penalty_entry,
        (
            "Penalty applied when clamping remains after edits; higher resists clamp-heavy "
            "results. Values ≥ 5 block range-clamped candidates altogether."
        ),
    )

    ttk.Label(penalty_group, text="Clamp melody bias").grid(
        row=0, column=2, sticky="w"
    )
    clamp_bias_entry = ttk.Entry(
        penalty_group,
        width=6,
        textvariable=app.arranger_gp_range_clamp_melody_bias,
    )
    clamp_bias_entry.grid(row=0, column=3, sticky="w")
    attach_tooltip(
        clamp_bias_entry,
        (
            "Extra melodic bias added when clamps occur; raise to nudge phrases away from "
            "edges. Values ≥ 5 block range-clamped candidates altogether."
        ),
    )

    ttk.Label(penalty_group, text="Melody shift weight").grid(
        row=1, column=0, sticky="w"
    )
    shift_weight_entry = ttk.Entry(
        penalty_group,
        width=6,
        textvariable=app.arranger_gp_melody_shift_weight,
    )
    shift_weight_entry.grid(row=1, column=1, sticky="w", padx=(pad // 2, pad // 2))
    attach_tooltip(
        shift_weight_entry,
        (
            "Weight against uneven octave jumps in the melody; higher discourages jumpy "
            "lines. Values ≥ 5 disable LocalOctave primitives entirely."
        ),
    )

    ttk.Label(penalty_group, text="Fidelity priority").grid(
        row=1, column=2, sticky="w"
    )
    fidelity_priority_entry = ttk.Entry(
        penalty_group,
        width=6,
        textvariable=app.arranger_gp_fidelity_priority_weight,
    )
    fidelity_priority_entry.grid(row=1, column=3, sticky="w")
    attach_tooltip(
        fidelity_priority_entry,
        (
            "Multiplier on melodic penalties when edits diverge; higher keeps fidelity "
            "dominant. Values ≥ 5 disable LocalOctave and SimplifyRhythm edits."
        ),
    )

    ttk.Label(penalty_group, text="Rhythm simplify weight").grid(
        row=2, column=0, sticky="w"
    )
    rhythm_weight_entry = ttk.Entry(
        penalty_group,
        width=6,
        textvariable=app.arranger_gp_rhythm_simplify_weight,
    )
    rhythm_weight_entry.grid(row=2, column=1, sticky="w", padx=(pad // 2, pad // 2))
    attach_tooltip(
        rhythm_weight_entry,
        (
            "Extra cost applied to SimplifyRhythm edits; raise to favour original "
            "rhythms. Values ≥ 5 disable SimplifyRhythm entirely."
        ),
    )

    ttk.Button(
        advanced_section,
        text="Reset GP settings to defaults",
        command=app.reset_arranger_gp_settings,
    ).grid(row=3, column=0, sticky="w", pady=(pad, 0))

    preset_actions = ttk.Frame(advanced_section)
    preset_actions.grid(row=4, column=0, sticky="w", pady=(pad // 2, 0))
    export_button = ttk.Button(
        preset_actions,
        text="Export GP preset...",
        command=app.export_arranger_gp_settings,
    )
    export_button.grid(row=0, column=0, sticky="w")
    attach_tooltip(
        export_button,
        "Save the current GP arranger knobs to a reusable preset file.",
    )
    import_button = ttk.Button(
        preset_actions,
        text="Import GP preset...",
        command=app.import_arranger_gp_settings,
    )
    import_button.grid(row=0, column=1, sticky="w", padx=(pad // 2, 0))
    attach_tooltip(
        import_button,
        "Load GP arranger knobs from a saved preset file.",
    )

    app._register_arranger_advanced_frame(advanced_section, mode="gp")

    ttk.Label(
        gp_section,
        text=(
            "When the time budget elapses early, the arranger falls back to "
            "the best-effort pipeline for comparison."
        ),
        style="Hint.TLabel",
        wraplength=360,
    ).grid(row=7, column=0, sticky="w", pady=(pad, 0))

    return gp_panel
