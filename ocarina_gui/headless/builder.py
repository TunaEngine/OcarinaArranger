"""Helpers that assemble the headless widget graph for tests."""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

from .views import HeadlessFingeringView, HeadlessPianoRoll, HeadlessStaffView
from .widgets import (
    HeadlessButton,
    HeadlessCheckbutton,
    HeadlessCombobox,
    HeadlessFrame,
    HeadlessNotebook,
    HeadlessProgressbar,
    HeadlessRadiobutton,
    HeadlessScale,
    HeadlessSpinbox,
    HeadlessTreeview,
)


def build_headless_ui(app: "App") -> None:
    """Populate minimal widget-like attributes for headless tests."""

    app.fingering_table = None
    preview = HeadlessFingeringView()
    register_preview = getattr(app, "_register_fingering_preview", None)
    if callable(register_preview):
        register_preview(preview)
    else:  # pragma: no cover - legacy path
        app.fingering_preview = preview
    app.fingering_grid = None
    app.roll_orig = HeadlessPianoRoll()
    app.roll_arr = HeadlessPianoRoll()
    if hasattr(app, "_register_auto_scroll_target"):
        app._register_auto_scroll_target(app.roll_orig)
        app._register_auto_scroll_target(app.roll_arr)
    app.staff_orig = HeadlessStaffView()
    app.staff_arr = HeadlessStaffView()
    app.side_fing_orig = HeadlessFingeringView()
    app.side_fing_arr = HeadlessFingeringView()
    if hasattr(app.roll_orig, "set_fingering_cb"):
        app.roll_orig.set_fingering_cb(
            lambda midi, side="original": app._on_preview_roll_hover(side, midi)
        )
    if hasattr(app.roll_arr, "set_fingering_cb"):
        app.roll_arr.set_fingering_cb(
            lambda midi, side="arranged": app._on_preview_roll_hover(side, midi)
        )

    for side in ("original", "arranged"):
        volume_button = HeadlessButton(
            lambda s=side: app._handle_preview_volume_button(s, None),
            enabled=True,
        )
        volume_button.configure(width=3, text="🔈", compound="center")
        volume_button.bind(
            "<ButtonRelease-1>",
            lambda event, s=side: app._handle_preview_volume_button(s, event),
            add="+",
        )
        volume_var = app._preview_volume_vars[side]
        volume_slider = HeadlessScale(
            variable=volume_var,
            from_=0.0,
            to=100.0,
            length=120,
        )
        volume_slider.bind(
            "<ButtonPress-1>",
            lambda event, s=side: app._on_preview_volume_press(s, event),
            add="+",
        )
        volume_slider.bind(
            "<B1-Motion>",
            lambda event, s=side: app._on_preview_volume_drag(s, event),
            add="+",
        )
        volume_slider.bind(
            "<ButtonRelease-1>",
            lambda event, s=side: app._on_preview_volume_release(s, event),
            add="+",
        )
        volume_buttons = getattr(app, "_preview_volume_buttons", None)
        if not isinstance(volume_buttons, dict):
            volume_buttons = {}
            app._preview_volume_buttons = volume_buttons
        volume_buttons[side] = volume_button
        volume_controls = getattr(app, "_preview_volume_controls", None)
        if not isinstance(volume_controls, dict):
            volume_controls = {}
            app._preview_volume_controls = volume_controls
        volume_controls[side] = (volume_button, volume_slider)
        volume_icon_sets = getattr(app, "_preview_volume_icons", None)
        if not isinstance(volume_icon_sets, dict):
            volume_icon_sets = {}
            app._preview_volume_icons = volume_icon_sets
        volume_icon_sets[side] = {"normal": None, "muted": None}
        if hasattr(app, "_update_mute_button_state"):
            try:
                app._update_mute_button_state(side)
            except Exception:
                pass

        tempo_ctrl = HeadlessSpinbox()
        metronome_ctrl = HeadlessCheckbutton()
        app._register_preview_adjust_widgets(side, tempo_ctrl, metronome_ctrl)
        loop_toggle = HeadlessCheckbutton()
        loop_start = HeadlessSpinbox()
        loop_end = HeadlessSpinbox()
        set_range_btn = HeadlessButton(lambda s=side: app._begin_loop_range_selection(s))
        app._register_preview_loop_range_button(side, set_range_btn)
        app._register_preview_loop_widgets(side, loop_toggle, loop_start, loop_end, set_range_btn)
        apply_btn = HeadlessButton(lambda s=side: app._apply_preview_settings(s))
        cancel_btn = HeadlessButton(lambda s=side: app._cancel_preview_settings(s))
        app._register_preview_control_buttons(side, apply_btn, cancel_btn)
        progress_frame = HeadlessFrame()
        app._register_preview_progress_frame(
            side,
            progress_frame,
            place={"relx": 0.0, "rely": 0.0, "relwidth": 1.0, "relheight": 1.0},
        )
    transpose_spin = HeadlessSpinbox()
    transpose_apply = HeadlessButton(app._apply_transpose_offset)
    transpose_cancel = HeadlessButton(app._cancel_transpose_offset)
    app._register_transpose_spinbox(
        transpose_spin, apply_button=transpose_apply, cancel_button=transpose_cancel
    )
    reimport_button = HeadlessButton(app.reimport_and_arrange)
    app._register_reimport_button(reimport_button)

    summary_columns = (
        "instrument",
        "status",
        "transpose",
        "easy",
        "medium",
        "hard",
        "very_hard",
        "tessitura",
    )
    app._arranger_summary_column_keys = summary_columns
    summary_container = HeadlessFrame()
    app._arranger_summary_container = summary_container
    app._arranger_summary_body = summary_container
    app._arranger_summary_tree = HeadlessTreeview(
        parent=summary_container, columns=summary_columns, show="headings"
    )
    app._arranger_summary_placeholder = None

    strategy_buttons: dict[str, HeadlessRadiobutton] = {}
    for value, label in (
        ("current", "Current instrument only"),
        ("starred-best", "Starred instruments (pick best)"),
    ):
        button = HeadlessRadiobutton(
            text=label,
            variable=app.arranger_strategy,
            value=value,
            parent=summary_container,
        )
        button.pack()
        strategy_buttons[value] = button
    app._arranger_strategy_buttons = strategy_buttons

    starred_container = HeadlessFrame(parent=summary_container)
    app._starred_instrument_container = starred_container
    app._starred_checkbox_widgets = {}
    starred_ids = set(getattr(app._viewmodel.state, "starred_instrument_ids", ()))
    for index, (instrument_id, instrument_name) in enumerate(app._instrument_name_by_id.items()):
        var = app._starred_instrument_vars.get(instrument_id)
        if var is None:
            var = tk.BooleanVar(master=app, value=instrument_id in starred_ids)
            trace_id = var.trace_add(
                "write",
                lambda *_args, iid=instrument_id: app._on_starred_var_changed(iid),
            )
            app._starred_instrument_vars[instrument_id] = var
            app._starred_var_traces[instrument_id] = trace_id
            app._register_convert_setting_var(var)
        else:
            desired = instrument_id in starred_ids
            try:
                current = bool(var.get())
            except Exception:
                current = not desired
            if current != desired:
                var.set(desired)
        check = HeadlessCheckbutton(
            text=instrument_name,
            variable=var,
            parent=starred_container,
        )
        check.grid(row=index, column=0, sticky="w")
        app._starred_checkbox_widgets[instrument_id] = check

    results_section = HeadlessFrame()
    app._arranger_results_section = results_section
    classic_frame = HeadlessFrame()
    best_effort_frame = HeadlessFrame()
    gp_frame = HeadlessFrame()
    app._arranger_mode_frames = {
        "classic": {"left": classic_frame},
        "best_effort": {"left": best_effort_frame},
        "gp": {"left": gp_frame},
    }
    notebook = HeadlessNotebook(parent=results_section)
    notebook.grid()
    app._register_arranger_results_notebook(notebook)

    progress_frame = HeadlessFrame(parent=results_section)
    progress = HeadlessProgressbar(parent=progress_frame, variable=app.arranger_progress_value)
    app._register_arranger_progress_widgets(progress_frame, progress)

    explanation_columns = ("bar", "action", "reason", "delta", "notes")
    explanation_tree = HeadlessTreeview(
        parent=results_section,
        columns=explanation_columns,
        show="headings",
        selectmode="browse",
    )
    app._register_arranger_explanations_tree(explanation_tree)
    explanation_filter = HeadlessCombobox(
        parent=results_section,
        textvariable=app.arranger_explanation_filter,
    )
    app._register_arranger_explanation_filter(explanation_filter)
    telemetry_container = HeadlessFrame(parent=results_section)
    app._register_arranger_telemetry_container(telemetry_container)

    best_effort_advanced = HeadlessFrame()
    gp_advanced = HeadlessFrame()
    app._register_arranger_advanced_frame(best_effort_advanced, mode="best_effort")
    app._register_arranger_advanced_frame(gp_advanced, mode="gp")

    def _update_arranger_mode_layout() -> None:
        try:
            mode = (app.arranger_mode.get() or "classic").strip().lower()
        except Exception:
            mode = "classic"
        if mode == "best_effort":
            classic_frame.grid_remove()
            gp_frame.grid_remove()
            best_effort_frame.grid()
            results_section.grid()
        elif mode == "gp":
            classic_frame.grid_remove()
            best_effort_frame.grid_remove()
            gp_frame.grid()
            results_section.grid()
        else:
            best_effort_frame.grid_remove()
            gp_frame.grid_remove()
            classic_frame.grid()
            results_section.grid_remove()

    app._update_arranger_mode_layout = _update_arranger_mode_layout
    _update_arranger_mode_layout()


if TYPE_CHECKING:  # pragma: no cover
    from ..app import App
