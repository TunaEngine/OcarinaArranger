"""Selection and transform helpers for the layout editor view-model."""

from __future__ import annotations

from typing import Optional

from .models import InstrumentLayoutState, Selection, SelectionKind


class SelectionMixin:
    """Handle selection changes and element manipulation."""

    state: InstrumentLayoutState

    # ------------------------------------------------------------------
    def select_element(self, kind: SelectionKind, index: Optional[int]) -> None:
        state = self.state
        if index is None:
            state.selection = None
            return

        if kind == SelectionKind.HOLE:
            if not (0 <= index < len(state.holes)):
                return
        elif kind == SelectionKind.WINDWAY:
            if not (0 <= index < len(state.windways)):
                return
        elif kind == SelectionKind.OUTLINE:
            if not (0 <= index < len(state.outline_points)):
                return
        else:
            state.selection = None
            return

        state.selection = Selection(kind=kind, index=index)

    # ------------------------------------------------------------------
    @staticmethod
    def _update_position(element, x: float, y: float) -> bool:
        x = float(max(0.0, x))
        y = float(max(0.0, y))
        if element.x == x and element.y == y:
            return False
        element.x = x
        element.y = y
        return True

    def set_selected_position(self, x: float, y: float) -> None:
        state = self.state
        selection = state.selection
        if selection is None:
            return
        moved = False
        if selection.kind == SelectionKind.HOLE:
            moved = self._update_position(state.holes[selection.index], x, y)
        elif selection.kind == SelectionKind.WINDWAY:
            moved = self._update_position(state.windways[selection.index], x, y)
        elif selection.kind == SelectionKind.OUTLINE:
            moved = self._update_position(state.outline_points[selection.index], x, y)
        if moved:
            state.dirty = True

    # ------------------------------------------------------------------
    def adjust_selected_radius(self, delta: float) -> None:
        state = self.state
        selection = state.selection
        if selection is None:
            return

        target = None
        if selection.kind == SelectionKind.HOLE:
            target = state.holes[selection.index]
        elif selection.kind == SelectionKind.WINDWAY:
            return

        if target is None:
            return

        new_radius = max(0.5, float(target.radius) + float(delta))
        if new_radius == target.radius:
            return
        target.radius = new_radius
        state.dirty = True

    # ------------------------------------------------------------------
    def set_selected_size(self, width: float, height: float) -> None:
        state = self.state
        selection = state.selection
        if selection is None or selection.kind != SelectionKind.WINDWAY:
            return

        windway = state.windways[selection.index]
        new_width = max(1.0, float(width))
        new_height = max(1.0, float(height))
        if windway.width == new_width and windway.height == new_height:
            return
        windway.width = new_width
        windway.height = new_height
        state.dirty = True
