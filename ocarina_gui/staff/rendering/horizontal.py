"""Rendering logic for the horizontal staff layout."""

from __future__ import annotations

from bisect import bisect_left
from typing import List, Tuple, TYPE_CHECKING

from ...note_values import describe_note_glyph
from .note_painter import NotePainter
from .types import Event

if TYPE_CHECKING:  # pragma: no cover - only imported for typing
    from ..view import StaffView


class HorizontalRenderer:
    """Renderer that draws a single horizontal staff view."""

    def __init__(self, view: "StaffView", note_painter: NotePainter) -> None:
        self._view = view
        self._note_painter = note_painter

    def render(self, events: Tuple[Event, ...], beats: int, beat_type: int) -> None:
        view = self._view
        palette = view._palette
        total_ticks = view._total_ticks
        width = view.LEFT_PAD + int(total_ticks * view.px_per_tick) + view.RIGHT_PAD
        height = 5 * view.staff_spacing + 120
        view._content_height = height
        view._scroll_width = max(1, width)

        view.canvas.config(scrollregion=(0, 0, width, height))
        view.canvas.create_rectangle(
            0,
            0,
            width,
            height,
            outline=palette.outline,
            fill=palette.background,
        )

        y_top = 40
        view._last_y_top = y_top

        header = f"Treble staff | {beats}/{beat_type} | notes: {len(events) if events else 0}"
        view.canvas.create_text(
            view.LEFT_PAD + 4,
            16,
            anchor="w",
            fill=palette.header_text,
            text=header,
        )

        self.redraw_visible_region(force=True)

        view.cursor.create_cursor_lines(height)
        view.cursor.create_loop_lines(height)
        view.set_cursor(view._cursor_tick)
        view.set_secondary_cursor(view._secondary_cursor_tick)
        view.cursor.update_loop_markers()

    def redraw_visible_region(self, force: bool = False) -> None:
        view = self._view
        try:
            layout_mode = getattr(view, "_layout_mode", "horizontal")
        except Exception:  # pragma: no cover - defensive
            layout_mode = "horizontal"
        if layout_mode == "wrapped":
            return

        try:
            viewport_width = int(view.canvas.winfo_width())
        except Exception:  # pragma: no cover - defensive
            return
        if viewport_width <= 0:
            return

        try:
            left_fraction, _right_fraction = view.canvas.xview()
        except Exception:  # pragma: no cover - defensive
            left_fraction = 0.0
        scroll_width = max(1, view._scroll_width)
        left_edge = int(left_fraction * scroll_width)
        right_edge = left_edge + viewport_width
        margin = max(256, viewport_width // 2)
        draw_left = max(0, left_edge - margin)
        draw_right = min(scroll_width, right_edge + margin)
        if not force and view._drawn_range is not None:
            prev_left, prev_right = view._drawn_range
            if draw_left >= prev_left and draw_right <= prev_right:
                return
        view._drawn_range = (draw_left, draw_right)

        palette = view._palette
        old_tag = view._virtual_tags[view._active_virtual_tag_index]
        next_index = 1 - view._active_virtual_tag_index
        new_tag = view._virtual_tags[next_index]
        view.canvas.delete(new_tag)

        y_top = getattr(view, "_last_y_top", 40)
        line_left = max(draw_left, view.LEFT_PAD)
        line_right = min(draw_right, view._scroll_width - 20)
        if line_left < line_right:
            for index in range(5):
                y = y_top + index * view.staff_spacing
                view.canvas.create_line(
                    line_left,
                    y,
                    line_right,
                    y,
                    fill=palette.staff_line,
                    state="hidden",
                    tags=(new_tag, "virtualized", "staff_line"),
                )

        measure_spacing_px = max(1, int(round(view._ticks_per_measure * view.px_per_tick)))
        measure_limit = min(draw_right, view._scroll_width - 40)
        if measure_spacing_px > 0 and line_left < measure_limit:
            start = max(view.LEFT_PAD, draw_left)
            offset = max(0, (start - view.LEFT_PAD) // measure_spacing_px * measure_spacing_px)
            x = view.LEFT_PAD + offset
            if x < start:
                x += measure_spacing_px
            while x <= measure_limit:
                view.canvas.create_line(
                    x,
                    y_top - 12,
                    x,
                    y_top + 4 * view.staff_spacing + 12,
                    fill=palette.measure_line,
                    state="hidden",
                    tags=(new_tag, "virtualized", "measure_line"),
                )
                x += measure_spacing_px

        px_per_tick = max(view.px_per_tick, 1e-6)
        tick_left = max(0, int((draw_left - view.LEFT_PAD) / px_per_tick) - 4)
        tick_right = max(0, int((draw_right - view.LEFT_PAD) / px_per_tick) + 4)

        visible_events: List[Event]
        if not view._events:
            visible_events = []
        else:
            start_index = bisect_left(view._event_onsets, tick_left)
            while start_index > 0:
                prev_event = view._events[start_index - 1]
                if prev_event[0] + prev_event[1] < tick_left:
                    break
                start_index -= 1
            visible_events = []
            for idx in range(start_index, len(view._events)):
                onset, duration, midi, program = view._events[idx]
                if onset > tick_right:
                    break
                if onset + duration < tick_left:
                    continue
                visible_events.append((onset, duration, midi, program))

        width_note, height_note = 12, 9
        pulses_per_quarter = view._cached[1] if view._cached else 480
        for onset, duration, midi, _program in visible_events:
            x0 = view.LEFT_PAD + int(onset * view.px_per_tick)
            pos = self._note_painter.staff_pos(midi)
            y = self._note_painter.y_for_pos(y_top, pos, view.staff_spacing)
            x_center = x0 + width_note / 2
            ledger_tags = (new_tag, "virtualized", "ledger_line")
            self._note_painter.draw_ledger_lines(
                y_top,
                pos,
                x_center,
                width_note,
                ledger_tags,
            )
            if midi % 12 in (1, 3, 6, 8, 10):
                view.canvas.create_text(
                    x0 - 10,
                    y,
                    text="#",
                    fill=palette.accidental_text,
                    font=("TkDefaultFont", 10),
                    state="hidden",
                    tags=(new_tag, "virtualized", "accidental"),
                )

            glyph = describe_note_glyph(int(duration), pulses_per_quarter)
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
                state="hidden",
                tags=(new_tag, "virtualized", "staff_note"),
            )

            if glyph is not None:
                stem_tags = (new_tag, "virtualized", "note_stem")
                self._note_painter.draw_note_stem_and_flags(
                    x0,
                    y,
                    width_note,
                    glyph,
                    pos,
                    stem_tags,
                )
                dot_tags = (new_tag, "virtualized", "note_dot")
                self._note_painter.draw_dots(
                    x0,
                    y,
                    width_note,
                    glyph,
                    dot_tags,
                )

            octave = midi // 12 - 1
            octave_y = y - view.staff_spacing * 1.6 if pos >= 8 else y + view.staff_spacing * 1.6
            view.canvas.create_text(
                x_center,
                octave_y,
                text=str(octave),
                fill=palette.header_text,
                font=("TkDefaultFont", 9),
                state="hidden",
                tags=(new_tag, "virtualized", "octave_label"),
            )

        view.canvas.itemconfigure(new_tag, state="normal")
        if view.canvas.find_withtag("overlay"):
            try:
                view.canvas.tag_lower(new_tag, "overlay")
            except Exception:  # pragma: no cover - best effort
                pass
        view.cursor.raise_cursor_lines()
        if old_tag != new_tag:
            view.canvas.delete(old_tag)
            view._active_virtual_tag_index = next_index
