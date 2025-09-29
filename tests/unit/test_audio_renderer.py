from __future__ import annotations

import threading
import time
from pathlib import Path

from ocarina_gui import audio
from ocarina_gui.audio.synth import rendering


class _DummyHandle(audio._PlaybackHandle):
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class _DummyPlayer(audio._AudioPlayer):
    def __init__(self) -> None:
        self.calls: list[tuple[bytes, int]] = []
        self.handles: list[_DummyHandle] = []
        self.stop_all_calls = 0

    def play(self, pcm: bytes, sample_rate: int) -> audio._PlaybackHandle:
        self.calls.append((pcm, sample_rate))
        handle = _DummyHandle()
        self.handles.append(handle)
        return handle

    def stop_all(self) -> None:
        self.stop_all_calls += 1


class _FailingPlayer(audio._AudioPlayer):
    def __init__(self) -> None:
        self.play_calls = 0
        self.stop_all_calls = 0

    def play(self, pcm: bytes, sample_rate: int) -> audio._PlaybackHandle | None:
        self.play_calls += 1
        return None

    def stop_all(self) -> None:
        self.stop_all_calls += 1


class _CountingPlayer(audio._AudioPlayer):
    def __init__(self) -> None:
        self.play_calls = 0
        self.stop_all_calls = 0
        self.handle = _DummyHandle()

    def play(self, pcm: bytes, sample_rate: int) -> audio._PlaybackHandle:
        self.play_calls += 1
        return self.handle

    def stop_all(self) -> None:
        self.stop_all_calls += 1


def _await_render(renderer: audio._SynthRenderer, timeout: float = 1.0) -> None:
    assert renderer._render_ready.wait(timeout)  # type: ignore[attr-defined]


def _wait_for_playback(
    player: _DummyPlayer, *, min_calls: int = 1, timeout: float = 1.0
) -> None:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if len(player.calls) >= min_calls:
            return
        time.sleep(0.01)
    raise AssertionError("expected playback to start")


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
    player = _DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        events = [(0, 480, 69, 79), (480, 480, 71, 79)]
        renderer.prepare(events, 480)
        started = renderer.start(0, 120.0)

        assert started
        _await_render(renderer)
        _wait_for_playback(player)
        assert player.calls, "expected play() to be invoked"
        pcm, sample_rate = player.calls[-1]
        assert sample_rate == renderer._SAMPLE_RATE
        assert len(pcm) > 0
    finally:
        renderer.shutdown()


def test_synth_renderer_uses_instrument_specific_waveforms() -> None:
    player = _DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        metronome = rendering.MetronomeSettings(enabled=False, beats_per_measure=4, beat_unit=4)

        piano_pcm, _ = renderer._render_events([(0, 480, 60, 0)], 120.0, 480, metronome)
        ocarina_pcm, _ = renderer._render_events([(0, 480, 60, 79)], 120.0, 480, metronome)

        assert piano_pcm != ocarina_pcm
    finally:
        renderer.shutdown()


def test_synth_renderer_caches_note_segments() -> None:
    player = _DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        rendering.clear_note_segment_cache()

        events = [(0, 960, 60, 79), (960, 960, 60, 79)]
        renderer.prepare(events, 480)
        assert renderer._render_ready.wait(2.0)  # type: ignore[attr-defined]
        first_cache = rendering.get_note_segment_cache_info()

        renderer.prepare(events, 480)
        assert renderer._render_ready.wait(2.0)  # type: ignore[attr-defined]
        second_cache = rendering.get_note_segment_cache_info()

        assert second_cache.hits > first_cache.hits
        rendering.clear_note_segment_cache()
    finally:
        renderer.shutdown()


def test_synth_renderer_reseeks_while_playing() -> None:
    player = _DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        events = [(0, 960, 60, 79)]
        renderer.prepare(events, 480)
        assert renderer.start(0, 120.0)
        _await_render(renderer)
        _wait_for_playback(player)
        renderer.seek(240)

        _wait_for_playback(player, min_calls=2)
        assert len(player.calls) >= 2
    finally:
        renderer.shutdown()


def test_synth_renderer_pause_stops_backend() -> None:
    player = _DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        events = [(0, 960, 60, 79)]
        renderer.prepare(events, 480)
        assert renderer.start(0, 120.0)
        _await_render(renderer)
        _wait_for_playback(player)
        handle = player.handles[-1]
        renderer.pause()

        assert handle.stopped
        assert renderer._handle is None  # type: ignore[attr-defined]
        assert player.stop_all_calls >= 1
    finally:
        renderer.shutdown()


def test_synth_renderer_stop_halts_backend_even_without_playing_flag() -> None:
    player = _DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        events = [(0, 960, 60, 79)]
        renderer.prepare(events, 480)
        assert renderer.start(0, 120.0)
        _await_render(renderer)
        _wait_for_playback(player)
        handle = player.handles[-1]
        renderer.stop()

        assert handle.stopped
        assert renderer._handle is None  # type: ignore[attr-defined]
        assert player.stop_all_calls >= 1
    finally:
        renderer.shutdown()


def test_synth_renderer_prepare_renders_asynchronously(monkeypatch) -> None:
    player = _DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        entered = threading.Event()
        release = threading.Event()

        def fake_render(self, events, tempo, ppq, metronome, progress_callback=None):  # type: ignore[no-untyped-def]
            if progress_callback is not None:
                progress_callback(0.0)
            entered.set()
            release.wait(0.2)
            if progress_callback is not None:
                progress_callback(1.0)
            return b"\x00\x00", max((tempo / 60.0) * ppq, 1e-3)

        monkeypatch.setattr(audio._SynthRenderer, "_render_events", fake_render, raising=False)

        renderer.prepare([(0, 960, 60, 79)], 480)

        assert entered.wait(0.2)
        assert not renderer._render_ready.is_set()  # type: ignore[attr-defined]

        release.set()
        _await_render(renderer, timeout=0.2)

        started = renderer.start(0, 120.0)
        assert started
        _wait_for_playback(player)
        assert player.calls
    finally:
        renderer.shutdown()


def test_set_tempo_rerenders_asynchronously_while_playing(monkeypatch) -> None:
    player = _DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        events = [(0, 960, 60, 79)]
        renderer.prepare(events, 480)
        assert renderer.start(0, 120.0)
        _await_render(renderer)
        _wait_for_playback(player)
        initial_handle = player.handles[-1]

        entered = threading.Event()
        release = threading.Event()
        call_done = threading.Event()

        def fake_render(self, events, tempo, ppq, metronome, progress_callback=None):  # type: ignore[no-untyped-def]
            if progress_callback is not None:
                progress_callback(0.0)
            entered.set()
            release.wait(0.2)
            if progress_callback is not None:
                progress_callback(1.0)
            return b"\x00\x00", max((tempo / 60.0) * ppq, 1e-3)

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
        _await_render(renderer, timeout=0.2)

        deadline = time.perf_counter() + 0.5
        while time.perf_counter() < deadline and len(player.handles) < 2:
            time.sleep(0.01)

        assert len(player.handles) >= 2, "playback should restart after re-render"
    finally:
        renderer.shutdown()


def test_synth_renderer_start_returns_false_when_player_fails() -> None:
    player = _FailingPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        renderer.prepare([(0, 960, 60, 79)], 480)
        _await_render(renderer)

        assert not renderer.start(0, 120.0)
        assert player.stop_all_calls >= 1
    finally:
        renderer.shutdown()


def test_synth_renderer_seek_restarts_backend_handle() -> None:
    player = _DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        events = [(0, 960, 60, 79)]
        renderer.prepare(events, 480)
        assert renderer.start(0, 120.0)
        _await_render(renderer)
        _wait_for_playback(player)
        first_handle = player.handles[-1]

        renderer.seek(240)

        assert first_handle.stopped
        assert player.handles[-1] is not first_handle
    finally:
        renderer.shutdown()


def test_synth_renderer_notifies_render_listener() -> None:
    player = _DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        class _CaptureListener:
            def __init__(self) -> None:
                self.events: list[tuple[str, int, float | bool]] = []

            def render_started(self, generation: int) -> None:
                self.events.append(("started", generation, 0.0))

            def render_progress(self, generation: int, progress: float) -> None:
                self.events.append(("progress", generation, progress))

            def render_complete(self, generation: int, success: bool) -> None:
                self.events.append(("complete", generation, success))

        listener = _CaptureListener()
        renderer.set_render_listener(listener)
        events = [(0, 960, 60, 79)]
        renderer.prepare(events, 480)
        assert renderer._render_ready.wait(0.5)  # type: ignore[attr-defined]
        listener.events.clear()

        renderer.set_tempo(150.0)
        assert renderer._render_ready.wait(0.5)  # type: ignore[attr-defined]

        assert any(name == "started" for name, _, _ in listener.events)
        assert any(name == "progress" and progress >= 1.0 for name, _, progress in listener.events)
        assert any(name == "complete" and success for name, _, success in listener.events)
    finally:
        renderer.shutdown()


def test_synth_renderer_reports_intermediate_progress(monkeypatch) -> None:
    player = _DummyPlayer()
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


def test_failover_player_falls_back_when_first_player_fails() -> None:
    failing = _FailingPlayer()
    succeeding = _CountingPlayer()
    player = audio._FailoverPlayer([failing, succeeding])

    handle = player.play(b"pcm", 22050)

    assert handle is succeeding.handle
    assert failing.play_calls == 1
    assert succeeding.play_calls == 1
    assert failing.stop_all_calls >= 1

    # Second play should no longer call the failing backend once it has been dropped.
    player.play(b"pcm", 22050)

    assert failing.play_calls == 1
    assert succeeding.play_calls == 2


def test_synth_renderer_stop_invokes_player_stop_all() -> None:
    player = _DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        renderer.prepare([(0, 960, 60, 79)], 480)
        assert renderer.start(0, 120.0)
        _await_render(renderer)
        _wait_for_playback(player)
        renderer.stop()

        assert player.stop_all_calls >= 1
    finally:
        renderer.shutdown()


def test_failover_player_stop_all_cascades() -> None:
    first = _CountingPlayer()
    second = _CountingPlayer()
    player = audio._FailoverPlayer([first, second])

    player.stop_all()

    assert first.stop_all_calls == 1
    assert second.stop_all_calls == 1


class _FakeWinsound:
    SND_FILENAME = 0x00020000
    SND_ASYNC = 0x0001
    SND_PURGE = 0x0040

    def __init__(self) -> None:
        self.calls: list[tuple[str | None, int]] = []

    def PlaySound(self, sound: str | None, flags: int) -> None:  # pragma: no cover - exercised via tests
        self.calls.append((sound, flags))


def test_winsound_player_writes_wave_file_and_stops(monkeypatch) -> None:
    fake = _FakeWinsound()
    monkeypatch.setattr(audio, "winsound", fake)
    player = audio._WinsoundPlayer()

    pcm = (b"\x00\x01" * 2000)
    handle = player.play(pcm, 22050)

    assert handle is not None
    assert fake.calls, "winsound should be invoked"
    path_str, flags = fake.calls[0]
    assert path_str is not None
    wave_path = Path(path_str)
    assert wave_path.exists()
    assert flags & fake.SND_FILENAME

    handle.stop()

    assert fake.calls[-1] == (None, fake.SND_PURGE)
    assert not wave_path.exists()


def test_winsound_player_stop_all_silences_handles(monkeypatch) -> None:
    fake = _FakeWinsound()
    monkeypatch.setattr(audio, "winsound", fake)
    player = audio._WinsoundPlayer()

    pcm = (b"\x00\x01" * 500)
    handle = player.play(pcm, 22050)

    assert handle is not None
    player.stop_all()

    assert fake.calls[-1] == (None, fake.SND_PURGE)