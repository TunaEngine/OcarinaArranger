"""Background rendering coordinator for the preview synthesiser."""

from __future__ import annotations

import logging
import threading
from queue import Empty, SimpleQueue
from typing import Callable, Optional, Sequence

from viewmodels.preview_playback_viewmodel import AudioRenderListener

from .rendering import Event, MetronomeSettings


logger = logging.getLogger(__name__)


class _RenderWorker:
    """Manage background rendering of note events and notify listeners."""

    def __init__(
        self,
        *,
        render_factory: Callable[
            [],
            Callable[
                [
                    Sequence[Event],
                    float,
                    int,
                    MetronomeSettings,
                    Optional[Callable[[float], None]],
                ],
                tuple[bytes, float],
            ],
        ],
    ) -> None:
        self._render_factory = render_factory
        self._lock = threading.Lock()
        self._render_ready = threading.Event()
        self._render_ready.set()
        # Dedicated background thread consuming render tasks.  Using a
        # long-lived thread avoids Windows debug breakpoints that can be
        # triggered when spawning threads during interpreter finalisation
        # (observed under pytest).
        self._tasks: SimpleQueue[Callable[[], None] | None] = SimpleQueue()
        self._thread: Optional[threading.Thread] = threading.Thread(
            target=self._worker_loop,
            name="preview-render",
            daemon=True,
        )
        self._thread.start()
        self._shutdown = False

        # The following state variables are protected by self._lock
        self._events: tuple[Event, ...] = ()
        self._ppq: int = 480
        self._render_generation = 0
        self._buffer_generation = 0
        self._render_target_tempo = 120.0
        self._render_target_metronome: MetronomeSettings | None = None
        self._render_tempo: float | None = None
        self._render_metronome: MetronomeSettings | None = None
        self._buffer: bytes = b""
        self._ticks_per_second: float = 1.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def shutdown(self) -> None:
        """Signal stop and wait for any active render tasks to complete."""
        # Block new schedules first.
        with self._lock:
            self._shutdown = True

        # Let any in-flight worker hit its finally: and set the ready flag.
        self._render_ready.wait(timeout=3.0)

        # Drop any queued-but-not-yet processed tasks.  These would be stale
        # renders that we no longer care about during shutdown.
        drained_task = False
        while True:
            try:
                task = self._tasks.get_nowait()
            except Empty:
                break
            else:
                if task is None:
                    # Sentinel already queued; nothing else to do.
                    break
                drained_task = True

        if drained_task:
            # Anything that was waiting on the cancelled render needs to be
            # notified that no work will arrive.
            self._render_ready.set()

        thread: Optional[threading.Thread]
        with self._lock:
            thread = self._thread
            self._thread = None

        if thread is not None:
            # Signal the background loop to exit and wait for it to stop.
            self._tasks.put(None)
            try:
                thread.join(timeout=3.0)
            except Exception:  # pragma: no cover - defensive guard
                logger.warning("Render worker thread join failed", exc_info=True)

        # Fresh queue instance in case the worker is ever restarted for tests.
        self._tasks = SimpleQueue()

    def update_source(
        self, events: Sequence[Event], pulses_per_quarter: int, tempo: float
    ) -> None:
        with self._lock:
            self._events = tuple(events)
            self._ppq = max(1, int(pulses_per_quarter))
            self._buffer = b""
            self._render_tempo = None
            self._render_metronome = None
            self._ticks_per_second = (tempo / 60.0) * self._ppq

    def ensure_buffer(
        self,
        *,
        tempo: float,
        force: bool,
        wait: bool,
        listener: AudioRenderListener | None,
        metronome_settings: MetronomeSettings,
    ) -> None:
        # This initial check is safe to do without a lock.
        if not self._render_ready.is_set() and wait:
            self._render_ready.wait()

        with self._lock:
            if self._shutdown:
                return
            needs_render = self._is_render_needed(force, tempo, metronome_settings)
            if not needs_render:
                return

            self._schedule_render_locked(tempo, listener, metronome_settings)

        if wait:
            self._render_ready.wait()

    def _is_render_needed(
        self, force: bool, tempo: float, metronome: MetronomeSettings
    ) -> bool:
        # This helper must be called with the lock held.
        if force:
            return True

        # If a render is already in progress, check if it's for the same settings.
        # If so, a new render is not needed.
        if not self._render_ready.is_set():
            target_matches = (
                abs(self._render_target_tempo - tempo) < 1e-6
                and self._render_target_metronome == metronome
            )
            if target_matches:
                return False

        if not self._events:
            # If there's no buffer, we need to "render" the silence.
            return not self._buffer and self._render_tempo is None

        # Is the current buffer valid for these settings?
        buffer_is_valid = (
            self._buffer
            and self._buffer_generation == self._render_generation
            and abs((self._render_tempo or 0.0) - tempo) < 1e-6
            and self._render_metronome == metronome
        )
        return not buffer_is_valid

    @property
    def buffer(self) -> bytes:
        with self._lock:
            return self._buffer

    @property
    def ticks_per_second(self) -> float:
        with self._lock:
            return self._ticks_per_second

    @property
    def buffer_generation(self) -> int:
        with self._lock:
            return self._buffer_generation

    @property
    def render_generation(self) -> int:
        with self._lock:
            return self._render_generation

    @property
    def ready_event(self) -> threading.Event:
        return self._render_ready

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _schedule_render_locked(
        self, tempo: float, listener: AudioRenderListener | None, metronome: MetronomeSettings
    ) -> None:
        # This helper must be called with the lock held.
        self._render_generation += 1
        generation = self._render_generation
        self._render_target_tempo = tempo
        self._render_target_metronome = metronome
        self._render_ready.clear()

        # Make local copies of data needed by the worker thread.
        events = self._events
        ppq = self._ppq

        active_listener = listener
        if active_listener is not None:
            try:
                active_listener.render_started(generation)
            except Exception:  # pragma: no cover - defensive listener guard
                logger.warning("Render listener render_started failed", exc_info=True)
                active_listener = None

        def report_progress(value: float) -> None:
            self._notify_render_progress(active_listener, generation, value)

        def worker() -> None:
            try:
                render_fn = self._render_factory()
                buffer, ticks_per_second = render_fn(
                    events,
                    tempo,
                    ppq,
                    metronome,
                    report_progress if active_listener is not None else None,
                )
                success = True
            except Exception:  # pragma: no cover - defensive guard
                logger.exception("SynthRenderer render failed")
                buffer = b""
                ticks_per_second = max((tempo / 60.0) * ppq, 1e-3)
                self._notify_render_progress(active_listener, generation, 1.0)
                success = False

            with self._lock:
                # Check if this render is still the most current one before updating state.
                if generation == self._render_generation:
                    self._buffer = buffer
                    self._render_tempo = tempo
                    self._ticks_per_second = ticks_per_second
                    self._buffer_generation = generation
                    self._render_metronome = metronome

            # Notifications can happen outside the lock.
            try:
                if self.render_generation == generation:
                    logger.debug(
                        "SynthRenderer.render completed: events=%d tempo=%.3f buffer_bytes=%d",
                        len(events),
                        tempo,
                        len(buffer),
                    )
                self._notify_render_progress(active_listener, generation, 1.0)
                self._notify_render_complete(active_listener, generation, success)
            finally:
                self._render_ready.set()

        try:
            self._tasks.put_nowait(worker)
        except Exception:  # pragma: no cover - queue put should not fail
            logger.exception("SynthRenderer render task queue put failed")
            with self._lock:
                if generation == self._render_generation:
                    self._buffer = b""
                    self._render_tempo = tempo
                    self._ticks_per_second = max((tempo / 60.0) * ppq, 1e-3)
                    self._buffer_generation = generation
                    self._render_metronome = metronome
            self._render_ready.set()
            self._notify_render_progress(active_listener, generation, 1.0)
            self._notify_render_complete(active_listener, generation, False)

    def _worker_loop(self) -> None:
        """Consume queued render tasks until shutdown."""
        while True:
            task = self._tasks.get()
            if task is None:
                return
            try:
                task()
            except Exception:  # pragma: no cover - defensive guard
                logger.exception("Render task execution failed")

    @staticmethod
    def _notify_render_progress(
        listener: AudioRenderListener | None, generation: int, progress: float
    ) -> None:
        if listener is None:
            return
        try:
            listener.render_progress(generation, progress)
        except Exception:  # pragma: no cover - defensive listener guard
            logger.warning("Render listener render_progress failed", exc_info=True)

    @staticmethod
    def _notify_render_complete(
        listener: AudioRenderListener | None, generation: int, success: bool
    ) -> None:
        if listener is None:
            return
        try:
            listener.render_complete(generation, success)
        except Exception:  # pragma: no cover - defensive listener guard
            logger.warning("Render listener render_complete failed", exc_info=True)


__all__ = ["_RenderWorker"]
