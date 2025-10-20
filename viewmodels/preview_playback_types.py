"""Shared data structures and interfaces for preview playback view-models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence, Tuple

from shared.tempo import TempoChange


Event = Tuple[int, int, int, int]


@dataclass(slots=True)
class LoopRegion:
    """Represents a loop selection measured in ticks."""

    enabled: bool = False
    start_tick: int = 0
    end_tick: int = 0


@dataclass(slots=True)
class PreviewPlaybackState:
    """Mutable state exposed by the preview playback view-model."""

    is_loaded: bool = False
    is_playing: bool = False
    position_tick: int = 0
    duration_tick: int = 0
    track_end_tick: int = 0
    pulses_per_quarter: int = 480
    tempo_bpm: float = 120.0
    beats_per_measure: int = 4
    beat_unit: int = 4
    metronome_enabled: bool = False
    loop: LoopRegion = field(default_factory=LoopRegion)
    last_error: str | None = None
    is_rendering: bool = False
    render_progress: float = 1.0
    _render_generation: int = 0
    volume: float = 1.0


class AudioRenderer(Protocol):
    """Minimal protocol for coordinating an audio playback backend."""

    def prepare(
        self,
        events: Sequence[Event],
        pulses_per_quarter: int,
        tempo_changes: Sequence[TempoChange] | None = None,
    ) -> None:
        ...

    def start(self, position_tick: int, tempo_bpm: float) -> bool:
        ...

    def pause(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def seek(self, tick: int) -> None:
        ...

    def set_tempo(self, tempo_bpm: float) -> None:
        ...

    def set_loop(self, loop: LoopRegion) -> None:
        ...

    def set_metronome(
        self, enabled: bool, beats_per_measure: int, beat_unit: int
    ) -> None:
        ...

    def set_render_listener(self, listener: "AudioRenderListener | None") -> None:
        ...

    def set_volume(self, volume: float) -> bool:
        ...


class AudioRenderListener(Protocol):
    """Receive notifications about asynchronous audio render progress."""

    def render_started(self, generation: int) -> None:
        ...

    def render_progress(self, generation: int, progress: float) -> None:
        ...

    def render_complete(self, generation: int, success: bool) -> None:
        ...


class NullAudioRenderer:
    """Fallback renderer that performs no actual audio output."""

    def prepare(
        self,
        events: Sequence[Event],
        pulses_per_quarter: int,
        tempo_changes: Sequence[TempoChange] | None = None,
    ) -> None:  # noqa: D401 - protocol compliance
        return None

    def start(self, position_tick: int, tempo_bpm: float) -> bool:
        return True

    def pause(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def seek(self, tick: int) -> None:
        return None

    def set_tempo(self, tempo_bpm: float) -> None:
        return None

    def set_loop(self, loop: LoopRegion) -> None:
        return None

    def set_metronome(
        self, enabled: bool, beats_per_measure: int, beat_unit: int
    ) -> None:
        return None

    def set_render_listener(self, listener: AudioRenderListener | None) -> None:  # noqa: D401 - protocol compliance
        return None

    def set_volume(self, volume: float) -> bool:  # noqa: D401 - protocol compliance
        return False


__all__ = [
    "AudioRenderListener",
    "AudioRenderer",
    "Event",
    "LoopRegion",
    "NullAudioRenderer",
    "PreviewPlaybackState",
]

