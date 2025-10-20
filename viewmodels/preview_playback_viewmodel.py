from __future__ import annotations

"""View-model describing playback state for preview panes."""

import hashlib
import logging
import threading
from typing import Callable, Sequence

from .preview_playback_render_tracker import PreviewRenderTracker
from .preview_playback_types import (
    AudioRenderListener,
    AudioRenderer,
    Event,
    LoopRegion,
    NullAudioRenderer,
    PreviewPlaybackState,
)
from shared.tempo import (
    TempoChange,
    TempoMap,
    align_duration_to_measure,
    first_tempo,
    normalized_tempo_changes,
)


logger = logging.getLogger(__name__)

class PreviewPlaybackViewModel:
    """Track playback timing for a single preview pane."""

    def __init__(self, audio_renderer: AudioRenderer | None = None) -> None:
        self._audio = audio_renderer or NullAudioRenderer()
        self._supports_audio = not isinstance(self._audio, NullAudioRenderer)
        self.state = PreviewPlaybackState()
        self._events: tuple[Event, ...] = ()
        self._tempo_changes: tuple[TempoChange, ...] = ()
        self._tempo_map: TempoMap | None = None
        self._fractional_ticks = 0.0
        self._state_lock = threading.Lock()
        self._prepared_signature: bytes | None = None
        self._render_observer: Callable[[], None] | None = None
        self._pending_playback_resume = False
        self._render_tracker = PreviewRenderTracker(self.state, self._state_lock)
        self._audio.set_render_listener(self._RenderListener(self))
        self._audio.set_volume(self.state.volume)

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------
    def set_render_observer(self, observer: Callable[[], None] | None) -> None:
        with self._state_lock:
            self._render_observer = observer

    def load(
        self,
        events: Sequence[Event],
        pulses_per_quarter: int,
        *,
        tempo_bpm: float | None = None,
        tempo_changes: Sequence[TempoChange] | None = None,
        beats_per_measure: int = 4,
        beat_unit: int = 4,
    ) -> None:
        normalized_events = tuple(events)
        normalized_tempi = tuple(tempo_changes or ())
        default_tempo = first_tempo(normalized_tempi, default=self.state.tempo_bpm)
        signature = self._compute_events_signature(
            normalized_events, pulses_per_quarter, normalized_tempi
        )

        was_loaded = self.state.is_loaded
        was_playing = self.state.is_playing
        events_changed = signature != self._prepared_signature

        logger.debug(
            "PreviewPlaybackViewModel.load requested: events=%d ppq=%d was_loaded=%s was_playing=%s events_changed=%s",
            len(normalized_events),
            pulses_per_quarter,
            was_loaded,
            was_playing,
            events_changed,
        )

        if was_playing:
            self.stop()
        elif was_loaded:
            if events_changed:
                self._audio.stop()
            else:
                self._audio.seek(0)
            self._fractional_ticks = 0.0
            self.state.last_error = None

        self._events = normalized_events
        self._tempo_changes = normalized_tempi
        duration = (
            max((onset + duration) for onset, duration, _midi, _program in self._events)
            if self._events
            else 0
        )
        pulses = max(1, int(pulses_per_quarter))
        beats = max(1, int(beats_per_measure))
        unit = max(1, int(beat_unit))
        track_end = align_duration_to_measure(duration, pulses, beats, unit)

        self.state.is_loaded = True
        self.state.is_playing = False
        self.state.position_tick = 0
        self.state.duration_tick = duration
        self.state.track_end_tick = track_end
        self.state.pulses_per_quarter = pulses_per_quarter
        self.state.beats_per_measure = max(1, beats_per_measure)
        self.state.beat_unit = max(1, beat_unit)
        self.state.loop = LoopRegion(enabled=False, start_tick=0, end_tick=track_end)
        self.state.last_error = None
        self.state.metronome_enabled = False
        self._fractional_ticks = 0.0

        desired_tempo = default_tempo
        if tempo_bpm is not None:
            try:
                desired_tempo = float(tempo_bpm)
            except (TypeError, ValueError):
                desired_tempo = default_tempo
        self.state.tempo_bpm = self._normalize_tempo(desired_tempo)

        # Ensure the audio renderer discards any previously configured loop.
        self._audio.set_loop(
            LoopRegion(
                enabled=False,
                start_tick=0,
                end_tick=self.state.track_end_tick,
            )
        )

        if events_changed:
            if self._render_tracker.mark_pending(len(self._events)):
                self._notify_render_observer()
            self._audio.prepare(
                self._events, pulses_per_quarter, tempo_changes=self._tempo_changes
            )
            self._prepared_signature = signature
            logger.debug(
                "PreviewPlaybackViewModel.load: scheduled async render for %d events (ppq=%d)",
                len(self._events),
                pulses_per_quarter,
            )
        else:
            self._render_tracker.mark_idle()
            self._prepared_signature = signature
            logger.debug(
                "PreviewPlaybackViewModel.load: reused existing render for %d events (ppq=%d)",
                len(self._events),
                pulses_per_quarter,
            )

        self._rebuild_tempo_map(self.state.tempo_bpm)
        self._audio.set_tempo(self.state.tempo_bpm)
        self._notify_render_observer()

        self._audio.set_metronome(
            self.state.metronome_enabled,
            self.state.beats_per_measure,
            self.state.beat_unit,
        )
        self._audio.set_volume(self.state.volume)
        if not self._events:
            self._render_tracker.mark_idle()
            self._notify_render_observer()
        logger.debug(
            "PreviewPlaybackViewModel.load: events=%d duration=%d pulses_per_quarter=%d",
            len(self._events),
            duration,
            pulses_per_quarter,
        )

    # ------------------------------------------------------------------
    # Commands issued by the UI
    # ------------------------------------------------------------------
    def toggle_playback(self) -> bool:
        if not self.state.is_loaded:
            logger.debug("toggle_playback ignored: nothing loaded")
            return False
        if self.state.is_playing:
            logger.debug(
                "toggle_playback: pausing at tick=%d", self.state.position_tick
            )
            self.state.is_playing = False
            self._audio.pause()
            self._pending_playback_resume = False
            return False

        if not self._supports_audio:
            self.state.last_error = "Audio playback is not available on this system."
            logger.debug("toggle_playback failed: no audio backend available")
            return False
        if self.state.position_tick >= self._active_loop_end():
            restart_tick = self.state.loop.start_tick if self.state.loop.enabled else 0
            logger.debug(
                "toggle_playback restarting at tick=%d due to loop end",
                restart_tick,
            )
            self.seek_to(restart_tick)

        started = self._audio.start(self.state.position_tick, self.state.tempo_bpm)
        self.state.is_playing = started
        if started:
            self.state.last_error = None
            if self.state.is_rendering:
                self._pending_playback_resume = True
            logger.debug(
                "toggle_playback: started at tick=%d tempo=%.3f",
                self.state.position_tick,
                self.state.tempo_bpm,
            )
        else:
            self.state.last_error = "Unable to start audio playback."
            self._pending_playback_resume = False
            logger.debug(
                "toggle_playback: audio backend refused to start at tick=%d",
                self.state.position_tick,
            )

        return started

    def advance(self, elapsed_seconds: float) -> None:
        if not self.state.is_loaded or not self.state.is_playing:
            return
        if elapsed_seconds <= 0:
            return
        if self._pending_playback_resume:
            return

        tempo_map = self._tempo_map
        if tempo_map is not None:
            start_tick = self.state.position_tick
            start_seconds = tempo_map.seconds_at(start_tick)
            target_seconds = start_seconds + elapsed_seconds
            target_tick = tempo_map.seconds_to_tick(target_seconds)
            whole_ticks = max(0, int(target_tick - start_tick))
            if whole_ticks <= 0:
                return
            self._fractional_ticks = 0.0
            self._move_forward(whole_ticks)
            return

        ticks_per_second = (self.state.tempo_bpm / 60.0) * self.state.pulses_per_quarter
        self._fractional_ticks += elapsed_seconds * ticks_per_second
        whole_ticks = int(self._fractional_ticks)
        if whole_ticks == 0:
            return

        self._fractional_ticks -= whole_ticks
        self._move_forward(whole_ticks)

    def seek_to(self, tick: int) -> None:
        if not self.state.is_loaded:
            logger.debug("seek_to ignored: nothing loaded")
            return

        target = self._clamp_tick(tick)
        if self.state.loop.enabled:
            loop_start, loop_end = self._normalized_loop()
            if loop_end > loop_start:
                if target < loop_start:
                    target = loop_start
                elif target > loop_end:
                    target = loop_end

        self.state.position_tick = target
        self._fractional_ticks = 0.0
        self._audio.seek(target)
        logger.debug("seek_to: moved cursor to tick=%d", target)

    def set_tempo(self, tempo_bpm: float) -> None:
        tempo_bpm = self._normalize_tempo(tempo_bpm)
        if abs(tempo_bpm - self.state.tempo_bpm) <= 1e-6:
            return

        self.state.tempo_bpm = tempo_bpm
        self._rebuild_tempo_map(tempo_bpm)
        self._audio.set_tempo(tempo_bpm)
        if self._render_tracker.mark_pending(len(self._events)):
            self._notify_render_observer()
        if self.state.is_playing:
            self._pending_playback_resume = True

    @staticmethod
    def _normalize_tempo(tempo_bpm: float) -> float:
        if tempo_bpm <= 0:
            return 30.0
        return max(30.0, min(400.0, tempo_bpm))

    def _rebuild_tempo_map(self, target_first: float) -> None:
        try:
            pulses = max(1, int(self.state.pulses_per_quarter))
        except Exception:
            pulses = 1
        try:
            normalized = normalized_tempo_changes(float(target_first), self._tempo_changes)
            self._tempo_map = TempoMap(pulses, normalized)
        except Exception:
            self._tempo_map = None

    def seconds_at_tick(self, tick: int) -> float:
        tempo_map = self._tempo_map
        if tempo_map is not None:
            return tempo_map.seconds_at(max(0, int(tick)))
        pulses = max(1, self.state.pulses_per_quarter)
        tempo = max(self.state.tempo_bpm, 1e-6)
        return max(0, int(tick)) / pulses * 60.0 / tempo

    def set_metronome(self, enabled: bool) -> None:
        if not self.state.is_loaded:
            self.state.metronome_enabled = bool(enabled)
            return

        desired = bool(enabled)
        if desired == self.state.metronome_enabled:
            return

        self.state.metronome_enabled = desired
        self._audio.set_metronome(
            self.state.metronome_enabled,
            self.state.beats_per_measure,
            self.state.beat_unit,
        )
        # ensure applied state reflects actual renderer configuration
        if self._render_tracker.mark_pending(len(self._events)):
            self._notify_render_observer()
        if self.state.is_playing:
            self._pending_playback_resume = True

    def set_loop(self, loop: LoopRegion) -> None:
        if not self.state.is_loaded:
            return

        requested_start = max(0, int(loop.start_tick))
        requested_end = max(requested_start, int(loop.end_tick))
        requested_loop = LoopRegion(
            enabled=bool(loop.enabled and requested_end > requested_start),
            start_tick=requested_start,
            end_tick=requested_end,
        )

        clamped_start = self._clamp_tick(requested_start)
        clamped_end = self._clamp_tick(requested_end)
        track_end = self.state.track_end_tick or self.state.duration_tick
        if clamped_end <= clamped_start:
            playback_loop = LoopRegion(
                enabled=False,
                start_tick=0,
                end_tick=track_end,
            )
        else:
            playback_loop = LoopRegion(
                enabled=requested_loop.enabled,
                start_tick=clamped_start,
                end_tick=clamped_end,
            )

        if not playback_loop.enabled:
            playback_loop = LoopRegion(
                enabled=False,
                start_tick=0,
                end_tick=track_end,
            )

        self.state.loop = requested_loop
        self._audio.set_loop(playback_loop)
        self.seek_to(self.state.position_tick)
        logger.debug(
            "set_loop: enabled=%s start=%d end=%d",
            loop.enabled,
            loop.start_tick,
            loop.end_tick,
        )

    def set_volume(self, volume: float) -> None:
        normalized = max(0.0, min(1.0, float(volume)))
        if abs(normalized - self.state.volume) <= 1e-6:
            logger.debug(
                "set_volume noop: requested=%.4f current=%.4f",  # pragma: no cover - debug aid
                normalized,
                self.state.volume,
            )
            return

        previous = self.state.volume
        self.state.volume = normalized
        needs_render = self._audio.set_volume(normalized)
        logger.debug(
            "set_volume applied: previous=%.4f new=%.4f needs_render=%s is_playing=%s events=%d",  # pragma: no cover - debug aid
            previous,
            normalized,
            needs_render,
            self.state.is_playing,
            len(self._events),
        )
        if needs_render and self._render_tracker.mark_pending(len(self._events)):
            self._notify_render_observer()
        if needs_render and self.state.is_playing:
            self._pending_playback_resume = True

    def reset_adjustments(self) -> None:
        """Restore cursor position and playback options to their defaults."""

        self.stop()
        self.state.position_tick = 0
        self._fractional_ticks = 0.0
        self.state.tempo_bpm = 120.0
        self.state.metronome_enabled = False
        loop = LoopRegion(enabled=False, start_tick=0, end_tick=self.state.duration_tick)
        self.state.loop = loop
        self.state.volume = 1.0
        self._audio.set_tempo(self.state.tempo_bpm)
        self._audio.set_metronome(
            self.state.metronome_enabled,
            self.state.beats_per_measure,
            self.state.beat_unit,
        )
        self._audio.set_loop(loop)
        self._audio.set_volume(self.state.volume)

    def stop(self) -> None:
        if self.state.is_loaded and self.state.is_playing:
            logger.debug(
                "stop: halting playback at tick=%d", self.state.position_tick
            )
            self.state.is_playing = False
        if self.state.is_loaded:
            self._fractional_ticks = 0.0
            self.state.last_error = None
        self._audio.stop()
        self._pending_playback_resume = False
        if self.state.is_loaded:
            logger.debug("stop: playback stopped")

    # ------------------------------------------------------------------
    # Render listener integration
    # ------------------------------------------------------------------
    class _RenderListener(AudioRenderListener):
        def __init__(self, owner: "PreviewPlaybackViewModel") -> None:
            self._owner = owner

        def render_started(self, generation: int) -> None:
            self._owner._on_render_started(generation)

        def render_progress(self, generation: int, progress: float) -> None:
            self._owner._on_render_progress(generation, progress)

        def render_complete(self, generation: int, success: bool) -> None:
            self._owner._on_render_complete(generation, success)

    def _notify_render_observer(self) -> None:
        observer = self._render_observer
        if observer is None:
            return
        try:
            observer()
        except Exception:
            logger.exception("PreviewPlaybackViewModel render observer failed")

    def _on_render_started(self, generation: int) -> None:
        if self._render_tracker.on_render_started(generation, len(self._events)):
            self._notify_render_observer()

    def _on_render_progress(self, generation: int, progress: float) -> None:
        if self._render_tracker.on_render_progress(generation, progress):
            self._notify_render_observer()

    def _on_render_complete(self, generation: int, success: bool) -> None:
        handled = self._render_tracker.on_render_complete(
            generation, success, len(self._events)
        )
        if not handled:
            return
        if self._pending_playback_resume and self.state.is_playing:
            self._pending_playback_resume = False
        self._notify_render_observer()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _move_forward(self, ticks: int) -> None:
        start = self.state.position_tick
        target = start + ticks
        loop_start, loop_end = self._normalized_loop()

        if self.state.loop.enabled and loop_end > loop_start:
            wrapped = False
            while target >= loop_end:
                overflow = target - loop_end
                target = loop_start + overflow
                wrapped = True
            target = min(target, loop_end)
            self.state.position_tick = target
            if wrapped or target < start:
                self._audio.seek(target)
            return

        if target >= self.state.duration_tick:
            self.state.position_tick = self.state.duration_tick
            self.state.is_playing = False
            self._audio.stop()
            return

        self.state.position_tick = target

    def _clamp_tick(self, tick: int) -> int:
        if tick <= 0:
            return 0
        if tick >= self.state.track_end_tick:
            return self.state.track_end_tick
        return tick

    def _normalized_loop(self) -> tuple[int, int]:
        if not self.state.loop.enabled:
            return 0, self.state.track_end_tick
        start = max(0, min(self.state.loop.start_tick, self.state.track_end_tick))
        end = max(start, min(self.state.loop.end_tick, self.state.track_end_tick))
        return start, end

    def _active_loop_end(self) -> int:
        if self.state.loop.enabled:
            _, end = self._normalized_loop()
            return end
        return self.state.track_end_tick

    def _compute_events_signature(
        self,
        events: Sequence[Event],
        pulses_per_quarter: int,
        tempo_changes: Sequence[TempoChange],
    ) -> bytes:
        hasher = hashlib.blake2b(digest_size=24)
        hasher.update(int(max(0, pulses_per_quarter)).to_bytes(4, "little", signed=False))
        hasher.update(len(events).to_bytes(4, "little", signed=False))
        for onset, duration, midi, program in events:
            hasher.update(int(max(0, onset)).to_bytes(8, "little", signed=False))
            hasher.update(int(max(0, duration)).to_bytes(8, "little", signed=False))
            hasher.update(int(max(0, midi)).to_bytes(2, "little", signed=False))
            hasher.update(int(max(0, program)).to_bytes(2, "little", signed=False))
        hasher.update(len(tempo_changes).to_bytes(4, "little", signed=False))
        for change in tempo_changes:
            hasher.update(int(max(0, change.tick)).to_bytes(8, "little", signed=False))
            tempo_scaled = int(round(max(1.0, change.tempo_bpm * 1000.0)))
            hasher.update(tempo_scaled.to_bytes(8, "little", signed=False))
        return hasher.digest()


__all__ = [
    "AudioRenderer",
    "LoopRegion",
    "NullAudioRenderer",
    "PreviewPlaybackState",
    "PreviewPlaybackViewModel",
]
