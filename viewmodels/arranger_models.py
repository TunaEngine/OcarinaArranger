"""Shared arranger data structures used by the view-model and UI."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional


GP_APPLY_RANKED = "ranked"
GP_APPLY_SESSION_WINNER = "session_winner"
GP_APPLY_OPTIONS = (GP_APPLY_RANKED, GP_APPLY_SESSION_WINNER)

GP_APPLY_LABELS = {
    GP_APPLY_RANKED: "Use ranked candidate",
    GP_APPLY_SESSION_WINNER: "Use session winner",
}


GP_RECOMMENDED_LIMITS = {
    "generations": 50,
    "population_size": 64,
    "archive_size": 64,
    "random_program_count": 64,
}

_GP_LIMIT_LABELS = {
    "generations": "generations",
    "population_size": "population size",
    "archive_size": "archive size",
    "random_program_count": "random programs",
}


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
class ArrangerGPSettings:
    """Expose tunable parameters for the GP arranger pipeline."""

    generations: int = 10
    population_size: int = 15
    time_budget_seconds: float | None = None
    archive_size: int = 8
    random_program_count: int = 8
    crossover_rate: float = 0.8
    mutation_rate: float = 0.2
    log_best_programs: int = 3
    random_seed: int = 0
    playability_weight: float = 1.0
    fidelity_weight: float = 1.8
    tessitura_weight: float = 1.0
    program_size_weight: float = 1.0
    contour_weight: float = 0.35
    lcs_weight: float = 0.65
    pitch_weight: float = 0.3
    fidelity_priority_weight: float = 3.0
    range_clamp_penalty: float = 4.9
    range_clamp_melody_bias: float = 4.0
    melody_shift_weight: float = 2.0
    rhythm_simplify_weight: float = 5.0
    apply_program_preference: str = GP_APPLY_SESSION_WINNER

    def normalized(self) -> "ArrangerGPSettings":
        """Return a configuration with sane, non-negative limits."""

        def _clamp_int(value: int, *, minimum: int, maximum: int) -> int:
            if value < minimum:
                return minimum
            if value > maximum:
                return maximum
            return value

        def _clamp_rate(value: float, *, minimum: float = 0.0, maximum: float = 1.0) -> float:
            if value < minimum:
                return minimum
            if value > maximum:
                return maximum
            return value

        def _non_negative(value: float, fallback: float) -> float:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                return fallback
            return numeric if numeric >= 0.0 else 0.0

        generations = _clamp_int(int(self.generations), minimum=1, maximum=250)
        population_size = _clamp_int(int(self.population_size), minimum=1, maximum=640)

        archive_size = _clamp_int(int(self.archive_size), minimum=1, maximum=640)
        if archive_size > population_size:
            archive_size = population_size

        random_program_count = _clamp_int(
            int(self.random_program_count), minimum=0, maximum=640
        )
        if random_program_count > population_size:
            random_program_count = population_size

        crossover_rate = _clamp_rate(float(self.crossover_rate))
        mutation_rate = _clamp_rate(float(self.mutation_rate))
        if crossover_rate == 0.0 and mutation_rate == 0.0:
            mutation_rate = 0.1

        log_best_programs = _clamp_int(int(self.log_best_programs), minimum=1, maximum=320)
        random_seed = int(self.random_seed)
        if random_seed < 0:
            random_seed = 0

        playability_weight = _non_negative(self.playability_weight, 1.0)
        fidelity_weight = _non_negative(self.fidelity_weight, 1.8)
        tessitura_weight = _non_negative(self.tessitura_weight, 1.0)
        program_size_weight = _non_negative(self.program_size_weight, 1.0)
        contour_weight = _non_negative(self.contour_weight, 0.35)
        lcs_weight = _non_negative(self.lcs_weight, 0.65)
        pitch_weight = _non_negative(self.pitch_weight, 0.3)
        fidelity_priority_weight = _non_negative(
            self.fidelity_priority_weight, 3.0
        )
        range_clamp_penalty = _non_negative(self.range_clamp_penalty, 4.9)
        range_clamp_melody_bias = _non_negative(
            self.range_clamp_melody_bias, 4.0
        )
        melody_shift_weight = _non_negative(self.melody_shift_weight, 2.0)
        rhythm_simplify_weight = _non_negative(self.rhythm_simplify_weight, 5.0)
        if contour_weight + lcs_weight + pitch_weight == 0:
            contour_weight, lcs_weight, pitch_weight = 0.35, 0.65, 0.3

        raw_budget = self.time_budget_seconds
        if raw_budget is None or raw_budget == "":
            budget_seconds: float | None = None
        else:
            try:
                budget_seconds = float(raw_budget)
            except (TypeError, ValueError):
                budget_seconds = None
            if budget_seconds is not None and budget_seconds < 0.0:
                budget_seconds = 0.0

        preference = str(self.apply_program_preference or "").strip().lower()
        if preference not in GP_APPLY_OPTIONS:
            preference = GP_APPLY_SESSION_WINNER

        return replace(
            self,
            generations=generations,
            population_size=population_size,
            time_budget_seconds=budget_seconds,
            archive_size=archive_size,
            random_program_count=random_program_count,
            crossover_rate=crossover_rate,
            mutation_rate=mutation_rate,
            log_best_programs=log_best_programs,
            random_seed=random_seed,
            playability_weight=playability_weight,
            fidelity_weight=fidelity_weight,
            tessitura_weight=tessitura_weight,
            program_size_weight=program_size_weight,
            contour_weight=contour_weight,
            lcs_weight=lcs_weight,
            pitch_weight=pitch_weight,
            fidelity_priority_weight=fidelity_priority_weight,
            range_clamp_penalty=range_clamp_penalty,
            range_clamp_melody_bias=range_clamp_melody_bias,
            melody_shift_weight=melody_shift_weight,
            rhythm_simplify_weight=rhythm_simplify_weight,
            apply_program_preference=preference,
        )


def gp_settings_warning(settings: ArrangerGPSettings) -> str:
    """Describe which GP knobs exceed the recommended range, if any."""

    normalized = settings.normalized()
    exceeded: list[str] = []
    for key, limit in GP_RECOMMENDED_LIMITS.items():
        value = getattr(normalized, key)
        if value > limit:
            label = _GP_LIMIT_LABELS[key]
            exceeded.append(f"{label} {value} (recommended ≤ {limit})")

    if not exceeded:
        return ""

    details = ", ".join(exceeded)
    return (
        "Warning: high GP settings may dramatically increase runtime: "
        f"{details}."
    )


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
    "ArrangerGPSettings",
    "ArrangerBudgetSettings",
    "ArrangerEditBreakdown",
    "ArrangerExplanationRow",
    "ArrangerInstrumentSummary",
    "ArrangerResultSummary",
    "ArrangerTelemetryHint",
    "GP_RECOMMENDED_LIMITS",
    "GP_APPLY_LABELS",
    "GP_APPLY_OPTIONS",
    "GP_APPLY_RANKED",
    "GP_APPLY_SESSION_WINNER",
    "gp_settings_warning",
]
