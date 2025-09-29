"""Builder for the "Convert" tab."""

from __future__ import annotations

from tkinter import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - used for type checkers only
    from ..app import App


__all__ = ["build_convert_tab"]


def build_convert_tab(app: "App", notebook: ttk.Notebook) -> None:
    pad = 8
    tab = ttk.Frame(notebook)
    notebook.add(tab, text="Convert")

    container = ttk.Frame(tab)
    container.pack(fill="both", expand=True, padx=pad, pady=pad)

    row = ttk.Frame(container)
    row.pack(fill="x", pady=pad)
    ttk.Label(row, text="Input MusicXML/MXL:").pack(side="left")
    ttk.Entry(row, textvariable=app.input_path).pack(side="left", fill="x", expand=True, padx=(pad, pad))
    ttk.Button(row, text="Browse...", command=app.browse).pack(side="left")
    ttk.Button(row, text="Play Original", command=app.play_original).pack(side="left", padx=(pad, 0))
    ttk.Button(row, text="Play Arranged", command=app.play_arranged).pack(side="left", padx=(pad, 0))

    options = ttk.LabelFrame(container, text="Options")
    options.pack(fill="x", pady=pad)

    row1 = ttk.Frame(options)
    row1.pack(fill="x", pady=pad)
    ttk.Label(row1, text="Target Mode:").pack(side="left")
    ttk.Radiobutton(row1, text="Auto (minor->Am, else C)", variable=app.prefer_mode, value="auto").pack(
        side="left", padx=(pad, 0)
    )
    ttk.Radiobutton(row1, text="Force C major", variable=app.prefer_mode, value="major").pack(
        side="left", padx=(pad, 0)
    )
    ttk.Radiobutton(row1, text="Force A minor", variable=app.prefer_mode, value="minor").pack(
        side="left", padx=(pad, 0)
    )

    row2 = ttk.Frame(options)
    row2.pack(fill="x", pady=pad)
    ttk.Checkbutton(row2, text="Prefer flats for accidentals", variable=app.prefer_flats).pack(side="left")
    ttk.Checkbutton(
        row2,
        text="Collapse chords to single melody line (voice 1, highest)",
        variable=app.collapse_chords,
    ).pack(side="left", padx=(pad, 0))

    row_instr = ttk.Frame(options)
    row_instr.pack(fill="x", pady=pad)
    ttk.Label(row_instr, text="Instrument:").pack(side="left")
    instrument_combo = ttk.Combobox(
        row_instr,
        textvariable=app.convert_instrument_var,
        state="readonly",
        width=24,
    )
    app._register_convert_instrument_combo(instrument_combo)
    instrument_combo.pack(side="left", padx=(pad, 0))

    row3 = ttk.Frame(options)
    row3.pack(fill="x", pady=pad)
    ttk.Checkbutton(
        row3,
        text="Favor lower register (drop notes by octave when safe)",
        variable=app.favor_lower,
    ).pack(side="left")
    ttk.Label(row3, text="Manual transpose:").pack(side="left", padx=(pad, 0))
    spin = ttk.Spinbox(row3, from_=-12, to=12, width=4, textvariable=app.transpose_offset)
    spin.pack(side="left")
    app._register_transpose_spinbox(spin)
    ttk.Label(row3, text="semitones").pack(side="left", padx=(4, 0))
    ttk.Label(row3, text="Range: min").pack(side="left", padx=(pad, 0))
    range_min_combo = ttk.Combobox(row3, width=8, textvariable=app.range_min)
    range_min_combo.pack(side="left")
    ttk.Label(row3, text="max").pack(side="left", padx=(pad, 0))
    range_max_combo = ttk.Combobox(row3, width=8, textvariable=app.range_max)
    range_max_combo.pack(side="left")
    app._register_range_comboboxes(range_min_combo, range_max_combo)

    actions = ttk.Frame(container)
    actions.pack(fill="x", pady=pad)
    reimport_button = ttk.Button(
        actions, text="Re-import and Arrange", command=app.reimport_and_arrange
    )
    app._register_reimport_button(reimport_button)
    reimport_button.pack(side="left")
    ttk.Button(actions, text="Convert and Save...", command=app.convert).pack(
        side="left", padx=(pad, 0)
    )
    ttk.Label(actions, textvariable=app.status).pack(side="left", padx=(pad, 0))

    footer = ttk.Label(
        container,
        text="Outputs .musicxml + .mxl | Part named 'Ocarina' | GM Program 80",
        style="Hint.TLabel",
    )
    footer.pack(anchor="w", pady=(pad, 0))
