"""Configuration objects for the best-effort arranger domain layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from ocarina_tools import GraceSettings as ImporterGraceSettings

from .soft_key import InstrumentRange


@dataclass(frozen=True)
class FeatureFlags:
    """Toggle experimental arranger features.

    The dynamic-programming octave folding step is gated behind ``dp_slack`` so
    we can stage the rollout and compare behaviour against the existing
    baseline.  Flags default to the conservative behaviour that matches the
    pre-DP pipeline.
    """

    dp_slack: bool = False


DEFAULT_FEATURE_FLAGS = FeatureFlags()


@dataclass(frozen=True)
class GraceSettings:
    """Domain-level settings for realizing and scoring grace notes."""

    policy: str = "tempo-weighted"
    fractions: Tuple[float, ...] = (0.125, 0.08333333333333333, 0.0625)
    max_chain: int = 3
    anchor_min_fraction: float = 0.25
    fold_out_of_range: bool = True
    drop_out_of_range: bool = True
    slow_tempo_bpm: float = 60.0
    fast_tempo_bpm: float = 132.0
    grace_bonus: float = 0.25

    def __post_init__(self) -> None:
        policy = (self.policy or "tempo-weighted").strip().lower()
        object.__setattr__(self, "policy", policy or "tempo-weighted")

        normalized = []
        for value in self.fractions:
            try:
                normalized.append(max(0.0, float(value)))
            except (TypeError, ValueError):
                continue
        if not normalized:
            normalized = [0.125]
        object.__setattr__(self, "fractions", tuple(normalized))

        if self.max_chain < 0:
            object.__setattr__(self, "max_chain", 0)

        anchor_fraction = max(0.0, float(self.anchor_min_fraction))
        object.__setattr__(self, "anchor_min_fraction", min(anchor_fraction, 1.0))

        slow = max(1.0, float(self.slow_tempo_bpm))
        fast = max(slow, float(self.fast_tempo_bpm))
        object.__setattr__(self, "slow_tempo_bpm", slow)
        object.__setattr__(self, "fast_tempo_bpm", fast)

        bonus = max(0.0, float(self.grace_bonus))
        object.__setattr__(self, "grace_bonus", min(1.0, bonus))

    def importer_settings(self) -> ImporterGraceSettings:
        """Return importer-compatible settings for MusicXML parsing."""

        return ImporterGraceSettings(
            policy=self.policy,
            fractions=self.fractions,
            max_chain=self.max_chain,
            fold_out_of_range=self.fold_out_of_range,
            drop_out_of_range=self.drop_out_of_range,
            slow_tempo_bpm=self.slow_tempo_bpm,
            fast_tempo_bpm=self.fast_tempo_bpm,
        )

    def anchor_min_ticks(self, pulses_per_quarter: int) -> int:
        base = max(1, int(pulses_per_quarter))
        return max(1, int(round(base * self.anchor_min_fraction)))


DEFAULT_GRACE_SETTINGS = GraceSettings()


_INSTRUMENT_RANGES: Dict[str, InstrumentRange] = {}


def register_instrument_range(instrument_id: str, instrument: InstrumentRange) -> None:
    """Register ``instrument`` so arrange() can resolve its playable range.

    The domain layer intentionally keeps the registry minimal; production code
    should populate it during application start-up while tests can inject
    temporary ranges.
    """

    instrument_id = instrument_id.strip()
    if not instrument_id:
        raise ValueError("instrument_id must be a non-empty string")
    _INSTRUMENT_RANGES[instrument_id] = instrument


def get_instrument_range(instrument_id: str) -> InstrumentRange:
    """Return the registered range for ``instrument_id``.

    Raises ``KeyError`` if the instrument has not been registered.  Callers can
    wrap the error when translating to higher-level APIs.
    """

    instrument_id = instrument_id.strip()
    if not instrument_id:
        raise ValueError("instrument_id must be a non-empty string")
    try:
        return _INSTRUMENT_RANGES[instrument_id]
    except KeyError as exc:  # pragma: no cover - defensive branch
        raise KeyError(f"Unknown instrument: {instrument_id}") from exc


def clear_instrument_registry() -> None:
    """Remove all registered instruments (intended for tests)."""

    _INSTRUMENT_RANGES.clear()


__all__ = [
    "FeatureFlags",
    "DEFAULT_FEATURE_FLAGS",
    "GraceSettings",
    "DEFAULT_GRACE_SETTINGS",
    "register_instrument_range",
    "get_instrument_range",
    "clear_instrument_registry",
]
