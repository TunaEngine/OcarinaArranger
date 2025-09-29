"""Threaded audio renderer that mixes note events into PCM audio."""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional, Sequence

from viewmodels.preview_playback_viewmodel import (
    AudioRenderListener,
    AudioRenderer,
    LoopRegion,
)

from ..players import _AudioPlayer, _PlaybackHandle
from .patches import _SynthPatch, _patch_for_program
from .rendering import (
    Event,
    MetronomeSettings,
    RenderConfig,
    note_segment,
    render_events,
    tempo_cache_key,
)
from .worker import _RenderWorker
from .tone import _midi_to_frequency  # noqa: F401 - re-exported for callers

logger = logging.getLogger(__name__)


class _SynthRenderer(AudioRenderer):
    """Very small synthesiser that renders note events to PCM audio."""

    _SAMPLE_RATE = 22050
    _AMPLITUDE = 0.45
    _PROGRESS_CHUNK_SIZE = 4096

    _note_segment = staticmethod(note_segment)
    _tempo_cache_key = staticmethod(tempo_cache_key)

    def __init__(self, player: _AudioPlayer) -> None:
        self._player = player
        self._events: tuple[Event, ...] = ()
        self._ppq: int = 480
        self._loop: LoopRegion = LoopRegion()
        self._tempo: float = 120.0
        self._handle: Optional[_PlaybackHandle] = None
        self._position_tick: int = 0
        self._is_playing = False
        self._worker = _RenderWorker(render_factory=lambda: self._render_events)
        self._render_ready = self._worker.ready_event
        self._metronome_enabled = False
        self._beats_per_measure = 4
        self._beat_unit = 4
        self._render_listener: AudioRenderListener | None = None
        self._config_lock = threading.Lock()
        self._playback_lock = threading.RLock()
        self._resume_threads: list[threading.Thread] = []

    # ------------------------------------------------------------------
    # AudioRenderer protocol implementation
    # ------------------------------------------------------------------
    def shutdown(self) -> None:
        """Cleanly stop playback and all background worker threads."""
        self._stop_playback()
        self._worker.shutdown()
        threads = list(self._resume_threads)
        for t in threads:
            t.join(timeout=1.0)
        self._resume_threads.clear()

    def prepare(self, events: Sequence[Event], pulses_per_quarter: int) -> None:
        self._stop_playback()
        self._events = tuple(events)
        self._ppq = max(1, pulses_per_quarter)
        self._worker.update_source(self._events, self._ppq, self._tempo)
        self._position_tick = 0
        self._ensure_buffer(force=True, wait=False)
        logger.debug(
            "SynthRenderer.prepare: events=%d ppq=%d buffer_bytes=%d (async)",
            len(self._events),
            self._ppq,
            len(self._worker.buffer),
        )

    def start(self, position_tick: int, tempo_bpm: float) -> bool:
        with self._playback_lock:
            logger.debug(
                "SynthRenderer.start requested at tick=%d tempo=%.3f",
                position_tick,
                tempo_bpm,
            )
            self._tempo = tempo_bpm
            self._position_tick = position_tick
            self._stop_playback()
            if not self._events:
                logger.debug("SynthRenderer.start aborted: no events available")
                return False
            self._ensure_buffer(wait=False)
            buffer_ready = bool(self._worker.buffer) and (
                self._worker.buffer_generation == self._worker.render_generation
            )
            if buffer_ready:
                started = self._play_from_tick(position_tick)
                logger.debug("SynthRenderer.start result=%s", started)
                return started
            generation = self._worker.render_generation
            self._restart_after_render(generation, position_tick)
            logger.debug(
                "SynthRenderer.start deferred until render generation %d", generation
            )
            return True

    def pause(self) -> None:
        logger.debug("SynthRenderer.pause invoked")
        self._stop_playback()

    def stop(self) -> None:
        logger.debug("SynthRenderer.stop invoked")
        self._stop_playback()

    def seek(self, tick: int) -> None:
        with self._playback_lock:
            self._position_tick = max(0, tick)
            if not self._is_playing:
                logger.debug(
                    "SynthRenderer.seek stored tick=%d (not playing)",
                    self._position_tick,
                )
                return
            logger.debug(
                "SynthRenderer.seek restarting playback from tick=%d",
                self._position_tick,
            )
            self._play_from_tick(self._position_tick)

    def set_tempo(self, tempo_bpm: float) -> None:
        with self._playback_lock:
            logger.debug("SynthRenderer.set_tempo: %.3f", tempo_bpm)
            self._tempo = tempo_bpm
            was_playing = self._is_playing
            position = self._position_tick
            self._stop_playback()
            self._ensure_buffer(force=True, wait=False)
            if not was_playing:
                return
            generation = self._worker.render_generation
            self._restart_after_render(generation, position)

    def set_loop(self, loop: LoopRegion) -> None:  # pragma: no cover - stored for future use
        self._loop = loop
        logger.debug(
            "SynthRenderer.set_loop: enabled=%s start=%d end=%d",
            loop.enabled,
            loop.start_tick,
            loop.end_tick,
        )

    def set_metronome(
        self, enabled: bool, beats_per_measure: int, beat_unit: int
    ) -> None:
        with self._config_lock:
            beats = max(1, beats_per_measure)
            unit = max(1, beat_unit)
            desired_enabled = bool(enabled)
            changed = (
                desired_enabled != self._metronome_enabled
                or beats != self._beats_per_measure
                or unit != self._beat_unit
            )
            if not changed:
                return

            self._metronome_enabled = desired_enabled
            self._beats_per_measure = beats
            self._beat_unit = unit
            logger.debug(
                "SynthRenderer.set_metronome: enabled=%s beats=%d unit=%d",
                self._metronome_enabled,
                self._beats_per_measure,
                self._beat_unit,
            )

        with self._playback_lock:
            was_playing = self._is_playing
            position = self._position_tick
            self._stop_playback()
            self._ensure_buffer(force=True, wait=False)
            if not was_playing:
                return
            generation = self._worker.render_generation
            self._restart_after_render(generation, position)

    def set_render_listener(self, listener: AudioRenderListener | None) -> None:
        self._render_listener = listener

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _stop_playback(self) -> None:
        with self._playback_lock:
            self._stop_handle_only()
            try:
                self._player.stop_all()
            except Exception:  # pragma: no cover - backend specific failures
                logger.warning("Audio player stop_all raised", exc_info=True)
            self._is_playing = False
            logger.debug("SynthRenderer: playback stopped")

    def _ensure_buffer(self, force: bool = False, wait: bool = True) -> None:
        with self._config_lock:
            metronome = MetronomeSettings(
                enabled=self._metronome_enabled,
                beats_per_measure=self._beats_per_measure,
                beat_unit=self._beat_unit,
            )
        self._worker.ensure_buffer(
            tempo=self._tempo,
            force=force,
            wait=wait,
            listener=self._render_listener,
            metronome_settings=metronome,
        )

    def _render_events(
        self,
        events: Sequence[Event],
        tempo: float,
        pulses_per_quarter: int,
        metronome: MetronomeSettings,
        progress_callback: Callable[[float], None] | None = None,
    ) -> tuple[bytes, float]:
        config = RenderConfig(
            sample_rate=self._SAMPLE_RATE,
            amplitude=self._AMPLITUDE,
            chunk_size=self._PROGRESS_CHUNK_SIZE,
            metronome=metronome,
        )
        return render_events(
            events, tempo, pulses_per_quarter, config, progress_callback
        )

    def _restart_after_render(self, generation: int, position: int) -> None:
        def resume() -> None:
            try:
                self._render_ready.wait()
                with self._playback_lock:
                    if self._worker.buffer_generation != generation:
                        return
                    try:
                        self._play_from_tick(position)
                    except Exception:  # pragma: no cover - defensive guard
                        logger.warning(
                            "SynthRenderer resume playback failed", exc_info=True
                        )
            except Exception:  # pragma: no cover - defensive guard
                logger.warning("SynthRenderer resume wait failed", exc_info=True)

        self._resume_threads = [t for t in self._resume_threads if t.is_alive()]
        thread = threading.Thread(
            target=resume,
            name=f"preview-resume-{generation}",
            daemon=False,
        )
        thread.start()
        self._resume_threads.append(thread)

    def _play_from_tick(self, tick: int) -> bool:
        with self._playback_lock:
            buffer = self._worker.buffer
            if not buffer:
                self._is_playing = False
                self._handle = None
                logger.debug("SynthRenderer._play_from_tick: no buffer to play")
                return False
            self._stop_handle_only()
            ticks_per_second = max(self._worker.ticks_per_second, 1e-3)
            start_sample = int(round(tick / ticks_per_second * self._SAMPLE_RATE))
            byte_offset = max(0, min(len(buffer), start_sample * 2))
            if byte_offset >= len(buffer):
                self._is_playing = False
                logger.debug(
                    "SynthRenderer._play_from_tick: byte_offset beyond buffer (tick=%d)",
                    tick,
                )
                return False
            slice_bytes = buffer[byte_offset:]
            handle = self._player.play(slice_bytes, self._SAMPLE_RATE)
            if handle is None:
                try:
                    self._player.stop_all()
                except Exception:  # pragma: no cover - backend specific failures
                    logger.warning("Audio player stop_all raised", exc_info=True)
                self._handle = None
                self._is_playing = False
                logger.debug(
                    "SynthRenderer._play_from_tick: backend returned no handle"
                )
                return False
            self._handle = handle
            self._is_playing = True
            logger.debug(
                "SynthRenderer._play_from_tick: started playback at tick=%d bytes=%d",
                tick,
                len(slice_bytes),
            )
            return True

    def _stop_handle_only(self) -> None:
        # Assumes playback lock is held.
        handle = self._handle
        if handle is None:
            return
        try:
            handle.stop()
        except Exception:  # pragma: no cover - backend specific failures
            logger.warning("Failed stopping playback", exc_info=True)
        self._handle = None
        logger.debug("SynthRenderer: handle cleared")


__all__ = [
    "Event",
    "_SynthPatch",
    "_SynthRenderer",
    "_patch_for_program",
    "_midi_to_frequency",
]