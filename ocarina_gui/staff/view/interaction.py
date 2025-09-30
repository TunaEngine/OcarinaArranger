"""User interaction helpers for :class:`StaffView`."""

from __future__ import annotations

import logging
import tkinter as tk
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing helpers
    from ..cursor import CursorController

__all__ = ["StaffViewInteractionMixin"]

logger = logging.getLogger(__name__)


class StaffViewInteractionMixin:
    """Mixin encapsulating cursor event handling for the staff view."""

    canvas: tk.Canvas
    LEFT_PAD: int
    px_per_tick: float
    _cursor_tick: int
    _total_ticks: int
    _layout_mode: str
    _cursor_controller: "CursorController"
    _cursor_cb: Optional[Callable[[int], None]]
    _last_press_serial: Optional[int]

    def _on_cursor_event(self, event: tk.Event) -> str:
        tick = self._tick_from_event(event)
        if tick is None:
            tick = self._cursor_tick
        event_type = getattr(event, "type", None)
        type_name = str(event_type)
        release_markers = {
            str(getattr(getattr(tk, "EventType", object), "ButtonRelease", None)),
            "EventType.ButtonRelease",
            "ButtonRelease",
            "5",
        }
        if type_name in release_markers:
            callback = getattr(self, "_cursor_drag_state_cb", None)
            if callback:
                try:
                    callback(False)
                except Exception:
                    logger.exception(
                        "StaffView cursor drag release callback failed",
                        extra={"widget": repr(self)},
                    )
            self._last_press_serial = None
            logger.debug(
                "StaffView ignoring release event serial=%s",
                getattr(event, "serial", None),
                extra={"widget": repr(self)},
            )
            return "break"
        press_markers = {
            str(getattr(getattr(tk, "EventType", object), "ButtonPress", None)),
            "EventType.ButtonPress",
            "ButtonPress",
            "4",
        }
        if type_name in press_markers:
            serial = getattr(event, "serial", None)
            if serial is not None and serial == self._last_press_serial:
                logger.debug(
                    "StaffView ignoring duplicate press serial=%s",
                    serial,
                    extra={"widget": repr(self)},
                )
                return "break"
            self._last_press_serial = serial
            callback = getattr(self, "_cursor_drag_state_cb", None)
            if callback:
                try:
                    callback(True)
                except Exception:
                    logger.exception(
                        "StaffView cursor drag press callback failed",
                        extra={"widget": repr(self)},
                    )
        logger.debug(
            "StaffView cursor event layout=%s x=%s y=%s tick=%s type=%s",
            self._layout_mode,
            getattr(event, "x", None),
            getattr(event, "y", None),
            tick,
            type_name,
            extra={"widget": repr(self)},
        )
        self.set_cursor(tick, allow_autoscroll=False)
        if self._cursor_cb:
            try:
                self._cursor_cb(self._cursor_tick)
            except Exception:
                logger.exception("StaffView cursor callback failed", extra={"widget": repr(self)})
        return "break"

    def _tick_from_event(self, event: tk.Event) -> Optional[int]:
        widget = getattr(event, "widget", None)
        try:
            canvas = widget if isinstance(widget, tk.Canvas) else self.canvas
            x = int(canvas.canvasx(event.x))
        except Exception:
            x = getattr(event, "x", 0)
        if self._layout_mode == "wrapped":
            try:
                canvas = widget if isinstance(widget, tk.Canvas) else self.canvas
                y = int(canvas.canvasy(event.y))
            except Exception:
                y = getattr(event, "y", 0)
            return self._wrap_point_to_tick(x, y)
        return self._tick_from_x(x)

    def _tick_from_x(self, x: int) -> Optional[int]:
        if self._layout_mode == "wrapped":
            return None
        delta = x - self.LEFT_PAD
        tick = int(round(delta / max(self.px_per_tick, 1e-6)))
        tick = max(0, tick)
        if self._total_ticks:
            tick = min(self._total_ticks, tick)
        return tick

    def _tick_to_x(self, tick: int) -> int:
        clamped = max(0, tick)
        if self._total_ticks:
            clamped = min(self._total_ticks, clamped)
        return self.LEFT_PAD + int(round(clamped * self.px_per_tick))

    def _wrap_tick_to_coords(self, tick: int) -> tuple[float, float, float]:
        return self._cursor_controller.wrap_tick_to_coords(tick)

    def _wrap_point_to_tick(self, x: int, y: int) -> Optional[int]:
        return self._cursor_controller.wrap_point_to_tick(x, y)

