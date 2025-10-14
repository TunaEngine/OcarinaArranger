from __future__ import annotations

import pytest

from helpers import make_linear_score, make_linear_score_with_tempo

from tests.ui._preview_helpers import write_score


def test_loop_range_selection_enables_loop(gui_app, tmp_path):
    tree, _ = make_linear_score_with_tempo()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    side = "arranged"
    playback = gui_app._preview_playback[side]
    pulses = max(1, playback.state.pulses_per_quarter)

    loop_enabled_var = gui_app._preview_loop_enabled_vars[side]
    loop_enabled_var.set(False)

    gui_app._begin_loop_range_selection(side)
    gui_app._handle_loop_range_click(side, pulses * 4)
    gui_app._handle_loop_range_click(side, pulses * 8)
    gui_app.update_idletasks()

    assert gui_app._coerce_tk_bool(loop_enabled_var.get()) is True

    gui_app._apply_preview_settings(side)
    gui_app.update_idletasks()

    loop_state = playback.state.loop
    assert loop_state.enabled
    assert loop_state.start_tick == pulses * 4
    assert loop_state.end_tick == pulses * 8


def test_preview_loop_invalid_range_disables_apply(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    loop_enabled = gui_app._preview_loop_enabled_vars["original"]
    loop_start = gui_app._preview_loop_start_vars["original"]
    loop_end = gui_app._preview_loop_end_vars["original"]
    apply_button = gui_app._preview_apply_buttons["original"]

    loop_enabled.set(True)
    loop_end.set(1.0)
    loop_start.set(2.0)
    gui_app.update_idletasks()

    assert "disabled" in apply_button.state()

    loop_start.set(0.5)
    gui_app.update_idletasks()

    assert "disabled" not in apply_button.state()


def test_preview_set_range_button_updates_loop_and_markers(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    button = gui_app._preview_loop_range_buttons["original"]
    start_var = gui_app._preview_loop_start_vars["original"]
    end_var = gui_app._preview_loop_end_vars["original"]

    button.invoke()

    playback = gui_app._preview_playback["original"]
    pulses_per_quarter = max(1, playback.state.pulses_per_quarter)
    duration_tick = max(pulses_per_quarter, playback.state.duration_tick)
    first_tick = min(pulses_per_quarter, duration_tick)
    second_tick = min(duration_tick, first_tick + pulses_per_quarter)
    if second_tick <= first_tick:
        second_tick = min(duration_tick, first_tick + max(1, pulses_per_quarter // 2))
    if second_tick <= first_tick:
        second_tick = first_tick + 1

    gui_app._on_preview_cursor_seek("original", first_tick)
    gui_app._on_preview_cursor_seek("original", second_tick)

    expected_start_tick = min(first_tick, second_tick)
    expected_end_tick = max(first_tick, second_tick)

    assert start_var.get() == pytest.approx(expected_start_tick / pulses_per_quarter)
    assert end_var.get() == pytest.approx(expected_end_tick / pulses_per_quarter)

    roll = gui_app.roll_orig
    assert roll is not None
    if hasattr(roll, "loop_region"):
        assert roll.loop_region == (
            expected_start_tick,
            expected_end_tick,
            True,
        )
    else:
        start_line = getattr(roll, "_loop_start_line", None)
        end_line = getattr(roll, "_loop_end_line", None)
        assert start_line is not None
        assert end_line is not None
        assert roll.canvas.itemcget(start_line, "state") == "normal"
        assert roll.canvas.itemcget(end_line, "state") == "normal"
        assert roll.canvas.itemcget(start_line, "fill") != roll.canvas.itemcget(end_line, "fill")
        start_coords = roll.canvas.coords(start_line)
        end_coords = roll.canvas.coords(end_line)
        assert pytest.approx(start_coords[0]) == start_coords[2]
        assert pytest.approx(end_coords[0]) == end_coords[2]
        assert start_coords[0] < end_coords[0]
