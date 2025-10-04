from __future__ import annotations

from tkinter import messagebox

import pytest

from helpers import make_linear_score, make_linear_score_with_tempo
from viewmodels.preview_playback_viewmodel import PreviewPlaybackViewModel

from tests.ui._preview_helpers import write_score


pytestmark = pytest.mark.usefixtures("ensure_original_preview")


def test_arranged_preview_transpose_requires_apply(gui_app, tmp_path, monkeypatch):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))

    calls = []
    original = gui_app.render_previews

    def _tracked_render():
        calls.append(True)
        return original()

    monkeypatch.setattr(gui_app, "render_previews", _tracked_render)

    gui_app.transpose_offset.set(gui_app.transpose_offset.get() + 1)
    gui_app.update_idletasks()
    apply_button = gui_app._transpose_apply_button
    cancel_button = gui_app._transpose_cancel_button
    assert apply_button is not None
    assert cancel_button is not None
    assert "disabled" not in apply_button.state()
    assert "disabled" not in cancel_button.state()
    assert not calls

    apply_button.invoke()
    gui_app.update_idletasks()

    assert calls
    assert "disabled" in apply_button.state()
    assert "disabled" in cancel_button.state()


def test_preview_play_button_toggles(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    play_text = gui_app._preview_play_vars["original"].get()
    assert play_text == "Play"

    gui_app._on_preview_play_toggle("original")
    gui_app.update_idletasks()
    assert gui_app._preview_play_vars["original"].get() == "Pause"

    gui_app._on_preview_play_toggle("original")
    gui_app.update_idletasks()
    assert gui_app._preview_play_vars["original"].get() == "Play"


def test_preview_playback_shows_note_when_not_hovered(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    fingering = gui_app.side_fing_orig
    assert fingering is not None

    def current_midi():
        if hasattr(fingering, "midi"):
            return getattr(fingering, "midi")
        return getattr(fingering, "_current_midi", None)

    gui_app._on_preview_roll_hover("original", None)
    gui_app._on_preview_play_toggle("original")
    gui_app.update_idletasks()

    playback = gui_app._preview_playback["original"]
    assert playback.state.is_playing

    first_event = gui_app._preview_events["original"][0]
    assert current_midi() == first_event[2]

    second_event = gui_app._preview_events["original"][1]
    playback.state.position_tick = second_event[0]
    gui_app._update_playback_visuals("original")
    assert current_midi() == second_event[2]

    gui_app._on_preview_roll_hover("original", 72)
    assert current_midi() == second_event[2]

    gui_app._on_preview_roll_hover("original", None)
    assert current_midi() == second_event[2]

    gui_app._on_preview_play_toggle("original")
    gui_app.update_idletasks()
    assert not playback.state.is_playing

    gui_app._on_preview_roll_hover("original", 72)
    assert current_midi() == 72

    gui_app._on_preview_roll_hover("original", None)
    assert current_midi() is None


def test_preview_hover_ignored_while_dragging(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    fingering = gui_app.side_fing_orig
    assert fingering is not None

    def current_midi():
        if hasattr(fingering, "midi"):
            return getattr(fingering, "midi")
        return getattr(fingering, "_current_midi", None)

    playback = gui_app._preview_playback["original"]
    first_event = gui_app._preview_events["original"][0]
    playback.state.position_tick = first_event[0]
    gui_app._update_playback_visuals("original")

    gui_app._on_preview_cursor_drag_state("original", True)
    gui_app._on_preview_roll_hover("original", first_event[2] + 12)
    assert current_midi() == first_event[2]

    gui_app._on_preview_cursor_drag_state("original", False)
    gui_app._on_preview_roll_hover("original", first_event[2] + 12)
    assert current_midi() == first_event[2] + 12


def test_transpose_cancel_restores_previous_value(gui_app, tmp_path, monkeypatch):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    original = int(gui_app.transpose_offset.get())
    calls = []

    def _tracked_render():
        calls.append(True)

    monkeypatch.setattr(gui_app, "render_previews", _tracked_render)

    gui_app.transpose_offset.set(original + 2)
    gui_app.update_idletasks()

    cancel_button = gui_app._transpose_cancel_button
    apply_button = gui_app._transpose_apply_button
    assert cancel_button is not None
    assert apply_button is not None
    assert "disabled" not in cancel_button.state()

    cancel_button.invoke()
    gui_app.update_idletasks()

    assert gui_app.transpose_offset.get() == original
    assert not calls
    assert "disabled" in cancel_button.state()
    assert "disabled" in apply_button.state()


def test_preview_play_toggle_resets_elapsed(gui_app, tmp_path, monkeypatch):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    job = gui_app._playback_job
    if job is not None:
        try:
            gui_app.after_cancel(job)
        except Exception:
            pass
        gui_app._playback_job = None

    playback = gui_app._preview_playback["original"]
    gui_app._playback_last_ts = 50.0

    times = iter([1000.0, 1000.5])
    monkeypatch.setattr("ui.main_window.time.perf_counter", lambda: next(times))

    gui_app._on_preview_play_toggle("original")
    assert playback.state.is_playing
    assert gui_app._playback_last_ts == pytest.approx(1000.0)


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


def test_preview_cursor_seek_updates_playback_state(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    gui_app._on_preview_cursor_seek("original", 240)
    playback = gui_app._preview_playback["original"]
    assert playback.state.position_tick == 240


def test_preview_tempo_control_updates_viewmodel(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    tempo_var = gui_app._preview_tempo_vars["original"]
    apply_button = gui_app._preview_apply_buttons["original"]
    cancel_button = gui_app._preview_cancel_buttons["original"]
    assert "disabled" in apply_button.state()
    assert "disabled" in cancel_button.state()

    tempo_var.set(150.0)
    gui_app.update_idletasks()
    assert "disabled" not in apply_button.state()

    apply_button.invoke()
    gui_app.update_idletasks()

    playback = gui_app._preview_playback["original"]
    assert playback.state.tempo_bpm == pytest.approx(150.0)
    assert "disabled" in apply_button.state()
    assert "disabled" in cancel_button.state()


def test_preview_loop_controls_apply_updates_viewmodel(gui_app, tmp_path):
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
    loop_start.set(0.0)
    loop_end.set(2.0)
    gui_app.update_idletasks()

    assert "disabled" not in apply_button.state()

    apply_button.invoke()
    gui_app.update_idletasks()

    playback = gui_app._preview_playback["original"]
    renderer = gui_app._test_audio_renderers["original"]
    assert playback.state.loop.enabled
    assert renderer.loop_region is not None and renderer.loop_region.enabled
    pulses_per_quarter = max(1, playback.state.pulses_per_quarter)
    assert playback.state.loop.start_tick == pytest.approx(int(round(0.0 * pulses_per_quarter)))
    assert playback.state.loop.end_tick == pytest.approx(int(round(2.0 * pulses_per_quarter)))
    assert "disabled" in apply_button.state()


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


def test_preview_adjust_controls_disable_while_playing(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    tempo_widget = gui_app._preview_tempo_controls["original"]
    metronome_widget = gui_app._preview_metronome_controls["original"]
    loop_widgets = gui_app._preview_loop_controls["original"]
    apply_button = gui_app._preview_apply_buttons["original"]

    assert "disabled" not in set(tempo_widget.state())
    assert "disabled" not in set(metronome_widget.state())
    for widget in loop_widgets:
        assert "disabled" not in set(widget.state())

    gui_app._on_preview_play_toggle("original")
    gui_app.update_idletasks()

    assert "disabled" in set(tempo_widget.state())
    assert "disabled" in set(metronome_widget.state())
    assert "disabled" in set(apply_button.state())
    for widget in loop_widgets:
        assert "disabled" in set(widget.state())

    gui_app._on_preview_play_toggle("original")
    gui_app.update_idletasks()

    assert "disabled" not in set(tempo_widget.state())
    assert "disabled" not in set(metronome_widget.state())
    for widget in loop_widgets:
        assert "disabled" not in set(widget.state())


def test_preview_metronome_toggle_updates_viewmodel(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    metronome_var = gui_app._preview_metronome_vars["original"]
    apply_button = gui_app._preview_apply_buttons["original"]
    metronome_var.set(True)
    gui_app.update_idletasks()
    apply_button.invoke()
    gui_app.update_idletasks()

    playback = gui_app._preview_playback["original"]
    assert playback.state.metronome_enabled


def test_preview_cancel_restores_previous_values(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    tempo_var = gui_app._preview_tempo_vars["original"]
    metronome_var = gui_app._preview_metronome_vars["original"]
    apply_button = gui_app._preview_apply_buttons["original"]
    cancel_button = gui_app._preview_cancel_buttons["original"]
    original_tempo = tempo_var.get()
    original_metronome = metronome_var.get()

    tempo_var.set(original_tempo + 12.0)
    metronome_var.set(not original_metronome)
    gui_app.update_idletasks()
    assert "disabled" not in cancel_button.state()

    cancel_button.invoke()
    gui_app.update_idletasks()

    assert tempo_var.get() == pytest.approx(original_tempo)
    assert metronome_var.get() == original_metronome
    assert "disabled" in apply_button.state()
    assert "disabled" in cancel_button.state()


def test_importing_new_file_resets_preview_adjustments(gui_app, tmp_path):
    tree_one, _ = make_linear_score()
    tree_two, _ = make_linear_score()
    first = write_score(tmp_path, tree_one, name="first.musicxml")
    second = write_score(tmp_path, tree_two, name="second.musicxml")

    gui_app.input_path.set(str(first))
    gui_app.render_previews()
    gui_app.update_idletasks()

    tempo_var = gui_app._preview_tempo_vars["arranged"]
    loop_start_var = gui_app._preview_loop_start_vars["arranged"]
    loop_end_var = gui_app._preview_loop_end_vars["arranged"]
    loop_enabled_var = gui_app._preview_loop_enabled_vars["arranged"]
    apply_button = gui_app._preview_apply_buttons["arranged"]

    assert apply_button is not None

    tempo_var.set(180.0)
    loop_start_var.set(1.0)
    loop_end_var.set(2.0)
    loop_enabled_var.set(True)
    gui_app.update_idletasks()
    apply_button.invoke()
    gui_app.update_idletasks()

    arranged_playback = gui_app._preview_playback["arranged"]
    arranged_playback.state.position_tick = 240
    gui_app._update_playback_visuals("arranged")
    assert arranged_playback.state.tempo_bpm != pytest.approx(120.0)
    assert arranged_playback.state.loop.enabled

    gui_app.input_path.set(str(second))
    gui_app.update_idletasks()

    arranged_playback = gui_app._preview_playback["arranged"]
    assert arranged_playback.state.position_tick == 0
    assert arranged_playback.state.tempo_bpm == pytest.approx(120.0)
    assert not arranged_playback.state.loop.enabled
    assert not arranged_playback.state.metronome_enabled
    assert not bool(gui_app._preview_loop_enabled_vars["arranged"].get())

    preview_settings = gui_app._viewmodel.state.preview_settings
    arranged_snapshot = preview_settings.get("arranged")
    assert arranged_snapshot is not None
    assert arranged_snapshot.tempo_bpm == pytest.approx(120.0)
    assert not arranged_snapshot.metronome_enabled
    assert not arranged_snapshot.loop_enabled
    assert arranged_snapshot.loop_start_beat == pytest.approx(0.0)
    assert arranged_snapshot.loop_end_beat >= arranged_snapshot.loop_start_beat


def test_arranged_tempo_matches_original_tempo(gui_app, tmp_path):
    tree, _ = make_linear_score_with_tempo(tempo=84)
    path = write_score(tmp_path, tree)

    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    original_applied = gui_app._preview_applied_settings["original"]
    arranged_applied = gui_app._preview_applied_settings["arranged"]

    assert original_applied["tempo"] == pytest.approx(84.0)
    assert arranged_applied["tempo"] == pytest.approx(84.0)

    gui_app._ensure_preview_tab_initialized("arranged")
    gui_app.update_idletasks()

    assert gui_app._preview_playback["original"].state.tempo_bpm == pytest.approx(84.0)
    assert gui_app._preview_playback["arranged"].state.tempo_bpm == pytest.approx(84.0)
    assert gui_app._preview_applied_settings["arranged"]["tempo"] == pytest.approx(84.0)


def test_preview_play_warns_when_audio_unavailable(gui_app, tmp_path, monkeypatch):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))

    warning_calls = []
    monkeypatch.setattr(messagebox, "showwarning", lambda *args, **kwargs: warning_calls.append(args))

    playback = PreviewPlaybackViewModel(audio_renderer=None)
    gui_app._preview_playback["original"] = playback

    gui_app.render_previews()
    gui_app.update_idletasks()

    gui_app._on_preview_play_toggle("original")
    gui_app.update_idletasks()

    assert warning_calls
    assert not playback.state.is_playing
    assert playback.state.last_error


def test_destroy_stops_preview_audio(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    playback = gui_app._preview_playback["original"]
    gui_app._on_preview_play_toggle("original")
    gui_app.update_idletasks()
    assert playback.state.is_playing

    gui_app.destroy()

    assert gui_app._playback_job is None
    assert not playback.state.is_playing
