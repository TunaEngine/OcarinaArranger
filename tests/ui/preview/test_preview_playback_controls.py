from __future__ import annotations

from tkinter import messagebox

import pytest

from helpers import make_linear_score
from viewmodels.preview_playback_viewmodel import PreviewPlaybackViewModel

from tests.ui._preview_helpers import write_score


def _current_midi_value(fingering: object) -> int | None:
    if hasattr(fingering, "midi"):
        return getattr(fingering, "midi")
    return getattr(fingering, "_current_midi", None)


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

    gui_app._on_preview_roll_hover("original", None)
    gui_app._on_preview_play_toggle("original")
    gui_app.update_idletasks()

    playback = gui_app._preview_playback["original"]
    assert playback.state.is_playing

    first_event = gui_app._preview_events["original"][0]
    assert _current_midi_value(fingering) == first_event[2]

    second_event = gui_app._preview_events["original"][1]
    playback.state.position_tick = second_event[0]
    gui_app._update_playback_visuals("original")
    assert _current_midi_value(fingering) == second_event[2]

    gui_app._on_preview_roll_hover("original", 72)
    assert _current_midi_value(fingering) == second_event[2]

    gui_app._on_preview_roll_hover("original", None)
    assert _current_midi_value(fingering) == second_event[2]

    gui_app._on_preview_play_toggle("original")
    gui_app.update_idletasks()
    assert not playback.state.is_playing

    gui_app._on_preview_roll_hover("original", 72)
    assert _current_midi_value(fingering) == 72

    gui_app._on_preview_roll_hover("original", None)
    assert _current_midi_value(fingering) is None


def test_preview_hover_ignored_while_dragging(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    fingering = gui_app.side_fing_orig
    assert fingering is not None

    playback = gui_app._preview_playback["original"]
    first_event = gui_app._preview_events["original"][0]
    playback.state.position_tick = first_event[0]
    gui_app._update_playback_visuals("original")

    gui_app._on_preview_cursor_drag_state("original", True)
    gui_app._on_preview_roll_hover("original", first_event[2] + 12)
    assert _current_midi_value(fingering) == first_event[2]

    gui_app._on_preview_cursor_drag_state("original", False)
    gui_app._on_preview_roll_hover("original", first_event[2] + 12)
    assert _current_midi_value(fingering) == first_event[2] + 12


def test_preview_cursor_drag_pauses_and_resumes_playback(gui_app, tmp_path, monkeypatch):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    playback = gui_app._preview_playback["original"]
    assert not playback.state.is_playing

    gui_app._on_preview_play_toggle("original")
    gui_app.update_idletasks()
    assert playback.state.is_playing

    calls: list[float] = []

    def _fake_perf_counter() -> float:
        value = 1000.0 + len(calls)
        calls.append(value)
        return value

    monkeypatch.setattr("time.perf_counter", _fake_perf_counter)

    gui_app._on_preview_cursor_drag_state("original", True)
    gui_app.update_idletasks()
    assert not playback.state.is_playing

    gui_app._on_preview_cursor_drag_state("original", False)
    gui_app.update_idletasks()
    assert playback.state.is_playing
    assert calls, "expected fake perf counter to be invoked"
    assert gui_app._playback_last_ts == pytest.approx(calls[-1])


def test_preview_cursor_seek_pauses_before_rewind(gui_app, tmp_path, monkeypatch):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    playback = gui_app._preview_playback["original"]
    gui_app._on_preview_play_toggle("original")
    gui_app.update_idletasks()
    assert playback.state.is_playing

    observed: list[bool] = []
    original_seek_to = playback.seek_to

    def _tracked_seek_to(tick: int) -> None:
        observed.append(playback.state.is_playing)
        original_seek_to(tick)

    monkeypatch.setattr(playback, "seek_to", _tracked_seek_to)

    gui_app._on_preview_cursor_seek("original", 0)
    gui_app.update_idletasks()

    assert observed, "expected cursor seek to invoke playback seek"
    assert observed[0] is False


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


def test_preview_cursor_seek_updates_playback_state(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    gui_app._on_preview_cursor_seek("original", 240)
    playback = gui_app._preview_playback["original"]
    assert playback.state.position_tick == 240


def test_preview_play_warns_when_audio_unavailable(gui_app, tmp_path, monkeypatch):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))

    warning_calls: list[tuple] = []
    monkeypatch.setattr(
        messagebox,
        "showwarning",
        lambda *args, **kwargs: warning_calls.append(args),
    )

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
