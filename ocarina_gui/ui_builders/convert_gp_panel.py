"""Builder for the GP arranger tuning panel shown on the Convert tab."""

from __future__ import annotations

from shared.ttk import ttk

from ui.widgets import attach_tooltip


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

    gp_config = ttk.Frame(gp_section)
    gp_config.grid(row=1, column=0, sticky="nsew", pady=(pad, 0))
    for column in range(3):
        gp_config.columnconfigure(column * 2, weight=0)
        gp_config.columnconfigure(column * 2 + 1, weight=1)

    ttk.Label(gp_config, text="Generations").grid(row=0, column=0, sticky="w")
    generations_spin = ttk.Spinbox(
        gp_config,
        from_=1,
        to=25,
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
        to=64,
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

    advanced_toggle = ttk.Frame(gp_section)
    advanced_toggle.grid(row=2, column=0, sticky="ew", pady=(pad, 0))
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
    advanced_section.grid(row=3, column=0, sticky="nsew", pady=(pad, 0))
    gp_section.rowconfigure(3, weight=1)
    advanced_section.columnconfigure(0, weight=1)
    advanced_section.rowconfigure(1, weight=1)

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
        to=64,
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
        to=64,
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
        row=2, column=0, sticky="w"
    )
    log_best_spin = ttk.Spinbox(
        session_group,
        from_=1,
        to=16,
        width=4,
        textvariable=app.arranger_gp_log_best,
    )
    log_best_spin.grid(row=2, column=1, sticky="w", padx=(pad // 2, pad))
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
    random_seed_entry.grid(row=2, column=3, sticky="w")
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

    ttk.Button(
        advanced_section,
        text="Reset GP settings to defaults",
        command=app.reset_arranger_gp_settings,
    ).grid(row=2, column=0, sticky="w", pady=(pad, 0))

    app._register_arranger_advanced_frame(advanced_section, mode="gp")

    ttk.Label(
        gp_section,
        text=(
            "When the time budget elapses early, the arranger falls back to "
            "the best-effort pipeline for comparison."
        ),
        style="Hint.TLabel",
        wraplength=360,
    ).grid(row=4, column=0, sticky="w", pady=(pad, 0))

    return gp_panel
