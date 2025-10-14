from __future__ import annotations

import threading
import time
from typing import Iterable

from ocarina_gui import audio
from ocarina_gui.audio.synth import rendering
from shared.tempo import TempoChange


class DummyHandle(audio._PlaybackHandle):
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class DummyPlayer(audio._AudioPlayer):
    def __init__(self) -> None:
        self.calls: list[tuple[bytes, int]] = []
        self.handles: list[DummyHandle] = []
        self.stop_all_calls = 0

    def play(self, pcm: bytes, sample_rate: int) -> audio._PlaybackHandle:
        self.calls.append((pcm, sample_rate))
        handle = DummyHandle()
        self.handles.append(handle)
        return handle

    def stop_all(self) -> None:
        self.stop_all_calls += 1


class FailingPlayer(audio._AudioPlayer):
    def __init__(self) -> None:
        self.play_calls = 0
        self.stop_all_calls = 0

    def play(self, pcm: bytes, sample_rate: int) -> audio._PlaybackHandle | None:
        self.play_calls += 1
        return None

    def stop_all(self) -> None:
        self.stop_all_calls += 1


class CountingPlayer(audio._AudioPlayer):
    def __init__(self) -> None:
        self.play_calls = 0
        self.stop_all_calls = 0
        self.handle = DummyHandle()

    def play(self, pcm: bytes, sample_rate: int) -> audio._PlaybackHandle:
        self.play_calls += 1
        return self.handle

    def stop_all(self) -> None:
        self.stop_all_calls += 1


def await_render(renderer: audio._SynthRenderer, timeout: float = 3.0) -> None:
    """Wait for the background render to complete within the timeout."""

    if renderer._render_ready.wait(timeout):  # type: ignore[attr-defined]
        return
    raise AssertionError(f"expected render to complete within {timeout} seconds")


def wait_for_playback(
    player: DummyPlayer, *, min_calls: int = 1, timeout: float = 1.0
) -> None:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if len(player.calls) >= min_calls:
            return
        time.sleep(0.01)
    raise AssertionError("expected playback to start")


def render_simple_events(renderer: audio._SynthRenderer) -> None:
    events = [(0, 480, 69, 79), (480, 480, 71, 79)]
    renderer.prepare(events, 480)


class FakeWinsound:
    SND_FILENAME = 0x00020000
    SND_ASYNC = 0x0001
    SND_PURGE = 0x0040

    def __init__(self) -> None:
        self.calls: list[tuple[str | None, int]] = []

    def PlaySound(self, sound: str | None, flags: int) -> None:  # pragma: no cover - exercised via tests
        self.calls.append((sound, flags))


def tempo_config(tempo_bpm: float, tempo_changes: Iterable[TempoChange] | None = None) -> tuple[rendering.RenderConfig, list[TempoChange]]:
    config = rendering.RenderConfig(
        sample_rate=audio._SynthRenderer._SAMPLE_RATE,
        amplitude=0.3,
        chunk_size=1024,
        metronome=rendering.MetronomeSettings(enabled=False, beats_per_measure=4, beat_unit=4),
    )
    changes = list(tempo_changes or [TempoChange(tick=0, tempo_bpm=tempo_bpm)])
    return config, changes


__all__ = [
    "await_render",
    "CountingPlayer",
    "DummyHandle",
    "DummyPlayer",
    "FailingPlayer",
    "FakeWinsound",
    "render_simple_events",
    "tempo_config",
    "wait_for_playback",
]
