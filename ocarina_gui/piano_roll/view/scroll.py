"""Scrolling helpers for the piano roll widget."""

from __future__ import annotations

from typing import Optional

import tkinter as tk
from tkinter import ttk

from app.config import get_auto_scroll_config

from ...scrolling import AutoScrollMode, move_canvas_to_pixel_fraction
from ..wrapped import WrappedLayout
from .types import SupportsGeometry


class ScrollMixin:
    """Provide scroll-bar configuration and auto-scroll behaviour."""

    canvas: tk.Canvas
    labels: tk.Canvas
    hbar: ttk.Scrollbar
    vbar: ttk.Scrollbar
    _hbar_grid_kwargs: dict[str, object] | None
    _vbar_grid_kwargs: dict[str, object] | None
    _time_scroll_orientation: str
    _time_layout_mode: str
    _viewport_hint: int
    _wrap_layout: Optional[WrappedLayout]
    _wrap_viewport_width: int
    _scroll_width: int
    _content_height: int
    _total_ticks: int
    _auto_scroll_mode: AutoScrollMode
    _last_scroll_fraction: Optional[float]

    def _configure_time_scrollbars(self) -> None:
        orientation = self._time_scroll_orientation
        if orientation == "horizontal":
            if self._hbar_grid_kwargs is not None:
                self.hbar.grid(**self._hbar_grid_kwargs)
            if self._vbar_grid_kwargs is not None:
                self.vbar.grid(**self._vbar_grid_kwargs)
            self.canvas.configure(
                xscrollcommand=self._xsync_from_main,
                yscrollcommand=self._ysync_from_main,
            )
            self.labels.configure(yscrollcommand=self._ysync_from_labels)
            self.hbar.configure(command=self.canvas.xview)
            self.vbar.configure(command=self._yview_both)
        else:
            if self._hbar_grid_kwargs is not None:
                self.hbar.grid_remove()
            if self._vbar_grid_kwargs is not None:
                self.vbar.grid(**self._vbar_grid_kwargs)
            self.canvas.configure(
                xscrollcommand=None,
                yscrollcommand=self._time_vertical_sync_main,
            )
            self.labels.configure(yscrollcommand=self._time_vertical_sync_labels)
            self.hbar.configure(command=self.canvas.xview)
            self.vbar.configure(command=self._time_scroll_from_vertical)
            try:
                self.canvas.xview_moveto(0.0)
                self.labels.xview_moveto(0.0)
                self.labels.yview_moveto(0.0)
            except Exception:
                pass

    def _yview_both(self, *args) -> None:
        self.canvas.yview(*args)
        self.labels.yview(*args)

    def _ysync_from_main(self, *args) -> None:
        if self._time_scroll_orientation == "horizontal":
            try:
                self.vbar.set(*args)
            except Exception:
                pass
        self.labels.yview_moveto(self.canvas.yview()[0])

    def _ysync_from_labels(self, *args) -> None:
        if self._time_scroll_orientation == "horizontal":
            try:
                self.vbar.set(*args)
            except Exception:
                pass
        self.canvas.yview_moveto(self.labels.yview()[0])

    def _xsync_from_main(self, *args) -> None:
        try:
            self.hbar.set(*args)
        except Exception:
            pass
        self._update_time_scroll_fraction()

    def _time_vertical_sync_main(self, *args) -> None:
        try:
            self.vbar.set(*args)
        except Exception:
            pass
        try:
            first = float(args[0])
        except Exception:
            first = self.canvas.yview()[0]
        try:
            self.labels.yview_moveto(first)
        except Exception:
            pass
        self._update_time_scroll_fraction()

    def _time_vertical_sync_labels(self, *args) -> None:
        try:
            self.vbar.set(*args)
        except Exception:
            pass
        try:
            first = float(args[0])
        except Exception:
            first = self.labels.yview()[0]
        try:
            self.canvas.yview_moveto(first)
        except Exception:
            pass
        self._update_time_scroll_fraction()

    def _time_scroll_from_vertical(self, *args) -> None:
        self.canvas.yview(*args)
        self.labels.yview(*args)
        self._update_time_scroll_fraction()

    def _update_time_scroll_fraction(self) -> None:
        try:
            if self._time_layout_mode == "wrapped":
                fraction = self.canvas.yview()[0]
                self._last_scroll_fraction = fraction
                return
            fraction = self.canvas.xview()[0]
        except Exception:
            return
        self._last_scroll_fraction = fraction
        self._redraw_visible_region()
        for target in getattr(self, "_x_targets", []):
            try:
                move_canvas_to_pixel_fraction(target, fraction)
            except Exception:
                pass

    def _on_mousewheel(self, event: tk.Event) -> None:
        delta = -1 if event.delta > 0 else 1
        if self._time_scroll_orientation == "vertical" and not (event.state & 0x0001):
            self._time_scroll_from_vertical("scroll", delta, "units")
        else:
            self._yview_both("scroll", delta, "units")

    def _redraw_visible_region(self, force: bool = False) -> None:
        if self._time_layout_mode == "wrapped":
            return
        viewport_width = self._get_viewport_width()
        if viewport_width <= 0:
            return
        try:
            left_fraction, _right_fraction = self.canvas.xview()
        except Exception:
            left_fraction = 0.0
        self._renderer.redraw_visible_region(
            self._current_geometry(),
            viewport_width,
            left_fraction,
            force=force,
        )
        self._raise_overlay_items()

    def _get_viewport_width(self, *, prefer_hint: bool = True) -> int:
        hint = getattr(self, "_viewport_hint", 0)

        try:
            width = int(self.canvas.winfo_width())
        except Exception:
            width = 0
        if width > 1:
            self._viewport_hint = width
            return width

        candidates: list[int] = []
        try:
            configured = float(self.canvas.cget("width"))
        except Exception:
            configured = 0.0
        configured_int = int(round(configured)) if configured > 1 else 0
        if configured_int > 1:
            candidates.append(configured_int)

        if hint > 1:
            candidates.append(int(hint))

        scroll_width = max(1, self._scroll_width)
        try:
            left_fraction, right_fraction = self.canvas.xview()
        except Exception:
            left_fraction, right_fraction = 0.0, 0.0
        fraction_span = right_fraction - left_fraction
        if fraction_span > 0:
            inferred = int(round(fraction_span * scroll_width))
            if inferred > 1:
                candidates.append(inferred)

        if not candidates:
            return 0

        if prefer_hint:
            chosen = max(candidates)
        else:
            non_hint = [value for value in candidates if value != hint]
            chosen = max(non_hint) if non_hint else max(candidates)

        self._viewport_hint = chosen
        return chosen

    def _get_viewport_height(self) -> int:
        try:
            height = int(self.canvas.winfo_height())
        except Exception:
            height = 0
        if height > 1:
            return height
        try:
            configured = float(self.canvas.cget("height"))
        except Exception:
            configured = 0.0
        configured_int = int(round(configured)) if configured > 1 else 0
        return configured_int

    def _maybe_autoscroll(self, position: int) -> None:
        if self._time_layout_mode == "wrapped":
            viewport_height = self._get_viewport_height()
            if viewport_height <= 0:
                return
            scroll_height = max(1, self._content_height)
            try:
                top_fraction = self.canvas.yview()[0]
            except Exception:
                top_fraction = 0.0
            top_edge = int(round(top_fraction * scroll_height))
            max_top = max(0, scroll_height - viewport_height)
            mode = self._auto_scroll_mode
            flip_config = get_auto_scroll_config().flip
            threshold_offset = max(1, int(round(viewport_height * flip_config.threshold_fraction)))
            advance = max(1, int(round(viewport_height * flip_config.page_offset_fraction)))
            layout = getattr(self, "_wrap_layout", None)
            line_top_target: int | None = None
            if layout is not None:
                match = layout.line_for_y(float(position))
                if match is not None:
                    _line, line_top = match
                    line_top_target = int(round(line_top))
            target = None
            if position < top_edge:
                if line_top_target is not None:
                    target = max(0, min(line_top_target, max_top))
                else:
                    target = max(0, position - advance)
            else:
                page_trigger_offset = threshold_offset
                if mode is AutoScrollMode.CONTINUOUS:
                    page_trigger_offset = max(1, int(round(viewport_height * 0.75)))
                page_trigger = top_edge + page_trigger_offset
                if position <= page_trigger:
                    return
                if line_top_target is not None and line_top_target > top_edge:
                    target = min(line_top_target, max_top)
                elif mode is AutoScrollMode.CONTINUOUS:
                    target = max(0, min(position - page_trigger_offset, max_top))
                else:
                    target = min(max_top, top_edge + advance)
            if target is None:
                return
            target = max(0, min(target, max_top))
            if abs(target - top_edge) < 1.0:
                return
            fraction = target / scroll_height
            if self._last_scroll_fraction is not None and abs(self._last_scroll_fraction - fraction) < 1e-4:
                return
            try:
                self.canvas.yview_moveto(fraction)
                self.labels.yview_moveto(fraction)
            except Exception:
                return
            self._last_scroll_fraction = fraction
            return

        viewport_width = self._get_viewport_width(prefer_hint=False)
        if viewport_width <= 0:
            return
        scroll_width = max(1, self._scroll_width)
        try:
            left_fraction = self.canvas.xview()[0]
        except Exception:
            left_fraction = 0.0
        left_edge = int(round(left_fraction * scroll_width))
        max_left = max(0, scroll_width - viewport_width)
        mode = self._auto_scroll_mode
        flip_config = get_auto_scroll_config().flip
        threshold_offset = max(1, int(round(viewport_width * flip_config.threshold_fraction)))
        advance = max(1, int(round(viewport_width * flip_config.page_offset_fraction)))
        target = None
        if position < left_edge:
            target = max(0, position - advance)
        else:
            page_trigger_offset = threshold_offset
            if mode is AutoScrollMode.CONTINUOUS:
                page_trigger_offset = max(1, int(round(viewport_width * 0.75)))

            page_trigger = left_edge + page_trigger_offset
            if position <= page_trigger:
                return

            if mode is AutoScrollMode.CONTINUOUS:
                target = position - page_trigger_offset
            else:
                target = left_edge + advance

        if target is None:
            return
        target = max(0, min(target, max_left))
        if abs(target - left_edge) < 1.0:
            return
        fraction = target / scroll_width
        if self._last_scroll_fraction is not None and abs(self._last_scroll_fraction - fraction) < 1e-4:
            return
        try:
            applied = move_canvas_to_pixel_fraction(self.canvas, fraction)
        except Exception:
            return
        self._last_scroll_fraction = applied

    # ------------------------------------------------------------------
    # Abstract hooks provided by ``PianoRoll``
    # ------------------------------------------------------------------
    def _current_geometry(self) -> SupportsGeometry:
        raise NotImplementedError

    def _raise_overlay_items(self) -> None:
        raise NotImplementedError

