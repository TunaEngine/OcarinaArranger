"""Headless counterparts of complex view widgets used by the GUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Callable, Optional, Sequence, Tuple

from ocarina_tools import NoteEvent

from .containers import HeadlessCanvas, HeadlessScrollbar
from ocarina_gui.piano_roll.view.tempo_markers import (
    _TEMPO_MARKER_BARLINE_PADDING as ROLL_TEMPO_BARLINE_PADDING,
    _TEMPO_MARKER_LEFT_PADDING as ROLL_TEMPO_LEFT_PADDING,
)
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
class HeadlessPianoRoll:
    label_width: int = 70
    LEFT_PAD: int = 10
    canvas: HeadlessCanvas = field(default_factory=HeadlessCanvas)
    _cached: Optional[Tuple[Sequence[NoteEvent], int, int, int]] = None
    _fingering_cb: Optional[Callable[[Optional[int]], None]] = None
    _cursor_cb: Optional[Callable[[int], None]] = None
    _cursor_drag_state_cb: Optional[Callable[[bool], None]] = None
    _cursor_tick: int = 0
    loop_region: Optional[Tuple[int, int, bool]] = None
    auto_scroll_mode: str = "flip"
    px_per_tick: float = 0.5
    px_per_note: float = 6.0
    max_midi: int = 84
    _tempo_markers: Tuple[tuple[int, str], ...] = ()

    def set_range(self, minimum: int, maximum: int) -> None:  # pragma: no cover - stored for completeness
        self.range = (minimum, maximum)

    def render(
        self,
        events: Sequence[NoteEvent],
        pulses_per_quarter: int,
        *,
        beats: int = 4,
        beat_unit: int = 4,
    ) -> None:
        self._cached = (events, pulses_per_quarter, beats, beat_unit)
        if self._fingering_cb:
            self._fingering_cb(None)

    def set_fingering_cb(self, callback: Callable[[Optional[int]], None]) -> None:
        self._fingering_cb = callback

    def set_cursor_callback(self, callback: Callable[[int], None]) -> None:
        self._cursor_cb = callback

    def set_cursor_drag_state_cb(self, callback: Callable[[bool], None]) -> None:
        self._cursor_drag_state_cb = callback

    def set_auto_scroll_mode(self, mode: object) -> None:
        if isinstance(mode, str):
            self.auto_scroll_mode = mode
        elif hasattr(mode, "value"):
            self.auto_scroll_mode = getattr(mode, "value")

    def set_cursor(self, tick: int, allow_autoscroll: bool = True) -> None:
        self._cursor_tick = max(0, tick)

    def sync_x_with(self, _target: HeadlessCanvas) -> None:  # pragma: no cover
        pass

    def set_tempo_markers(self, markers: Sequence[tuple[int, str]]) -> None:
        self._tempo_markers = tuple(markers)
        geometry = self._current_geometry()
        base_y = max(
            24.0,
            geometry.note_y(self.max_midi)
            + min(self.px_per_note * 0.4, 14.0)
            - 18.0,
        )
        self.canvas.set_tempo_markers(
            self._tempo_markers,
            left_pad=self.LEFT_PAD,
            px_per_tick=self.px_per_tick,
            base_y=base_y,
            left_padding=ROLL_TEMPO_LEFT_PADDING,
            barline_padding=ROLL_TEMPO_BARLINE_PADDING,
        )

    def _current_geometry(self) -> SimpleNamespace:
        base_y = 36.0

        def _note_y(_midi: int) -> float:
            return base_y

        return SimpleNamespace(note_y=_note_y)

    def set_zoom(self, _delta: int) -> None:  # pragma: no cover
        pass

    def set_time_zoom(self, _multiplier: float) -> None:  # pragma: no cover
        pass

    def set_loop_region(self, start_tick: int, end_tick: int, visible: bool) -> None:
        self.loop_region = (start_tick, end_tick, visible)


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
    _last_y_top: float = 42.0

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

    def render(
        self,
        events: Sequence[NoteEvent],
        pulses_per_quarter: int,
        beats: int,
        beat_type: int,
    ) -> None:
        self._cached = (events, pulses_per_quarter, beats, beat_type)

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

    def set_tempo_markers(self, markers: Sequence[tuple[int, str]]) -> None:
        self._tempo_markers = tuple(markers)

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
