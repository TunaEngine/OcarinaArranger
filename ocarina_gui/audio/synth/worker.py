"""Background rendering coordinator for the preview synthesiser."""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional, Sequence
from concurrent.futures import ThreadPoolExecutor, Future

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
        # Single-thread pool to avoid per-render thread creation races (Windows GC/pytest).
        self._executor: Optional[ThreadPoolExecutor] = None
        self._futures: list[Future] = []
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

        # Tear down the single worker thread deterministically.
        exec_ref = None
        with self._lock:
            exec_ref = self._executor
            self._executor = None
        if exec_ref is not None:
            # Cancel queued tasks (if any) and wait for the worker to exit.
            try:
                exec_ref.shutdown(wait=True, cancel_futures=True)
            except Exception:
                logger.warning("Executor shutdown raised", exc_info=True)

        # Clear completed futures list.
        with self._lock:
            self._futures = [f for f in self._futures if not f.done()]

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

        # Lazily create the single worker the first time.
        if self._executor is None:
            # One reusable OS thread for all preview renders.
            executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="preview-render"
            )

            # Mark preview render threads as daemonic so test processes exit cleanly
            # even if a renderer escapes shutdown (e.g. due to a failing test).
            try:
                thread_factory = executor._thread_factory  # type: ignore[attr-defined]

                def _daemon_thread_factory(*args, **kwargs):
                    thread = thread_factory(*args, **kwargs)
                    thread.daemon = True
                    return thread

                executor._thread_factory = _daemon_thread_factory  # type: ignore[attr-defined]
            except AttributeError:
                logger.debug("ThreadPoolExecutor missing _thread_factory; using defaults")

            self._executor = executor
        try:
            fut = self._executor.submit(worker)
            self._futures.append(fut)
        except RuntimeError:
            # Happens if executor is shutting down; ignore new work.
            logger.exception("Failed to submit render task")
            return
        except Exception:  # pragma: no cover - thread launch failure
            logger.exception("SynthRenderer render thread failed to start")
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