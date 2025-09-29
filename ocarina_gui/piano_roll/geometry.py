"""Geometry helpers for the piano roll widget."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RenderGeometry:
    """Metrics used to translate between ticks, MIDI notes and pixels."""

    min_midi: int
    max_midi: int
    px_per_note: float
    px_per_tick: float
    left_pad: int
    right_pad: int
    label_width: int

    def note_y(self, midi: int) -> float:
        return (self.max_midi - midi) * self.px_per_note + 14

    def midi_from_y(self, y: int) -> Optional[int]:
        top = self.note_y(self.max_midi)
        if y < top:
            return None
        index = int((y - top) // self.px_per_note)
        return self.max_midi - index

    def tick_to_x(self, tick: int, total_ticks: int) -> int:
        clamped = max(0, tick)
        if total_ticks:
            clamped = min(total_ticks, clamped)
        return self.left_pad + int(round(clamped * self.px_per_tick))

    def x_to_tick(self, x: int, total_ticks: int) -> int:
        if x < self.left_pad:
            return 0
        tick = int(round((x - self.left_pad) / max(self.px_per_tick, 1e-6)))
        if total_ticks:
            tick = min(total_ticks, tick)
        return max(0, tick)
