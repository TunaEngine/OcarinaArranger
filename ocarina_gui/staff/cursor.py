"""Cursor and loop rendering helpers for :mod:`ocarina_gui.staff.view`."""

from __future__ import annotations

from typing import Optional, Sequence, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .view import StaffView
    from ..themes import StaffPalette


class CursorController:
    """Operate on cursor and loop canvas items for :class:`StaffView`."""

    def __init__(self, view: "StaffView") -> None:
        self._view = view

    # ------------------------------------------------------------------
    # Canvas item lifecycle
    # ------------------------------------------------------------------
    def reset_canvas_items(self) -> None:
        view = self._view
        view._cursor_line = None
        view._secondary_cursor_line = None
        view._loop_start_line = None
        view._loop_end_line = None

    def create_cursor_lines(self, height: int) -> None:
        view = self._view
        palette = view._palette
        if view.canvas.find_withtag("time_cursor"):
            view.canvas.delete("time_cursor")
        view._cursor_line = view.canvas.create_line(
            view.LEFT_PAD,
            0,
            view.LEFT_PAD,
            height,
            fill=palette.cursor_primary,
            width=2,
            tags=("time_cursor_primary", "time_cursor", "overlay"),
        )
        view._secondary_cursor_line = view.canvas.create_line(
            view.LEFT_PAD,
            0,
            view.LEFT_PAD,
            height,
            fill=palette.cursor_secondary,
            width=1,
            dash=(4, 4),
            state="hidden",
            tags=("time_cursor_secondary", "time_cursor", "overlay"),
        )
        self.raise_cursor_lines()

    def create_loop_lines(self, height: int) -> None:
        view = self._view
        palette = view._palette
        view._loop_start_line = view.canvas.create_line(
            view.LEFT_PAD,
            0,
            view.LEFT_PAD,
            height,
            fill=palette.cursor_secondary,
            width=2,
            state="hidden",
            tags=("loop_start_line", "overlay"),
        )
        view._loop_end_line = view.canvas.create_line(
            view.LEFT_PAD,
            0,
            view.LEFT_PAD,
            height,
            fill=palette.cursor_primary,
            width=2,
            state="hidden",
            tags=("loop_end_line", "overlay"),
        )
        self.raise_cursor_lines()

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------
    def raise_loop_lines(self) -> None:
        view = self._view
        if view._loop_start_line is not None:
            view.canvas.tag_raise(view._loop_start_line)
        if view._loop_end_line is not None:
            view.canvas.tag_raise(view._loop_end_line)

    def raise_cursor_lines(self) -> None:
        view = self._view
        if view.canvas.find_withtag("overlay"):
            try:
                view.canvas.tag_raise("overlay")
            except Exception:  # pragma: no cover - Tkinter quirk
                pass
        self.raise_loop_lines()
        if view._secondary_cursor_line is not None:
            view.canvas.tag_raise(view._secondary_cursor_line)
        if view._cursor_line is not None:
            view.canvas.tag_raise(view._cursor_line)

    # ------------------------------------------------------------------
    # Palette updates
    # ------------------------------------------------------------------
    def apply_palette(self, palette: "StaffPalette") -> None:
        view = self._view
        if view._loop_start_line is not None:
            view.canvas.itemconfigure(view._loop_start_line, fill=palette.cursor_secondary)
        if view._loop_end_line is not None:
            view.canvas.itemconfigure(view._loop_end_line, fill=palette.cursor_primary)
        if view._cursor_line is not None:
            view.canvas.itemconfigure(view._cursor_line, fill=palette.cursor_primary)
        if view._secondary_cursor_line is not None:
            view.canvas.itemconfigure(view._secondary_cursor_line, fill=palette.cursor_secondary)

    # ------------------------------------------------------------------
    # Cursor positioning
    # ------------------------------------------------------------------
    def set_cursor(self, tick: int, *, allow_autoscroll: bool = True) -> None:
        view = self._view
        view._cursor_tick = max(0, int(tick))
        if view._cursor_line is None:
            return
        if view._layout_mode == "wrapped":
            x, y_top, y_bottom = self.wrap_tick_to_coords(view._cursor_tick)
            view.canvas.coords(view._cursor_line, x, y_top, x, y_bottom)
            view.canvas.itemconfigure(view._cursor_line, state="normal", fill=view._palette.cursor_primary)
            self.raise_cursor_lines()
            if view._secondary_cursor_tick is None and view._secondary_cursor_line is not None:
                view.canvas.itemconfigure(view._secondary_cursor_line, state="hidden")
            if allow_autoscroll:
                view._maybe_autoscroll(int(y_top))
            return
        height = view._content_height or int(view.canvas.winfo_height()) or 1
        x = view._tick_to_x(view._cursor_tick)
        view.canvas.coords(view._cursor_line, x, 0, x, height)
        view.canvas.itemconfigure(view._cursor_line, state="normal", fill=view._palette.cursor_primary)
        self.raise_cursor_lines()
        if view._secondary_cursor_tick is None and view._secondary_cursor_line is not None:
            view.canvas.itemconfigure(view._secondary_cursor_line, state="hidden")
        if allow_autoscroll:
            view._maybe_autoscroll(int(x))

    def set_secondary_cursor(self, tick: Optional[int]) -> None:
        view = self._view
        if tick is None:
            view._secondary_cursor_tick = None
        else:
            view._secondary_cursor_tick = max(0, int(tick))
        if view._secondary_cursor_line is None:
            return
        if view._secondary_cursor_tick is None:
            view.canvas.itemconfigure(view._secondary_cursor_line, state="hidden")
            return
        if view._layout_mode == "wrapped":
            x, y_top, y_bottom = self.wrap_tick_to_coords(view._secondary_cursor_tick)
            view.canvas.coords(view._secondary_cursor_line, x, y_top, x, y_bottom)
        else:
            height = view._content_height or int(view.canvas.winfo_height()) or 1
            x = view._tick_to_x(view._secondary_cursor_tick)
            view.canvas.coords(view._secondary_cursor_line, x, 0, x, height)
        view.canvas.itemconfigure(
            view._secondary_cursor_line,
            state="normal",
            fill=view._palette.cursor_secondary,
        )
        self.raise_cursor_lines()

    # ------------------------------------------------------------------
    # Loop markers
    # ------------------------------------------------------------------
    def set_loop_region(self, start_tick: int, end_tick: int, visible: bool) -> None:
        view = self._view
        start = min(start_tick, end_tick)
        end = max(start_tick, end_tick)
        if view._total_ticks:
            start = max(0, min(view._total_ticks, start))
            end = max(0, min(view._total_ticks, end))
        view._loop_start_tick = max(0, start)
        view._loop_end_tick = max(view._loop_start_tick, end)
        view._loop_visible = bool(visible and view._loop_end_tick > view._loop_start_tick)
        view.loop_region = (view._loop_start_tick, view._loop_end_tick, view._loop_visible)
        self.update_loop_markers()

    def update_loop_markers(self) -> None:
        view = self._view
        if view._loop_start_line is None or view._loop_end_line is None:
            return
        if not view._loop_visible or view._total_ticks <= 0:
            view.canvas.itemconfigure(view._loop_start_line, state="hidden")
            view.canvas.itemconfigure(view._loop_end_line, state="hidden")
            return
        if view._layout_mode == "wrapped":
            start_x, start_y_top, start_y_bottom = self.wrap_tick_to_coords(view._loop_start_tick)
            end_x, end_y_top, end_y_bottom = self.wrap_tick_to_coords(view._loop_end_tick)
            layout = view._wrap_layout or {}
            content_width = float(layout.get("content_width", view.LEFT_PAD + view.RIGHT_PAD + 400))
            x_min = float(view.LEFT_PAD)
            x_max = max(x_min, content_width - view.RIGHT_PAD)
            start_x = max(x_min, min(start_x, x_max))
            end_x = max(x_min, min(end_x, x_max))
            view.canvas.coords(view._loop_start_line, start_x, start_y_top, start_x, start_y_bottom)
            view.canvas.coords(view._loop_end_line, end_x, end_y_top, end_x, end_y_bottom)
        else:
            height = view._content_height or int(view.canvas.winfo_height()) or 1
            start_x = view._tick_to_x(view._loop_start_tick)
            end_x = view._tick_to_x(view._loop_end_tick)
            view.canvas.coords(view._loop_start_line, start_x, 0, start_x, height)
            view.canvas.coords(view._loop_end_line, end_x, 0, end_x, height)
        view.canvas.itemconfigure(view._loop_start_line, state="normal")
        view.canvas.itemconfigure(view._loop_end_line, state="normal")
        self.raise_cursor_lines()

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------
    def wrap_tick_to_coords(self, tick: int) -> Tuple[float, float, float]:
        view = self._view
        layout = view._wrap_layout or {}
        ticks_per_line = int(layout.get("ticks_per_line", 0) or 0)
        lines: Sequence[dict[str, float]] = layout.get("lines", [])  # type: ignore[arg-type]
        if not lines:
            height = float(view._content_height or int(view.canvas.winfo_height()) or 1)
            return float(view.LEFT_PAD), 0.0, height
        clamped = max(0, int(tick))
        if view._total_ticks:
            clamped = min(view._total_ticks, clamped)
        ticks_span = max(1, ticks_per_line)
        line_index = min(len(lines) - 1, clamped // ticks_span)
        info = lines[line_index]
        local_tick = clamped - line_index * ticks_span
        x = view.LEFT_PAD + int(round(local_tick * view.px_per_tick))
        y_top = float(info.get("y_top", 0.0))
        y_bottom = float(info.get("y_bottom", y_top + 1.0))
        return float(x), y_top, y_bottom

    def wrap_point_to_tick(self, x: int, y: int) -> Optional[int]:
        view = self._view
        layout = view._wrap_layout or {}
        lines: Sequence[dict[str, float]] = layout.get("lines", [])  # type: ignore[arg-type]
        if not lines:
            return None
        ticks_per_line = int(layout.get("ticks_per_line", 0) or 0)
        if ticks_per_line <= 0:
            return None
        line_height = float(layout.get("line_height", 0) or 0.0)
        system_spacing = float(layout.get("system_spacing", 0) or 0.0)
        segment = line_height + system_spacing if line_height > 0 else 1.0
        index = int(y // segment) if segment > 0 else 0
        index = max(0, min(len(lines) - 1, index))
        info = lines[index]
        line_top = float(info.get("y_top", index * segment))
        while index > 0 and y < line_top:
            index -= 1
            info = lines[index]
            line_top = float(info.get("y_top", line_top))
        local_tick = int(round((x - view.LEFT_PAD) / max(view.px_per_tick, 1e-6)))
        local_tick = max(0, local_tick)
        line_start = int(round(info.get("start", index * ticks_per_line)))
        line_end = int(round(info.get("end", line_start + ticks_per_line)))
        tick = line_start + local_tick
        if line_end >= line_start:
            tick = min(tick, line_end)
        if view._total_ticks:
            tick = min(view._total_ticks, tick)
        return max(0, tick)

