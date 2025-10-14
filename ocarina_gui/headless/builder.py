"""Helpers that assemble the headless widget graph for tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .views import HeadlessFingeringView, HeadlessPianoRoll, HeadlessStaffView
from .widgets import (
    HeadlessButton,
    HeadlessCheckbutton,
    HeadlessFrame,
    HeadlessScale,
    HeadlessSpinbox,
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


if TYPE_CHECKING:  # pragma: no cover
    from ..app import App
