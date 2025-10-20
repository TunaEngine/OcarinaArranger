"""GP-specific helpers for arranger preview computations."""

from __future__ import annotations

from typing import Mapping, Sequence

from domain.arrangement.api import summarize_difficulty
from domain.arrangement.config import GraceSettings
from domain.arrangement.difficulty import difficulty_score
from domain.arrangement.gp import GPSessionConfig, GPInstrumentCandidate, GlobalTranspose
from domain.arrangement.gp.penalties import ScoringPenalties
from domain.arrangement.gp.fitness import FidelityConfig, FitnessConfig, FitnessObjective

from viewmodels.arranger_models import (
    ArrangerEditBreakdown,
    ArrangerExplanationRow,
    ArrangerInstrumentSummary,
    ArrangerResultSummary,
    ArrangerTelemetryHint,
)

from .arranger_preview_utils import _normalize_difficulty


def _gp_session_config(settings) -> GPSessionConfig:
    normalized = settings.normalized()
    base = GPSessionConfig()
    archive_size = normalized.archive_size or base.archive_size
    archive_size = max(1, min(archive_size, normalized.population_size))
    random_program_count = normalized.random_program_count or base.random_program_count
    random_program_count = max(0, min(random_program_count, normalized.population_size))

    crossover_rate = normalized.crossover_rate
    mutation_rate = normalized.mutation_rate
    if crossover_rate == 0.0 and mutation_rate == 0.0:
        mutation_rate = base.mutation_rate

    base_fitness = base.fitness_config or FitnessConfig()
    fitness_config = FitnessConfig(
        playability=FitnessObjective(
            weight=normalized.playability_weight,
            normalizer=base_fitness.playability.normalizer,
        ),
        fidelity=FitnessObjective(
            weight=normalized.fidelity_weight,
            normalizer=base_fitness.fidelity.normalizer,
        ),
        tessitura=FitnessObjective(
            weight=normalized.tessitura_weight,
            normalizer=base_fitness.tessitura.normalizer,
        ),
        program_size=FitnessObjective(
            weight=normalized.program_size_weight,
            normalizer=base_fitness.program_size.normalizer,
        ),
        fidelity_components=FidelityConfig(
            contour_weight=normalized.contour_weight,
            lcs_weight=normalized.lcs_weight,
            pitch_weight=normalized.pitch_weight,
            contour_normalizer=base_fitness.fidelity_components.contour_normalizer,
            lcs_normalizer=base_fitness.fidelity_components.lcs_normalizer,
            pitch_normalizer=base_fitness.fidelity_components.pitch_normalizer,
        ),
    )

    return GPSessionConfig(
        generations=normalized.generations,
        population_size=normalized.population_size,
        archive_size=max(1, archive_size),
        random_seed=normalized.random_seed,
        random_program_count=max(0, random_program_count),
        crossover_rate=crossover_rate,
        mutation_rate=mutation_rate,
        log_best_programs=max(1, normalized.log_best_programs),
        span_limits=base.span_limits,
        constraints=base.constraints,
        fitness_config=fitness_config,
        time_budget_seconds=normalized.time_budget_seconds,
        scoring_penalties=ScoringPenalties(
            fidelity_weight=normalized.fidelity_priority_weight,
            range_clamp_penalty=normalized.range_clamp_penalty,
            range_clamp_melody_bias=normalized.range_clamp_melody_bias,
            melody_shift_weight=normalized.melody_shift_weight,
            rhythm_simplify_weight=normalized.rhythm_simplify_weight,
        ),
    )


def _gp_instrument_summary(
    candidate: GPInstrumentCandidate,
    name_map: Mapping[str, str],
    winner_id: str,
    *,
    transposition_offset: int = 0,
) -> ArrangerInstrumentSummary:
    easy, medium, hard, very_hard, tessitura, _ = _normalize_difficulty(candidate.difficulty)
    return ArrangerInstrumentSummary(
        instrument_id=candidate.instrument_id,
        instrument_name=name_map.get(candidate.instrument_id, candidate.instrument_id),
        easy=easy,
        medium=medium,
        hard=hard,
        very_hard=very_hard,
        tessitura=tessitura,
        transposition=_gp_transposition(candidate.program) + transposition_offset,
        is_winner=candidate.instrument_id == winner_id,
    )


def _gp_result_summary(
    original_span,
    candidate: GPInstrumentCandidate,
    name_map: Mapping[str, str],
    *,
    threshold: float,
    transposition_offset: int = 0,
    grace_settings: GraceSettings,
) -> ArrangerResultSummary:
    easy, medium, hard, very_hard, tessitura, _ = _normalize_difficulty(candidate.difficulty)
    starting_summary = summarize_difficulty(
        original_span, candidate.instrument, grace_settings=grace_settings
    )
    start_score = difficulty_score(starting_summary, grace_settings=grace_settings)
    final_score = difficulty_score(candidate.difficulty, grace_settings=grace_settings)
    return ArrangerResultSummary(
        instrument_id=candidate.instrument_id,
        instrument_name=name_map.get(candidate.instrument_id, candidate.instrument_id),
        transposition=_gp_transposition(candidate.program) + transposition_offset,
        easy=easy,
        medium=medium,
        hard=hard,
        very_hard=very_hard,
        tessitura=tessitura,
        starting_difficulty=start_score,
        final_difficulty=final_score,
        difficulty_threshold=threshold,
        met_threshold=final_score <= threshold,
        difficulty_delta=start_score - final_score,
        applied_steps=_gp_applied_steps(candidate.program),
        edits=ArrangerEditBreakdown(),
    )


def _gp_explanations(candidate: GPInstrumentCandidate) -> tuple[ArrangerExplanationRow, ...]:
    rows: list[ArrangerExplanationRow] = []
    for event in candidate.explanations:
        rows.append(
            ArrangerExplanationRow(
                bar=event.bar,
                action=event.action,
                reason=event.reason,
                reason_code=event.reason_code,
                difficulty_delta=event.difficulty_delta,
                before_note_count=len(event.before.notes),
                after_note_count=len(event.after.notes),
                span_id=event.span_id,
                span=event.span,
                key_id=event.key_id,
            )
        )
    return tuple(rows)


def _gp_telemetry(
    result,
    config: GPSessionConfig,
) -> tuple[ArrangerTelemetryHint, ...]:
    hints: list[ArrangerTelemetryHint] = [
        ArrangerTelemetryHint(
            category="GP Session",
            message=(
                f"Completed {result.session.generations} generation(s) "
                f"in {result.session.elapsed_seconds:.2f}s "
                f"(termination: {result.termination_reason})."
            ),
        ),
        ArrangerTelemetryHint(
            category="GP Session",
            message=(
                f"Population {config.population_size}; archive kept "
                f"{len(result.archive_summary)}/{config.archive_size} program(s)."
            ),
        ),
    ]
    if config.time_budget_seconds is not None:
        hints.append(
            ArrangerTelemetryHint(
                category="GP Session",
                message=f"Time budget {config.time_budget_seconds:.1f}s configured.",
            )
        )
    if result.fallback is not None:
        hints.append(
            ArrangerTelemetryHint(
                category="Fallback",
                message=(
                    "Best-effort arranger fallback winner: "
                    f"{result.fallback.chosen.instrument_id}."
                ),
            )
        )
    return tuple(hints)


def _gp_transposition(program: Sequence) -> int:
    shift = 0
    for operation in program:
        if isinstance(operation, GlobalTranspose):
            try:
                shift += int(operation.semitones)
            except (TypeError, ValueError):
                continue
    return shift


def _gp_applied_steps(program: Sequence) -> tuple[str, ...]:
    steps: list[str] = []
    for operation in program:
        label = operation.__class__.__name__
        if isinstance(operation, GlobalTranspose):
            try:
                semitones = int(operation.semitones)
            except (TypeError, ValueError):
                semitones = 0
            label = f"GlobalTranspose({semitones:+d})"
        steps.append(label)
    return tuple(steps)


__all__ = [
    "_gp_session_config",
    "_gp_instrument_summary",
    "_gp_result_summary",
    "_gp_explanations",
    "_gp_telemetry",
    "_gp_transposition",
    "_gp_applied_steps",
]
