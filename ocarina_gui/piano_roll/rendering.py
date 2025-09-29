"""Rendering helpers for the piano roll widget."""

from __future__ import annotations

import tkinter as tk
from bisect import bisect_left
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from ..constants import midi_to_name
from .events import Event
from .geometry import RenderGeometry
from .notes import is_accidental, label_for_midi


@dataclass
class RenderOutcome:
    """Metadata produced when rendering the piano roll."""

    total_ticks: int
    content_height: int
    scroll_width: int
    has_events: bool


class PianoRollRenderer:
    """Manage drawing of piano roll content and virtualization."""

    def __init__(self, canvas: tk.Canvas, labels: tk.Canvas, palette) -> None:
        self.canvas = canvas
        self.labels = labels
        self._palette = palette
        self._virtual_tags = ("virtualized_a", "virtualized_b")
        self._active_virtual_tag_index = 0
        self._normalized_events: Tuple[Event, ...] = ()
        self._event_onsets: Tuple[int, ...] = ()
        self._quarter_px = 0
        self._drawn_range: Optional[Tuple[int, int]] = None
        self._scroll_width = 1
        self._content_height = 0
        self._total_ticks = 0

    def set_palette(self, palette) -> None:
        self._palette = palette

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def render(
        self,
        events: Sequence[Event],
        pulses_per_quarter: int,
        geometry: RenderGeometry,
    ) -> RenderOutcome:
        palette = self._palette
        normalized = tuple(events)
        self.canvas.delete("all")
        self.labels.delete("all")
        self._active_virtual_tag_index = 0
        self._drawn_range = None

        if not normalized:
            self._normalized_events = ()
            self._event_onsets = ()
            self._quarter_px = 0
            self._scroll_width = 1
            self._total_ticks = 0
            self._content_height = int(self.canvas.winfo_height())
            self._render_empty_state(geometry)
            return RenderOutcome(
                total_ticks=0,
                content_height=self._content_height,
                scroll_width=self._scroll_width,
                has_events=False,
            )

        last_tick = max(onset + duration for (onset, duration, _midi, _program) in normalized)
        height = (geometry.max_midi - geometry.min_midi + 1) * geometry.px_per_note + 28
        total_time_px = int(round(last_tick * geometry.px_per_tick))
        width = geometry.left_pad + total_time_px + geometry.right_pad

        self._total_ticks = last_tick
        self._content_height = height
        self._scroll_width = max(1, width)
        self._normalized_events = normalized
        self._event_onsets = tuple(event[0] for event in normalized)
        self._quarter_px = max(1, int(round(pulses_per_quarter * geometry.px_per_tick)))

        self.canvas.config(scrollregion=(0, 0, width, height))
        self.labels.config(scrollregion=(0, 0, geometry.label_width, height))

        self._draw_label_rows(geometry, palette)

        return RenderOutcome(
            total_ticks=self._total_ticks,
            content_height=self._content_height,
            scroll_width=self._scroll_width,
            has_events=True,
        )

    def redraw_visible_region(
        self,
        geometry: RenderGeometry,
        viewport_width: int,
        left_fraction: float,
        *,
        force: bool = False,
    ) -> None:
        if not self._normalized_events or self._quarter_px <= 0:
            return
        scroll_width = max(1, self._scroll_width)
        left_edge = int(left_fraction * scroll_width)
        right_edge = left_edge + viewport_width
        margin = max(256, viewport_width // 2)
        draw_left = max(0, left_edge - margin)
        draw_right = min(scroll_width, right_edge + margin)
        if not force and self._drawn_range is not None:
            prev_left, prev_right = self._drawn_range
            if draw_left >= prev_left and draw_right <= prev_right:
                return
        self._drawn_range = (draw_left, draw_right)

        palette = self._palette
        height = self._content_height or int(self.canvas.winfo_height()) or 1
        old_tag = self._virtual_tags[self._active_virtual_tag_index]
        next_index = 1 - self._active_virtual_tag_index
        new_tag = self._virtual_tags[next_index]
        self.canvas.delete(new_tag)

        note_label_tag = "note_value_label"

        self._draw_background_rows(new_tag, draw_left, draw_right, geometry, palette)
        self._draw_grid_lines(new_tag, draw_left, draw_right, height, geometry, palette)

        visible_events = self._events_in_window(draw_left, draw_right, geometry)
        for onset, duration, midi, _program in visible_events:
            self._draw_note_rect(new_tag, onset, duration, midi, geometry, palette)

        self.canvas.itemconfigure(new_tag, state="normal")
        if self.canvas.find_withtag("overlay"):
            try:
                self.canvas.tag_lower(new_tag, "overlay")
            except Exception:
                pass
        self.canvas.tag_raise(note_label_tag)
        if old_tag != new_tag:
            self.canvas.delete(old_tag)
        self._active_virtual_tag_index = next_index

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _render_empty_state(self, geometry: RenderGeometry) -> None:
        palette = self._palette
        self.canvas.create_text(
            10,
            10,
            anchor="nw",
            fill=palette.placeholder_text,
            text="(No events)",
        )
        self.labels.create_text(
            geometry.label_width - 6,
            10,
            anchor="ne",
            fill=palette.header_text,
            text="notes",
        )

    def _draw_label_rows(self, geometry: RenderGeometry, palette) -> None:
        for midi in range(geometry.min_midi, geometry.max_midi + 1):
            y = geometry.note_y(midi)
            fill = palette.accidental_row_fill if is_accidental(midi) else palette.natural_row_fill
            self.labels.create_rectangle(
                0,
                y,
                geometry.label_width,
                y + geometry.px_per_note,
                outline="",
                fill=fill,
            )
            if is_accidental(midi):
                self.labels.create_text(
                    geometry.label_width - 6,
                    y + geometry.px_per_note / 2,
                    anchor="e",
                    fill=palette.note_label_text,
                    text="#",
                    tags=("note_label",),
                )
            else:
                self.labels.create_text(
                    geometry.label_width - 6,
                    y + geometry.px_per_note / 2,
                    anchor="e",
                    fill=palette.note_label_text,
                    text=label_for_midi(midi),
                    tags=("note_label",),
                )

    def _draw_background_rows(
        self,
        tag: str,
        draw_left: int,
        draw_right: int,
        geometry: RenderGeometry,
        palette,
        *,
        target: Optional[tk.Canvas] = None,
    ) -> None:
        canvas = target or self.canvas
        for midi in range(geometry.min_midi, geometry.max_midi + 1):
            y = geometry.note_y(midi)
            fill = palette.accidental_row_fill if is_accidental(midi) else palette.natural_row_fill
            canvas.create_rectangle(
                draw_left,
                y,
                draw_right,
                y + geometry.px_per_note,
                outline="",
                fill=fill,
                state="hidden",
                tags=(tag, "virtualized", "row_background"),
            )

    def _draw_grid_lines(
        self,
        tag: str,
        draw_left: int,
        draw_right: int,
        height: int,
        geometry: RenderGeometry,
        palette,
    ) -> None:
        spacing = self._quarter_px
        if spacing <= 0:
            return
        start = max(geometry.left_pad, draw_left)
        offset = max(0, int((start - geometry.left_pad) // spacing) * spacing)
        x = geometry.left_pad + offset
        if x < start:
            x += spacing
        while x <= draw_right:
            self.canvas.create_line(
                x,
                0,
                x,
                height,
                fill=palette.grid_line,
                state="hidden",
                tags=(tag, "virtualized", "grid_line"),
            )
            x += spacing

    def _events_in_window(self, draw_left: int, draw_right: int, geometry: RenderGeometry) -> Iterable[Event]:
        if not self._event_onsets:
            return self._normalized_events

        px_per_tick = max(geometry.px_per_tick, 1e-6)
        tick_left = max(0, int((draw_left - geometry.left_pad) / px_per_tick) - 4)
        tick_right = max(0, int((draw_right - geometry.left_pad) / px_per_tick) + 4)

        start_index = bisect_left(self._event_onsets, tick_left)
        while start_index > 0:
            prev_event = self._normalized_events[start_index - 1]
            if prev_event[0] + prev_event[1] < tick_left:
                break
            start_index -= 1

        visible: List[Event] = []
        for idx in range(start_index, len(self._normalized_events)):
            onset, duration, _midi, _program = self._normalized_events[idx]
            if onset > tick_right:
                break
            if onset + duration < tick_left:
                continue
            visible.append(self._normalized_events[idx])
        return visible

    def _draw_note_rect(
        self,
        tag: str,
        onset: int,
        duration: int,
        midi: int,
        geometry: RenderGeometry,
        palette,
    ) -> None:
        x0 = geometry.left_pad + int(round(onset * geometry.px_per_tick))
        y0 = geometry.note_y(midi)
        x1 = x0 + max(4, int(round(duration * geometry.px_per_tick)))
        y1 = y0 + geometry.px_per_note - 3
        fill = palette.note_fill_sharp if is_accidental(midi) else palette.note_fill_natural
        self.canvas.create_rectangle(
            x0,
            y0 + 1,
            x1,
            y1,
            outline=palette.note_outline,
            fill=fill,
            width=1,
            state="hidden",
            tags=(tag, "virtualized", "note_rect"),
        )
        note_text = midi_to_name(midi)
        center_x = (x0 + x1) / 2
        name_font = ("TkDefaultFont", max(6, int(geometry.px_per_note * 0.6)))
        self.canvas.create_text(
            center_x,
            y0 + geometry.px_per_note * 0.55,
            text=note_text,
            fill=palette.note_label_text,
            font=name_font,
            state="hidden",
            tags=(tag, "virtualized", "note_value_label"),
            justify="center",
        )

    # ------------------------------------------------------------------
    # Accessors for state required by the view
    # ------------------------------------------------------------------
    @property
    def scroll_width(self) -> int:
        return self._scroll_width

    @property
    def total_ticks(self) -> int:
        return self._total_ticks

    @property
    def content_height(self) -> int:
        return self._content_height

    @property
    def quarter_px(self) -> int:
        return self._quarter_px
