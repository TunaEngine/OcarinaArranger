"""Controls and widgets for preview playback interactions."""

from __future__ import annotations

from tkinter import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - used for type checkers only
    from ..app import App


__all__ = ["build_preview_controls"]


def build_preview_controls(app: "App", parent: ttk.Frame, side: str) -> None:
    controls = ttk.Frame(parent)
    controls.pack(fill="x")
    ttk.Button(
        controls,
        textvariable=app._preview_play_vars[side],
        width=12,
        command=lambda: app._on_preview_play_toggle(side),
    ).pack(fill="x", pady=(0, 6))
    ttk.Button(controls, text="Zoom +", width=12, command=lambda: app._zoom_all(+2)).pack(fill="x", pady=2)
    ttk.Button(controls, text="Zoom -", width=12, command=lambda: app._zoom_all(-2)).pack(fill="x", pady=2)
    ttk.Button(controls, text="Time +", width=12, command=lambda: app._hzoom_all(1.25)).pack(fill="x", pady=2)
    ttk.Button(controls, text="Time -", width=12, command=lambda: app._hzoom_all(0.8)).pack(fill="x", pady=2)

    playback_box = ttk.LabelFrame(parent, text="Playback")
    playback_box.pack(fill="x", pady=(8, 0))
    tempo_row = ttk.Frame(playback_box)
    tempo_row.pack(fill="x", pady=(4, 0))
    ttk.Label(tempo_row, text="Tempo (BPM):").pack(side="left")
    tempo_spin = ttk.Spinbox(
        tempo_row,
        from_=30,
        to=400,
        increment=1,
        width=6,
        textvariable=app._preview_tempo_vars[side],
    )
    tempo_spin.pack(side="left", padx=(4, 0))
    metronome_check = ttk.Checkbutton(
        playback_box,
        text="Metronome",
        variable=app._preview_metronome_vars[side],
    )
    metronome_check.pack(anchor="w", pady=(4, 4))
    app._register_preview_adjust_widgets(side, tempo_spin, metronome_check)
    loop_box = ttk.LabelFrame(playback_box, text="Loop")
    loop_box.pack(fill="x", pady=(0, 4))
    loop_toggle = ttk.Checkbutton(
        loop_box,
        text="Enable",
        variable=app._preview_loop_enabled_vars[side],
    )
    loop_toggle.pack(anchor="w", pady=(4, 0))
    start_row = ttk.Frame(loop_box)
    start_row.pack(fill="x", pady=(2, 0))
    ttk.Label(start_row, text="Start beat:").pack(side="left")
    loop_start = ttk.Spinbox(
        start_row,
        from_=0.0,
        to=9999.0,
        increment=0.25,
        width=6,
        textvariable=app._preview_loop_start_vars[side],
        format="%.2f",
    )
    loop_start.pack(side="left", padx=(4, 0))
    end_row = ttk.Frame(loop_box)
    end_row.pack(fill="x", pady=(2, 4))
    ttk.Label(end_row, text="End beat:").pack(side="left")
    loop_end = ttk.Spinbox(
        end_row,
        from_=0.0,
        to=9999.0,
        increment=0.25,
        width=6,
        textvariable=app._preview_loop_end_vars[side],
        format="%.2f",
    )
    loop_end.pack(side="left", padx=(4, 0))
    set_range_btn = ttk.Button(
        loop_box,
        text="Set range",
        command=lambda s=side: app._begin_loop_range_selection(s),
    )
    set_range_btn.pack(anchor="w", pady=(0, 4))
    app._register_preview_loop_range_button(side, set_range_btn)
    app._register_preview_loop_widgets(side, loop_toggle, loop_start, loop_end, set_range_btn)
    button_row = ttk.Frame(playback_box)
    button_row.pack(fill="x", pady=(0, 4))
    apply_btn = ttk.Button(
        button_row,
        text="Apply",
        width=8,
        command=lambda: app._apply_preview_settings(side),
    )
    apply_btn.pack(side="left")
    cancel_btn = ttk.Button(
        button_row,
        text="Cancel",
        width=8,
        command=lambda: app._cancel_preview_settings(side),
    )
    cancel_btn.pack(side="left", padx=(4, 0))
    app._register_preview_control_buttons(side, apply_btn, cancel_btn)

    if side == "arranged":
        transpose = ttk.Frame(parent)
        transpose.pack(fill="x", pady=(8, 0))
        ttk.Label(transpose, text="Manual transpose:").pack(side="left")
        spin = ttk.Spinbox(
            transpose,
            from_=-12,
            to=12,
            width=4,
            textvariable=app.transpose_offset,
        )
        spin.pack(side="left", padx=(4, 0))
        ttk.Label(transpose, text="semitones").pack(side="left", padx=(4, 0))
        button_row = ttk.Frame(transpose)
        button_row.pack(fill="x", pady=(4, 0))
        apply_btn = ttk.Button(
            button_row,
            text="Apply",
            width=8,
            command=app._apply_transpose_offset,
        )
        apply_btn.pack(side="left")
        cancel_btn = ttk.Button(
            button_row,
            text="Cancel",
            width=8,
            command=app._cancel_transpose_offset,
        )
        cancel_btn.pack(side="left", padx=(4, 0))
        app._register_transpose_spinbox(
            spin, apply_button=apply_btn, cancel_button=cancel_btn
        )
