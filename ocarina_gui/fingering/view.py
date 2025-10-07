"""Tkinter canvas widget that renders configurable ocarina fingerings."""

from __future__ import annotations

import logging
import tkinter as tk
from typing import Callable, Optional
from ocarina_gui.constants import midi_to_name, natural_of
from ocarina_gui.themes import ThemeSpec, get_current_theme, register_theme_listener
from ocarina_tools.pitch import parse_note_name

from .library import get_current_instrument, register_instrument_listener
from .outline_renderer import OutlineImage, render_outline_photoimage
from .specs import InstrumentSpec
from .view_interaction import FingeringInteractionMixin
from .view_static import FingeringStaticCanvasMixin


__all__ = ["FingeringView", "render_outline_photoimage", "OutlineImage"]


_LOGGER = logging.getLogger(__name__)


class FingeringView(FingeringStaticCanvasMixin, FingeringInteractionMixin, tk.Canvas):
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
        self._outline_cache_key: tuple | None = None
        self._instrument_revision: int = 0
        self._static_revision: int = -1
        self._unsubscribe = register_instrument_listener(self._on_instrument_changed)
        self._theme_unsubscribe: Optional[Callable[[], None]] = register_theme_listener(
            self._on_theme_changed
        )
        self._outline_image: OutlineImage | None = None
        self._outline_canvas_id: int | None = None
        self._static_signature: tuple | None = None
        self._next_static_signature: tuple | None = None
        self._hole_canvas_binding: str | None = None
        self._last_handled_serial: int | None = None
        self._hole_hitboxes: list[tuple[float, float, float, float]] = []
        self._handled_hole_event_count: int = 0
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Initialising FingeringView scale=%s instrument=%s outline_points=%s",
                self._scale,
                instrument.instrument_id,
                len(instrument.outline.points) if instrument.outline else 0,
            )
        self._draw_static()

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
            if clamped >= 2:
                self.create_oval(
                    left,
                    top,
                    right,
                    bottom,
                    outline="",
                    width=0,
                    fill=covered_color,
                    tags=("state", "hole-hitbox", hole_tag),
                )
            else:
                self._draw_half_covered(
                    left,
                    top,
                    right,
                    bottom,
                    covered_color,
                    ("state", "hole-hitbox", hole_tag),
                )

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
                tags=("state", "windway-hitbox", windway_tag),
            )

        self.tag_raise("hole-hitbox")
        self.tag_raise("windway-hitbox")

    # ------------------------------------------------------------------
    def _on_instrument_changed(self, instrument: InstrumentSpec) -> None:
        if not self.winfo_exists():
            if self._unsubscribe:
                self._unsubscribe()
                self._unsubscribe = None
            return
        self._instrument = instrument
        self._instrument_revision += 1
        self._restore_display_state()

    def _on_theme_changed(self, theme: ThemeSpec) -> None:
        if not self.winfo_exists():
            if self._theme_unsubscribe:
                self._theme_unsubscribe()
                self._theme_unsubscribe = None
            return
        self._theme = theme
        self._restore_display_state(force_static=True)

    def _restore_display_state(self, *, force_static: bool = False) -> None:
        signature = self._static_signature_for(self._instrument)
        has_displayed_note = self._current_note_name is not None or self._current_midi is not None
        needs_static = force_static or self._static_signature is None
        if not needs_static and signature != self._static_signature:
            needs_static = True
        if not needs_static and self._static_revision != self._instrument_revision and not has_displayed_note:
            needs_static = True
        if not needs_static and not has_displayed_note:
            needs_static = True
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Restore display state force_static=%s needs_static=%s current_note=%s revision=%s",
                force_static,
                needs_static,
                self._current_note_name,
                self._instrument_revision,
            )
        if needs_static:
            self._next_static_signature = signature
            self._draw_static()
        else:
            self._next_static_signature = None
            self._static_signature = signature
            self._static_revision = self._instrument_revision
        if self._current_note_name:
            self.show_fingering(self._current_note_name, self._current_midi)
        elif self._current_midi is not None:
            self.set_midi(self._current_midi)
        else:
            self.clear()

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
    def event_generate(self, sequence: str, *args, **kwargs) -> None:  # type: ignore[override]
        """Generate an event and fall back to manual dispatch for synthetic clicks.

        Tests drive the canvas by calling ``event_generate`` with explicit ``x`` and
        ``y`` coordinates.  Some Tk builds fail to dispatch tag bindings for those
        synthetic events, so we detect that case and manually route the click
        through the canvas hit-test logic to keep behavior consistent.
        """

        should_fallback = (
            sequence in {"<Button-1>", "<ButtonPress-1>"}
            and self._hole_click_handler is not None
            and "x" in kwargs
            and "y" in kwargs
        )
        previous_count = self._handled_hole_event_count if should_fallback else None
        super().event_generate(sequence, *args, **kwargs)
        if should_fallback and previous_count == self._handled_hole_event_count:
            try:
                x_coord = float(kwargs.get("x"))
                y_coord = float(kwargs.get("y"))
            except (TypeError, ValueError):
                return
            event = tk.Event()
            event.widget = self
            event.x = self.canvasx(x_coord)
            event.y = self.canvasy(y_coord)
            event.serial = None
            self._handle_canvas_hole_click(event)
