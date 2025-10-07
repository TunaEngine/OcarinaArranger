"""Base implementation for the treble staff preview widget."""

from __future__ import annotations

import logging
import tkinter as tk

from shared.ttk import ttk
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

from ...scrolling import AutoScrollMode, normalize_auto_scroll_mode
from ...themes import StaffPalette, ThemeSpec, get_current_theme, register_theme_listener
from shared.tk_style import apply_round_scrollbar_style, get_ttk_style
from ..cursor import CursorController
from ..rendering import StaffRenderer
from ..scrollbars import ScrollbarManager
from .types import Event
from ocarina_tools import NoteEvent

logger = logging.getLogger(__name__)


class StaffViewBase(ttk.Frame):
    """Shared state and behaviour for :class:`StaffView`."""

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._theme_unsubscribe: Optional[Callable[[], None]] = None
        self._palette = get_current_theme().palette.staff
        try:
            get_ttk_style(self)
        except tk.TclError:
            pass
        self.canvas = tk.Canvas(self, bg=self._palette.background, height=180, highlightthickness=0)
        self.canvas.configure(xscrollincrement=1)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.hbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        apply_round_scrollbar_style(self.hbar)
        self.vbar = ttk.Scrollbar(self, orient="vertical")
        apply_round_scrollbar_style(self.vbar)
        self._theme_unsubscribe = register_theme_listener(self._on_theme_changed)

        self.canvas.grid(row=0, column=1, sticky="nsew")
        self.vbar.grid(row=0, column=2, sticky="ns")
        self.hbar.grid(row=1, column=0, columnspan=3, sticky="ew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, minsize=70)  # Placeholder to match PianoRoll
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)

        self.px_per_tick = 0.25
        self.LEFT_PAD = 10
        self.RIGHT_PAD = 120
        self.staff_spacing = 8
        self._cached: Optional[Tuple[Sequence[Event | Tuple[int, int, int, int]], int, int, int]] = None
        self._x_targets: List[tk.Canvas] = []
        self._cursor_line: Optional[int] = None
        self._secondary_cursor_line: Optional[int] = None
        self._cursor_tick = 0
        self._secondary_cursor_tick: Optional[int] = None
        self._loop_start_line: Optional[int] = None
        self._loop_end_line: Optional[int] = None
        self._loop_start_tick = 0
        self._loop_end_tick = 0
        self._loop_visible = False
        self.loop_region: tuple[int, int, bool] = (0, 0, False)
        self._content_height = 0
        self._total_ticks = 0
        self._scroll_width = 1
        self._events: Tuple[Event, ...] = ()
        self._event_onsets: Tuple[int, ...] = ()
        self._ticks_per_measure = 0
        self._drawn_range: Optional[Tuple[int, int]] = None
        self._virtual_tags = ("virtualized_a", "virtualized_b")
        self._active_virtual_tag_index = 0
        self._layout_mode = "horizontal"
        self._wrap_layout: Optional[dict[str, object]] = None
        self._auto_scroll_mode = AutoScrollMode.FLIP
        self._last_press_serial: Optional[int] = None
        self._wrap_pending_rerender = False
        self._scrollbars = ScrollbarManager(self)
        self._cursor_controller = CursorController(self)
        self._renderer = StaffRenderer(self)
        self._cursor_cb: Optional[Callable[[int], None]] = None
        self._cursor_drag_state_cb: Optional[Callable[[bool], None]] = None
        self._scrollbars.configure_for_layout(self._layout_mode)
        for sequence in ("<Button-1>", "<ButtonPress-1>", "<ButtonRelease-1>", "<B1-Motion>"):
            self.canvas.bind(sequence, self._on_cursor_event)
        # Ensure clicks on rendered items propagate to the cursor handler.
        for sequence in ("<Button-1>", "<ButtonPress-1>", "<ButtonRelease-1>"):
            self.canvas.tag_bind("virtualized", sequence, self._on_cursor_event, add="+")
        self.bind("<Map>", self._on_map_event, add="+")

    @property
    def scrollbars(self) -> ScrollbarManager:
        return self._scrollbars

    @property
    def cursor(self) -> CursorController:
        return self._cursor_controller

    def destroy(self) -> None:  # type: ignore[override]
        if self._theme_unsubscribe is not None:
            self._theme_unsubscribe()
            self._theme_unsubscribe = None
        super().destroy()

    # ------------------------------------------------------------------
    # Backwards-compatible helpers used by tests
    # ------------------------------------------------------------------
    def _staff_pos(self, midi: int) -> int:
        """Return the staff position index for a MIDI pitch."""

        return int(round((int(midi) - 64) * 7 / 12))

    def _y_for_pos(self, y_top: int, pos: int) -> float:
        """Convert a staff position into a canvas y-coordinate."""

        return float(y_top + (8 - int(pos)) * (self.staff_spacing / 2))

    def sync_x_with(self, target_canvas: tk.Canvas) -> None:
        if target_canvas not in self._x_targets:
            self._x_targets.append(target_canvas)

    def set_cursor_callback(self, callback: Callable[[int], None]) -> None:
        self._cursor_cb = callback

    def set_cursor_drag_state_cb(self, callback: Callable[[bool], None]) -> None:
        self._cursor_drag_state_cb = callback

    def set_time_zoom(self, multiplier: float) -> None:
        new_px = max(0.1, min(5.0, self.px_per_tick * multiplier))
        if abs(new_px - self.px_per_tick) > 1e-6:
            self.px_per_tick = new_px
            if self._cached:
                events, ppq, beats, beat_type = self._cached
                self.render(events, ppq, beats, beat_type)

    def set_auto_scroll_mode(self, mode: AutoScrollMode | str) -> None:
        normalized = normalize_auto_scroll_mode(mode)
        if normalized is self._auto_scroll_mode:
            return
        self._auto_scroll_mode = normalized

    def set_layout_mode(self, mode: str) -> None:
        normalized = mode.lower()
        if normalized not in {"horizontal", "wrapped"}:
            raise ValueError(f"Unsupported layout mode: {mode}")
        if normalized == self._layout_mode:
            return
        self._layout_mode = normalized
        logger.debug(
            "StaffView layout mode updated (%s)",
            normalized,
            extra={"widget": repr(self)},
        )
        self._scrollbars.configure_for_layout(self._layout_mode)
        self._scrollbars.reset_scroll_fraction()
        self._scrollbars.ensure_visible(self._layout_mode)
        if self._cached:
            events, ppq, beats, beat_type = self._cached
            self.render(events, ppq, beats, beat_type)
        try:
            self.after_idle(lambda: self._scrollbars.ensure_visible(self._layout_mode))
        except Exception:
            self._scrollbars.ensure_visible(self._layout_mode)
        self._scrollbars.log_state("set_layout_mode", self._layout_mode)

    def render(
        self,
        events: Sequence[Event | Tuple[int, int, int, int]],
        pulses_per_quarter: int,
        beats: int = 4,
        beat_type: int = 4,
    ) -> None:
        self.canvas.delete("all")
        self._cached = (events, pulses_per_quarter, beats, beat_type)
        self._cursor_controller.reset_canvas_items()
        self._drawn_range = None
        self._active_virtual_tag_index = 0
        self._scrollbars.reset_scroll_fraction()

        normalized_events = tuple(self._normalize_events(events))
        sorted_events = tuple(sorted(normalized_events, key=lambda item: item[0]))
        total_ticks = (
            max((event.onset + event.duration) for event in sorted_events)
            if sorted_events
            else 0
        )
        self._total_ticks = total_ticks
        self._events = sorted_events
        self._event_onsets = tuple(event.onset for event in sorted_events)

        ticks_per_beat = int(pulses_per_quarter * (4 / beat_type))
        self._ticks_per_measure = max(1, beats * ticks_per_beat)
        if self._layout_mode == "wrapped":
            self._renderer.render_wrapped(sorted_events, pulses_per_quarter, beats, beat_type)
            return

        self._renderer.render_horizontal(sorted_events, beats, beat_type)

    def _normalize_events(
        self, events: Sequence[Event | Tuple[int, int, int, int]]
    ) -> Iterable[Event]:
        for event in events:
            if isinstance(event, NoteEvent):
                yield event
            else:
                onset, duration, midi, program = event  # type: ignore[misc]
                yield NoteEvent(onset, duration, midi, program)

    def _on_canvas_configure(self, _event: tk.Event) -> None:
        if self._layout_mode == "wrapped":
            if self._cached:
                events, ppq, beats, beat_type = self._cached
                self._renderer.render_wrapped(tuple(events), ppq, beats, beat_type)
            return
        self._renderer.redraw_visible_region(force=True)

    def _on_map_event(self, _event: tk.Event) -> None:
        if self._layout_mode != "wrapped":
            return
        self._show_vertical_scrollbar()

    def _request_wrapped_rerender(self) -> None:
        if self._layout_mode != "wrapped":
            return
        if self._wrap_pending_rerender:
            return
        viewport_width = self._get_viewport_width()
        if viewport_width <= 1:
            self._wrap_pending_rerender = True
            return
        self._wrap_pending_rerender = True

        def _rerender() -> None:
            self._wrap_pending_rerender = False
            if self._layout_mode != "wrapped":
                return
            cached = self._cached
            if not cached:
                return
            try:
                events, ppq, beats, beat_type = cached
                self.render(events, ppq, beats, beat_type)
            except Exception:
                logger.exception(
                    "StaffView failed to rerender wrapped layout", extra={"widget": repr(self)}
                )

        try:
            self.after_idle(_rerender)
        except Exception:
            _rerender()
        self._ensure_vertical_bar_mapped()

    def _redraw_visible_region(self, force: bool = False) -> None:
        self._renderer.redraw_visible_region(force)

    def apply_palette(self, palette: StaffPalette) -> None:
        self._palette = palette
        self.canvas.configure(bg=palette.background)
        self._cursor_controller.apply_palette(palette)
        if self._cached:
            events, ppq, beats, beat_type = self._cached
            self.render(events, ppq, beats, beat_type)

    def _on_theme_changed(self, theme: ThemeSpec) -> None:
        self.apply_palette(theme.palette.staff)

    def set_cursor(self, tick: int, *, allow_autoscroll: bool = True) -> None:
        self._cursor_controller.set_cursor(tick, allow_autoscroll=allow_autoscroll)

    def set_secondary_cursor(self, tick: Optional[int]) -> None:
        self._cursor_controller.set_secondary_cursor(tick)

    def _create_cursor_lines(self, height: int) -> None:
        self._cursor_controller.create_cursor_lines(height)

    def _create_loop_lines(self, height: int) -> None:
        self._cursor_controller.create_loop_lines(height)

    def _raise_loop_lines(self) -> None:
        self._cursor_controller.raise_loop_lines()

    def _raise_cursor_lines(self) -> None:
        self._cursor_controller.raise_cursor_lines()

    def set_loop_region(self, start_tick: int, end_tick: int, visible: bool) -> None:
        self._cursor_controller.set_loop_region(start_tick, end_tick, visible)

    def _update_loop_markers(self) -> None:
        self._cursor_controller.update_loop_markers()















