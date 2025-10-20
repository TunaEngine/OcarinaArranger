"""Helpers for interpreting and allocating grace notes from MusicXML."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple
import xml.etree.ElementTree as ET

from shared.ottava import OttavaShift


__all__ = [
    "GraceSettings",
    "_PendingGrace",
    "_classify_grace",
    "_tempo_scale",
    "_allocate_grace_durations",
    "_fold_grace_midi",
]


@dataclass(frozen=True)
class GraceSettings:
    """Configuration for realizing buffered grace notes."""

    policy: str = "tempo-weighted"
    fractions: Tuple[float, ...] = (0.125, 0.08333333333333333, 0.0625)
    max_chain: int = 3
    fold_out_of_range: bool = True
    drop_out_of_range: bool = True
    slow_tempo_bpm: float = 60.0
    fast_tempo_bpm: float = 132.0

    def __post_init__(self) -> None:
        policy = (self.policy or "tempo-weighted").strip().lower()
        object.__setattr__(self, "policy", policy or "tempo-weighted")

        if self.max_chain <= 0:
            object.__setattr__(self, "max_chain", 0)

        normalized: List[float] = []
        for value in self.fractions:
            try:
                normalized.append(max(0.0, float(value)))
            except (TypeError, ValueError):
                continue
        if not normalized:
            normalized = [0.125]
        object.__setattr__(self, "fractions", tuple(normalized))

        slow = float(self.slow_tempo_bpm)
        fast = float(self.fast_tempo_bpm)
        if fast < slow:
            slow, fast = fast, slow
        object.__setattr__(self, "slow_tempo_bpm", max(1.0, slow))
        object.__setattr__(self, "fast_tempo_bpm", max(self.slow_tempo_bpm, fast))


@dataclass
class _PendingGrace:
    midi: int
    ottava_shifts: Tuple[OttavaShift, ...]
    grace_type: str | None


def _classify_grace(grace_el: ET.Element | None) -> str | None:
    if grace_el is None:
        return None
    slash = (grace_el.get("slash") or "").strip().lower()
    if slash in {"true", "yes", "1"}:
        return "acciaccatura"
    return "appoggiatura"


def _tempo_scale(tempo_bpm: float | int | None, settings: GraceSettings) -> float:
    if settings.policy != "tempo-weighted":
        return 1.0
    try:
        tempo = float(tempo_bpm) if tempo_bpm is not None else settings.fast_tempo_bpm
    except (TypeError, ValueError):
        tempo = settings.fast_tempo_bpm
    if tempo <= settings.slow_tempo_bpm:
        return 1.0
    if tempo >= settings.fast_tempo_bpm:
        return 0.5
    span = settings.fast_tempo_bpm - settings.slow_tempo_bpm
    ratio = (tempo - settings.slow_tempo_bpm) / span
    return max(0.5, 1.0 - 0.5 * ratio)


def _allocate_grace_durations(
    total_ticks: int,
    count: int,
    tempo_bpm: float | int | None,
    settings: GraceSettings,
) -> list[int]:
    if count <= 0 or total_ticks <= 1 or settings.max_chain == 0:
        return []
    available = max(0, int(total_ticks) - 1)
    if available <= 0:
        return []

    scale = _tempo_scale(tempo_bpm, settings)
    durations: list[int] = []
    remaining = available
    for index in range(count):
        fraction_index = min(index, len(settings.fractions) - 1)
        fraction = settings.fractions[fraction_index] * scale
        raw = int(round(total_ticks * fraction))
        minimum_remaining = max(0, count - index - 1)
        if minimum_remaining >= remaining:
            assigned = 1
        else:
            assigned = max(1, min(remaining - minimum_remaining, raw))
        durations.append(assigned)
        remaining -= assigned
        if remaining <= 0 and index < count - 1:
            break
    return durations


def _fold_grace_midi(
    midi: int,
    principal_midi: int | None,
    settings: GraceSettings,
) -> int | None:
    value = int(midi)
    if settings.fold_out_of_range and principal_midi is not None:
        while value - principal_midi > 12:
            value -= 12
        while principal_midi - value > 12:
            value += 12
    if 0 <= value <= 127:
        return value
    if settings.fold_out_of_range:
        while value < 0:
            value += 12
        while value > 127:
            value -= 12
    if 0 <= value <= 127:
        return value
    if settings.drop_out_of_range:
        return None
    return value
