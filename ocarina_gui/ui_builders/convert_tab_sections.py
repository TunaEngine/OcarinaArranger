"""Helper builders for sections within the Convert tab."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from shared.ttk import ttk
from ui.widgets import attach_tooltip

from .convert_gp_panel import build_gp_panel
from .convert_grace_section import build_grace_section

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from ..app import App


__all__ = [
    "build_instrument_section",
    "build_arranger_mode_section",
    "build_import_export_section",
    "build_playback_section",
]


def build_instrument_section(app: "App", parent: ttk.Frame, pad: int) -> ttk.LabelFrame:
    """Create the instrument/range controls for the Convert tab."""
    instrument_section = ttk.LabelFrame(
        parent, text="1. Instrument & Range", padding=pad, style="Panel.TLabelframe"
    )
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

    targets_section = ttk.LabelFrame(
        instrument_section,
        text="Arrangement Targets",
        padding=pad,
        style="Panel.TLabelframe",
    )
    targets_section.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(pad, 0))
    instrument_section.rowconfigure(4, weight=1)
    targets_section.columnconfigure(0, weight=1)
    targets_section.rowconfigure(2, weight=1)
    targets_section.rowconfigure(3, weight=1)

    ttk.Label(
        targets_section,
        text="Choose how arranger v2 and v3 select instruments for comparison.",
        style="Hint.TLabel",
        wraplength=360,
    ).grid(row=0, column=0, sticky="w")

    strategy_frame = ttk.Frame(targets_section)
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

    starred_section = ttk.Frame(targets_section)
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
        targets_section,
        text="Arrangement Summary",
        padding=pad,
        style="Panel.TLabelframe",
    )
    summary_section.grid(row=3, column=0, sticky="nsew", pady=(pad, 0))
    summary_section.columnconfigure(0, weight=1)
    summary_section.rowconfigure(0, weight=1)
    summary_container = ttk.Frame(summary_section)
    summary_container.grid(row=0, column=0, sticky="nsew")
    app._register_arranger_summary_container(summary_container)

    grace_section = build_grace_section(app, instrument_section, pad)
    grace_section.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=(pad, 0))
    instrument_section.rowconfigure(5, weight=1)

    return instrument_section


def build_arranger_mode_section(
    app: "App", parent: ttk.Frame, pad: int
) -> Dict[str, ttk.Frame]:
    """Construct the arranger mode controls and return the mode panels."""
    mode_section = ttk.LabelFrame(
        parent,
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
    modes = (
        ("classic", "Classic v1"),
        ("best_effort", "Best-Effort v2"),
        ("gp", "Genetic Programming v3"),
    )
    for index, (value, label) in enumerate(modes):
        padding_x = (0, pad) if index < len(modes) - 1 else (0, 0)
        ttk.Radiobutton(
            mode_selector,
            text=label,
            variable=app.arranger_mode,
            value=value,
            style="Segmented.TRadiobutton",
        ).pack(side="left", padx=padding_x)

    mode_stack = ttk.Frame(mode_section)
    mode_stack.grid(row=2, column=0, sticky="nsew", pady=(pad, 0))
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

    advanced_toggle = ttk.Frame(best_effort_section)
    advanced_toggle.grid(row=0, column=0, sticky="ew")
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
    advanced_section.grid(row=1, column=0, sticky="nsew", pady=(pad, 0))
    advanced_section.columnconfigure(0, weight=1)

    ttk.Checkbutton(
        advanced_section,
        text="Enable DP-with-slack",
        variable=app.arranger_dp_slack,
    ).grid(row=0, column=0, sticky="w")
    ttk.Label(
        advanced_section,
        text="Uses the octave-folding dynamic program; defaults to on.",
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

    app._register_arranger_advanced_frame(advanced_section, mode="best_effort")

    gp_panel = build_gp_panel(app, mode_stack, pad)

    return {
        "classic": classic_panel,
        "best_effort": best_effort_panel,
        "gp": gp_panel,
    }


def build_import_export_section(app: "App", parent: ttk.Frame, pad: int) -> ttk.LabelFrame:
    """Create the import/export controls and return the surrounding frame."""
    import_section = ttk.LabelFrame(
        parent, text="Import & Export", padding=pad, style="Panel.TLabelframe"
    )
    import_section.grid(row=0, column=0, sticky="nsew")
    import_section.columnconfigure(0, weight=1)

    ttk.Label(import_section, text="Input MusicXML/MXL").grid(row=0, column=0, sticky="w")
    path_row = ttk.Frame(import_section)
    path_row.grid(row=1, column=0, sticky="ew", pady=(4, pad))
    path_row.columnconfigure(0, weight=1)
    ttk.Entry(path_row, textvariable=app.input_path).grid(row=0, column=0, sticky="ew")
    ttk.Button(path_row, text="Browse...", command=app.browse).grid(
        row=0, column=1, padx=(pad // 2, 0)
    )

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

    return import_section


def build_playback_section(app: "App", parent: ttk.Frame, pad: int) -> ttk.LabelFrame:
    """Create the playback controls for the Convert tab."""
    playback_section = ttk.LabelFrame(
        parent, text="Playback", padding=pad, style="Panel.TLabelframe"
    )
    playback_section.grid(row=1, column=0, sticky="nsew", pady=(pad, 0))
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

    return playback_section
