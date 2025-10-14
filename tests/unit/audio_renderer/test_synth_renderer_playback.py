from __future__ import annotations

from ocarina_gui import audio

from .helpers import DummyPlayer, FailingPlayer, await_render, render_simple_events, wait_for_playback


def test_synth_renderer_reseeks_while_playing() -> None:
    player = DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        events = [(0, 960, 60, 79)]
        renderer.prepare(events, 480)
        assert renderer.start(0, 120.0)
        await_render(renderer)
        wait_for_playback(player)
        renderer.seek(240)

        wait_for_playback(player, min_calls=2)
        assert len(player.calls) >= 2
    finally:
        renderer.shutdown()


def test_synth_renderer_pause_stops_backend() -> None:
    player = DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        events = [(0, 960, 60, 79)]
        renderer.prepare(events, 480)
        assert renderer.start(0, 120.0)
        await_render(renderer)
        wait_for_playback(player)
        handle = player.handles[-1]
        renderer.pause()

        assert handle.stopped
        assert renderer._handle is None  # type: ignore[attr-defined]
        assert player.stop_all_calls >= 1
    finally:
        renderer.shutdown()


def test_synth_renderer_stop_halts_backend_even_without_playing_flag() -> None:
    player = DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        events = [(0, 960, 60, 79)]
        renderer.prepare(events, 480)
        assert renderer.start(0, 120.0)
        await_render(renderer)
        wait_for_playback(player)
        handle = player.handles[-1]
        renderer.stop()

        assert handle.stopped
        assert renderer._handle is None  # type: ignore[attr-defined]
        assert player.stop_all_calls >= 1
    finally:
        renderer.shutdown()


def test_synth_renderer_start_returns_false_when_player_fails() -> None:
    player = FailingPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        renderer.prepare([(0, 960, 60, 79)], 480)
        await_render(renderer)

        assert not renderer.start(0, 120.0)
        assert player.stop_all_calls >= 1
    finally:
        renderer.shutdown()


def test_synth_renderer_seek_restarts_backend_handle() -> None:
    player = DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        events = [(0, 960, 60, 79)]
        renderer.prepare(events, 480)
        assert renderer.start(0, 120.0)
        await_render(renderer)
        wait_for_playback(player)
        first_handle = player.handles[-1]

        renderer.seek(240)

        assert first_handle.stopped
        assert player.handles[-1] is not first_handle
    finally:
        renderer.shutdown()


def test_synth_renderer_notifies_render_listener() -> None:
    player = DummyPlayer()
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
        assert renderer._render_ready.wait(1.0)  # type: ignore[attr-defined]
        listener.events.clear()

        renderer.set_tempo(150.0)
        assert renderer._render_ready.wait(1.0)  # type: ignore[attr-defined]

        assert any(name == "started" for name, _, _ in listener.events)
        assert any(name == "progress" and progress >= 1.0 for name, _, progress in listener.events)
        assert any(name == "complete" and success for name, _, success in listener.events)
    finally:
        renderer.shutdown()


def test_synth_renderer_stop_invokes_player_stop_all() -> None:
    player = DummyPlayer()
    renderer = audio._SynthRenderer(player)
    try:
        render_simple_events(renderer)
        assert renderer.start(0, 120.0)
        await_render(renderer)
        wait_for_playback(player)
        renderer.stop()

        assert player.stop_all_calls >= 1
    finally:
        renderer.shutdown()
