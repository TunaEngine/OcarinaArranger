from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import PlaybackTiming
from ui.main_window.preview import playback as playback_module


class FakeClock:
    def __init__(self, values: list[float]):
        if not values:
            raise ValueError("FakeClock requires at least one timestamp")
        self._values = iter(values)
        self._last = values[-1]

    def perf_counter(self) -> float:
        try:
            self._last = next(self._values)
        except StopIteration:
            pass
        return self._last


class DummyPlayback:
    def __init__(self, playing: bool) -> None:
        self.state = SimpleNamespace(
            is_loaded=True,
            is_playing=playing,
            is_rendering=False,
            position_tick=0,
        )
        self.advance_calls: list[float] = []

    def advance(self, elapsed: float) -> None:
        self.advance_calls.append(elapsed)


class DummyController(playback_module.PreviewPlaybackControlMixin):
    def __init__(self) -> None:
        self._headless = False
        self._preview_playback: dict[str, DummyPlayback] = {}
        self._preview_play_vars: dict[str, object] = {}
        self._preview_tempo_vars: dict[str, object] = {}
        self._preview_metronome_vars: dict[str, object] = {}
        self._preview_loop_enabled_vars: dict[str, object] = {}
        self._preview_loop_start_vars: dict[str, object] = {}
        self._preview_loop_end_vars: dict[str, object] = {}
        self._preview_applied_settings: dict[str, dict[str, object]] = {}
        self._suspend_tempo_update: set[str] = set()
        self._suspend_metronome_update: set[str] = set()
        self._suspend_loop_update: set[str] = set()
        self._playback_job = None
        self._playback_last_ts = None
        self.after_calls: list[int] = []
        self._scheduled_callback = None

    def after(self, delay: int, callback):
        self.after_calls.append(delay)
        self._scheduled_callback = callback
        return f"job-{len(self.after_calls)}"

    def after_cancel(self, job):
        pass

    def _roll_for_side(self, side: str):  # pragma: no cover - stub
        return None

    def _staff_for_side(self, side: str):  # pragma: no cover - stub
        return None

    def _update_preview_render_progress(self, side: str) -> None:  # pragma: no cover - stub
        pass

    def _set_preview_controls_enabled(self, side: str, enabled: bool) -> None:  # pragma: no cover - stub
        pass

    def _update_preview_fingering(self, side: str) -> None:  # pragma: no cover - stub
        pass

    def _update_loop_marker_visuals(self, side: str) -> None:  # pragma: no cover - stub
        pass


@pytest.mark.parametrize("playing", [False, True])
def test_playback_loop_interval(monkeypatch, playing: bool) -> None:
    timing = PlaybackTiming(idle_fps=24, active_fps=72)
    monkeypatch.setattr(playback_module.PreviewPlaybackControlMixin, "_PLAYBACK_TIMING", timing)
    controller = DummyController()
    playback = DummyPlayback(playing)
    controller._preview_playback["arranged"] = playback
    clock = FakeClock([0.0, 0.02, 0.04])
    monkeypatch.setattr(playback_module.time, "perf_counter", clock.perf_counter)

    controller._schedule_playback_loop()
    expected_interval = (
        timing.active_interval_ms if playing else timing.idle_interval_ms
    )
    assert controller.after_calls[-1] == expected_interval

    callback = controller._scheduled_callback
    assert callback is not None
    callback()

    assert controller.after_calls[-1] == expected_interval
    assert playback.advance_calls
