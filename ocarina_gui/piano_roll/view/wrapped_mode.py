"""Support for the wrapped (vertical) piano roll layout."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

import tkinter as tk

from ..rendering import PianoRollRenderer
from ..wrapped import WrappedLayout, WrappedLine, render_wrapped_view
from ...themes import PianoRollPalette
from .types import SupportsGeometry

if TYPE_CHECKING:  # pragma: no cover - only for type checking
    from .widget import PianoRoll


class WrappedModeMixin:
    """Render helpers for the wrapped piano roll layout."""

    canvas: tk.Canvas
    labels: tk.Canvas
    _palette: PianoRollPalette
    _renderer: PianoRollRenderer
    _wrap_layout: Optional[WrappedLayout]
    _wrap_viewport_width: int
    _total_ticks: int
    _content_height: int
    _scroll_width: int
    _label_highlight: Optional[int]
    _loop_start_line: Optional[int]
    _loop_end_line: Optional[int]
    _cursor_line: Optional[int]
    _loop_visible: bool
    px_per_tick: float
    LEFT_PAD: int
    RIGHT_PAD: int

    def _render_wrapped_vertical(
        self: "PianoRoll",
        events,
        pulses_per_quarter: int,
    ) -> None:
        geometry = self._current_geometry()
        viewport_width = self._get_viewport_width(prefer_hint=False)
        result = render_wrapped_view(
            events=events,
            geometry=geometry,
            palette=self._palette,
            canvas=self.canvas,
            labels=self.labels,
            renderer=self._renderer,
            px_per_tick=self.px_per_tick,
            left_pad=self.LEFT_PAD,
            right_pad=self.RIGHT_PAD,
            viewport_width=viewport_width,
        )

        self._wrap_layout = result.layout
        self._wrap_viewport_width = viewport_width
        self._total_ticks = result.total_ticks
        self._content_height = result.content_height
        self._scroll_width = result.scroll_width
        self._label_highlight = result.label_highlight_id
        self._loop_start_line = result.loop_start_line_id
        self._loop_end_line = result.loop_end_line_id
        self._cursor_line = result.cursor_line_id

        self._loop_visible = bool(self._loop_visible and result.total_ticks > 0)
        self._update_loop_markers()
        self.set_cursor(self._cursor_tick)
        self._raise_overlay_items()

    def _wrap_tick_to_coords(self, tick: int) -> Tuple[float, float, float]:
        layout = self._wrap_layout
        if layout is None or not layout.lines:
            height = float(self._content_height or int(self.canvas.winfo_height()) or 1)
            return float(self.LEFT_PAD), 0.0, height
        return layout.coords_for_tick(
            tick,
            px_per_tick=self.px_per_tick,
            left_pad=self.LEFT_PAD,
            total_ticks=self._total_ticks,
        )

    def _wrap_point_to_tick(self, x: int, y: int) -> Optional[int]:
        layout = self._wrap_layout
        if layout is None or not layout.lines:
            return None
        return layout.tick_from_point(
            x,
            y,
            px_per_tick=self.px_per_tick,
            left_pad=self.LEFT_PAD,
            total_ticks=self._total_ticks,
        )

    def _wrap_line_for_y(self, y: float) -> Optional[Tuple[WrappedLine, float]]:
        layout = self._wrap_layout
        if layout is None:
            return None
        result = layout.line_for_y(y)
        if result is None:
            return None
        return result

    # ------------------------------------------------------------------
    # Abstract hooks
    # ------------------------------------------------------------------
    def _current_geometry(self) -> SupportsGeometry:
        raise NotImplementedError

    def _update_loop_markers(self) -> None:
        raise NotImplementedError

    def _raise_overlay_items(self) -> None:
        raise NotImplementedError

    def set_cursor(self, tick: int) -> None:
        raise NotImplementedError
