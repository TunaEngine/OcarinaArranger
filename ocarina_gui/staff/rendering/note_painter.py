"""Utilities for drawing note-related elements on the staff canvas."""

from __future__ import annotations

from typing import Tuple, TYPE_CHECKING

from ...note_values import NoteGlyphDescription
from .geometry import staff_pos, staff_y, tie_control_offsets

if TYPE_CHECKING:  # pragma: no cover - only imported for typing
    from ..view import StaffView


class NotePainter:
    """Helper responsible for rendering individual note components."""

    def __init__(self, view: "StaffView") -> None:
        self._view = view

    def staff_pos(self, midi: int) -> int:
        """Return the staff position for the given MIDI value."""

        return staff_pos(midi)

    def y_for_pos(self, y_top: int, pos: int, staff_spacing: int) -> float:
        """Return the vertical coordinate for the given staff position."""

        return staff_y(y_top, pos, float(staff_spacing))

    def draw_ledger_lines(
        self,
        y_top: int,
        pos: int,
        x_center: float,
        note_width: float,
        tags: Tuple[str, ...],
        *,
        state: str = "hidden",
    ) -> None:
        """Draw ledger lines for a note positioned outside the staff."""

        extra = max(4.0, note_width * 0.25)
        x_left = max(0.0, x_center - note_width / 2 - extra)
        x_right = x_center + note_width / 2 + extra
        if pos < 0:
            for ledger_pos in range(pos, 0, 2):
                self._ledger_line(y_top, ledger_pos, x_left, x_right, tags, state=state)
        elif pos > 8:
            for ledger_pos in range(10, pos + 1, 2):
                self._ledger_line(y_top, ledger_pos, x_left, x_right, tags, state=state)

    def draw_note_stem_and_flags(
        self,
        x0: float,
        y_center: float,
        note_width: float,
        glyph: NoteGlyphDescription,
        pos: int,
        tags: Tuple[str, ...],
        *,
        state: str = "hidden",
    ) -> None:
        """Draw stems and flags for notes that require them."""

        if not glyph.requires_stem():
            return

        view = self._view
        stem_length = view.staff_spacing * 3.5
        stem_up = pos < 6
        stem_x = x0 + note_width if stem_up else x0
        y_end = y_center - stem_length if stem_up else y_center + stem_length
        view.canvas.create_line(
            stem_x,
            y_center,
            stem_x,
            y_end,
            fill=view._palette.note_outline,
            width=1.3,
            tags=tags,
            state=state,
        )

        flag_map = {
            "eighth": 1,
            "sixteenth": 2,
            "thirty-second": 3,
            "sixty-fourth": 4,
        }
        flag_count = flag_map.get(glyph.base, 0)
        if flag_count == 0:
            return

        flag_length = note_width * 1.2
        flag_height = view.staff_spacing * 0.8
        for index in range(flag_count):
            if stem_up:
                start_y = y_end + index * (flag_height * 0.65)
                view.canvas.create_line(
                    stem_x,
                    start_y,
                    stem_x + flag_length,
                    start_y + flag_height * 0.35,
                    stem_x + flag_length * 0.85,
                    start_y + flag_height,
                    smooth=True,
                    fill=view._palette.note_outline,
                    width=1.1,
                    tags=tags,
                    state=state,
                )
            else:
                start_y = y_end - index * (flag_height * 0.65)
                view.canvas.create_line(
                    stem_x,
                    start_y,
                    stem_x - flag_length,
                    start_y - flag_height * 0.35,
                    stem_x - flag_length * 0.85,
                    start_y - flag_height,
                    smooth=True,
                    fill=view._palette.note_outline,
                    width=1.1,
                    tags=tags,
                    state=state,
                )

    def draw_dots(
        self,
        x0: float,
        y_center: float,
        note_width: float,
        glyph: NoteGlyphDescription,
        tags: Tuple[str, ...],
        *,
        state: str = "hidden",
    ) -> None:
        """Draw augmentation dots for dotted notes."""

        if glyph.dots <= 0:
            return

        view = self._view
        radius = note_width * 0.18
        gap = note_width * 0.45
        x = x0 + note_width + gap
        for _ in range(glyph.dots):
            view.canvas.create_oval(
                x - radius,
                y_center - radius,
                x + radius,
                y_center + radius,
                outline=view._palette.note_outline,
                fill=view._palette.note_outline,
                tags=tags,
                state=state,
            )
            x += gap

    def draw_tie(
        self,
        y_top: int,
        pos: int,
        start_x: float,
        end_x: float,
        tags: Tuple[str, ...],
        *,
        state: str = "hidden",
    ) -> None:
        """Draw a curved tie between two note heads."""

        if end_x - start_x < 1.0:
            return

        view = self._view
        y_center = self.y_for_pos(y_top, pos, view.staff_spacing)
        base_offset, curve_offset = tie_control_offsets(view.staff_spacing, pos)
        base_y = y_center + base_offset
        control_y = y_center + curve_offset
        width = max(1.1, view.staff_spacing * 0.14)
        span = end_x - start_x
        control_dx = span * 0.35
        points = (
            start_x,
            base_y,
            start_x + control_dx,
            control_y,
            end_x - control_dx,
            control_y,
            end_x,
            base_y,
        )
        view.canvas.create_line(
            *points,
            smooth=True,
            width=width,
            fill=view._palette.note_outline,
            tags=tags,
            state=state,
        )

    def _ledger_line(
        self,
        y_top: int,
        pos: int,
        x_left: float,
        x_right: float,
        tags: Tuple[str, ...],
        *,
        state: str = "hidden",
    ) -> None:
        """Draw a single ledger line at the supplied staff position."""

        view = self._view
        y = self.y_for_pos(y_top, pos, view.staff_spacing)
        view.canvas.create_line(
            x_left,
            y,
            x_right,
            y,
            fill=view._palette.staff_line,
            width=1,
            tags=tags,
            state=state,
        )
