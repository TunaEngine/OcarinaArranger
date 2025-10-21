"""Headless counterparts of complex view widgets used by the GUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence, Tuple

from ocarina_tools import NoteEvent

from .containers import HeadlessCanvas, HeadlessScrollbar
from .piano_roll import HeadlessPianoRoll
from ocarina_gui.staff.view.base import (
    _TEMPO_MARKER_BARLINE_PADDING as STAFF_TEMPO_BARLINE_PADDING,
    _TEMPO_MARKER_LEFT_PADDING as STAFF_TEMPO_LEFT_PADDING,
)





class HeadlessFingeringView:
    def __init__(self) -> None:
        self.midi: Optional[int] = None
        self.note_name: Optional[str] = None
        self.status: str = ""
        self._hole_click_handler: Optional[Callable[[int], None]] = None
        self._windway_click_handler: Optional[Callable[[int], None]] = None

    def set_midi(self, midi: Optional[int]) -> None:
        if midi is None:
            self.show_fingering(None, None)
            return

        try:
            from ..fingering import midi_to_name

            self.show_fingering(midi_to_name(midi), midi)
        except Exception:
            self.midi = midi
            self.note_name = None
            self.status = ""

    def show_fingering(self, note_name: Optional[str], midi: Optional[int]) -> None:
        self.note_name = note_name.strip() if note_name else None
        self.midi = midi
        if not self.note_name:
            self.status = ""
            return

        try:
            from ..fingering import get_current_instrument, midi_to_name, natural_of
            from ocarina_tools.pitch import parse_note_name

            instrument = get_current_instrument()
            mapping = instrument.note_map.get(self.note_name)

            midi_value = midi
            if midi_value is None:
                try:
                    midi_value = parse_note_name(self.note_name)
                except Exception:
                    midi_value = None

            if midi_value is not None:
                if mapping is None:
                    mapping = instrument.note_map.get(midi_to_name(midi_value))
                if mapping is None:
                    mapping = instrument.note_map.get(natural_of(midi_value))

            self.status = "" if mapping is not None else "No fingering available"
        except Exception:
            self.status = ""

    def set_hole_click_handler(self, handler: Optional[Callable[[int], None]]) -> None:
        self._hole_click_handler = handler

    def trigger_hole_click(self, hole_index: int) -> None:
        if self._hole_click_handler:
            self._hole_click_handler(hole_index)

    def set_windway_click_handler(self, handler: Optional[Callable[[int], None]]) -> None:
        self._windway_click_handler = handler

    def trigger_windway_click(self, windway_index: int) -> None:
        if self._windway_click_handler:
            self._windway_click_handler(windway_index)


@dataclass
class HeadlessStaffView:
    LEFT_PAD: int = 10
    px_per_tick: float = 0.25
    canvas: HeadlessCanvas = field(default_factory=HeadlessCanvas)
    hbar: HeadlessScrollbar = field(default_factory=lambda: HeadlessScrollbar("hbar"))
    vbar: HeadlessScrollbar = field(default_factory=lambda: HeadlessScrollbar("vbar"))
    _cached: Optional[Tuple[Sequence[NoteEvent], int, int, int]] = None
    cursor_tick: int = 0
    secondary_cursor_tick: Optional[int] = None
    _cursor_cb: Optional[Callable[[int], None]] = None
    _cursor_drag_state_cb: Optional[Callable[[bool], None]] = None
    auto_scroll_mode: str = "flip"
    loop_region: Optional[Tuple[int, int, bool]] = None
    _layout_mode: str = "horizontal"
    _hbar_grid_defaults: dict[str, object] = field(default_factory=dict, init=False)
    _vbar_grid_defaults: dict[str, object] = field(default_factory=dict, init=False)
    _wrap_pending_rerender: bool = False
    _tempo_markers: Tuple[tuple[int, str], ...] = ()
    _tempo_marker_items: list[int] = field(default_factory=list)
    _last_y_top: float = 42.0
    total_ticks: int = 0

    def __post_init__(self) -> None:
        self._hbar_grid_defaults = {"row": 1, "column": 0, "columnspan": 3, "sticky": "ew"}
        self._vbar_grid_defaults = {"row": 0, "column": 2, "sticky": "ns"}
        self.hbar.grid(**self._hbar_grid_defaults)
        self.vbar.grid(**self._vbar_grid_defaults)

    def sync_x_with(self, _target: HeadlessCanvas) -> None:  # pragma: no cover
        pass

    def set_time_zoom(self, multiplier: float) -> None:  # pragma: no cover
        new_px = max(0.1, min(5.0, self.px_per_tick * multiplier))
        if abs(new_px - self.px_per_tick) > 1e-6:
            self.px_per_tick = new_px
            if self._cached:
                events, ppq, beats, beat_type = self._cached
                self.render(events, ppq, beats, beat_type)
        else:
            self.px_per_tick = new_px
        if self._tempo_markers:
            self.set_tempo_markers(self._tempo_markers)

    def render(
        self,
        events: Sequence[NoteEvent],
        pulses_per_quarter: int,
        beats: int,
        beat_type: int,
        *,
        total_ticks: int | None = None,
    ) -> None:
        self._cached = (events, pulses_per_quarter, beats, beat_type)
        self.total_ticks = int(total_ticks or 0)

    def set_cursor(self, tick: int, allow_autoscroll: bool = True) -> None:
        self.cursor_tick = max(0, int(tick))
        if self._cursor_cb:
            self._cursor_cb(self.cursor_tick)

    def set_loop_region(self, start_tick: int, end_tick: int, visible: bool) -> None:
        self.loop_region = (start_tick, end_tick, visible)

    def set_cursor_callback(self, callback: Callable[[int], None]) -> None:
        self._cursor_cb = callback

    def set_tempo_markers(self, markers: Sequence[tuple[int, str]]) -> None:
        self._tempo_markers = tuple(markers)
        self._tempo_marker_items = list(range(len(self._tempo_markers)))
        base_y = max(24.0, self._last_y_top - 18.0)
        self.canvas.set_tempo_markers(
            self._tempo_markers,
            left_pad=self.LEFT_PAD,
            px_per_tick=self.px_per_tick,
            base_y=base_y,
            left_padding=STAFF_TEMPO_LEFT_PADDING,
            barline_padding=STAFF_TEMPO_BARLINE_PADDING,
        )

    def set_cursor_drag_state_cb(self, callback: Callable[[bool], None]) -> None:
        self._cursor_drag_state_cb = callback

    def set_secondary_cursor(self, tick: Optional[int]) -> None:
        if tick is None:
            self.secondary_cursor_tick = None
        else:
            self.secondary_cursor_tick = max(0, int(tick))
        return

    def set_auto_scroll_mode(self, mode: object) -> None:
        if isinstance(mode, str):
            self.auto_scroll_mode = mode
        elif hasattr(mode, "value"):
            self.auto_scroll_mode = getattr(mode, "value")

    def set_layout_mode(self, mode: str) -> None:
        normalized = mode.lower()
        if normalized not in {"horizontal", "wrapped"}:
            raise ValueError(f"Unsupported layout mode: {mode}")
        self._layout_mode = normalized
        if normalized == "wrapped":
            self.hbar.grid_remove()
            self.vbar.grid(**self._vbar_grid_defaults)
        else:
            self.hbar.grid(**self._hbar_grid_defaults)
            self.vbar.grid(**self._vbar_grid_defaults)

    def update_idletasks(self) -> None:  # pragma: no cover - compatibility stub
        pass

    def _request_wrapped_rerender(self) -> None:  # pragma: no cover - headless no-op
        self._wrap_pending_rerender = False
