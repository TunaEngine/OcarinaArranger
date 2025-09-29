"""Loop marker management for the piano roll."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

import tkinter as tk

from ...themes import PianoRollPalette
from ..wrapped import WrappedLayout

if TYPE_CHECKING:  # pragma: no cover - only for type checking
    from .widget import PianoRoll


class LoopMixin:
    """Maintain loop overlays in both horizontal and wrapped layouts."""

    canvas: tk.Canvas
    _palette: PianoRollPalette
    _loop_start_line: Optional[int]
    _loop_end_line: Optional[int]
    _loop_start_tick: int
    _loop_end_tick: int
    _loop_visible: bool
    _time_layout_mode: str
    _total_ticks: int
    _content_height: int

    def set_loop_region(self: "PianoRoll", start_tick: int, end_tick: int, visible: bool) -> None:
        start = min(start_tick, end_tick)
        end = max(start_tick, end_tick)
        if self._total_ticks:
            start = max(0, min(self._total_ticks, start))
            end = max(0, min(self._total_ticks, end))
        self._loop_start_tick = max(0, start)
        self._loop_end_tick = max(self._loop_start_tick, end)
        self._loop_visible = bool(visible and self._loop_end_tick > self._loop_start_tick)
        self._update_loop_markers()
        self._raise_overlay_items()

    def _update_loop_markers(self: "PianoRoll") -> None:
        if self._loop_start_line is None or self._loop_end_line is None:
            return
        if not self._loop_visible or self._total_ticks <= 0:
            self.canvas.itemconfigure(self._loop_start_line, state="hidden")
            self.canvas.itemconfigure(self._loop_end_line, state="hidden")
            return
        if self._time_layout_mode == "wrapped":
            start_x, start_y_top, start_y_bottom = self._wrap_tick_to_coords(self._loop_start_tick)
            end_x, end_y_top, end_y_bottom = self._wrap_tick_to_coords(self._loop_end_tick)
            width = self._wrap_layout.content_width if self._wrap_layout else float(self.LEFT_PAD + 400)
            x_min = float(self.LEFT_PAD)
            x_max = max(x_min, width - self.RIGHT_PAD)
            start_x = max(x_min, min(start_x, x_max))
            end_x = max(x_min, min(end_x, x_max))
            self.canvas.coords(self._loop_start_line, start_x, start_y_top, start_x, start_y_bottom)
            self.canvas.coords(self._loop_end_line, end_x, end_y_top, end_x, end_y_bottom)
            self.canvas.itemconfigure(self._loop_start_line, state="normal")
            self.canvas.itemconfigure(self._loop_end_line, state="normal")
            self.canvas.tag_raise(self._loop_start_line)
            self.canvas.tag_raise(self._loop_end_line)
            if self._cursor_line is not None:
                self.canvas.tag_raise(self._cursor_line)
            return

        height = self._content_height or int(self.canvas.winfo_height())
        geometry = self._current_geometry()
        start_x = geometry.tick_to_x(self._loop_start_tick, self._total_ticks)
        end_x = geometry.tick_to_x(self._loop_end_tick, self._total_ticks)
        self.canvas.coords(self._loop_start_line, start_x, 0, start_x, height)
        self.canvas.coords(self._loop_end_line, end_x, 0, end_x, height)
        self.canvas.itemconfigure(self._loop_start_line, state="normal")
        self.canvas.itemconfigure(self._loop_end_line, state="normal")
        self.canvas.tag_raise(self._loop_start_line)
        self.canvas.tag_raise(self._loop_end_line)
        if self._cursor_line is not None:
            self.canvas.tag_raise(self._cursor_line)

    # ------------------------------------------------------------------
    # Abstract hooks
    # ------------------------------------------------------------------
    def _wrap_tick_to_coords(self, tick: int):  # pragma: no cover - abstract
        raise NotImplementedError

    def _current_geometry(self):  # pragma: no cover - abstract
        raise NotImplementedError

    _cursor_line: Optional[int]
    LEFT_PAD: int
    RIGHT_PAD: int
    _wrap_layout: Optional[WrappedLayout]
