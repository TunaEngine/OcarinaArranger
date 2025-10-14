from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .phrase import PhraseSpan


@dataclass(frozen=True)
class InstrumentRange:
    """Describe the playable range and comfortable center for an instrument."""

    min_midi: int
    max_midi: int
    comfort_center: float | None = None

    def __post_init__(self) -> None:
        if self.min_midi > self.max_midi:
            raise ValueError("min_midi must be <= max_midi")
        if self.comfort_center is None:
            center = (self.min_midi + self.max_midi) / 2.0
            object.__setattr__(self, "comfort_center", center)

    @property
    def span(self) -> int:
        return max(1, self.max_midi - self.min_midi)


@dataclass(frozen=True)
class KeySearchWeights:
    rho: float = 0.6
    sigma: float = 0.6
    tau: float = 0.1


@dataclass(frozen=True)
class KeyFit:
    transposition: int
    in_range_ratio: float
    time_above_high: float
    time_below_low: float
    tessitura_spread: float
    score: float


def _normalized_duration_ratios(span: PhraseSpan, transposition: int, instrument: InstrumentRange) -> tuple[float, float, float]:
    total_duration = sum(note.duration for note in span.notes)
    if total_duration <= 0:
        return 0.0, 0.0, 0.0

    in_range = 0
    above = 0
    below = 0
    low = instrument.min_midi
    high = instrument.max_midi

    for note in span.notes:
        midi = note.midi + transposition
        duration = note.duration
        if midi < low:
            below += duration
        elif midi > high:
            above += duration
        else:
            in_range += duration

    ratio = in_range / total_duration
    return ratio, above / total_duration, below / total_duration


def _tessitura_spread(span: PhraseSpan, transposition: int, instrument: InstrumentRange) -> float:
    total_duration = sum(note.duration for note in span.notes)
    if total_duration <= 0:
        return 0.0

    center = instrument.comfort_center or (instrument.min_midi + instrument.max_midi) / 2.0
    weighted = 0.0
    for note in span.notes:
        midi = note.midi + transposition
        weighted += note.duration * abs(midi - center)
    normalized = weighted / total_duration
    return normalized / instrument.span


def _score_transposition(span: PhraseSpan, transposition: int, instrument: InstrumentRange, weights: KeySearchWeights) -> KeyFit:
    in_range_ratio, above_ratio, below_ratio = _normalized_duration_ratios(span, transposition, instrument)
    spread = _tessitura_spread(span, transposition, instrument)
    score = in_range_ratio - (weights.rho * above_ratio) - (weights.sigma * below_ratio) - (weights.tau * spread)
    return KeyFit(
        transposition=transposition,
        in_range_ratio=round(in_range_ratio, 6),
        time_above_high=round(above_ratio, 6),
        time_below_low=round(below_ratio, 6),
        tessitura_spread=round(spread, 6),
        score=score,
    )


def soft_key_search(
    span: PhraseSpan,
    instrument: InstrumentRange,
    *,
    transpositions: Iterable[int] | None = None,
    top_k: int = 2,
    weights: KeySearchWeights | None = None,
) -> list[KeyFit]:
    """Score each candidate transposition and return the best ``top_k`` results."""

    if transpositions is None:
        transpositions = range(-10, 11)
    if top_k <= 0:
        return []

    weight_values = weights or KeySearchWeights()
    fits = [
        _score_transposition(span, transposition, instrument, weight_values)
        for transposition in transpositions
    ]

    fits.sort(
        key=lambda fit: (
            -fit.score,
            fit.time_above_high,
            fit.time_below_low,
            abs(fit.transposition),
            fit.transposition,
        )
    )
    return fits[: min(top_k, len(fits))]


__all__ = [
    "InstrumentRange",
    "KeySearchWeights",
    "KeyFit",
    "soft_key_search",
]
