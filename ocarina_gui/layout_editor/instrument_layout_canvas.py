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
from ocarina_gui.fingering.outline_renderer import OutlineImage, render_outline_photoimage
from ocarina_gui.themes import (
    LayoutEditorPalette,
    ThemeSpec,
    get_current_theme,
    register_theme_listener,
)


class InstrumentLayoutCanvas(tk.Canvas):
    """Interactive canvas that visualizes and edits instrument layouts."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        on_select: Callable[[SelectionKind, Optional[int]], None],
        on_move: Callable[[SelectionKind, int, float, float], None],
    ) -> None:
        palette = get_current_theme().palette.layout_editor
        super().__init__(
            master,
            background=palette.workspace_background,
            highlightthickness=0,
            borderwidth=0,
        )
        self._on_select = on_select
        self._on_move = on_move
        self._margin = 24
        self._state: Optional[InstrumentLayoutState] = None
        self._item_lookup: Dict[int, Tuple[SelectionKind, int]] = {}
        self._tooltip_texts: Dict[int, str] = {}
        self._selection_indicator: Optional[int] = None
        self._drag: Optional[Tuple[SelectionKind, int, float, float]] = None
        self._tooltip = CanvasTooltip(self)
        self._outline_image: OutlineImage | None = None
        self._outline_cache_key: tuple | None = None
        self._theme_unsubscribe: Callable[[], None] | None = None
        try:
            self._theme_unsubscribe = register_theme_listener(self._on_theme_changed)
        except Exception:
            self._theme_unsubscribe = None
        self._palette: LayoutEditorPalette = palette
        self._workspace_background = palette.workspace_background
        self._instrument_surface = palette.instrument_surface
        self._instrument_outline = palette.instrument_outline
        self._hole_fill = palette.hole_fill
        self._hole_outline = palette.hole_outline
        self._windway_fill = palette.windway_fill
        self._windway_outline = palette.windway_outline
        self._grid_color = palette.grid_line
        self._handle_fill = palette.handle_fill
        self._handle_outline = palette.handle_outline
        self._selection_outline = palette.selection_outline
        self._last_high_quality = True

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Destroy>", lambda _e: self._tooltip.close(), add="+")

    # ------------------------------------------------------------------
    def render(self, state: InstrumentLayoutState, *, high_quality: bool = True) -> None:
        self._state = state
        width = state.canvas_width + 2 * self._margin
        height = state.canvas_height + 2 * self._margin
        instrument_background = self._instrument_surface
        self.configure(
            width=width,
            height=height,
            background=self._workspace_background,
        )
        self.delete("all")
        self._item_lookup.clear()
        self._tooltip_texts.clear()
        self._selection_indicator = None
        self.create_rectangle(
            self._margin,
            self._margin,
            width - self._margin,
            height - self._margin,
            fill=instrument_background,
            outline="",
        )

        self._draw_background_grid(width, height)

        outline_color = self._instrument_outline
        spline_steps = max(1, int(getattr(state.style, "outline_spline_steps", 48)))

        if state.outline_points:
            pixel_points = [
                (point.x + self._margin, point.y + self._margin)
                for point in state.outline_points
            ]
            if state.outline_closed and pixel_points and pixel_points[0] != pixel_points[-1]:
                pixel_points = pixel_points + [pixel_points[0]]
            if high_quality:
                stroke_width = max(0.5, float(state.style.outline_width))
                cache_key = (
                    tuple((round(pt[0], 4), round(pt[1], 4)) for pt in pixel_points),
                    int(width),
                    int(height),
                    round(stroke_width, 4),
                    outline_color,
                    instrument_background,
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
                        background_color=instrument_background,
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
                outline_image = None
                if len(pixel_points) >= 2:
                    coords = []
                    for point in pixel_points:
                        coords.extend([point[0], point[1]])
                    self.create_line(
                        *coords,
                        fill=outline_color,
                        width=max(0.5, float(state.style.outline_width)),
                        smooth=state.style.outline_smooth,
                        splinesteps=spline_steps,
                    )
            for index, point in enumerate(state.outline_points):
                x = point.x + self._margin
                y = point.y + self._margin
                handle = self.create_rectangle(
                    x - 4,
                    y - 4,
                    x + 4,
                    y + 4,
                    outline=self._handle_outline,
                    fill=self._handle_fill,
                )
                self._item_lookup[handle] = (SelectionKind.OUTLINE, index)
                self._tooltip_texts[handle] = f"Outline point #{index + 1}"

        else:
            self._outline_image = None
            self._outline_cache_key = None

        for index, hole in enumerate(state.holes):
            x = hole.x + self._margin
            y = hole.y + self._margin
            radius = hole.radius
            item = self.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                outline=self._hole_outline,
                width=1,
                fill=self._hole_fill,
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
                outline=self._windway_outline,
                width=1,
                fill=self._windway_fill,
            )
            self._item_lookup[item] = (SelectionKind.WINDWAY, index)
            self._tooltip_texts[item] = friendly_label(
                windway.identifier, f"Windway {index + 1}"
            )

        self._draw_selection_indicator()
        self._tooltip.hide()
        self._last_high_quality = high_quality

    # ------------------------------------------------------------------
    def _draw_background_grid(self, width: int, height: int) -> None:
        step = 20
        color = self._grid_color
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
                outline=self._selection_outline,
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
                outline=self._selection_outline,
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
                outline=self._selection_outline,
                width=2,
            )

        if self._selection_indicator is not None:
            self.itemconfigure(self._selection_indicator, fill="")

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
        if self._drag is not None and self._state is not None:
            state = self._state
            self._drag = None
            self.render(state)
        else:
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

    # ------------------------------------------------------------------
    def _apply_palette(self, palette: LayoutEditorPalette) -> None:
        self._palette = palette
        self._workspace_background = palette.workspace_background
        self._instrument_surface = palette.instrument_surface
        self._instrument_outline = palette.instrument_outline
        self._hole_fill = palette.hole_fill
        self._hole_outline = palette.hole_outline
        self._windway_fill = palette.windway_fill
        self._windway_outline = palette.windway_outline
        self._grid_color = palette.grid_line
        self._handle_fill = palette.handle_fill
        self._handle_outline = palette.handle_outline
        self._selection_outline = palette.selection_outline
        if self._state is None:
            self.configure(background=self._workspace_background)

    def _on_theme_changed(self, theme: ThemeSpec) -> None:
        self._apply_palette(theme.palette.layout_editor)
        state = self._state
        if state is not None:
            try:
                self.render(state, high_quality=self._last_high_quality)
            except Exception:
                pass

    def destroy(self) -> None:  # type: ignore[override]
        if self._theme_unsubscribe is not None:
            try:
                self._theme_unsubscribe()
            except Exception:
                pass
            self._theme_unsubscribe = None
        self._tooltip.close()
        super().destroy()


__all__ = ["InstrumentLayoutCanvas"]
