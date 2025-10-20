from __future__ import annotations

import pytest

from shared.tempo import TempoChange, align_duration_to_measure

from viewmodels.preview_playback_viewmodel import (
    LoopRegion,
    PreviewPlaybackState,
    PreviewPlaybackViewModel,
)

from ._preview_playback_helpers import StubAudioRenderer, _build_viewmodel, _make_events


def test_load_prepares_audio_and_resets_state() -> None:
    viewmodel, renderer = _build_viewmodel()
    events = _make_events((0, 120, 60), (240, 90, 62))

    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)

    assert renderer.prepared == (tuple(events), 120)
    assert renderer.prepare_calls == 1
    assert viewmodel.state.duration_tick == 330
    expected_track_end = align_duration_to_measure(330, 120, 4, 4)
    assert viewmodel.state.track_end_tick == expected_track_end
    assert viewmodel.state.position_tick == 0
    assert not viewmodel.state.is_playing


def test_toggle_play_interacts_with_audio_renderer() -> None:
    viewmodel, renderer = _build_viewmodel()
    events = _make_events((0, 120, 60))
    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)

    viewmodel.toggle_playback()
    assert viewmodel.state.is_playing
    assert renderer.started == [(0, viewmodel.state.tempo_bpm)]

    viewmodel.toggle_playback()
    assert not viewmodel.state.is_playing
    assert renderer.paused == 1


def test_toggle_play_handles_audio_start_failure() -> None:
    viewmodel, renderer = _build_viewmodel()
    events = _make_events((0, 120, 60))
    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)
    renderer.start_should_fail = True

    viewmodel.toggle_playback()

    assert not viewmodel.state.is_playing
    assert renderer.started == []


def test_toggle_play_defers_cursor_until_render_finishes() -> None:
    viewmodel, renderer = _build_viewmodel()
    renderer.auto_render = False
    events = _make_events((0, 240, 60))

    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)

    assert viewmodel.state.is_rendering

    viewmodel.toggle_playback()

    assert viewmodel.state.is_playing
    assert renderer.started == [(0, viewmodel.state.tempo_bpm)]

    viewmodel.advance(1.0)
    assert viewmodel.state.position_tick == 0

    renderer.trigger_render()

    assert not viewmodel.state.is_rendering

    viewmodel.advance(1.0)
    assert viewmodel.state.position_tick > 0


def test_advance_updates_position_and_stops_at_end() -> None:
    viewmodel, _ = _build_viewmodel()
    events = _make_events((0, 120, 60))
    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)
    viewmodel.toggle_playback()

    viewmodel.advance(0.5)
    assert viewmodel.state.position_tick == 120

    # Advancing past the end should clamp to the duration and stop playback.
    viewmodel.advance(1.0)
    assert viewmodel.state.position_tick == viewmodel.state.duration_tick
    assert not viewmodel.state.is_playing


def test_advance_respects_variable_tempo_changes() -> None:
    viewmodel, renderer = _build_viewmodel()
    events = _make_events((0, 480, 60), (480, 480, 62))
    tempo_changes = (
        TempoChange(tick=0, tempo_bpm=120.0),
        TempoChange(tick=480, tempo_bpm=60.0),
    )

    viewmodel.load(
        events,
        pulses_per_quarter=480,
        tempo_bpm=120.0,
        tempo_changes=tempo_changes,
        beats_per_measure=4,
        beat_unit=4,
    )
    renderer.trigger_render()
    viewmodel.toggle_playback()

    viewmodel.advance(0.5)
    assert viewmodel.state.position_tick == 480

    viewmodel.advance(1.0)
    assert viewmodel.state.position_tick == 960
    assert not viewmodel.state.is_playing


def test_tempo_change_while_playing_defers_cursor_until_render_completes() -> None:
    viewmodel, renderer = _build_viewmodel()
    renderer.auto_render = False
    events = _make_events((0, 480, 60))

    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)
    viewmodel.toggle_playback()
    renderer.trigger_render()

    viewmodel.advance(1.0)
    initial_position = viewmodel.state.position_tick
    assert initial_position > 0

    viewmodel.set_tempo(180.0)
    assert viewmodel.state.is_rendering

    viewmodel.advance(1.0)
    assert viewmodel.state.position_tick == initial_position

    renderer.trigger_render()

    viewmodel.advance(1.0)
    assert viewmodel.state.position_tick > initial_position


def test_set_volume_updates_renderer_and_state() -> None:
    viewmodel, renderer = _build_viewmodel()

    viewmodel.set_volume(0.42)

    assert renderer.volume_updates[-1] == pytest.approx(0.42)
    assert viewmodel.state.volume == pytest.approx(0.42)

    viewmodel.set_volume(-1.0)

    assert renderer.volume_updates[-1] == pytest.approx(0.0)
    assert viewmodel.state.volume == pytest.approx(0.0)


def test_load_skips_re_render_when_events_unchanged() -> None:
    viewmodel, renderer = _build_viewmodel()
    events = _make_events((0, 120, 60))

    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)
    assert renderer.prepare_calls == 1

    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=3, beat_unit=8)

    assert renderer.prepare_calls == 1
    assert renderer.metronome_updates[-1] == (False, 3, 8)
    assert viewmodel.state.render_progress == 1.0


def test_load_reuse_seeks_without_stopping_when_events_match() -> None:
    viewmodel, renderer = _build_viewmodel()
    events = _make_events((0, 120, 60), (240, 60, 62))

    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)
    viewmodel.seek_to(180)
    renderer.stopped = 0
    renderer.sought.clear()

    repeated_events = _make_events((0, 120, 60), (240, 60, 62))
    viewmodel.load(repeated_events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)

    assert renderer.prepare_calls == 1
    assert renderer.stopped == 0
    assert renderer.sought == [0]
    assert viewmodel.state.position_tick == 0


def test_load_re_renders_when_pulses_per_quarter_change() -> None:
    viewmodel, renderer = _build_viewmodel()
    events = _make_events((0, 120, 60))

    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)
    assert renderer.prepare_calls == 1

    viewmodel.load(events, pulses_per_quarter=240, beats_per_measure=4, beat_unit=4)

    assert renderer.prepare_calls == 2


def test_load_stops_audio_when_events_change() -> None:
    viewmodel, renderer = _build_viewmodel()
    first = _make_events((0, 120, 60))
    second = _make_events((0, 240, 60))

    viewmodel.load(first, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)
    renderer.stopped = 0

    viewmodel.load(second, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)

    assert renderer.prepare_calls == 2
    assert renderer.stopped == 1


def test_seek_clamps_and_notifies_audio_renderer() -> None:
    viewmodel, renderer = _build_viewmodel()
    events = _make_events((0, 60, 60))
    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)

    viewmodel.seek_to(999)
    assert viewmodel.state.position_tick == viewmodel.state.track_end_tick
    assert renderer.sought[-1] == viewmodel.state.track_end_tick


def test_set_tempo_updates_audio_renderer() -> None:
    viewmodel, renderer = _build_viewmodel()
    events = _make_events((0, 120, 60))
    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)

    viewmodel.set_tempo(90.0)
    assert viewmodel.state.tempo_bpm == 90.0
    assert renderer.tempo_updates[-1] == 90.0


def test_stop_halts_audio_and_resets_fractional_progress() -> None:
    viewmodel, renderer = _build_viewmodel()
    events = _make_events((0, 120, 60))
    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)

    viewmodel.toggle_playback()
    viewmodel.advance(0.5)
    position = viewmodel.state.position_tick

    viewmodel.stop()

    assert not viewmodel.state.is_playing
    assert renderer.stopped >= 1
    assert viewmodel.state.position_tick == position


def test_toggle_play_reports_error_without_audio_backend() -> None:
    viewmodel = PreviewPlaybackViewModel(audio_renderer=None)
    events = _make_events((0, 120, 60))
    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)

    result = viewmodel.toggle_playback()

    assert not result
    assert not viewmodel.state.is_playing
    assert viewmodel.state.last_error


def test_successful_start_clears_previous_error() -> None:
    viewmodel = PreviewPlaybackViewModel(audio_renderer=None)
    events = _make_events((0, 120, 60))
    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)

    viewmodel.toggle_playback()
    assert viewmodel.state.last_error

    _, renderer = _build_viewmodel()
    viewmodel = PreviewPlaybackViewModel(audio_renderer=renderer)
    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)
    result = viewmodel.toggle_playback()

    assert result
    assert viewmodel.state.last_error is None


def test_load_updates_time_signature_and_metronome_defaults() -> None:
    viewmodel, renderer = _build_viewmodel()
    events = _make_events((0, 120, 60))

    viewmodel.load(events, pulses_per_quarter=240, beats_per_measure=3, beat_unit=8)

    assert viewmodel.state.beats_per_measure == 3
    assert viewmodel.state.beat_unit == 8
    assert not viewmodel.state.metronome_enabled
    assert renderer.metronome_updates[-1] == (False, 3, 8)


def test_set_metronome_persists_and_resets_on_reload() -> None:
    viewmodel, renderer = _build_viewmodel()
    events = _make_events((0, 480, 60))

    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=6, beat_unit=8)
    viewmodel.set_metronome(True)

    assert viewmodel.state.metronome_enabled
    assert renderer.metronome_updates[-1] == (True, 6, 8)

    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=5, beat_unit=4)

    assert not viewmodel.state.metronome_enabled
    assert renderer.metronome_updates[-1] == (False, 5, 4)


def test_render_listener_updates_state_flags() -> None:
    viewmodel, renderer = _build_viewmodel()

    listener = renderer.render_listener
    assert listener is not None

    listener.render_started(1)
    assert viewmodel.state.is_rendering
    listener.render_progress(1, 0.5)
    assert abs(viewmodel.state.render_progress - 0.5) < 1e-6

    listener.render_complete(1, True)
    assert not viewmodel.state.is_rendering
    assert viewmodel.state.render_progress == 1.0


def test_render_observer_receives_progress_updates() -> None:
    viewmodel, renderer = _build_viewmodel()
    events = _make_events((0, 120, 60))

    notifications: list[tuple[bool, float]] = []
    viewmodel.set_render_observer(
        lambda: notifications.append(
            (viewmodel.state.is_rendering, viewmodel.state.render_progress)
        )
    )

    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)

    assert notifications
    assert notifications[0][0]
    assert any(progress > 0.0 for _active, progress in notifications)
    assert notifications[-1][1] == 1.0
    assert notifications[-1][0] is False
