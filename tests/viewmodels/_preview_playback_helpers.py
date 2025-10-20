from __future__ import annotations

from viewmodels.preview_playback_viewmodel import (
    LoopRegion,
    PreviewPlaybackViewModel,
)


class StubAudioRenderer:
    def __init__(self) -> None:
        self.prepared: tuple[tuple[tuple[int, int, int, int], ...], int] | None = None
        self.started: list[tuple[int, float]] = []
        self.paused = 0
        self.stopped = 0
        self.sought: list[int] = []
        self.tempo_updates: list[float] = []
        self.loop_updates: list[LoopRegion] = []
        self.metronome_updates: list[tuple[bool, int, int]] = []
        self.volume_updates: list[float] = []
        self.start_should_fail = False
        self.render_listener = None
        self._generation = 0
        self.prepare_calls = 0
        self.auto_render = True
        self.volume_requires_render = False
        self.tempo_changes: tuple = ()

    def prepare(self, events, pulses_per_quarter: int, tempo_changes=None) -> None:  # type: ignore[override]
        self.prepare_calls += 1
        self.prepared = (tuple(events), pulses_per_quarter)
        self.tempo_changes = tuple(tempo_changes or ())
        self._notify_render()

    def start(self, position_tick: int, tempo_bpm: float) -> bool:
        if self.start_should_fail:
            return False
        self.started.append((position_tick, tempo_bpm))
        return True

    def pause(self) -> None:
        self.paused += 1

    def stop(self) -> None:
        self.stopped += 1

    def seek(self, tick: int) -> None:
        self.sought.append(tick)

    def set_tempo(self, tempo_bpm: float) -> None:
        self.tempo_updates.append(tempo_bpm)
        self._notify_render()

    def set_loop(self, loop: LoopRegion) -> None:
        self.loop_updates.append(loop)

    def set_metronome(self, enabled: bool, beats_per_measure: int, beat_unit: int) -> None:
        self.metronome_updates.append((enabled, beats_per_measure, beat_unit))
        self._notify_render()

    def set_render_listener(self, listener) -> None:  # type: ignore[override]
        self.render_listener = listener

    def set_volume(self, volume: float) -> bool:
        self.volume_updates.append(volume)
        if self.volume_requires_render:
            self._notify_render()
            return True
        return False

    def trigger_render(
        self, progress: tuple[float, ...] = (0.0, 1.0), success: bool = True
    ) -> None:
        if self.render_listener is None:
            return
        self._generation += 1
        self.render_listener.render_started(self._generation)
        for value in progress:
            self.render_listener.render_progress(self._generation, value)
        self.render_listener.render_complete(self._generation, success)

    def _notify_render(self) -> None:
        if self.render_listener is None or not self.auto_render:
            return
        self.trigger_render()


def _build_viewmodel() -> tuple[PreviewPlaybackViewModel, StubAudioRenderer]:
    renderer = StubAudioRenderer()
    viewmodel = PreviewPlaybackViewModel(audio_renderer=renderer)
    return viewmodel, renderer


def _make_events(*specs: tuple[int, ...]) -> list[tuple[int, int, int, int]]:
    events: list[tuple[int, int, int, int]] = []
    for spec in specs:
        if len(spec) == 4:
            onset, duration, midi, program = spec
        elif len(spec) == 3:
            onset, duration, midi = spec
            program = 79
        else:
            raise ValueError("Event specs must have 3 or 4 elements")
        events.append((int(onset), int(duration), int(midi), int(program)))
    return events
