"""Rendering logic for the wrapped staff layout."""

from __future__ import annotations

import math
from bisect import bisect_left
from typing import Tuple, TYPE_CHECKING

from ...note_values import describe_note_glyph
from .note_painter import NotePainter
from .types import Event

if TYPE_CHECKING:  # pragma: no cover - only imported for typing
    from ..view import StaffView


class WrappedRenderer:
    """Renderer that wraps the staff across multiple systems."""

    def __init__(self, view: "StaffView", note_painter: NotePainter) -> None:
        self._view = view
        self._note_painter = note_painter

    def render(
        self,
        events: Tuple[Event, ...],
        pulses_per_quarter: int,
        beats: int,
        beat_type: int,
    ) -> None:
        view = self._view
        palette = view._palette
        view._wrap_layout = None
        view._wrap_pending_rerender = False
        try:
            viewport_width = int(view.canvas.winfo_width())
        except Exception:  # pragma: no cover - defensive
            viewport_width = 0
        if viewport_width <= 1:
            view._wrap_pending_rerender = True
            return
        min_width = view.LEFT_PAD + view.RIGHT_PAD + 600
        width = max(min_width, viewport_width)
        available_width = max(1, width - view.LEFT_PAD - view.RIGHT_PAD)
        ticks_per_line = max(1, int(round(available_width / max(view.px_per_tick, 1e-6))))
        total_ticks = view._total_ticks
        line_count = 1 if total_ticks == 0 else max(1, math.ceil(total_ticks / ticks_per_line))
        line_height = 5 * view.staff_spacing + 120
        system_spacing = int(view.staff_spacing * 6)
        total_height = line_count * line_height + max(0, line_count - 1) * system_spacing
        header = f"Treble staff | {beats}/{beat_type} | notes: {len(events)}"

        view._content_height = total_height
        view._scroll_width = max(1, width)
        view.canvas.config(scrollregion=(0, 0, width, total_height))
        view.canvas.delete("all")
        view.scrollbars.show_vertical_scrollbar()
        view.canvas.create_text(
            view.LEFT_PAD + 4,
            16,
            anchor="w",
            fill=palette.header_text,
            text=header,
        )

        lines: list[dict[str, float]] = []
        view._wrap_layout = {
            "ticks_per_line": ticks_per_line,
            "line_height": line_height,
            "system_spacing": system_spacing,
            "lines": lines,
            "content_width": float(width),
        }

        if not events:
            view.cursor.create_cursor_lines(total_height)
            view.cursor.create_loop_lines(total_height)
            view.set_cursor(view._cursor_tick)
            view.set_secondary_cursor(view._secondary_cursor_tick)
            view.cursor.update_loop_markers()
            return

        measure_spacing_px = max(1, int(round(view._ticks_per_measure * view.px_per_tick)))

        for line_index in range(line_count):
            line_start = line_index * ticks_per_line
            line_end = min(total_ticks, line_start + ticks_per_line)
            y_offset = line_index * (line_height + system_spacing)
            view.canvas.create_rectangle(
                0,
                y_offset,
                width,
                y_offset + line_height,
                outline=palette.outline,
                fill=palette.background,
            )
            y_top = y_offset + 40
            lines.append(
                {
                    "start": float(line_start),
                    "end": float(line_end),
                    "y_top": float(y_top),
                    "y_bottom": float(y_offset + line_height),
                }
            )
            for index in range(5):
                y = y_top + index * view.staff_spacing
                view.canvas.create_line(
                    view.LEFT_PAD,
                    y,
                    width - 20,
                    y,
                    fill=palette.staff_line,
                )
            if measure_spacing_px > 0:
                local_tick = max(0, (line_start // view._ticks_per_measure) * view._ticks_per_measure)
                if local_tick < line_start:
                    local_tick += view._ticks_per_measure
                while local_tick <= line_end:
                    x = view.LEFT_PAD + int(round((local_tick - line_start) * view.px_per_tick))
                    view.canvas.create_line(
                        x,
                        y_top - 12,
                        x,
                        y_top + 4 * view.staff_spacing + 12,
                        fill=palette.measure_line,
                    )
                    local_tick += view._ticks_per_measure

            start_index = bisect_left(view._event_onsets, line_start)
            while start_index > 0:
                prev_onset, prev_duration, _prev_midi, _prev_program = view._events[start_index - 1]
                if prev_onset + prev_duration <= line_start:
                    break
                start_index -= 1
            width_note, height_note = 12, 9
            pulses_per_quarter_value = view._cached[1] if view._cached else pulses_per_quarter
            idx = start_index
            while idx < len(view._events):
                onset, duration, midi, _program = view._events[idx]
                if onset >= line_end:
                    break
                if onset + duration <= line_start:
                    idx += 1
                    continue
                x0 = view.LEFT_PAD + int(round((max(onset, line_start) - line_start) * view.px_per_tick))
                pos = self._note_painter.staff_pos(midi)
                y = self._note_painter.y_for_pos(y_top, pos, view.staff_spacing)
                x_center = x0 + width_note / 2
                self._note_painter.draw_ledger_lines(
                    y_top,
                    pos,
                    x_center,
                    width_note,
                    ("wrapped_ledger",),
                    state="normal",
                )
                if midi % 12 in (1, 3, 6, 8, 10):
                    view.canvas.create_text(
                        x0 - 10,
                        y,
                        text="#",
                        fill=palette.accidental_text,
                        font=("TkDefaultFont", 10),
                    )
                glyph = describe_note_glyph(int(duration), pulses_per_quarter_value)
                fill_color = palette.note_fill
                if glyph is not None and glyph.base in {"whole", "half"}:
                    fill_color = palette.background
                view.canvas.create_oval(
                    x0,
                    y - height_note / 2,
                    x0 + width_note,
                    y + height_note / 2,
                    outline=palette.note_outline,
                    fill=fill_color,
                )
                if glyph is not None:
                    self._note_painter.draw_note_stem_and_flags(
                        x0,
                        y,
                        width_note,
                        glyph,
                        pos,
                        ("wrapped_stem",),
                        state="normal",
                    )
                    self._note_painter.draw_dots(
                        x0,
                        y,
                        width_note,
                        glyph,
                        ("wrapped_dot",),
                        state="normal",
                    )
                octave = midi // 12 - 1
                octave_y = y - view.staff_spacing * 1.6 if pos >= 8 else y + view.staff_spacing * 1.6
                view.canvas.create_text(
                    x_center,
                    octave_y,
                    text=str(octave),
                    fill=palette.header_text,
                    font=("TkDefaultFont", 9),
                )
                idx += 1

        view.cursor.create_cursor_lines(total_height)
        view.cursor.create_loop_lines(total_height)
        view.set_cursor(view._cursor_tick)
        view.set_secondary_cursor(view._secondary_cursor_tick)
        view.cursor.update_loop_markers()
