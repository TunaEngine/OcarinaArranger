"""Shared arranger data structures used by the view-model and UI."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional


@dataclass(frozen=True)
class ArrangerInstrumentSummary:
    """UI-facing snapshot of arranger difficulty metrics for an instrument."""

    instrument_id: str
    instrument_name: str
    easy: float
    medium: float
    hard: float
    very_hard: float
    tessitura: float
    transposition: int = 0
    is_winner: bool = False


@dataclass(frozen=True)
class ArrangerEditBreakdown:
    """Aggregate edit counts applied by the salvage cascade."""

    total: int = 0
    octave: int = 0
    rhythm: int = 0
    substitution: int = 0


@dataclass(frozen=True)
class ArrangerResultSummary:
    """Expose arranger v2 outcome metrics for the summary tab."""

    instrument_id: str
    instrument_name: str
    transposition: int
    easy: float
    medium: float
    hard: float
    very_hard: float
    tessitura: float
    starting_difficulty: float
    final_difficulty: float
    difficulty_threshold: float
    met_threshold: bool
    difficulty_delta: float
    applied_steps: tuple[str, ...] = field(default_factory=tuple)
    edits: ArrangerEditBreakdown = field(default_factory=ArrangerEditBreakdown)


@dataclass(frozen=True)
class ArrangerExplanationRow:
    """Flattened explanation payload for UI display."""

    bar: int
    action: str
    reason: str
    reason_code: str
    difficulty_delta: float
    before_note_count: int
    after_note_count: int
    span_id: str
    span: Optional[str] = None
    key_id: Optional[str] = None


@dataclass(frozen=True)
class ArrangerTelemetryHint:
    """Telemetry insight exposed through the UI telemetry tab."""

    category: str
    message: str


@dataclass(frozen=True)
class ArrangerBudgetSettings:
    """Expose salvage budget ceilings to the UI layer."""

    max_octave_edits: int = 1
    max_rhythm_edits: int = 1
    max_substitutions: int = 1
    max_steps_per_span: int = 3

    def normalized(self) -> "ArrangerBudgetSettings":
        """Return a variant with non-negative integer limits."""

        def _clamp(value: int, minimum: int = 0, maximum: int = 99) -> int:
            if value < minimum:
                return minimum
            if value > maximum:
                return maximum
            return value

        return replace(
            self,
            max_octave_edits=_clamp(int(self.max_octave_edits)),
            max_rhythm_edits=_clamp(int(self.max_rhythm_edits)),
            max_substitutions=_clamp(int(self.max_substitutions)),
            max_steps_per_span=_clamp(int(self.max_steps_per_span), minimum=1),
        )


__all__ = [
    "ArrangerBudgetSettings",
    "ArrangerEditBreakdown",
    "ArrangerExplanationRow",
    "ArrangerInstrumentSummary",
    "ArrangerResultSummary",
    "ArrangerTelemetryHint",
]
