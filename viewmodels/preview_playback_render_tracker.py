"""Track asynchronous render activity for preview playback."""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from .preview_playback_types import PreviewPlaybackState


logger = logging.getLogger(__name__)


class PreviewRenderTracker:
    """Maintain render progress data shared with the UI."""

    def __init__(self, state: PreviewPlaybackState, state_lock: threading.Lock) -> None:
        self._state = state
        self._state_lock = state_lock
        self._render_generation = 0
        self._pending_render_request_time: float | None = None
        self._pending_render_event_count: int | None = None
        self._render_start_times: dict[int, float] = {}
        self._render_request_latencies: dict[int, float] = {}
        self._render_last_progress: dict[int, float] = {}
        self._render_event_counts: dict[int, int] = {}

    # ------------------------------------------------------------------
    # Public API used by the view-model
    # ------------------------------------------------------------------
    def mark_pending(self, event_count: int) -> bool:
        """Record that a render has been requested."""

        with self._state_lock:
            if not self._state.is_loaded:
                return False
            self._state.is_rendering = True
            self._state.render_progress = 0.0
            self._pending_render_request_time = time.perf_counter()
            self._pending_render_event_count = event_count
            generation = self._render_generation

        logger.debug(
            "PreviewPlaybackViewModel: render pending for %d events (current_generation=%d)",
            event_count,
            generation,
        )
        return True

    def mark_idle(self, progress: float = 1.0) -> None:
        """Return the tracker to an idle, non-rendering state."""

        with self._state_lock:
            self._state.is_rendering = False
            self._state.render_progress = progress
            self._pending_render_request_time = None
            self._pending_render_event_count = None

    def on_render_started(self, generation: int, fallback_event_count: int) -> bool:
        """Record that the backend acknowledged a render request."""

        with self._state_lock:
            if generation < self._render_generation:
                return False
            now = time.perf_counter()
            request_time = self._pending_render_request_time
            events = self._pending_render_event_count or fallback_event_count
            self._pending_render_request_time = None
            self._pending_render_event_count = None
            self._render_generation = generation
            self._state._render_generation = generation
            self._state.is_rendering = True
            self._state.render_progress = 0.0
            self._render_start_times[generation] = now
            self._render_event_counts[generation] = events
            if request_time is not None:
                latency = max(0.0, now - request_time)
                self._render_request_latencies[generation] = latency
            else:
                self._render_request_latencies.pop(generation, None)
                latency = None
            self._render_last_progress[generation] = 0.0

        latency_msg = "" if latency is None else f" after {latency:.3f}s wait"
        logger.debug(
            "PreviewPlaybackViewModel: render generation %d started%s (events=%d)",
            generation,
            latency_msg,
            events,
        )
        return True

    def on_render_progress(self, generation: int, progress: float) -> bool:
        """Update tracked progress and optionally emit a log entry."""

        should_log = False
        with self._state_lock:
            if generation != self._render_generation:
                return False
            clamped = max(0.0, min(1.0, progress))
            previous = self._render_last_progress.get(generation, 0.0)
            if clamped >= 1.0 or clamped - previous >= 0.1:
                should_log = True
                self._render_last_progress[generation] = clamped
            self._state.render_progress = clamped
            start_time = self._render_start_times.get(generation)

        if should_log:
            elapsed_msg = ""
            if start_time is not None:
                elapsed = max(0.0, time.perf_counter() - start_time)
                elapsed_msg = f" elapsed={elapsed:.3f}s"
            logger.debug(
                "PreviewPlaybackViewModel: render generation %d progress=%.0f%%%s",
                generation,
                self._state.render_progress * 100.0,
                elapsed_msg,
            )
        return True

    def on_render_complete(
        self, generation: int, success: bool, fallback_event_count: int
    ) -> bool:
        """Handle completion of an asynchronous render."""

        with self._state_lock:
            if generation < self._render_generation:
                return False
            now = time.perf_counter()
            start_time = self._render_start_times.pop(generation, None)
            request_latency = self._render_request_latencies.pop(generation, None)
            events = self._render_event_counts.pop(generation, fallback_event_count)
            self._render_last_progress.pop(generation, None)
            elapsed: Optional[float]
            if start_time is None:
                elapsed = None
            else:
                elapsed = max(0.0, now - start_time)
            self._render_generation = generation
            self._state._render_generation = generation
            self._state.render_progress = 1.0 if success else 0.0
            self._state.is_rendering = False

        latency_part = "" if request_latency is None else f", wait={request_latency:.3f}s"
        duration_part = "" if elapsed is None else f", render={elapsed:.3f}s"
        logger.debug(
            "PreviewPlaybackViewModel: render generation %d complete (success=%s, events=%d%s%s)",
            generation,
            success,
            events,
            latency_part,
            duration_part,
        )
        return True


__all__ = ["PreviewRenderTracker"]

