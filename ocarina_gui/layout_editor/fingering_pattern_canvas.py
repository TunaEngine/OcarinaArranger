"""Canvas widget that toggles fingering patterns for a note."""

from __future__ import annotations

from typing import Callable, List, Sequence, Tuple

import tkinter as tk

from ..color_utils import hex_to_rgb, mix_colors, rgb_to_hex
from viewmodels.instrument_layout_editor_viewmodel import InstrumentLayoutState


class FingeringPatternCanvas(tk.Canvas):
    """Interactive canvas that toggles fingering patterns for a note."""

    def __init__(self, master: tk.Misc, *, on_toggle: Callable[[int, int], bool]) -> None:
        super().__init__(master, background="#f7f7f7", highlightthickness=0)
        self._on_toggle = on_toggle
        self._margin = 24
        self._state: InstrumentLayoutState | None = None
        self._pattern: List[int] = []
        self._hole_items: List[int] = []
        self._half_fill_color = "#b0b0b0"
        self._default_size = (280, 200)
        self.configure(width=self._default_size[0], height=self._default_size[1])
        self.bind("<ButtonPress-1>", self._on_click)

    def render(self, state: InstrumentLayoutState, pattern: Sequence[int]) -> None:
        self._state = state
        self._pattern = [max(0, min(2, int(value))) for value in pattern]
        width = state.canvas_width + 2 * self._margin
        height = state.canvas_height + 2 * self._margin
        background = state.style.background_color or "#ffffff"
        self.configure(width=width, height=height, background=background)
        self.delete("all")
        self._hole_items = []
        self._half_fill_color = self._compute_half_fill_color(
            background,
            state.style.covered_fill_color or "#000000",
        )

        if state.outline_points:
            outline_coords: List[float] = []
            for point in state.outline_points:
                outline_coords.extend([point.x + self._margin, point.y + self._margin])
            if state.outline_closed and len(outline_coords) >= 4:
                outline_coords.extend(outline_coords[:2])
            outline_color = state.style.outline_color or "#4f4f4f"
            self.create_line(
                *outline_coords,
                fill=outline_color,
                width=max(0.5, float(state.style.outline_width)),
                smooth=state.style.outline_smooth,
            )

        if not state.holes:
            self.create_text(
                width / 2,
                height / 2,
                text="Add holes to edit fingerings",
                fill="#666666",
                font=("TkDefaultFont", 9),
                width=max(100, width - 40),
            )
            return

        for index, hole in enumerate(state.holes):
            x = hole.x + self._margin
            y = hole.y + self._margin
            radius = hole.radius
            value = self._pattern[index] if index < len(self._pattern) else 0
            fill, stipple = self._fill_for_value(
                value,
                background,
                state.style.covered_fill_color or "#000000",
            )
            item = self.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                outline=state.style.hole_outline_color,
                width=1,
                fill=fill,
                stipple=stipple,
            )
            self._hole_items.append(item)

    def show_message(self, message: str) -> None:
        self._state = None
        self._pattern = []
        self._hole_items = []
        self._half_fill_color = "#b0b0b0"
        self.configure(
            width=self._default_size[0],
            height=self._default_size[1],
            background="#f7f7f7",
        )
        self.delete("all")
        if message:
            self.create_text(
                self._default_size[0] / 2,
                self._default_size[1] / 2,
                text=message,
                fill="#666666",
                font=("TkDefaultFont", 9),
                width=self._default_size[0] - 24,
            )

    def set_hole_state(self, index: int, value: int) -> None:
        if not (0 <= index < len(self._hole_items)):
            return
        state = self._state
        if state is None:
            return
        background = state.style.background_color or "#ffffff"
        covered = state.style.covered_fill_color or "#000000"
        fill, stipple = self._fill_for_value(value, background, covered)
        self.itemconfigure(self._hole_items[index], fill=fill, stipple=stipple)
        if index >= len(self._pattern):
            self._pattern.extend([0] * (index + 1 - len(self._pattern)))
        clamped = max(0, min(2, int(value)))
        self._pattern[index] = clamped

    # ------------------------------------------------------------------
    def _on_click(self, event: tk.Event) -> None:
        state = self._state
        if state is None or not state.holes:
            return

        x = event.x - self._margin
        y = event.y - self._margin
        for index, hole in enumerate(state.holes):
            dx = x - hole.x
            dy = y - hole.y
            if dx * dx + dy * dy <= hole.radius * hole.radius:
                current = self._pattern[index] if index < len(self._pattern) else 0
                new_value = (int(current) + 1) % 3
                if self._on_toggle(index, new_value):
                    self.set_hole_state(index, new_value)
                return

    # ------------------------------------------------------------------
    def _fill_for_value(self, value: int, background: str, covered: str) -> Tuple[str, str]:
        clamped = max(0, min(2, int(value)))
        if clamped >= 2:
            return covered, ""
        if clamped == 1:
            return self._half_fill_color, "gray50"
        return background, ""

    def _compute_half_fill_color(self, background: str, covered: str) -> str:
        base_background = background or "#ffffff"
        base_covered = covered or "#000000"
        try:
            bg_rgb = hex_to_rgb(base_background)
            covered_rgb = hex_to_rgb(base_covered)
        except Exception:
            return base_covered
        mixed = mix_colors(covered_rgb, bg_rgb, 0.5)
        return rgb_to_hex(mixed)


__all__ = ["FingeringPatternCanvas"]
