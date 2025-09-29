"""Canvas and style helpers for the layout editor view-model."""

from __future__ import annotations

from typing import Any

from .models import InstrumentLayoutState


class LayoutAppearanceMixin:
    """Mutations related to the instrument canvas and styling."""

    state: InstrumentLayoutState

    # ------------------------------------------------------------------
    def set_canvas_size(self, width: int, height: int) -> None:
        width = max(1, int(width))
        height = max(1, int(height))
        state = self.state
        if state.canvas_width == width and state.canvas_height == height:
            return
        state.canvas_width = width
        state.canvas_height = height
        state.dirty = True

    def set_title(self, title: str) -> None:
        state = self.state
        title = str(title)
        if state.title == title:
            return
        state.title = title
        state.dirty = True

    def update_style(self, **changes: Any) -> None:
        state = self.state
        style = state.style
        updated = False
        for key, value in changes.items():
            if not hasattr(style, key):
                continue
            current = getattr(style, key)
            if current == value:
                continue
            setattr(style, key, value)
            updated = True
        if updated:
            state.dirty = True
