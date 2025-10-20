from __future__ import annotations

import pytest

from helpers import make_linear_score, make_linear_score_with_tempo
from services.project_service import PreviewPlaybackSnapshot
from shared.tempo import align_duration_to_measure

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


def test_disabling_loop_aligns_end_with_track(gui_app, tmp_path):
    tree, _ = make_linear_score_with_tempo()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    side = "arranged"
    playback = gui_app._preview_playback[side]
    pulses = max(1, playback.state.pulses_per_quarter)

    loop_start_var = gui_app._preview_loop_start_vars[side]
    loop_end_var = gui_app._preview_loop_end_vars[side]
    loop_enabled_var = gui_app._preview_loop_enabled_vars[side]

    loop_start_var.set(1.0)
    loop_end_var.set(2.0)
    loop_enabled_var.set(True)
    gui_app.update_idletasks()
    gui_app._apply_preview_settings(side)
    gui_app.update_idletasks()

    loop_enabled_var.set(False)
    gui_app.update_idletasks()
    gui_app._apply_preview_settings(side)
    gui_app.update_idletasks()

    assert not gui_app._coerce_tk_bool(loop_enabled_var.get())
    assert loop_start_var.get() == pytest.approx(0.0)
    aligned_end = align_duration_to_measure(
        playback.state.duration_tick,
        playback.state.pulses_per_quarter,
        playback.state.beats_per_measure,
        playback.state.beat_unit,
    )
    assert loop_end_var.get() == pytest.approx(aligned_end / pulses)


def test_loop_markers_use_track_bounds_when_disabled(gui_app, tmp_path):
    tree, _ = make_linear_score_with_tempo()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    side = "arranged"
    playback = gui_app._preview_playback[side]

    loop_start_var = gui_app._preview_loop_start_vars[side]
    loop_end_var = gui_app._preview_loop_end_vars[side]
    loop_enabled_var = gui_app._preview_loop_enabled_vars[side]

    loop_start_var.set(4.0)
    loop_end_var.set(8.0)
    loop_enabled_var.set(False)
    gui_app.update_idletasks()

    gui_app._update_loop_marker_visuals(side)

    roll = gui_app._roll_for_side(side)
    assert roll is not None
    expected_end = align_duration_to_measure(
        playback.state.duration_tick,
        playback.state.pulses_per_quarter,
        playback.state.beats_per_measure,
        playback.state.beat_unit,
    )
    if hasattr(roll, "loop_region"):
        assert roll.loop_region == (0, expected_end, False)
    else:
        start_line = getattr(roll, "_loop_start_line", None)
        end_line = getattr(roll, "_loop_end_line", None)
        assert start_line is not None
        assert end_line is not None
        assert getattr(roll, "_loop_start_tick", None) == 0
        assert getattr(roll, "_loop_end_tick", None) == expected_end
        state_start = roll.canvas.itemcget(start_line, "state")
        state_end = roll.canvas.itemcget(end_line, "state")
        assert state_start == state_end == "hidden"


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


def test_loading_new_score_resets_loop_end_to_track_length(gui_app, tmp_path):
    short_tree, _ = make_linear_score()
    short_path = write_score(tmp_path, short_tree, name="short.musicxml")

    long_tree, long_root = make_linear_score()
    tail_note = long_root.findall(".//note")[-1]
    tail_duration = tail_note.find("duration")
    assert tail_duration is not None
    tail_duration.text = "16"
    long_path = write_score(tmp_path, long_tree, name="long.musicxml")

    side = "arranged"
    gui_app.input_path.set(str(short_path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    playback = gui_app._preview_playback[side]
    pulses = max(1, playback.state.pulses_per_quarter)
    short_end_tick = align_duration_to_measure(
        playback.state.duration_tick,
        playback.state.pulses_per_quarter,
        playback.state.beats_per_measure,
        playback.state.beat_unit,
    )

    loop_enabled_var = gui_app._preview_loop_enabled_vars[side]
    loop_start_var = gui_app._preview_loop_start_vars[side]
    loop_end_var = gui_app._preview_loop_end_vars[side]
    loop_start_var.set(0.0)
    loop_end_var.set(short_end_tick / pulses)
    loop_enabled_var.set(True)
    gui_app.update_idletasks()
    gui_app._apply_preview_settings(side)
    gui_app.update_idletasks()

    assert gui_app._coerce_tk_bool(loop_enabled_var.get()) is True
    assert loop_end_var.get() == pytest.approx(short_end_tick / pulses)

    gui_app.input_path.set(str(long_path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    new_playback = gui_app._preview_playback[side]
    new_pulses = max(1, new_playback.state.pulses_per_quarter)
    long_end_tick = align_duration_to_measure(
        new_playback.state.duration_tick,
        new_playback.state.pulses_per_quarter,
        new_playback.state.beats_per_measure,
        new_playback.state.beat_unit,
    )

    assert gui_app._coerce_tk_bool(loop_enabled_var.get()) is False
    assert loop_start_var.get() == pytest.approx(0.0)
    assert loop_end_var.get() == pytest.approx(long_end_tick / new_pulses)


def test_preview_snapshot_loop_bounds_clamped_to_track(gui_app, tmp_path):
    tree, _ = make_linear_score_with_tempo()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))

    snapshot = PreviewPlaybackSnapshot(
        tempo_bpm=120.0,
        metronome_enabled=False,
        loop_enabled=True,
        loop_start_beat=0.0,
        loop_end_beat=32.0,
        volume=1.0,
    )
    gui_app._viewmodel.update_preview_settings({"arranged": snapshot})

    gui_app.render_previews()
    gui_app.update_idletasks()

    side = "arranged"
    playback = gui_app._preview_playback[side]
    pulses = max(1, playback.state.pulses_per_quarter)

    track_end_tick = playback.state.track_end_tick
    if track_end_tick <= 0:
        track_end_tick = align_duration_to_measure(
            playback.state.duration_tick,
            playback.state.pulses_per_quarter,
            playback.state.beats_per_measure,
            playback.state.beat_unit,
        )
    expected_end_beats = track_end_tick / pulses if track_end_tick > 0 else 0.0

    loop_enabled_var = gui_app._preview_loop_enabled_vars[side]
    loop_end_var = gui_app._preview_loop_end_vars[side]

    assert gui_app._coerce_tk_bool(loop_enabled_var.get()) is True
    assert loop_end_var.get() == pytest.approx(expected_end_beats)

    loop_state = playback.state.loop
    assert loop_state.enabled
    assert loop_state.end_tick == track_end_tick
