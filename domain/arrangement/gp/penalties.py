"""Shared dataclasses for tuning GP scoring penalties."""

from __future__ import annotations

from dataclasses import dataclass

PENALTY_DISABLE_WEIGHT = 5.0
RHYTHM_SIMPLIFY_DISABLE_WEIGHT = PENALTY_DISABLE_WEIGHT


@dataclass(frozen=True)
class ScoringPenalties:
    """Tunable weights applied when ranking GP instrument candidates."""

    fidelity_weight: float = 3.0
    range_clamp_penalty: float = 5.0
    range_clamp_melody_bias: float = 4.0
    melody_shift_weight: float = 2.0
    rhythm_simplify_weight: float = 5.0

    def allow_rhythm_simplify(self) -> bool:
        """Return ``True`` when SimplifyRhythm primitives may be generated."""

        return self.rhythm_simplify_weight < RHYTHM_SIMPLIFY_DISABLE_WEIGHT

    def allow_melody_shift(self) -> bool:
        """Return ``True`` when LocalOctave primitives may be generated."""

        return self.melody_shift_weight < PENALTY_DISABLE_WEIGHT

    def allow_range_clamp(self) -> bool:
        """Return ``True`` when range-clamped spans may be considered."""

        return (
            self.range_clamp_penalty < PENALTY_DISABLE_WEIGHT
            and self.range_clamp_melody_bias < PENALTY_DISABLE_WEIGHT
        )

    def allow_fidelity_edits(self) -> bool:
        """Return ``True`` when non-transpose edits may be explored."""

        return self.fidelity_weight < PENALTY_DISABLE_WEIGHT


__all__ = [
    "PENALTY_DISABLE_WEIGHT",
    "RHYTHM_SIMPLIFY_DISABLE_WEIGHT",
    "ScoringPenalties",
]
