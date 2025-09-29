"""Cursor and tick conversion helpers for the piano roll."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import tkinter as tk

from ...themes import PianoRollPalette
from ..wrapped import WrappedLayout
from .types import SupportsGeometry

if TYPE_CHECKING:  # pragma: no cover - only for type checking
    from .widget import PianoRoll


class CursorMixin:
    """Manage the time cursor and tick conversions."""

    canvas: tk.Canvas
    LEFT_PAD: int
    RIGHT_PAD: int
    _content_height: int
    _cursor_line: Optional[int]
    _cursor_tick: int
    _time_layout_mode: str
    _total_ticks: int
    _wrap_layout: Optional[WrappedLayout]
    _loop_start_line: Optional[int]
    _loop_end_line: Optional[int]
    _palette: PianoRollPalette

    def set_cursor(self: "PianoRoll", tick: int, *, allow_autoscroll: bool = True) -> None:
        clamped = max(0, min(self._total_ticks, tick)) if self._total_ticks else max(0, tick)
        previous_tick = self._cursor_tick
        self._cursor_tick = clamped
        if self._cursor_line is None:
            return
        if self._time_layout_mode == "wrapped":
            x, y_top, y_bottom = self._wrap_tick_to_coords(self._cursor_tick)
            width = self._wrap_layout.content_width if self._wrap_layout else float(self.LEFT_PAD + 400)
            x = max(float(self.LEFT_PAD), min(x, max(self.LEFT_PAD, width - self.RIGHT_PAD)))
            coords = self.canvas.coords(self._cursor_line)
            if (
                coords
                and abs(coords[0] - x) < 0.5
                and abs(coords[2] - x) < 0.5
                and abs(coords[1] - y_top) < 0.5
                and abs(coords[3] - y_bottom) < 0.5
                and previous_tick == clamped
            ):
                return
            self.canvas.coords(self._cursor_line, x, y_top, x, y_bottom)
            if self._loop_start_line is not None:
                self.canvas.tag_raise(self._loop_start_line)
            if self._loop_end_line is not None:
                self.canvas.tag_raise(self._loop_end_line)
            self.canvas.tag_raise(self._cursor_line)
            self.canvas.itemconfigure(
                self._cursor_line,
                state="normal",
                fill=self._palette.cursor_primary,
            )
            if allow_autoscroll:
                self._maybe_autoscroll(int(y_top))
            return

        height = self._content_height or int(self.canvas.winfo_height())
        x = self._current_geometry().tick_to_x(self._cursor_tick, self._total_ticks)
        coords = self.canvas.coords(self._cursor_line)
        if (
            coords
            and abs(coords[0] - x) < 0.5
            and abs(coords[2] - x) < 0.5
            and abs(coords[3] - height) < 1.0
            and previous_tick == clamped
        ):
            return
        self.canvas.coords(self._cursor_line, x, 0, x, height)
        if self._loop_start_line is not None:
            self.canvas.tag_raise(self._loop_start_line)
        if self._loop_end_line is not None:
            self.canvas.tag_raise(self._loop_end_line)
        self.canvas.tag_raise(self._cursor_line)
        self.canvas.itemconfigure(
            self._cursor_line,
            state="normal",
            fill=self._palette.cursor_primary,
        )
        if allow_autoscroll:
            self._maybe_autoscroll(x)

    def _tick_to_x(self, tick: int) -> int:
        return self._current_geometry().tick_to_x(tick, self._total_ticks)

    def _tick_from_event(self: "PianoRoll", event: tk.Event) -> Optional[int]:
        widget = getattr(event, "widget", None)
        try:
            canvas = widget if isinstance(widget, tk.Canvas) else self.canvas
            x = int(canvas.canvasx(event.x))
        except Exception:
            x = getattr(event, "x", 0)
        if self._time_layout_mode == "wrapped":
            try:
                canvas = widget if isinstance(widget, tk.Canvas) else self.canvas
                y = int(canvas.canvasy(event.y))
            except Exception:
                y = getattr(event, "y", 0)
            return self._wrap_point_to_tick(x, y)
        return self._tick_from_x(x)

    def _tick_from_x(self, x: int) -> Optional[int]:
        if self._time_layout_mode == "wrapped":
            return None
        return self._current_geometry().x_to_tick(x, self._total_ticks)

    # ------------------------------------------------------------------
    # Abstract hooks
    # ------------------------------------------------------------------
    def _wrap_tick_to_coords(self, tick: int):  # pragma: no cover - abstract
        raise NotImplementedError

    def _wrap_point_to_tick(self, x: int, y: int):  # pragma: no cover - abstract
        raise NotImplementedError

    def _current_geometry(self) -> SupportsGeometry:  # pragma: no cover - abstract
        raise NotImplementedError

    def _maybe_autoscroll(self, position: int) -> None:  # pragma: no cover - abstract
        raise NotImplementedError
