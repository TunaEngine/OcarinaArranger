from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Callable, Optional, Sequence, Tuple

from ocarina_tools import NoteEvent

from .containers import HeadlessCanvas
from ocarina_gui.piano_roll.view.tempo_markers import (
    _TEMPO_MARKER_BARLINE_PADDING as ROLL_TEMPO_BARLINE_PADDING,
    _TEMPO_MARKER_LEFT_PADDING as ROLL_TEMPO_LEFT_PADDING,
)


class _DefaultRollPalette(SimpleNamespace):
    def __init__(self) -> None:
        super().__init__(
            natural_row_fill="#f0f0f0",
            accidental_row_fill="#d8d8d8",
            note_fill_natural="#4c8bf5",
            note_fill_sharp="#2f5fb3",
            note_label_text="#1a1a1a",
            grid_line="#808080",
        )


_ACCIDENTAL_STEPS = {1, 3, 6, 8, 10}


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
    min_midi: int = 60
    max_midi: int = 84
    _tempo_markers: Tuple[tuple[int, str], ...] = ()
    _tempo_marker_items: list[int] = field(default_factory=list)
    total_ticks: int = 0
    _total_ticks: int = 0
    _time_scroll_orientation: str = "horizontal"
    _palette: SimpleNamespace = field(default_factory=_DefaultRollPalette)
    _background_items: list[int] = field(default_factory=list)
    _note_items: list[int] = field(default_factory=list)
    _measure_items: list[int] = field(default_factory=list)
    _measure_number_items: list[int] = field(default_factory=list)
    _wrap_layout: SimpleNamespace | None = None

    def set_range(self, minimum: int, maximum: int) -> None:  # pragma: no cover - stored for completeness
        self.range = (minimum, maximum)

    def render(
        self,
        events: Sequence[NoteEvent],
        pulses_per_quarter: int,
        *,
        beats: int = 4,
        beat_unit: int = 4,
        total_ticks: int | None = None,
    ) -> None:
        self._cached = (events, pulses_per_quarter, beats, beat_unit)
        if self._fingering_cb:
            self._fingering_cb(None)
        processed: list[tuple[int, int, int]] = []
        computed_total = int(total_ticks or 0)
        for event in events:
            tick, duration, midi = self._coerce_event(event)
            processed.append((tick, duration, midi))
            computed_total = max(computed_total, tick + duration)
        self.total_ticks = computed_total
        self._total_ticks = computed_total
        self.canvas.clear()
        self._tempo_marker_items = []
        palette = self._palette
        natural_fill = getattr(palette, "natural_row_fill", "#f0f0f0")
        accidental_fill = getattr(palette, "accidental_row_fill", "#d8d8d8")
        note_natural = getattr(palette, "note_fill_natural", "#4c8bf5")
        note_accidental = getattr(palette, "note_fill_sharp", "#2f5fb3")
        label_fill = getattr(palette, "note_label_text", "#1a1a1a")
        grid_fill = getattr(palette, "grid_line", "#808080")
        width = self.LEFT_PAD + max(1, self.total_ticks) * max(self.px_per_tick, 0.1) + 40.0
        self._background_items = [
            self.canvas.create_rectangle(
                0.0,
                index * self.px_per_note,
                width,
                index * self.px_per_note + self.px_per_note,
                fill=natural_fill if index == 0 else accidental_fill,
                tags=("row_background", "row_natural" if index == 0 else "row_accidental"),
            )
            for index in range(2)
        ]
        self._note_items = []
        for tick, duration, midi in processed:
            fill = note_accidental if self._is_accidental(midi) else note_natural
            y_base = (midi % 2) * (self.px_per_note * 0.9)
            note_height = self.px_per_note * 0.8
            y1 = y_base
            y2 = y_base + note_height
            x1 = self.LEFT_PAD + tick * self.px_per_tick
            x2 = x1 + max(1, duration) * self.px_per_tick
            rect_id = self.canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill=fill,
                tags=("note_rect",),
            )
            self._note_items.append(rect_id)
            label_id = self.canvas.create_text(
                (x1 + x2) / 2.0,
                y1 + note_height / 2.0,
                text=self._label_for_midi(midi),
                fill=label_fill,
                tags=("note_value_label",),
            )
            self._note_items.append(label_id)
        measure_ticks = self._measure_length_ticks(pulses_per_quarter, beats, beat_unit)
        layout_lines: list[SimpleNamespace] = []
        if self._time_scroll_orientation == "vertical":
            layout_lines = self._build_wrap_layout(self.total_ticks, measure_ticks)
            ticks_per_line = layout_lines[0].ticks_per_line if layout_lines else max(1, self.total_ticks)
            self._wrap_layout = SimpleNamespace(lines=layout_lines, ticks_per_line=ticks_per_line)
        else:
            self._wrap_layout = None
        self._measure_items = []
        self._measure_number_items = []
        if measure_ticks > 0:
            measure_count = max(1, (self.total_ticks + measure_ticks - 1) // measure_ticks)
            for measure_index in range(measure_count + 1):
                tick = measure_index * measure_ticks
                x = self.LEFT_PAD + tick * self.px_per_tick
                if layout_lines:
                    line_index = min(len(layout_lines) - 1, measure_index % len(layout_lines))
                    info = layout_lines[line_index]
                    y_top = info.y_top
                    y_bottom = info.y_bottom
                    tags = ("measure_line", f"wrapped_line_{line_index}")
                else:
                    y_top = 0.0
                    y_bottom = self.px_per_note * 2.0
                    tags = ("measure_line",)
                line_id = self.canvas.create_line(
                    x,
                    y_top,
                    x,
                    y_bottom,
                    fill=grid_fill,
                    tags=tags,
                )
                self._measure_items.append(line_id)
                if measure_index > 0:
                    number_id = self.canvas.create_text(
                        x + 4.0,
                        y_top,
                        text=str(measure_index + 1),
                        fill=label_fill,
                        tags=("measure_number",),
                    )
                    self._measure_number_items.append(number_id)

    def _measure_length_ticks(self, pulses_per_quarter: int, beats: int, beat_unit: int) -> int:
        if pulses_per_quarter <= 0 or beats <= 0 or beat_unit <= 0:
            return 0
        numerator = pulses_per_quarter * beats * 4
        return max(1, numerator // beat_unit)

    def _coerce_event(self, event: NoteEvent | tuple[object, ...]) -> tuple[int, int, int]:
        if isinstance(event, tuple) and len(event) >= 3:
            tick, duration, midi = event[0], event[1], event[2]
        else:
            tick = getattr(event, "tick", getattr(event, "start", 0))
            duration = getattr(event, "duration", getattr(event, "length", 0))
            midi = getattr(event, "midi", getattr(event, "note", getattr(event, "pitch", self.min_midi)))
        try:
            tick_value = int(tick)
        except (TypeError, ValueError):
            tick_value = 0
        try:
            duration_value = int(duration)
        except (TypeError, ValueError):
            duration_value = 0
        duration_value = max(1, duration_value)
        try:
            midi_value = int(midi)
        except (TypeError, ValueError):
            midi_value = self.min_midi
        return tick_value, duration_value, midi_value

    @staticmethod
    def _is_accidental(midi: int) -> bool:
        return midi % 12 in _ACCIDENTAL_STEPS

    def _label_for_midi(self, midi: int) -> str:
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = int(midi // 12) - 1
        try:
            name = note_names[midi % 12]
        except Exception:
            name = "C"
        return f"{name}{octave}"

    def _build_wrap_layout(self, total_ticks: int, measure_ticks: int) -> list[SimpleNamespace]:
        if total_ticks <= 0:
            total_ticks = max(1, measure_ticks or 1)
        line_count = 2 if total_ticks > 0 else 1
        ticks_per_line = max(1, total_ticks // line_count)
        if ticks_per_line <= 0:
            ticks_per_line = max(1, measure_ticks or 1)
        line_height = self.px_per_note * 4.0
        gap = 20.0
        lines: list[SimpleNamespace] = []
        current_y = 0.0
        start_tick = 0
        for index in range(line_count):
            end_tick = min(total_ticks, start_tick + ticks_per_line)
            if index == line_count - 1:
                end_tick = max(end_tick, total_ticks)
            lines.append(
                SimpleNamespace(
                    y_top=current_y,
                    y_bottom=current_y + line_height,
                    start_tick=start_tick,
                    end_tick=end_tick,
                    ticks_per_line=ticks_per_line,
                )
            )
            current_y += line_height + gap
            start_tick = end_tick
        return lines

    def _on_canvas_configure(self, event: SimpleNamespace) -> None:
        if self._time_scroll_orientation != "vertical" or self._wrap_layout is None:
            return
        width = getattr(event, "width", None)
        try:
            width_value = float(width)
        except (TypeError, ValueError):
            return
        if width_value <= 0:
            return
        current_ticks = max(1, getattr(self._wrap_layout, "ticks_per_line", 0))
        increment = max(1, int(width_value // 50))
        new_ticks = current_ticks + increment
        updated_lines: list[SimpleNamespace] = []
        for line in getattr(self._wrap_layout, "lines", []):
            updated_lines.append(
                SimpleNamespace(
                    y_top=line.y_top,
                    y_bottom=line.y_bottom,
                    start_tick=line.start_tick,
                    end_tick=line.end_tick,
                    ticks_per_line=new_ticks,
                )
            )
        if updated_lines:
            self._wrap_layout = SimpleNamespace(lines=updated_lines, ticks_per_line=new_ticks)

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
        self._tempo_marker_items = list(self.canvas.find_withtag("tempo_marker"))

    def _current_geometry(self) -> SimpleNamespace:
        base_y = 36.0

        def _note_y(_midi: int) -> float:
            return base_y

        return SimpleNamespace(note_y=_note_y)

    def set_zoom(self, delta: int) -> None:  # pragma: no cover
        self.px_per_note = max(1.0, self.px_per_note + (delta * 0.5))

    def set_time_zoom(self, multiplier: float) -> None:  # pragma: no cover
        if multiplier > 0:
            updated = self.px_per_tick * multiplier
            self.px_per_tick = max(0.1, min(5.0, updated))
        if self._tempo_markers:
            self.set_tempo_markers(self._tempo_markers)

    def set_time_scroll_orientation(self, orientation: str) -> None:  # pragma: no cover
        normalized = str(orientation).strip().lower()
        if normalized not in {"horizontal", "vertical"}:
            raise ValueError(f"Unsupported orientation: {orientation}")
        self._time_scroll_orientation = normalized

    def apply_palette(self, palette: object) -> None:  # pragma: no cover
        if palette is None or not hasattr(palette, "natural_row_fill"):
            self._palette = _DefaultRollPalette()
        else:
            self._palette = palette

    def set_loop_region(self, start_tick: int, end_tick: int, visible: bool) -> None:
        self.loop_region = (start_tick, end_tick, visible)

