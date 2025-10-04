"""Tkinter canvas widget that renders configurable ocarina fingerings."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Optional

from ocarina_gui.color_utils import hex_to_rgb
from ocarina_gui.constants import midi_to_name, natural_of
from ocarina_gui.themes import ThemeSpec, get_current_theme, register_theme_listener
from ocarina_tools.pitch import parse_note_name

from .library import get_current_instrument, register_instrument_listener
from .specs import InstrumentSpec


__all__ = ["FingeringView"]


@dataclass(frozen=True)
class _FingeringCanvasColors:
    """Resolved colors for rendering fingering canvases."""

    background: str
    outline: str
    hole_outline: str
    covered_fill: str


class FingeringView(tk.Canvas):
    """Displays configurable ocarina fingerings for a given MIDI pitch."""

    def __init__(self, master: tk.Misc, *, scale: float = 1.0, **kwargs) -> None:
        self._scale = max(0.1, float(scale))
        instrument = get_current_instrument()
        self._theme: ThemeSpec | None = get_current_theme()
        initial_colors = self._resolve_canvas_colors(instrument)
        width, height = self._scaled_canvas_size(instrument)
        super().__init__(
            master,
            width=width,
            height=height,
            bg=initial_colors.background,
            highlightthickness=0,
            **kwargs,
        )
        self._instrument = instrument
        self._note_text_id: Optional[int] = None
        self._title_text_id: Optional[int] = None
        self._status_text_id: Optional[int] = None
        self._current_midi: Optional[int] = None
        self._current_note_name: Optional[str] = None
        self._status_message: str = ""
        self._hole_tags: list[str] = []
        self._windway_tags: list[str] = []
        self._hole_click_handler: Optional[Callable[[int], None]] = None
        self._windway_click_handler: Optional[Callable[[int], None]] = None
        self._unsubscribe = register_instrument_listener(self._on_instrument_changed)
        self._theme_unsubscribe: Optional[Callable[[], None]] = register_theme_listener(
            self._on_theme_changed
        )
        self._draw_static()

    # ------------------------------------------------------------------
    def _scaled_canvas_size(self, instrument: InstrumentSpec) -> tuple[int, int]:
        width, height = instrument.canvas_size
        scaled_width = max(1, int(round(float(width) * self._scale)))
        scaled_height = max(1, int(round(float(height) * self._scale)))
        return (scaled_width, scaled_height)

    def _scale_distance(self, value: float) -> float:
        return float(value) * self._scale

    def _scale_radius(self, radius: float) -> float:
        scaled = float(radius) * self._scale
        return max(1.0, scaled)

    def _scale_outline_width(self, width: float) -> float:
        scaled = float(width) * self._scale
        return max(0.5, scaled)

    # ------------------------------------------------------------------
    def destroy(self) -> None:  # type: ignore[override]
        try:
            if self._unsubscribe:
                self._unsubscribe()
                self._unsubscribe = None
            if self._theme_unsubscribe:
                self._theme_unsubscribe()
                self._theme_unsubscribe = None
        finally:
            super().destroy()

    # ------------------------------------------------------------------
    def clear(self) -> None:
        """Clear the current fingering display."""

        self.delete("state")
        self._current_midi = None
        self._current_note_name = None
        self._set_status("")
        if self._note_text_id is not None:
            self.itemconfigure(self._note_text_id, text="")

    def set_midi(self, midi: Optional[int]) -> None:
        """Update the fingering display for the provided MIDI pitch."""

        if midi is None:
            self.clear()
            return

        self.show_fingering(midi_to_name(midi), midi)

    def show_fingering(self, note_name: Optional[str], midi: Optional[int]) -> None:
        """Render the fingering for ``note_name`` and optional ``midi`` pitch."""

        normalized = note_name.strip() if note_name else ""
        if not normalized:
            self.clear()
            return

        self._current_note_name = normalized
        self._current_midi = midi

        instrument = self._instrument

        midi_value = midi
        if midi_value is None:
            try:
                midi_value = parse_note_name(normalized)
            except ValueError:
                midi_value = None

        display_name = midi_to_name(midi_value) if midi_value is not None else normalized
        if self._note_text_id is not None:
            self.itemconfigure(self._note_text_id, text=display_name)

        self.delete("state")

        mapping = instrument.note_map.get(normalized)
        fallback_names: list[str] = []
        if midi_value is not None:
            canonical = midi_to_name(midi_value)
            fallback_names.extend(name for name in (canonical, natural_of(midi_value)) if name)

        for fallback in fallback_names:
            if mapping is None and fallback and fallback != normalized:
                mapping = instrument.note_map.get(fallback)

        if mapping is None:
            self._set_status("No fingering available")
            return

        holes = instrument.holes
        windways = instrument.windways
        sequence = list(mapping)
        total = len(holes) + len(windways)
        if len(sequence) < total:
            sequence.extend([0] * (total - len(sequence)))
        elif len(sequence) > total:
            sequence = sequence[:total]
        hole_states = sequence[: len(holes)]
        windway_states = sequence[len(holes) : len(holes) + len(windways)]

        colors = self._resolve_canvas_colors()
        covered_color = colors.covered_fill or "#000000"

        self._set_status("")
        for index, (hole, covered) in enumerate(zip(holes, hole_states)):
            clamped = max(0, min(2, int(covered)))
            if clamped <= 0:
                continue
            outer_radius = max(1.0, self._scale_radius(hole.radius))
            inset = self._scale_distance(3.0)
            inner_radius = max(1.0, outer_radius - inset)
            center_x = self._scale_distance(hole.x)
            center_y = self._scale_distance(hole.y)
            left = center_x - inner_radius
            top = center_y - inner_radius
            right = center_x + inner_radius
            bottom = center_y + inner_radius
            hole_tag = self._hole_tag(index)
            tags = ("state", hole_tag)
            if clamped >= 2:
                self.create_oval(
                    left,
                    top,
                    right,
                    bottom,
                    outline="",
                    width=0,
                    fill=covered_color,
                    tags=tags,
                )
            else:
                self._draw_half_covered(left, top, right, bottom, covered_color, tags)

        for index, (windway, closed) in enumerate(zip(windways, windway_states)):
            clamped = 0 if int(closed) <= 0 else 2
            if clamped <= 0:
                continue
            half_width = max(1.0, self._scale_distance(windway.width / 2.0))
            half_height = max(1.0, self._scale_distance(windway.height / 2.0))
            center_x = self._scale_distance(windway.x)
            center_y = self._scale_distance(windway.y)
            left = center_x - half_width
            top = center_y - half_height
            right = center_x + half_width
            bottom = center_y + half_height
            windway_tag = self._windway_tag(index)
            self.create_rectangle(
                left,
                top,
                right,
                bottom,
                outline="",
                width=0,
                fill=covered_color,
                tags=("state", windway_tag),
            )

    # ------------------------------------------------------------------
    def _on_instrument_changed(self, instrument: InstrumentSpec) -> None:
        if not self.winfo_exists():
            if self._unsubscribe:
                self._unsubscribe()
                self._unsubscribe = None
            return
        self._instrument = instrument
        self._restore_display_state()

    def _on_theme_changed(self, theme: ThemeSpec) -> None:
        if not self.winfo_exists():
            if self._theme_unsubscribe:
                self._theme_unsubscribe()
                self._theme_unsubscribe = None
            return
        self._theme = theme
        self._restore_display_state()

    def _restore_display_state(self) -> None:
        self._draw_static()
        if self._current_note_name:
            self.show_fingering(self._current_note_name, self._current_midi)
        elif self._current_midi is not None:
            self.set_midi(self._current_midi)
        else:
            self.clear()

    def _draw_static(self) -> None:
        self.delete("static")
        self.delete("note")
        self._note_text_id = None
        self._title_text_id = None
        self._status_text_id = None
        instrument = self._instrument
        scaled_width, scaled_height = self._scaled_canvas_size(instrument)
        colors = self._resolve_canvas_colors()
        palette = getattr(self._theme, "palette", None)
        text_primary = getattr(palette, "text_primary", "#222222")
        text_muted = getattr(palette, "text_muted", "#333333")
        self.configure(width=scaled_width, height=scaled_height, bg=colors.background)

        if instrument.outline is not None:
            outline_points: list[tuple[float, float]] = list(instrument.outline.points)
            if instrument.outline.closed and outline_points[0] != outline_points[-1]:
                outline_points = outline_points + [outline_points[0]]
            coordinates: list[float] = []
            for x, y in outline_points:
                coordinates.append(self._scale_distance(x))
                coordinates.append(self._scale_distance(y))
            self.create_line(
                *coordinates,
                fill=colors.outline,
                width=self._scale_outline_width(instrument.style.outline_width),
                smooth=instrument.style.outline_smooth,
                tags=("static", "outline"),
            )

        hole_tags: list[str] = []
        for index, hole in enumerate(instrument.holes):
            radius = max(1.0, self._scale_radius(hole.radius))
            center_x = self._scale_distance(hole.x)
            center_y = self._scale_distance(hole.y)
            hole_tag = self._hole_tag(index)
            hole_tags.append(hole_tag)
            hitbox_id = self.create_oval(
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
                outline="",
                width=0,
                fill=colors.background,
                tags=("static", "hole-hitbox", hole_tag),
            )
            self.create_oval(
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
                outline=colors.hole_outline,
                width=1,
                tags=("static", "hole", hole_tag),
            )
            self.tag_lower(hitbox_id)
        self._hole_tags = hole_tags
        self._refresh_hole_bindings()

        windway_tags: list[str] = []
        for index, windway in enumerate(instrument.windways):
            half_width = max(1.0, self._scale_distance(windway.width / 2.0))
            half_height = max(1.0, self._scale_distance(windway.height / 2.0))
            center_x = self._scale_distance(windway.x)
            center_y = self._scale_distance(windway.y)
            windway_tag = self._windway_tag(index)
            windway_tags.append(windway_tag)
            hitbox_id = self.create_rectangle(
                center_x - half_width,
                center_y - half_height,
                center_x + half_width,
                center_y + half_height,
                outline="",
                width=0,
                fill=colors.background,
                tags=("static", "windway-hitbox", windway_tag),
            )
            self.create_rectangle(
                center_x - half_width,
                center_y - half_height,
                center_x + half_width,
                center_y + half_height,
                outline=colors.hole_outline,
                width=1,
                fill=colors.background,
                tags=("static", "windway", windway_tag),
            )
            self.tag_lower(hitbox_id)
        self._windway_tags = windway_tags
        self._refresh_windway_bindings()

        padding_x = self._scale_distance(12)
        padding_y = self._scale_distance(12)
        title_x = padding_x
        title_y = padding_y
        note_y = title_y + self._scale_distance(18)
        title_font_size = max(1, int(round(9 * self._scale)))
        note_font_size = max(1, int(round(11 * self._scale)))
        self._title_text_id = self.create_text(
            title_x,
            title_y,
            text=instrument.title,
            fill=text_muted,
            font=("TkDefaultFont", title_font_size),
            anchor="nw",
            tags=("static", "title"),
        )
        self._note_text_id = self.create_text(
            title_x,
            note_y,
            text="",
            fill=text_primary,
            font=("TkDefaultFont", note_font_size),
            anchor="nw",
            tags=("note",),
        )
        status_y = note_y + self._scale_distance(16)
        status_font_size = max(1, int(round(9 * self._scale)))
        self._status_text_id = self.create_text(
            title_x,
            status_y,
            text="",
            fill="#aa0000",
            font=("TkDefaultFont", status_font_size),
            anchor="nw",
            tags=("note", "status"),
        )
        self.tag_raise("note")

    def _resolve_canvas_colors(
        self, instrument: InstrumentSpec | None = None
    ) -> _FingeringCanvasColors:
        spec = instrument or self._instrument
        style = spec.style
        background = style.background_color or "#ffffff"
        outline = style.outline_color or "#000000"
        hole_outline = style.hole_outline_color or outline
        covered_fill = style.covered_fill_color or hole_outline

        if self._is_dark_theme():
            swap_background = hole_outline or background
            swap_foreground = background or outline
            background = swap_background
            outline = swap_foreground
            hole_outline = swap_foreground
            covered_fill = swap_foreground

        return _FingeringCanvasColors(
            background=background,
            outline=outline,
            hole_outline=hole_outline,
            covered_fill=covered_fill,
        )

    def _is_dark_theme(self) -> bool:
        theme = self._theme
        if theme is None:
            return False

        background = theme.palette.window_background
        try:
            red, green, blue = hex_to_rgb(background)
        except ValueError:
            return "dark" in theme.theme_id.lower()

        # Rec. 601 luma approximation to determine perceived brightness.
        luminance = (0.299 * red + 0.587 * green + 0.114 * blue) / 255.0
        return luminance < 0.5

    def _set_status(self, message: str) -> None:
        self._status_message = message
        if self._status_text_id is not None:
            self.itemconfigure(self._status_text_id, text=message)

    def _draw_half_covered(
        self,
        left: float,
        top: float,
        right: float,
        bottom: float,
        fill_color: str,
        tags: tuple[str, ...],
    ) -> None:
        self.create_arc(
            left,
            top,
            right,
            bottom,
            start=90,
            extent=180,
            style=tk.PIESLICE,
            outline="",
            width=0,
            fill=fill_color,
            tags=tags,
        )

    # ------------------------------------------------------------------
    def set_hole_click_handler(self, handler: Optional[Callable[[int], None]]) -> None:
        """Set a callback invoked when a hole is clicked."""

        self._hole_click_handler = handler
        self._refresh_hole_bindings()

    def _hole_tag(self, index: int) -> str:
        return f"hole:{index}"

    def _windway_tag(self, index: int) -> str:
        return f"windway:{index}"

    def _refresh_hole_bindings(self) -> None:
        tags = list(self._hole_tags)
        for tag in tags:
            self.tag_unbind(tag, "<Button-1>")

        handler = self._hole_click_handler
        if handler is None:
            return

        for index, tag in enumerate(tags):
            self.tag_bind(
                tag,
                "<Button-1>",
                lambda event, hole=index: self._handle_hole_click(event, hole),
            )

    def _handle_hole_click(self, _event: tk.Event, hole_index: int) -> None:
        handler = self._hole_click_handler
        if handler is None:
            return
        handler(hole_index)

    def set_windway_click_handler(self, handler: Optional[Callable[[int], None]]) -> None:
        """Set a callback invoked when a windway is clicked."""

        self._windway_click_handler = handler
        self._refresh_windway_bindings()

    def _refresh_windway_bindings(self) -> None:
        tags = list(self._windway_tags)
        for tag in tags:
            self.tag_unbind(tag, "<Button-1>")

        handler = self._windway_click_handler
        if handler is None:
            return

        for index, tag in enumerate(tags):
            self.tag_bind(
                tag,
                "<Button-1>",
                lambda event, windway=index: self._handle_windway_click(event, windway),
            )

    def _handle_windway_click(self, _event: tk.Event, windway_index: int) -> None:
        handler = self._windway_click_handler
        if handler is None:
            return
        handler(windway_index)
