"""Canvas widget for editing instrument layouts."""

from __future__ import annotations

from typing import Callable, Dict, Optional, Tuple

import tkinter as tk

from viewmodels.instrument_layout_editor_viewmodel import (
    InstrumentLayoutState,
    SelectionKind,
)

from .canvas_tooltip import CanvasTooltip
from .labels import friendly_label


class InstrumentLayoutCanvas(tk.Canvas):
    """Interactive canvas that visualizes and edits instrument layouts."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        on_select: Callable[[SelectionKind, Optional[int]], None],
        on_move: Callable[[SelectionKind, int, float, float], None],
    ) -> None:
        super().__init__(master, background="#f7f7f7", highlightthickness=0)
        self._on_select = on_select
        self._on_move = on_move
        self._margin = 24
        self._state: Optional[InstrumentLayoutState] = None
        self._item_lookup: Dict[int, Tuple[SelectionKind, int]] = {}
        self._tooltip_texts: Dict[int, str] = {}
        self._selection_indicator: Optional[int] = None
        self._drag: Optional[Tuple[SelectionKind, int, float, float]] = None
        self._tooltip = CanvasTooltip(self)

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Destroy>", lambda _e: self._tooltip.close(), add="+")

    # ------------------------------------------------------------------
    def render(self, state: InstrumentLayoutState) -> None:
        self._state = state
        width = state.canvas_width + 2 * self._margin
        height = state.canvas_height + 2 * self._margin
        self.configure(
            width=width,
            height=height,
            background=state.style.background_color,
        )
        self.delete("all")
        self._item_lookup.clear()
        self._tooltip_texts.clear()
        self._selection_indicator = None

        self._draw_background_grid(width, height)

        if state.outline_points:
            outline_coords = []
            for point in state.outline_points:
                outline_coords.extend([point.x + self._margin, point.y + self._margin])
            if state.outline_closed and len(outline_coords) >= 4:
                outline_coords.extend(outline_coords[:2])
            if outline_coords:
                outline_color = state.style.outline_color or "#4f4f4f"
                self.create_line(
                    *outline_coords,
                    fill=outline_color,
                    width=max(0.5, float(state.style.outline_width)),
                    smooth=state.style.outline_smooth,
                )
            for index, point in enumerate(state.outline_points):
                x = point.x + self._margin
                y = point.y + self._margin
                handle = self.create_rectangle(
                    x - 4,
                    y - 4,
                    x + 4,
                    y + 4,
                    outline="#2c7be5",
                    fill="#ffffff",
                )
                self._item_lookup[handle] = (SelectionKind.OUTLINE, index)
                self._tooltip_texts[handle] = f"Outline point #{index + 1}"

        for index, hole in enumerate(state.holes):
            x = hole.x + self._margin
            y = hole.y + self._margin
            radius = hole.radius
            item = self.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                outline=state.style.hole_outline_color,
                width=1,
                fill=state.style.background_color,
            )
            self._item_lookup[item] = (SelectionKind.HOLE, index)
            self._tooltip_texts[item] = friendly_label(hole.identifier, f"Hole {index + 1}")

        for index, windway in enumerate(state.windways):
            center_x = windway.x + self._margin
            center_y = windway.y + self._margin
            half_width = windway.width / 2.0
            half_height = windway.height / 2.0
            item = self.create_rectangle(
                center_x - half_width,
                center_y - half_height,
                center_x + half_width,
                center_y + half_height,
                outline=state.style.hole_outline_color,
                width=1,
                fill=state.style.background_color,
            )
            self._item_lookup[item] = (SelectionKind.WINDWAY, index)
            self._tooltip_texts[item] = friendly_label(
                windway.identifier, f"Windway {index + 1}"
            )

        self._draw_selection_indicator()
        self._tooltip.hide()

    # ------------------------------------------------------------------
    def _draw_background_grid(self, width: int, height: int) -> None:
        step = 20
        color = "#e1e1e1"
        for x in range(self._margin, width - self._margin + 1, step):
            self.create_line(x, self._margin, x, height - self._margin, fill=color)
        for y in range(self._margin, height - self._margin + 1, step):
            self.create_line(self._margin, y, width - self._margin, y, fill=color)

    def _draw_selection_indicator(self) -> None:
        state = self._state
        if state is None:
            return
        if self._selection_indicator is not None:
            self.delete(self._selection_indicator)
            self._selection_indicator = None
        selection = state.selection
        if selection is None:
            return
        margin = self._margin
        if selection.kind == SelectionKind.HOLE:
            hole = state.holes[selection.index]
            radius = hole.radius + 4
            x = hole.x + margin
            y = hole.y + margin
            self._selection_indicator = self.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                outline="#ff8800",
                width=2,
                dash=(4, 2),
            )
        elif selection.kind == SelectionKind.WINDWAY:
            windway = state.windways[selection.index]
            x = windway.x + margin
            y = windway.y + margin
            half_width = windway.width / 2.0 + 4
            half_height = windway.height / 2.0 + 4
            self._selection_indicator = self.create_rectangle(
                x - half_width,
                y - half_height,
                x + half_width,
                y + half_height,
                outline="#ff8800",
                width=2,
                dash=(4, 2),
            )
        elif selection.kind == SelectionKind.OUTLINE:
            point = state.outline_points[selection.index]
            x = point.x + margin
            y = point.y + margin
            self._selection_indicator = self.create_rectangle(
                x - 6,
                y - 6,
                x + 6,
                y + 6,
                outline="#ff8800",
                width=2,
            )

    # ------------------------------------------------------------------
    def _on_press(self, event: tk.Event) -> None:
        if not self._item_lookup:
            return
        closest = self.find_closest(event.x, event.y)
        if not closest:
            self._on_select(SelectionKind.NONE, None)
            return
        item = closest[0]
        info = self._item_lookup.get(item)
        if info is None:
            self._on_select(SelectionKind.NONE, None)
            return
        kind, index = info
        self._on_select(kind, index)

        state = self._state
        if state is None:
            return
        margin = self._margin
        if kind == SelectionKind.HOLE:
            element = state.holes[index]
            center_x = element.x + margin
            center_y = element.y + margin
        elif kind == SelectionKind.WINDWAY:
            element = state.windways[index]
            center_x = element.x + margin
            center_y = element.y + margin
        elif kind == SelectionKind.OUTLINE:
            element = state.outline_points[index]
            center_x = element.x + margin
            center_y = element.y + margin
        else:
            return
        self._drag = (kind, index, event.x - center_x, event.y - center_y)

    def _on_drag(self, event: tk.Event) -> None:
        if not self._drag:
            return
        kind, index, offset_x, offset_y = self._drag
        margin = self._margin
        center_x = event.x - offset_x
        center_y = event.y - offset_y
        self._on_move(kind, index, center_x - margin, center_y - margin)

    def _on_release(self, _event: tk.Event) -> None:
        self._drag = None

    def _on_motion(self, event: tk.Event) -> None:
        if not self._tooltip_texts:
            self._tooltip.hide()
            return
        items = self.find_withtag("current")
        if not items:
            self._tooltip.hide()
            return
        item = items[0]
        text = self._tooltip_texts.get(item)
        if not text:
            self._tooltip.hide()
            return
        root_x = self.winfo_rootx() + event.x + 12
        root_y = self.winfo_rooty() + event.y + 12
        self._tooltip.show(text, root_x, root_y)

    def _on_leave(self, _event: tk.Event) -> None:
        self._tooltip.hide()


__all__ = ["InstrumentLayoutCanvas"]
