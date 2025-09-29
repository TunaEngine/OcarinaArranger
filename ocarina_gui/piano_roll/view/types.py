"""Shared typing helpers for the piano roll view package."""

from __future__ import annotations

from typing import Protocol


class SupportsGeometry(Protocol):
    """Minimal protocol satisfied by ``RenderGeometry``."""

    min_midi: int
    max_midi: int

    def tick_to_x(self, tick: int, total_ticks: int) -> int:
        ...

    def x_to_tick(self, x: int, total_ticks: int) -> int | None:
        ...

    def midi_from_y(self, y: int) -> int | None:
        ...

    def note_y(self, midi: int) -> int:
        ...
