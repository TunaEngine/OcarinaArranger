"""Configuration objects for the best-effort arranger domain layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

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
    "register_instrument_range",
    "get_instrument_range",
    "clear_instrument_registry",
]
