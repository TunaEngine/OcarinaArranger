"""Helpers for rendering and navigating the wrapped piano roll layout."""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence, Tuple

import tkinter as tk

from .events import Event
from .geometry import RenderGeometry
from .notes import label_for_midi, is_accidental
from ..themes import PianoRollPalette

if TYPE_CHECKING:
    from .rendering import PianoRollRenderer


@dataclass(frozen=True)
class WrappedLine:
    """Describe a single wrapped system in the vertical layout."""

    start: float
    end: float
    y_top: float
    y_bottom: float

    def contains(self, y: float) -> bool:
        return self.y_top <= y <= self.y_bottom


@dataclass(frozen=True)
class WrappedLayout:
    """Geometry metadata for the wrapped piano roll layout."""

    ticks_per_line: int
    line_height: float
    system_spacing: float
    lines: Sequence[WrappedLine]
    content_width: float

    def _line_span(self) -> int:
        return max(1, self.ticks_per_line)

    def coords_for_tick(self, tick: int, *, px_per_tick: float, left_pad: int, total_ticks: int) -> tuple[float, float, float]:
        """Translate a tick to the horizontal pixel and vertical system bounds."""

        if not self.lines:
            return float(left_pad), 0.0, 0.0

        clamped = max(0, tick)
        if total_ticks:
            clamped = min(total_ticks, clamped)

        span = self._line_span()
        index = min(len(self.lines) - 1, clamped // span)
        info = self.lines[index]
        local_tick = clamped - index * span
        x = left_pad + int(round(local_tick * px_per_tick))
        return float(x), info.y_top, info.y_bottom

    def tick_from_point(self, x: int, y: int, *, px_per_tick: float, left_pad: int, total_ticks: int) -> int | None:
        """Convert a canvas coordinate back into a tick value."""

        if not self.lines:
            return None

        span = self._line_span()
        line_height = self.line_height
        system_spacing = self.system_spacing
        segment = line_height + system_spacing if line_height > 0 else 1.0

        index = int(y // segment) if segment > 0 else 0
        index = max(0, min(len(self.lines) - 1, index))
        info = self.lines[index]
        line_top = info.y_top
        while index > 0 and y < line_top:
            index -= 1
            info = self.lines[index]
            line_top = info.y_top

        local_tick = int(round((x - left_pad) / max(px_per_tick, 1e-6)))
        local_tick = max(0, local_tick)
        tick = index * span + local_tick
        if total_ticks:
            tick = min(total_ticks, tick)
        return tick

    def line_for_y(self, y: float) -> tuple[WrappedLine, float] | None:
        """Return the line that contains the given y position."""

        if not self.lines:
            return None

        for info in self.lines:
            if info.contains(y):
                return info, info.y_top

        first = self.lines[0]
        last = self.lines[-1]
        if y < first.y_top:
            return first, first.y_top
        return last, last.y_top


@dataclass(frozen=True)
class WrappedRenderResult:
    """Information returned after drawing the wrapped layout."""

    layout: WrappedLayout
    total_ticks: int
    content_height: int
    scroll_width: int
    label_highlight_id: int
    loop_start_line_id: int
    loop_end_line_id: int
    cursor_line_id: int


def render_wrapped_view(
    *,
    events: Tuple[Event, ...],
    geometry: RenderGeometry,
    palette: PianoRollPalette,
    canvas: tk.Canvas,
    labels: tk.Canvas,
    renderer: "PianoRollRenderer",
    px_per_tick: float,
    left_pad: int,
    right_pad: int,
    viewport_width: int,
    ticks_per_measure: int,
    total_ticks: int | None = None,
) -> WrappedRenderResult:
    """Render events using the wrapped piano roll layout."""

    canvas.delete("all")
    labels.delete("all")

    inferred_total = (
        max((onset + duration) for (onset, duration, _midi, _program) in events)
        if events
        else 0
    )
    effective_total = max(inferred_total, int(total_ticks or 0))

    min_width = geometry.left_pad + geometry.right_pad + 600
    width = max(min_width, viewport_width)
    available_width = max(1, width - geometry.left_pad - geometry.right_pad)
    px_per_tick = max(px_per_tick, 1e-6)
    ticks_per_line = max(1, int(round(available_width / px_per_tick)))
    note_rows = geometry.max_midi - geometry.min_midi + 1
    line_height = note_rows * geometry.px_per_note + 28
    system_spacing = int(max(geometry.px_per_note * 1.5, 24))
    line_count = 1 if effective_total == 0 else int(math.ceil(effective_total / ticks_per_line))
    total_height = int(line_count * line_height + max(0, line_count - 1) * system_spacing)

    canvas.config(scrollregion=(0, 0, width, total_height))
    labels.config(scrollregion=(0, 0, geometry.label_width, total_height))

    if not events:
        line_count = 1

    lines: list[WrappedLine] = []
    event_onsets = tuple(event[0] for event in events)

    for line_index in range(line_count):
        line_start = line_index * ticks_per_line
        if effective_total and line_index == line_count - 1:
            line_end = float(effective_total)
        else:
            line_end = float(min(effective_total, line_start + ticks_per_line))

        y_offset = line_index * (line_height + system_spacing)
        y_top = float(y_offset)
        y_bottom = float(y_offset + line_height)

        tag = f"wrapped_line_{line_index}"

        lines.append(
            WrappedLine(
                start=float(line_start),
                end=line_end,
                y_top=y_top,
                y_bottom=y_bottom,
            )
        )

        canvas.create_rectangle(
            0,
            y_top,
            width,
            y_bottom,
            outline="",
            fill=palette.background,
        )

        for midi in range(geometry.min_midi, geometry.max_midi + 1):
            row_top = geometry.note_y(midi)
            fill = palette.accidental_row_fill if is_accidental(midi) else palette.natural_row_fill
            canvas.create_rectangle(
                geometry.left_pad,
                row_top,
                width - right_pad,
                row_top + geometry.px_per_note,
                outline="",
                fill=fill,
                tags=(tag,),
            )
            labels_row_top = y_offset + geometry.note_y(midi)
            labels.create_rectangle(
                0,
                labels_row_top,
                geometry.label_width,
                labels_row_top + geometry.px_per_note,
                outline="",
                fill=fill,
            )
            label = "#" if is_accidental(midi) else label_for_midi(midi)
            labels.create_text(
                geometry.label_width - 6,
                labels_row_top + geometry.px_per_note / 2,
                anchor="e",
                fill=palette.note_label_text,
                text=label,
                font=("TkDefaultFont", max(6, int(geometry.px_per_note * 0.6))),
                tags=("note_label",),
            )

        if ticks_per_measure > 0 and events:
            measure_spacing_px = max(1, int(round(ticks_per_measure * px_per_tick)))
            if measure_spacing_px > 0:
                max_x = width - right_pad
                label_offset = geometry.note_y(geometry.max_midi) + min(
                    geometry.px_per_note * 0.4,
                    14.0,
                )
                measure_tick = int(math.floor(line_start / max(1, ticks_per_measure))) * max(
                    1, ticks_per_measure
                )
                if measure_tick < line_start:
                    measure_tick += max(1, ticks_per_measure)
                line_has_measure = False
                while measure_tick <= line_end + 1e-6:
                    local_tick = measure_tick - line_start
                    x = left_pad + int(round(local_tick * px_per_tick))
                    if x > max_x:
                        break
                    canvas.create_line(
                        x,
                        0,
                        x,
                        line_height,
                        fill=palette.measure_line,
                        width=1,
                        state="hidden",
                        tags=(tag, "virtualized", "measure_line"),
                    )
                    measure_number = measure_tick // max(1, ticks_per_measure) + 1
                    if measure_number > 1:
                        canvas.create_text(
                            x,
                            label_offset,
                            text=str(measure_number),
                            fill=palette.measure_number_text,
                            font=("TkDefaultFont", 8),
                            anchor="n",
                            state="hidden",
                            tags=(tag, "virtualized", "measure_number"),
                        )
                    line_has_measure = True
                    measure_tick += max(1, ticks_per_measure)
                if not line_has_measure:
                    canvas.create_line(
                        left_pad,
                        0,
                        left_pad,
                        line_height,
                        fill=palette.measure_line,
                        width=1,
                        state="hidden",
                        tags=(tag, "virtualized", "measure_line"),
                    )

        if not events:
            continue

        start_index = bisect_left(event_onsets, line_start)
        while start_index > 0:
            prev_onset, prev_duration, _prev_midi, _prev_program = events[start_index - 1]
            if prev_onset + prev_duration <= line_start:
                break
            start_index -= 1

        idx = start_index
        while idx < len(events):
            onset, duration, midi, _program = events[idx]
            if onset >= line_start + ticks_per_line:
                break
            if onset + duration <= line_start:
                idx += 1
                continue
            local_start = max(onset, line_start)
            local_end = min(onset + duration, line_start + ticks_per_line)
            local_onset = int(local_start - line_start)
            local_duration = int(max(1, local_end - local_start))
            renderer._draw_note_rect(
                tag,
                local_onset,
                local_duration,
                midi,
                geometry,
                palette,
            )
            idx += 1

        canvas.move(tag, 0, y_offset)
        canvas.itemconfigure(tag, state="normal")

    canvas.tag_raise("measure_number")

    highlight_height = geometry.px_per_note
    label_highlight = labels.create_rectangle(
        0,
        0,
        geometry.label_width,
        highlight_height,
        outline="",
        fill=palette.highlight_fill,
        state="hidden",
    )
    labels.tag_raise("note_label")

    content_width = float(width)
    loop_start_line = canvas.create_line(
        geometry.left_pad,
        0,
        content_width - right_pad,
        0,
        fill=palette.loop_start_line,
        width=2,
        state="hidden",
        tags=("loop_start_marker", "overlay"),
    )
    loop_end_line = canvas.create_line(
        geometry.left_pad,
        0,
        content_width - right_pad,
        0,
        fill=palette.loop_end_line,
        width=2,
        state="hidden",
        tags=("loop_end_marker", "overlay"),
    )
    cursor_line = canvas.create_line(
        geometry.left_pad,
        0,
        content_width - right_pad,
        0,
        fill=palette.cursor_primary,
        width=2,
        tags=("time_cursor", "overlay"),
    )

    layout = WrappedLayout(
        ticks_per_line=ticks_per_line,
        line_height=float(line_height),
        system_spacing=float(system_spacing),
        lines=tuple(lines),
        content_width=content_width,
    )

    return WrappedRenderResult(
        layout=layout,
        total_ticks=effective_total,
        content_height=total_height,
        scroll_width=width,
        label_highlight_id=label_highlight,
        loop_start_line_id=loop_start_line,
        loop_end_line_id=loop_end_line,
        cursor_line_id=cursor_line,
    )
