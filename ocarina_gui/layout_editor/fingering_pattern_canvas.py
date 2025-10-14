"""Canvas widget that visualises and edits fingering patterns."""

from __future__ import annotations

from typing import Callable, List, Sequence, Tuple

import tkinter as tk

from ..color_utils import hex_to_rgb, mix_colors, rgb_to_hex
from viewmodels.instrument_layout_editor_viewmodel import InstrumentLayoutState
from ocarina_gui.fingering.outline_renderer import OutlineImage, render_outline_photoimage
from ocarina_gui.themes import (
    LayoutEditorPalette,
    ThemeSpec,
    get_current_theme,
    register_theme_listener,
)


class FingeringPatternCanvas(tk.Canvas):
    """Interactive canvas that toggles fingering patterns for a note."""

    def __init__(self, master: tk.Misc, *, on_toggle: Callable[[int, int], bool]) -> None:
        theme = get_current_theme()
        palette = theme.palette.layout_editor
        super().__init__(
            master,
            background=palette.workspace_background,
            highlightthickness=0,
        )
        self._on_toggle = on_toggle
        self._margin = 24
        self._state: InstrumentLayoutState | None = None
        self._pattern: List[int] = []
        self._hole_items: List[int] = []
        self._palette: LayoutEditorPalette = palette
        self._text_muted = theme.palette.text_muted
        self._workspace_background = palette.workspace_background
        self._instrument_surface = palette.instrument_surface
        self._instrument_outline = palette.instrument_outline
        self._hole_outline = palette.hole_outline
        self._hole_fill = palette.hole_fill
        self._covered_fill = palette.covered_fill
        self._half_fill_color = self._compute_half_fill_color(
            self._hole_fill, self._covered_fill
        )
        self._default_size = (280, 200)
        self.configure(width=self._default_size[0], height=self._default_size[1])
        self.bind("<ButtonPress-1>", self._on_click)
        self._outline_image: OutlineImage | None = None
        self._outline_cache_key: tuple | None = None
        self._theme_unsubscribe: Callable[[], None] | None = None
        try:
            self._theme_unsubscribe = register_theme_listener(self._on_theme_changed)
        except Exception:
            self._theme_unsubscribe = None

    def render(self, state: InstrumentLayoutState, pattern: Sequence[int]) -> None:
        self._state = state
        self._pattern = [max(0, min(2, int(value))) for value in pattern]
        width = state.canvas_width + 2 * self._margin
        height = state.canvas_height + 2 * self._margin
        background = self._instrument_surface
        covered = self._covered_fill
        self.configure(width=width, height=height, background=background)
        self.delete("all")
        self._hole_items = []
        self._half_fill_color = self._compute_half_fill_color(background, covered)

        if state.outline_points:
            pixel_points = [
                (point.x + self._margin, point.y + self._margin)
                for point in state.outline_points
            ]
            if state.outline_closed and pixel_points and pixel_points[0] != pixel_points[-1]:
                pixel_points = pixel_points + [pixel_points[0]]
            outline_color = self._instrument_outline
            spline_steps = max(1, int(getattr(state.style, "outline_spline_steps", 48)))
            stroke_width = max(0.5, float(state.style.outline_width))
            cache_key = (
                tuple((round(pt[0], 4), round(pt[1], 4)) for pt in pixel_points),
                int(width),
                int(height),
                round(stroke_width, 4),
                outline_color,
                background,
                bool(state.style.outline_smooth),
                bool(state.outline_closed),
                int(spline_steps),
            )
            if self._outline_image is None or self._outline_cache_key != cache_key:
                outline_image = render_outline_photoimage(
                    self,
                    pixel_points,
                    canvas_size=(width, height),
                    stroke_width=stroke_width,
                    stroke_color=outline_color,
                    background_color=background,
                    smooth=state.style.outline_smooth,
                    closed=state.outline_closed,
                    spline_steps=spline_steps,
                )
                if outline_image is not None:
                    self._outline_image = outline_image
                    self._outline_cache_key = cache_key
                else:
                    self._outline_image = None
                    self._outline_cache_key = None
            outline_image = self._outline_image
            if outline_image is not None:
                self.create_image(
                    0,
                    0,
                    image=outline_image.photo_image,
                    anchor="nw",
                )
        else:
            self._outline_image = None
            self._outline_cache_key = None

        if not state.holes:
            self.create_text(
                width / 2,
                height / 2,
                text="Add holes to edit fingerings",
                fill=self._text_muted,
                font=("TkDefaultFont", 9),
                width=max(100, width - 40),
            )
            return

        for index, hole in enumerate(state.holes):
            x = hole.x + self._margin
            y = hole.y + self._margin
            radius = hole.radius
            value = self._pattern[index] if index < len(self._pattern) else 0
            fill, stipple = self._fill_for_value(value, background, covered)
            item = self.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                outline=self._hole_outline,
                width=1,
                fill=fill,
                stipple=stipple,
            )
            self._hole_items.append(item)

    def show_message(self, message: str) -> None:
        self._state = None
        self._pattern = []
        self._hole_items = []
        self._half_fill_color = self._compute_half_fill_color(
            self._hole_fill, self._covered_fill
        )
        self.configure(
            width=self._default_size[0],
            height=self._default_size[1],
            background=self._workspace_background,
        )
        self.delete("all")
        if message:
            self.create_text(
                self._default_size[0] / 2,
                self._default_size[1] / 2,
                text=message,
                fill=self._text_muted,
                font=("TkDefaultFont", 9),
                width=self._default_size[0] - 24,
            )

    def set_hole_state(self, index: int, value: int) -> None:
        if not (0 <= index < len(self._hole_items)):
            return
        state = self._state
        if state is None:
            return
        background = self._instrument_surface
        covered = self._covered_fill
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

    # ------------------------------------------------------------------
    def _apply_palette(self, theme: ThemeSpec) -> None:
        palette = theme.palette.layout_editor
        self._palette = palette
        self._text_muted = theme.palette.text_muted
        self._workspace_background = palette.workspace_background
        self._instrument_surface = palette.instrument_surface
        self._instrument_outline = palette.instrument_outline
        self._hole_outline = palette.hole_outline
        self._hole_fill = palette.hole_fill
        self._covered_fill = palette.covered_fill
        self._half_fill_color = self._compute_half_fill_color(
            self._hole_fill, self._covered_fill
        )
        if self._state is None:
            self.configure(background=self._workspace_background)

    def _on_theme_changed(self, theme: ThemeSpec) -> None:
        self._apply_palette(theme)
        state = self._state
        if state is not None:
            try:
                self.render(state, self._pattern)
            except Exception:
                pass

    def destroy(self) -> None:  # type: ignore[override]
        if self._theme_unsubscribe is not None:
            try:
                self._theme_unsubscribe()
            except Exception:
                pass
            self._theme_unsubscribe = None
        super().destroy()


__all__ = ["FingeringPatternCanvas"]
