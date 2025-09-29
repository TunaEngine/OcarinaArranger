"""Tkinter canvas widget that renders configurable ocarina fingerings."""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from ocarina_gui.constants import midi_to_name, natural_of
from ocarina_tools.pitch import parse_note_name

from .library import get_current_instrument, register_instrument_listener
from .specs import InstrumentSpec


__all__ = ["FingeringView"]


class FingeringView(tk.Canvas):
    """Displays configurable ocarina fingerings for a given MIDI pitch."""

    def __init__(self, master: tk.Misc, *, scale: float = 1.0, **kwargs) -> None:
        self._scale = max(0.1, float(scale))
        instrument = get_current_instrument()
        width, height = self._scaled_canvas_size(instrument)
        super().__init__(
            master,
            width=width,
            height=height,
            bg=instrument.style.background_color,
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
        self._hole_click_handler: Optional[Callable[[int], None]] = None
        self._unsubscribe = register_instrument_listener(self._on_instrument_changed)
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
        sequence = list(mapping)
        if len(sequence) < len(holes):
            sequence.extend([0] * (len(holes) - len(sequence)))
        elif len(sequence) > len(holes):
            sequence = sequence[: len(holes)]

        covered_color = instrument.style.covered_fill_color or "#000000"

        self._set_status("")
        for index, (hole, covered) in enumerate(zip(holes, sequence)):
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

    # ------------------------------------------------------------------
    def _on_instrument_changed(self, instrument: InstrumentSpec) -> None:
        if not self.winfo_exists():
            if self._unsubscribe:
                self._unsubscribe()
                self._unsubscribe = None
            return
        self._instrument = instrument
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
        self.configure(
            width=scaled_width, height=scaled_height, bg=instrument.style.background_color
        )

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
                fill=instrument.style.outline_color,
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
                fill=instrument.style.background_color,
                tags=("static", "hole-hitbox", hole_tag),
            )
            self.create_oval(
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
                outline=instrument.style.hole_outline_color,
                width=1,
                tags=("static", "hole", hole_tag),
            )
            self.tag_lower(hitbox_id)
        self._hole_tags = hole_tags
        self._refresh_hole_bindings()

        title_x = scaled_width / 2
        title_y = self._scale_distance(20)
        note_y = title_y + self._scale_distance(18)
        title_font_size = max(1, int(round(9 * self._scale)))
        note_font_size = max(1, int(round(11 * self._scale)))
        self._title_text_id = self.create_text(
            title_x,
            title_y,
            text=instrument.title,
            fill="#333333",
            font=("TkDefaultFont", title_font_size),
            tags=("static", "title"),
        )
        self._note_text_id = self.create_text(
            title_x,
            note_y,
            text="",
            fill="#222222",
            font=("TkDefaultFont", note_font_size),
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
            tags=("note", "status"),
        )
        self.tag_raise("note")

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
