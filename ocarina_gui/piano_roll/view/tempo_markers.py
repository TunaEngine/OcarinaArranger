"""Tempo marker overlay support for the piano roll widget."""

from __future__ import annotations

import tkinter as tk
from typing import Sequence

from ...themes import PianoRollPalette
from ..wrapped import WrappedLayout
from .types import SupportsGeometry

_TEMPO_MARKER_MIN_BOTTOM = 24.0
_TEMPO_MARKER_VERTICAL_OFFSET = 18.0
_TEMPO_MARKER_LEFT_PADDING = 8.0
_TEMPO_MARKER_BARLINE_PADDING = 6.0


class TempoMarkerMixin:
    """Provide tempo marker rendering behaviour for the piano roll."""

    canvas: tk.Canvas
    LEFT_PAD: int
    RIGHT_PAD: int
    _palette: PianoRollPalette
    _time_layout_mode: str
    _tempo_markers: tuple[tuple[int, str], ...]
    _tempo_marker_items: list[int]
    _wrap_layout: WrappedLayout | None

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._tempo_markers: tuple[tuple[int, str], ...] = ()
        self._tempo_marker_items: list[int] = []

    # ------------------------------------------------------------------
    # Abstract hooks
    # ------------------------------------------------------------------
    def _current_geometry(self) -> SupportsGeometry:  # pragma: no cover - abstract
        raise NotImplementedError

    def _wrap_tick_to_coords(self, tick: int):  # pragma: no cover - abstract
        raise NotImplementedError

    def _raise_overlay_items(self) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_tempo_markers(self, markers: Sequence[tuple[int, str]]) -> None:
        normalized: list[tuple[int, str]] = []
        for tick, text in markers:
            try:
                tick_int = max(0, int(tick))
            except Exception:
                continue
            label = str(text).strip()
            if not label:
                continue
            normalized.append((tick_int, label))
        self._tempo_markers = tuple(normalized)
        self._redraw_tempo_markers()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _clear_tempo_marker_items(self) -> None:
        if not self._tempo_marker_items:
            return
        for item in self._tempo_marker_items:
            try:
                self.canvas.delete(item)
            except Exception:
                continue
        self._tempo_marker_items = []

    def _redraw_tempo_markers(self) -> None:
        self._clear_tempo_marker_items()
        if not self._tempo_markers:
            return
        layout_mode = getattr(self, "_time_layout_mode", "horizontal")
        geometry = self._current_geometry()
        palette = self._palette

        if layout_mode == "horizontal":
            px_per_tick = max(geometry.px_per_tick, 1e-6)
            left_pad = geometry.left_pad
            baseline = geometry.note_y(geometry.max_midi) + min(
                geometry.px_per_note * 0.4,
                14.0,
            )
            y = max(_TEMPO_MARKER_MIN_BOTTOM, baseline - _TEMPO_MARKER_VERTICAL_OFFSET)
            min_left = float(left_pad) + _TEMPO_MARKER_LEFT_PADDING

            for tick, label in self._tempo_markers:
                bar_x = left_pad + tick * px_per_tick
                x = bar_x + _TEMPO_MARKER_BARLINE_PADDING
                try:
                    item = self.canvas.create_text(
                        x,
                        y,
                        text=label,
                        fill=palette.measure_number_text,
                        font=("TkDefaultFont", 9),
                        anchor="sw",
                        tags=("tempo_marker", "overlay"),
                    )
                except Exception:
                    continue
                item_id = int(item)
                self._nudge_tempo_marker_bounds(item_id, min_left=min_left)
                self._tempo_marker_items.append(item_id)
        elif layout_mode == "wrapped":
            layout = getattr(self, "_wrap_layout", None)
            if not getattr(layout, "lines", None):
                return
            baseline_offset = geometry.note_y(geometry.max_midi) + min(
                geometry.px_per_note * 0.4,
                14.0,
            )
            baseline_offset = max(
                _TEMPO_MARKER_MIN_BOTTOM,
                baseline_offset - _TEMPO_MARKER_VERTICAL_OFFSET,
            )
            min_x = float(self.LEFT_PAD)
            max_x = max(
                min_x,
                float(getattr(layout, "content_width", min_x + 1.0)) - float(self.RIGHT_PAD),
            )
            min_left = min_x + _TEMPO_MARKER_LEFT_PADDING
            for tick, label in self._tempo_markers:
                x, y_top, _ = self._wrap_tick_to_coords(tick)
                anchor_x = float(x) + _TEMPO_MARKER_BARLINE_PADDING
                clamped_x = max(min_x, min(max_x, anchor_x))
                y = max(y_top + _TEMPO_MARKER_MIN_BOTTOM, y_top + baseline_offset)
                try:
                    item = self.canvas.create_text(
                        clamped_x,
                        y,
                        text=label,
                        fill=palette.measure_number_text,
                        font=("TkDefaultFont", 9),
                        anchor="sw",
                        tags=("tempo_marker", "overlay"),
                    )
                except Exception:
                    continue
                item_id = int(item)
                self._nudge_tempo_marker_bounds(item_id, min_left=min_left)
                self._tempo_marker_items.append(item_id)
        else:
            return

        if self._tempo_marker_items:
            try:
                self.canvas.tag_raise("tempo_marker")
            except Exception:
                pass
        self._raise_overlay_items()

    def _nudge_tempo_marker_bounds(
        self,
        item: int,
        *,
        min_left: float | None = None,
    ) -> None:
        if min_left is None:
            return
        try:
            bbox = self.canvas.bbox(item)
        except Exception:
            return
        if not bbox:
            return
        left = float(bbox[0])
        if left < min_left:
            try:
                self.canvas.move(item, min_left - left, 0.0)
            except Exception:
                return
