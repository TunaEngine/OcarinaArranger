"""Builder for the "Convert" tab."""

from __future__ import annotations

from shared.ttk import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - used for type checkers only
    from ..app import App


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

    # 2. Arranger Algorithm
    algorithm_section = ttk.LabelFrame(left_column, text="2. Arranger Algorithm", padding=pad, style="Panel.TLabelframe")
    algorithm_section.grid(row=1, column=0, sticky="nsew", pady=(pad, 0))
    algorithm_section.columnconfigure(0, weight=1)

    ttk.Label(algorithm_section, text="Target Mode").grid(row=0, column=0, sticky="w")
    target_mode_frame = ttk.Frame(algorithm_section)
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

    preferences_frame = ttk.Frame(algorithm_section)
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

    manual_frame = ttk.Frame(algorithm_section)
    manual_frame.grid(row=3, column=0, sticky="w")
    ttk.Label(manual_frame, text="Manual transpose:").grid(row=0, column=0, sticky="w")
    spin = ttk.Spinbox(manual_frame, from_=-12, to=12, width=4, textvariable=app.transpose_offset)
    spin.grid(row=0, column=1, padx=(pad // 2, pad // 2))
    app._register_transpose_spinbox(spin)
    ttk.Label(manual_frame, text="semitones").grid(row=0, column=2, sticky="w")

    ttk.Label(
        algorithm_section,
        text="Apply an additional transposition after the automatic arrangement.",
        style="Hint.TLabel",
        wraplength=360,
    ).grid(row=4, column=0, sticky="w", pady=(4, 0))

    # Import & Export
    import_section = ttk.LabelFrame(right_column, text="Import & Export", padding=pad, style="Panel.TLabelframe")
    import_section.grid(row=0, column=0, sticky="nsew")
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
    playback_section = ttk.LabelFrame(right_column, text="Playback", padding=pad, style="Panel.TLabelframe")
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
