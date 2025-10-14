from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Direction = Literal["up", "down"]
Source = Literal["octave-shift", "ottava", "micro-edit"]


def _normalize_size(size: int) -> int:
    if size <= 0:
        return 8
    # MusicXML commonly uses 8, 15, or 22. Map to octaves by rounding to the nearest multiple of 7.
    octaves = max(1, round(size / 7.0))
    return int(octaves * 8)


@dataclass(frozen=True)
class OttavaShift:
    source: Source
    direction: Direction
    size: int = 8
    number: str | None = None

    def __post_init__(self) -> None:
        if self.direction not in {"up", "down"}:
            raise ValueError("direction must be 'up' or 'down'")
        normalized = _normalize_size(self.size)
        object.__setattr__(self, "size", normalized)

    @property
    def semitones(self) -> int:
        octaves = max(1, self.size // 8)
        return 12 * octaves if self.direction == "up" else -12 * octaves

    def describe(self) -> str:
        label = "8va" if self.direction == "up" else "8vb"
        if self.size >= 16:
            factor = round(self.size / 8)
            label = f"{factor * 8}{'ma' if self.direction == 'up' else 'mb'}"
        return f"{self.source}:{label}" if self.source != "micro-edit" else f"micro:{label}"


__all__ = ["OttavaShift"]
