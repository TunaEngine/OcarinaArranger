"""Tkinter piano roll widget used in the preview tab."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, Sequence, Tuple

from ...fingering import FingeringView
from ...scrolling import AutoScrollMode, normalize_auto_scroll_mode
from ...themes import PianoRollPalette, ThemeSpec, get_current_theme, register_theme_listener
from ..events import Event, EventLike, normalize_events
from ..geometry import RenderGeometry
from ..notes import label_for_midi
from ..rendering import PianoRollRenderer
from .cursor import CursorMixin
from .hover import HoverMixin
from .loops import LoopMixin
from .scroll import ScrollMixin
from .types import SupportsGeometry
from .wrapped_mode import WrappedModeMixin


class PianoRoll(
    HoverMixin,
    LoopMixin,
    CursorMixin,
    WrappedModeMixin,
    ScrollMixin,
    ttk.Frame,
):
    """Scrollable piano-roll with optional fingering preview support."""

    def __init__(self, master: tk.Misc, show_fingering: bool = False, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self.label_width = 70
        self._palette = get_current_theme().palette.piano_roll
        self.labels = tk.Canvas(self, bg=self._palette.background, width=self.label_width, height=240, highlightthickness=0)
        self.canvas = tk.Canvas(self, bg=self._palette.background, height=240, highlightthickness=0)
        self.canvas.configure(xscrollincrement=1)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self._show_fingering = show_fingering
        self.fingering = FingeringView(self) if self._show_fingering else None
        self.hbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self._yview_both)
        self._hover_cb: Optional[Callable[[Optional[int]], None]] = None
        self._cursor_cb: Optional[Callable[[int], None]] = None
        self._label_highlight: Optional[int] = None
        self._theme_unsubscribe: Optional[Callable[[], None]] = register_theme_listener(self._on_theme_changed)

        self._hbar_grid_kwargs: dict[str, object] | None = None
        self._vbar_grid_kwargs: dict[str, object] | None = None
        self._layout_widgets()
        self._time_scroll_orientation = "horizontal"
        self._time_layout_mode = "horizontal"

        self.px_per_tick = 0.25
        self.LEFT_PAD = 10
        self.RIGHT_PAD = 120
        self.px_per_note = 18
        self.min_midi = 48
        self.max_midi = 84
        self._x_targets: list[tk.Canvas] = []
        self._cursor_line: Optional[int] = None
        self._cursor_tick = 0
        self._content_height = 0
        self._total_ticks = 0
        self._scroll_width = 1
        self._last_scroll_fraction: Optional[float] = None
        self._loop_start_line: Optional[int] = None
        self._loop_end_line: Optional[int] = None
        self._loop_start_tick = 0
        self._loop_end_tick = 0
        self._loop_visible = False
        self._auto_scroll_mode = AutoScrollMode.FLIP
        self._viewport_hint = 0

        self._wrap_layout = None
        self._wrap_viewport_width = 0
        self._configure_time_scrollbars()

        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.labels.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Motion>", self._hover_from_event)
        self.labels.bind("<Motion>", self._hover_from_event)
        self.canvas.bind("<Leave>", lambda _event: self._hover_emit(None))
        self.labels.bind("<Leave>", lambda _event: self._hover_emit(None))
        self.canvas.bind("<Button-1>", self._on_cursor_event)
        self.canvas.bind("<B1-Motion>", self._on_cursor_event)

        self._renderer = PianoRollRenderer(self.canvas, self.labels, self._palette)
        self._cached: Optional[Tuple[Tuple[Event, ...], int]] = None

    def _wrap_line_for_y(self, y: float):
        """Bridge hover mixin requests to the wrapped-layout helper."""

        return WrappedModeMixin._wrap_line_for_y(self, y)

    def destroy(self) -> None:  # type: ignore[override]
        if self._theme_unsubscribe is not None:
            self._theme_unsubscribe()
            self._theme_unsubscribe = None
        super().destroy()

    def _layout_widgets(self) -> None:
        if self._show_fingering and self.fingering is not None:
            self.fingering.grid(row=0, column=0, sticky="nsw")
            self.labels.grid(row=0, column=1, sticky="nsew")
            self.canvas.grid(row=0, column=2, sticky="nsew")
            self.vbar.grid(row=0, column=3, sticky="ns")
            self.hbar.grid(row=1, column=0, columnspan=4, sticky="ew")
            self.grid_rowconfigure(0, weight=1)
            self.grid_columnconfigure(2, weight=1)
            self._hbar_grid_kwargs = {"row": 1, "column": 0, "columnspan": 4, "sticky": "ew"}
            self._vbar_grid_kwargs = {"row": 0, "column": 3, "sticky": "ns"}
        else:
            self.labels.grid(row=0, column=0, sticky="nsew")
            self.canvas.grid(row=0, column=1, sticky="nsew")
            self.vbar.grid(row=0, column=2, sticky="ns")
            self.hbar.grid(row=1, column=0, columnspan=3, sticky="ew")
            self.grid_rowconfigure(0, weight=1)
            self.grid_columnconfigure(1, weight=1)
            self._hbar_grid_kwargs = {"row": 1, "column": 0, "columnspan": 3, "sticky": "ew"}
            self._vbar_grid_kwargs = {"row": 0, "column": 2, "sticky": "ns"}

    def set_range(self, minimum: int, maximum: int) -> None:
        self.min_midi, self.max_midi = minimum, maximum

    def set_zoom(self, delta: int) -> None:
        new_height = max(6, min(30, self.px_per_note + delta))
        if abs(new_height - self.px_per_note) > 1e-6:
            self.px_per_note = new_height
            if self._cached:
                events, ppq = self._cached
                self.render(events, ppq)

    def set_time_zoom(self, multiplier: float) -> None:
        new_px = max(0.1, min(5.0, self.px_per_tick * multiplier))
        if abs(new_px - self.px_per_tick) > 1e-6:
            self.px_per_tick = new_px
            if self._cached:
                events, ppq = self._cached
                self.render(events, ppq)

    def set_time_scroll_orientation(self, orientation: str) -> None:
        normalized = orientation.lower()
        if normalized not in {"horizontal", "vertical"}:
            raise ValueError(f"Unsupported orientation: {orientation}")
        if normalized == self._time_scroll_orientation:
            return
        self._time_scroll_orientation = normalized
        self._time_layout_mode = "wrapped" if normalized == "vertical" else "horizontal"
        self._configure_time_scrollbars()
        self._wrap_viewport_width = 0
        self._update_time_scroll_fraction()

    def sync_x_with(self, target_canvas: tk.Canvas) -> None:
        if target_canvas not in self._x_targets:
            self._x_targets.append(target_canvas)

    def render(self, events: Sequence[EventLike], pulses_per_quarter: int) -> None:
        normalized_events = tuple(sorted(normalize_events(events), key=lambda item: item[0]))
        self._cached = (normalized_events, pulses_per_quarter)
        self._label_highlight = None
        self._cursor_line = None
        self._loop_start_line = None
        self._loop_end_line = None
        self._wrap_layout = None
        self._last_scroll_fraction = None

        if self._time_layout_mode == "wrapped":
            self._render_wrapped_vertical(normalized_events, pulses_per_quarter)
            return

        outcome = self._renderer.render(normalized_events, pulses_per_quarter, self._current_geometry())
        self._total_ticks = outcome.total_ticks
        self._content_height = outcome.content_height
        self._scroll_width = outcome.scroll_width

        if not outcome.has_events:
            self._loop_visible = False
            return

        self._redraw_visible_region(force=True)

        palette = self._palette
        height = self._content_height or int(self.canvas.winfo_height())
        self._label_highlight = self.labels.create_rectangle(
            0,
            0,
            self.label_width,
            0,
            outline="",
            fill=palette.highlight_fill,
            state="hidden",
        )
        self.labels.tag_raise("note_label")

        self._loop_start_line = self.canvas.create_line(
            self.LEFT_PAD,
            0,
            self.LEFT_PAD,
            height,
            fill=palette.loop_start_line,
            width=2,
            state="hidden",
            tags=("loop_start_marker", "overlay"),
        )
        self._loop_end_line = self.canvas.create_line(
            self.LEFT_PAD,
            0,
            self.LEFT_PAD,
            height,
            fill=palette.loop_end_line,
            width=2,
            state="hidden",
            tags=("loop_end_marker", "overlay"),
        )
        self._cursor_line = self.canvas.create_line(
            self.LEFT_PAD,
            0,
            self.LEFT_PAD,
            height,
            fill=palette.cursor_primary,
            width=2,
            tags=("time_cursor", "overlay"),
        )
        self.canvas.tag_raise("overlay")
        self._update_loop_markers()
        self.set_cursor(self._cursor_tick)

    def _on_canvas_configure(self, event: tk.Event) -> None:
        try:
            width = int(getattr(event, "width", 0))
        except Exception:
            width = 0
        if width > 1:
            self._viewport_hint = width
        if self._time_layout_mode == "wrapped":
            if width > 1:
                if self._cached and width != self._wrap_viewport_width:
                    events, ppq = self._cached
                    self._render_wrapped_vertical(events, ppq)
                else:
                    self._wrap_viewport_width = width
            return
        self._redraw_visible_region(force=True)

    def set_fingering_cb(self, callback: Callable[[Optional[int]], None]) -> None:
        self._hover_cb = callback

    def set_cursor_callback(self, callback: Callable[[int], None]) -> None:
        self._cursor_cb = callback

    def set_auto_scroll_mode(self, mode: AutoScrollMode | str) -> None:
        normalized = normalize_auto_scroll_mode(mode)
        if self._auto_scroll_mode is normalized:
            return
        self._auto_scroll_mode = normalized

    def _on_cursor_event(self, event: tk.Event) -> None:
        tick = self._tick_from_event(event)
        if tick is None:
            return
        self.set_cursor(tick)
        if self._cursor_cb:
            self._cursor_cb(tick)

    def apply_palette(self, palette: PianoRollPalette) -> None:
        self._palette = palette
        self.labels.configure(bg=palette.background)
        self.canvas.configure(bg=palette.background)
        self._renderer.set_palette(palette)
        if self._cached:
            events, ppq = self._cached
            self.render(events, ppq)

    def _on_theme_changed(self, theme: ThemeSpec) -> None:
        self.apply_palette(theme.palette.piano_roll)

    def _raise_overlay_items(self) -> None:
        if self.canvas.find_withtag("overlay"):
            try:
                self.canvas.tag_raise("overlay")
            except Exception:
                pass
        if self._cursor_line is not None:
            self.canvas.tag_raise(self._cursor_line)

    def _current_geometry(self) -> SupportsGeometry:
        return RenderGeometry(
            min_midi=self.min_midi,
            max_midi=self.max_midi,
            px_per_note=self.px_per_note,
            px_per_tick=self.px_per_tick,
            left_pad=self.LEFT_PAD,
            right_pad=self.RIGHT_PAD,
            label_width=self.label_width,
        )

    # ------------------------------------------------------------------
    # Mix-in bridge helpers
    # ------------------------------------------------------------------
    def _wrap_tick_to_coords(self, tick: int):  # type: ignore[override]
        """Delegate to the wrapped-layout helper implementation."""

        return WrappedModeMixin._wrap_tick_to_coords(self, tick)

    def _wrap_point_to_tick(self, x: int, y: int):  # type: ignore[override]
        """Resolve a wrapped-layout click to a tick value."""

        return WrappedModeMixin._wrap_point_to_tick(self, x, y)

    def _maybe_autoscroll(self, position: int) -> None:  # type: ignore[override]
        """Reuse the scroll mix-in’s concrete auto-scroll behaviour."""

        ScrollMixin._maybe_autoscroll(self, position)

    # ------------------------------------------------------------------
    # Backwards-compatible helpers used by tests
    # ------------------------------------------------------------------
    def _label_for_midi(self, midi: int) -> str:
        """Return the display label for a MIDI pitch."""

        return label_for_midi(int(midi))

    def _midi_from_y(self, y: int) -> Optional[int]:
        """Expose geometry conversion for hover-related tests."""

        geometry = self._current_geometry()
        try:
            return geometry.midi_from_y(int(y))
        except Exception:
            return None

    def _y(self, midi: int) -> int:
        """Return the nominal y-position for the provided MIDI note."""

        return int(round(self._current_geometry().note_y(int(midi))))
