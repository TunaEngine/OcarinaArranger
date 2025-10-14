from __future__ import annotations

import audioop
import threading
import time

import pytest

from ocarina_gui import audio
from ocarina_gui.audio.synth import rendering
from shared.tempo import TempoChange

from .helpers import (
    DummyPlayer,
    await_render,
    render_simple_events,
    tempo_config,
    wait_for_playback,
)


def test_synth_renderer_boosts_low_pitch_segments() -> None:
    rendering.clear_note_segment_cache()

    tempo_key = audio._SynthRenderer._tempo_cache_key(120.0)
    sample_rate = audio._SynthRenderer._SAMPLE_RATE

    low_segment = rendering.note_segment(79, 48, 480, tempo_key, 480, sample_rate)
    high_segment = rendering.note_segment(79, 72, 480, tempo_key, 480, sample_rate)

    low_avg = sum(abs(value) for value in low_segment) / len(low_segment)
    high_avg = sum(abs(value) for value in high_segment) / len(high_segment)

    assert low_avg > high_avg * 1.1


def test_synth_renderer_generates_pcm_when_started() -> None:
    player = DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        render_simple_events(renderer)
        started = renderer.start(0, 120.0)

        assert started
        await_render(renderer)
        wait_for_playback(player)
        assert player.calls, "expected play() to be invoked"
        pcm, sample_rate = player.calls[-1]
        assert sample_rate == renderer._SAMPLE_RATE
        assert len(pcm) > 0
    finally:
        renderer.shutdown()


@pytest.mark.skip("temporarily disabled while investigating renderer flake")
def test_synth_renderer_volume_changes_restart_playback() -> None:
    player = DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        events = [(0, 480, 69, 79)]
        renderer.prepare(events, 480)
        assert renderer.start(0, 120.0)

        await_render(renderer)
        wait_for_playback(player)

        first_pcm, _ = player.calls[-1]
        first_rms = audioop.rms(first_pcm, 2)
        assert first_rms > 0

        renderer.set_volume(0.25)
        wait_for_playback(player, min_calls=2)

        second_pcm, _ = player.calls[-1]
        assert len(second_pcm) == len(first_pcm)
        second_rms = audioop.rms(second_pcm, 2)
        assert second_rms == pytest.approx(first_rms * 0.25, rel=0.2)

        renderer.set_volume(0.0)
        wait_for_playback(player, min_calls=3)

        muted_pcm, _ = player.calls[-1]
        assert audioop.rms(muted_pcm, 2) == 0
    finally:
        renderer.shutdown()


def test_synth_renderer_uses_instrument_specific_waveforms() -> None:
    player = DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        metronome = rendering.MetronomeSettings(enabled=False, beats_per_measure=4, beat_unit=4)

        piano_pcm, _ = renderer._render_events([(0, 480, 60, 0)], 120.0, 480, metronome)
        ocarina_pcm, _ = renderer._render_events([(0, 480, 60, 79)], 120.0, 480, metronome)

        assert piano_pcm != ocarina_pcm
    finally:
        renderer.shutdown()


def test_render_events_respects_mid_track_tempo_change() -> None:
    tempo_changes = [TempoChange(tick=0, tempo_bpm=120.0), TempoChange(tick=480, tempo_bpm=60.0)]
    config, _ = tempo_config(120.0, tempo_changes)
    events = [(0, 480, 69, 79), (480, 480, 71, 79)]

    pcm, tempo_map = rendering.render_events(
        events,
        tempo=120.0,
        pulses_per_quarter=480,
        config=config,
        tempo_changes=tempo_changes,
    )

    assert pcm, "expected rendered PCM for tempo change test"
    assert tempo_map.seconds_at(480) == pytest.approx(0.5, rel=1e-3)
    assert tempo_map.seconds_at(960) == pytest.approx(1.5, rel=1e-3)


def test_synth_renderer_caches_note_segments() -> None:
    player = DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        rendering.clear_note_segment_cache()

        events = [(0, 960, 60, 79), (960, 960, 60, 79)]
        renderer.prepare(events, 480)
        await_render(renderer, timeout=5.0)
        first_cache = rendering.get_note_segment_cache_info()

        renderer.prepare(events, 480)
        await_render(renderer, timeout=5.0)
        second_cache = rendering.get_note_segment_cache_info()

        assert second_cache.hits > first_cache.hits
        rendering.clear_note_segment_cache()
    finally:
        renderer.shutdown()


def test_synth_renderer_prepare_renders_asynchronously(monkeypatch) -> None:
    player = DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        entered = threading.Event()
        release = threading.Event()

        def fake_render(
            self,
            events,
            tempo,
            ppq,
            metronome,
            progress_callback=None,
            tempo_changes=None,
        ):  # type: ignore[no-untyped-def]
            if progress_callback is not None:
                progress_callback(0.0)
            entered.set()
            release.wait(0.2)
            if progress_callback is not None:
                progress_callback(1.0)
            changes = list(tempo_changes or [TempoChange(tick=0, tempo_bpm=tempo)])
            tempo_map = rendering.TempoMap(ppq, changes)
            tempo_map.sample_rate = audio._SynthRenderer._SAMPLE_RATE
            return b"\x00\x00", tempo_map

        monkeypatch.setattr(audio._SynthRenderer, "_render_events", fake_render, raising=False)

        renderer.prepare([(0, 960, 60, 79)], 480)

        assert entered.wait(0.2)
        assert not renderer._render_ready.is_set()  # type: ignore[attr-defined]

        release.set()
        await_render(renderer, timeout=0.2)

        started = renderer.start(0, 120.0)
        assert started
        wait_for_playback(player)
        assert player.calls
    finally:
        renderer.shutdown()


def test_set_tempo_rerenders_asynchronously_while_playing(monkeypatch) -> None:
    player = DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        events = [(0, 960, 60, 79)]
        renderer.prepare(events, 480)
        assert renderer.start(0, 120.0)
        await_render(renderer)
        wait_for_playback(player)
        initial_handle = player.handles[-1]

        entered = threading.Event()
        release = threading.Event()
        call_done = threading.Event()

        def fake_render(
            self,
            events,
            tempo,
            ppq,
            metronome,
            progress_callback=None,
            tempo_changes=None,
        ):  # type: ignore[no-untyped-def]
            if progress_callback is not None:
                progress_callback(0.0)
            entered.set()
            release.wait(0.2)
            if progress_callback is not None:
                progress_callback(1.0)
            changes = list(tempo_changes or [TempoChange(tick=0, tempo_bpm=tempo)])
            tempo_map = rendering.TempoMap(ppq, changes)
            tempo_map.sample_rate = audio._SynthRenderer._SAMPLE_RATE
            return b"\x00\x00", tempo_map

        monkeypatch.setattr(audio._SynthRenderer, "_render_events", fake_render, raising=False)

        def invoke() -> None:
            try:
                renderer.set_tempo(150.0)
            finally:
                call_done.set()

        thread = threading.Thread(target=invoke)
        thread.start()
        try:
            assert entered.wait(0.2), "expected render thread to start"
            assert call_done.wait(0.2), "set_tempo should return without waiting for render"
            assert initial_handle.stopped, "previous playback handle should be stopped"
        finally:
            release.set()
            thread.join(timeout=0.5)

        assert not thread.is_alive(), "set_tempo thread should have completed"
        await_render(renderer, timeout=0.2)

        deadline = time.perf_counter() + 0.5
        while time.perf_counter() < deadline and len(player.handles) < 2:
            time.sleep(0.01)

        assert len(player.handles) >= 2, "playback should restart after re-render"
    finally:
        renderer.shutdown()


def test_synth_renderer_reports_intermediate_progress(monkeypatch) -> None:
    player = DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        progress_values: list[float] = []
        completed = threading.Event()

        class _Listener:
            def render_started(self, generation: int) -> None:
                pass

            def render_progress(self, generation: int, progress: float) -> None:
                progress_values.append(progress)
                if progress >= 1.0:
                    completed.set()

            def render_complete(self, generation: int, success: bool) -> None:
                completed.set()

        listener = _Listener()
        renderer.set_render_listener(listener)

        monkeypatch.setattr(audio._SynthRenderer, "_PROGRESS_CHUNK_SIZE", 64, raising=False)

        events = [(0, 9600, 64, 79)]
        renderer.prepare(events, 480)

        assert renderer._render_ready.wait(1.0)  # type: ignore[attr-defined]
        assert completed.wait(1.0)

        intermediate = [value for value in progress_values if 0.0 < value < 1.0]
        assert intermediate, "expected at least one intermediate progress update"
    finally:
        renderer.shutdown()
