"""Hover handling and label highlighting helpers."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING, Callable

import tkinter as tk

if TYPE_CHECKING:  # pragma: no cover - only for type checking
    from .piano_roll import PianoRoll


class HoverMixin:
    """Provide hover feedback behaviour for the piano roll."""

    labels: tk.Canvas
    _label_highlight: Optional[int]
    _hover_cb: Optional[Callable[[Optional[int]], None]]
    min_midi: int
    max_midi: int
    label_width: int

    def _hover_from_event(self: "PianoRoll", event: tk.Event) -> None:
        widget = getattr(event, "widget", None)
        y = getattr(event, "y", None)
        if y is None:
            self._hover_emit(None)
            return
        self._hover_emit(int(y), widget)

    def _hover_emit(self: "PianoRoll", y: Optional[int], widget: Optional[tk.Canvas] = None) -> None:
        if y is None:
            self._update_label_highlight(None)
            if self._hover_cb:
                self._hover_cb(None)
            return

        if self._time_layout_mode == "wrapped":
            try:
                y_val = float(widget.canvasy(y)) if widget is not None else float(y)
            except Exception:
                y_val = float(y)
            line_info = self._wrap_line_for_y(y_val)
            if line_info is None:
                self._update_label_highlight(None)
                if self._hover_cb:
                    self._hover_cb(None)
                return
            info, line_top = line_info
            local_y = y_val - line_top
            midi = self._current_geometry().midi_from_y(int(local_y))
            if midi is None:
                self._update_label_highlight(None)
                if self._hover_cb:
                    self._hover_cb(None)
                return
            highlight_midi = midi
            if midi < self.min_midi:
                highlight_midi = self.min_midi
            elif midi > self.max_midi:
                highlight_midi = self.max_midi
            self._update_label_highlight(highlight_midi, line_top=line_top)
            if self._hover_cb:
                if self.min_midi <= midi <= self.max_midi:
                    self._hover_cb(midi)
                else:
                    self._hover_cb(None)
            return

        y_val = int(y)

        if widget is not None:
            try:
                y_val = int(widget.canvasy(y))
            except Exception:
                y_val = int(y)

        midi = self._current_geometry().midi_from_y(y_val)
        if midi is None or midi > self.max_midi:
            self._update_label_highlight(None)
            if self._hover_cb:
                self._hover_cb(None)
            return

        highlight_midi = midi
        if midi < self.min_midi:
            highlight_midi = self.min_midi

        self._update_label_highlight(highlight_midi)
        if self._hover_cb:
            self._hover_cb(midi)

    def _update_label_highlight(
        self: "PianoRoll", midi: Optional[int], *, line_top: float | None = None
    ) -> None:
        if self._label_highlight is None:
            return
        if midi is None:
            self.labels.itemconfigure(self._label_highlight, state="hidden")
            return
        y = self._current_geometry().note_y(midi)
        if line_top is not None:
            y += float(line_top)
        self.labels.coords(self._label_highlight, 0, y, self.label_width, y + self.px_per_note)
        self.labels.itemconfigure(self._label_highlight, state="normal")
        self.labels.tag_raise("note_label")

    # ------------------------------------------------------------------
    # Abstract hooks
    # ------------------------------------------------------------------
    def _wrap_line_for_y(self, y: float):  # pragma: no cover - abstract
        raise NotImplementedError

    def _current_geometry(self):  # pragma: no cover - abstract
        raise NotImplementedError

    px_per_note: float
