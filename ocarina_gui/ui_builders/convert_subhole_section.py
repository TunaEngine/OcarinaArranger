from typing import TYPE_CHECKING

from shared.ttk import ttk

from ui.widgets import attach_tooltip


if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..app import App


__all__ = ["build_subhole_section"]


def build_subhole_section(app: "App", parent: ttk.LabelFrame, pad: int) -> ttk.LabelFrame:
    """Create controls for configuring subhole comfort thresholds."""

    subhole_section = ttk.LabelFrame(
        parent,
        text="Subhole Comfort",
        padding=pad,
        style="Panel.TLabelframe",
    )
    subhole_section.columnconfigure(0, weight=1)

    ttk.Label(
        subhole_section,
        text="Set the maximum rate of half-hole changes the arranger should allow.",
        style="Hint.TLabel",
        wraplength=360,
    ).grid(row=0, column=0, sticky="w")

    caps_frame = ttk.Frame(subhole_section)
    caps_frame.grid(row=1, column=0, sticky="ew", pady=(pad // 2, 0))
    caps_frame.columnconfigure(1, weight=1)
    caps_frame.columnconfigure(3, weight=1)

    ttk.Label(caps_frame, text="Overall change cap (Hz)").grid(row=0, column=0, sticky="w")
    overall_entry = ttk.Entry(
        caps_frame,
        width=8,
        textvariable=app.subhole_max_changes,
    )
    overall_entry.grid(row=0, column=1, sticky="w", padx=(pad // 2, pad))
    attach_tooltip(
        overall_entry,
        "Maximum average pitch-change frequency allowed before edits are applied.",
    )

    ttk.Label(caps_frame, text="Subhole change cap (Hz)").grid(
        row=0, column=2, sticky="w"
    )
    subhole_entry = ttk.Entry(
        caps_frame,
        width=8,
        textvariable=app.subhole_max_subhole_changes,
    )
    subhole_entry.grid(row=0, column=3, sticky="w")
    attach_tooltip(
        subhole_entry,
        "Maximum rate of explicitly tagged subhole transitions before edits occur.",
    )

    pair_frame = ttk.Frame(subhole_section)
    pair_frame.grid(row=2, column=0, sticky="ew", pady=(pad // 2, 0))
    pair_frame.columnconfigure(0, weight=1)

    ttk.Label(pair_frame, text="Pair-specific limits").grid(row=0, column=0, sticky="w")
    pair_entry = ttk.Entry(
        pair_frame,
        textvariable=app.subhole_pair_limits,
        width=48,
    )
    pair_entry.grid(row=1, column=0, sticky="ew")
    attach_tooltip(
        pair_entry,
        "Optional overrides in the form pitchA-pitchB=rate[@ease], separated by commas.",
    )

    controls = ttk.Frame(subhole_section)
    controls.grid(row=3, column=0, sticky="ew", pady=(pad // 2, 0))
    controls.columnconfigure(0, weight=1)

    reset_button = ttk.Button(
        controls,
        text="Reset subhole limits",
        command=app.reset_subhole_settings,
    )
    reset_button.grid(row=0, column=1, sticky="e")
    attach_tooltip(reset_button, "Restore the default subhole comfort thresholds.")

    return subhole_section
