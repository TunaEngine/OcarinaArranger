"""Scroll handling helpers for :class:`StaffView`."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional, TYPE_CHECKING

from app.config import get_auto_scroll_config

from ...scrolling import AutoScrollMode, move_canvas_to_pixel_fraction

if TYPE_CHECKING:  # pragma: no cover - typing helpers
    from ..rendering import StaffRenderer
    from ..scrollbars import ScrollbarManager


__all__ = ["StaffViewScrollingMixin"]


class StaffViewScrollingMixin:
    """Mixin that encapsulates scrollbar management and auto-scroll logic."""

    canvas: tk.Canvas
    hbar: ttk.Scrollbar
    _scrollbars: "ScrollbarManager"
    _renderer: "StaffRenderer"
    _layout_mode: str
    _auto_scroll_mode: AutoScrollMode
    _scroll_width: int
    _content_height: int
    _x_targets: list[tk.Canvas]

    def _configure_scrollbars(self) -> None:
        self._scrollbars.configure_for_layout(self._layout_mode)

    def _ysync_wrapped(self, *args) -> None:
        self._scrollbars.ysync_wrapped(*args)

    def _ensure_scrollbars_visible(self) -> None:
        self._scrollbars.ensure_visible(self._layout_mode)

    def _show_vertical_scrollbar(self) -> None:
        self._scrollbars.show_vertical_scrollbar()

    def _ensure_vertical_bar_mapped(self) -> None:
        self._scrollbars.ensure_vertical_bar_mapped()

    def _configure_placeholder_column(self) -> None:
        self._scrollbars.configure_placeholder_column(self._layout_mode)

    def _remap_vertical_scrollbar(self, context: str) -> bool:
        return self._scrollbars.remap_vertical_scrollbar(context)

    def _grid_vertical_scrollbar(
        self, options: dict[str, object] | None, *, context: str = "direct"
    ) -> None:
        self._scrollbars.grid_vertical_scrollbar(options, context=context)

    def _finalize_vertical_scrollbar(self) -> None:
        self._scrollbars.finalize_vertical_scrollbar()

    def _is_vbar_mapped(self) -> bool:
        return self._scrollbars.is_vbar_mapped()

    def _xsync_from_staff(self, *args) -> None:
        first = self.canvas.xview()[0]
        self._scrollbars.update_last_scroll_fraction(first)
        try:
            self.hbar.set(*args)
        except Exception:
            pass
        self._renderer.redraw_visible_region()
        for target in self._x_targets:
            try:
                move_canvas_to_pixel_fraction(target, first)
            except Exception:
                pass

    def _get_viewport_width(self) -> int:
        try:
            width = int(self.canvas.winfo_width())
        except Exception:
            width = 0
        if width > 1:
            return width
        try:
            configured = float(self.canvas.cget("width"))
        except Exception:
            configured = 0.0
        return int(round(configured)) if configured > 1 else 0

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
        return int(round(configured)) if configured > 1 else 0

    def _maybe_autoscroll(self, position: int) -> None:
        if self._layout_mode == "wrapped":
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
            target: Optional[int] = None
            if position < top_edge:
                target = max(0, position - advance)
            else:
                page_trigger_offset = threshold_offset
                if mode is AutoScrollMode.CONTINUOUS:
                    page_trigger_offset = max(1, int(round(viewport_height * 0.75)))
                page_trigger = top_edge + page_trigger_offset
                if position <= page_trigger:
                    return
                if mode is AutoScrollMode.CONTINUOUS:
                    target = position - page_trigger_offset
                else:
                    target = top_edge + advance
            if target is None:
                return
            target = max(0, min(target, max_top))
            fraction = target / max(1, scroll_height)
            last_fraction = self._scrollbars.last_scroll_fraction()
            if last_fraction is not None and abs(last_fraction - fraction) < 1e-4:
                return
            try:
                self.canvas.yview_moveto(fraction)
            except Exception:
                return
            self._scrollbars.update_last_scroll_fraction(fraction)
            return

        viewport_width = self._get_viewport_width()
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
        target: Optional[int] = None
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
        fraction = target / max(1, scroll_width)
        last_fraction = self._scrollbars.last_scroll_fraction()
        if last_fraction is not None and abs(last_fraction - fraction) < 1e-4:
            return
        try:
            self.canvas.xview_moveto(fraction)
        except Exception:
            return
        self._scrollbars.update_last_scroll_fraction(fraction)

    def _log_scrollbar_state(self, context: str) -> None:
        self._scrollbars.log_state(context, self._layout_mode)
