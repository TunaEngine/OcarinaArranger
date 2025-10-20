from __future__ import annotations

from typing import TYPE_CHECKING

from shared.ttk import ttk

from ui.widgets import attach_tooltip


if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..app import App


__all__ = ["build_grace_section"]


def build_grace_section(app: "App", parent: ttk.LabelFrame, pad: int) -> ttk.LabelFrame:
    """Create the grace-note configuration controls and attach them to ``parent``."""

    grace_section = ttk.LabelFrame(
        parent,
        text="Grace Notes",
        padding=pad,
        style="Panel.TLabelframe",
    )
    grace_section.columnconfigure(0, weight=1)

    ttk.Label(
        grace_section,
        text="Control how ornamental grace notes are realized and scored.",
        style="Hint.TLabel",
        wraplength=360,
    ).grid(row=0, column=0, sticky="w")

    policy_row = ttk.Frame(grace_section)
    policy_row.grid(row=1, column=0, sticky="ew", pady=(pad // 2, 0))
    ttk.Label(policy_row, text="Timing policy").grid(row=0, column=0, sticky="w")
    policy_combo = ttk.Combobox(
        policy_row,
        textvariable=app.grace_policy,
        values=("tempo-weighted", "fixed"),
        state="readonly",
        width=18,
    )
    policy_combo.grid(row=0, column=1, sticky="w", padx=(pad // 2, 0))
    attach_tooltip(
        policy_combo,
        "Tempo-weighted shortens grace durations at faster tempos; fixed keeps them constant.",
    )

    fractions_frame = ttk.LabelFrame(
        grace_section,
        text="Grace durations",
        padding=(pad // 2, pad // 2),
        style="Panel.TLabelframe",
    )
    fractions_frame.grid(row=2, column=0, sticky="nsew", pady=(pad // 2, 0))
    fractions_frame.columnconfigure(1, weight=1)

    fraction_specs = (
        ("First", app.grace_fraction_primary, app._grace_fraction_displays.get("fraction_0")),
        ("Second", app.grace_fraction_secondary, app._grace_fraction_displays.get("fraction_1")),
        ("Third", app.grace_fraction_tertiary, app._grace_fraction_displays.get("fraction_2")),
    )
    for index, (label, variable, display) in enumerate(fraction_specs):
        ttk.Label(fractions_frame, text=f"{label} grace fraction").grid(
            row=index, column=0, sticky="w"
        )
        scale = ttk.Scale(
            fractions_frame,
            variable=variable,
            from_=0.0,
            to=0.5,
            orient="horizontal",
        )
        scale.grid(row=index, column=1, sticky="ew", padx=(pad // 2, pad // 2))
        attach_tooltip(
            scale,
            "Adjust the portion of the anchor note stolen by each grace in a chain.",
        )
        if display is not None:
            ttk.Label(fractions_frame, textvariable=display, width=5).grid(
                row=index, column=2, sticky="e"
            )

    controls = ttk.Frame(grace_section)
    controls.grid(row=3, column=0, sticky="nsew", pady=(pad // 2, 0))
    controls.columnconfigure(1, weight=1)
    controls.columnconfigure(3, weight=1)

    ttk.Label(controls, text="Max chain").grid(row=0, column=0, sticky="w")
    chain_spin = ttk.Spinbox(
        controls,
        from_=0,
        to=8,
        width=4,
        textvariable=app.grace_max_chain,
    )
    chain_spin.grid(row=0, column=1, sticky="w", padx=(pad // 2, pad))
    attach_tooltip(chain_spin, "Maximum number of grace notes kept before pruning the chain.")

    ttk.Label(controls, text="Anchor minimum").grid(row=0, column=2, sticky="w")
    anchor_entry = ttk.Entry(
        controls,
        width=6,
        textvariable=app.grace_anchor_min_fraction,
    )
    anchor_entry.grid(row=0, column=3, sticky="w")
    attach_tooltip(
        anchor_entry,
        "Smallest fraction of the anchor note to preserve after allocating graces.",
    )

    fold_check = ttk.Checkbutton(
        controls,
        text="Fold out-of-range",
        variable=app.grace_fold_out_of_range,
    )
    fold_check.grid(row=1, column=0, columnspan=2, sticky="w", pady=(pad // 2, 0))
    attach_tooltip(
        fold_check,
        "Wrap grace pitches into the playable range instead of leaving them untouched.",
    )

    drop_check = ttk.Checkbutton(
        controls,
        text="Drop out-of-range",
        variable=app.grace_drop_out_of_range,
    )
    drop_check.grid(row=1, column=2, columnspan=2, sticky="w", pady=(pad // 2, 0))
    attach_tooltip(
        drop_check,
        "Remove grace notes that remain outside the instrument range after folding.",
    )

    ttk.Label(controls, text="Slow tempo").grid(row=2, column=0, sticky="w")
    slow_entry = ttk.Entry(controls, width=6, textvariable=app.grace_slow_tempo)
    slow_entry.grid(row=2, column=1, sticky="w", padx=(pad // 2, pad))
    attach_tooltip(
        slow_entry,
        "Tempo threshold (BPM) where tempo-weighted scaling keeps full grace duration.",
    )

    ttk.Label(controls, text="Fast tempo").grid(row=2, column=2, sticky="w")
    fast_entry = ttk.Entry(controls, width=6, textvariable=app.grace_fast_tempo)
    fast_entry.grid(row=2, column=3, sticky="w")
    attach_tooltip(
        fast_entry,
        "Tempo threshold (BPM) where tempo-weighted scaling halves grace duration.",
    )

    ttk.Label(controls, text="Grace bonus").grid(row=3, column=0, sticky="w")
    bonus_entry = ttk.Entry(controls, width=6, textvariable=app.grace_bonus)
    bonus_entry.grid(row=3, column=1, sticky="w", padx=(pad // 2, pad))
    attach_tooltip(
        bonus_entry,
        "Difficulty bonus applied when passages include properly realized grace notes.",
    )

    reset_button = ttk.Button(
        controls,
        text="Reset to defaults",
        command=app.reset_grace_settings,
    )
    reset_button.grid(row=4, column=3, sticky="e", pady=(pad, 0))
    attach_tooltip(reset_button, "Restore all grace note settings to their default values.")

    return grace_section
