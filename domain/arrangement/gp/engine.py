"""Evaluation and orchestration helpers for the arrangement GP engine."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Sequence, Tuple

from domain.arrangement.config import GraceSettings
from domain.arrangement.difficulty import DifficultySummary, difficulty_score, summarize_difficulty
from domain.arrangement.folding import FoldingResult, FoldingSettings, fold_octaves_with_slack
from domain.arrangement.phrase import PhraseSpan
from domain.arrangement.soft_key import InstrumentRange

from .selection import Individual
from .session_logging import GenerationLog


@dataclass(frozen=True)
class LocalSearchBudgets:
    """Caps applied to the memetic local-search hook."""

    max_total_edits: int | None = None
    max_edits_per_span: int | None = None


@dataclass(frozen=True)
class SpanEvaluation:
    """Difficulty and annotation metadata for a candidate span."""

    index: int
    span: PhraseSpan
    difficulty: DifficultySummary
    annotations: Tuple[str, ...] = ()
    folding: FoldingResult | None = None
    grace_settings: GraceSettings | None = None

    @property
    def playability_penalty(self) -> float:
        return difficulty_score(self.difficulty, grace_settings=self.grace_settings)

    def with_updates(
        self,
        *,
        span: PhraseSpan | None = None,
        difficulty: DifficultySummary | None = None,
        annotations: Tuple[str, ...] | None = None,
        folding: FoldingResult | None = None,
        grace_settings: GraceSettings | None = None,
    ) -> "SpanEvaluation":
        return SpanEvaluation(
            index=self.index,
            span=span or self.span,
            difficulty=difficulty or self.difficulty,
            annotations=self.annotations if annotations is None else annotations,
            folding=folding if folding is not None else self.folding,
            grace_settings=self.grace_settings if grace_settings is None else grace_settings,
        )


@dataclass
class _BudgetTracker:
    budgets: LocalSearchBudgets
    used_total: int
    used_per_span: dict[int, int]

    @classmethod
    def from_evaluations(
        cls, budgets: LocalSearchBudgets, evaluations: Sequence[SpanEvaluation]
    ) -> "_BudgetTracker":
        used_total = sum(len(evaluation.annotations) for evaluation in evaluations)
        used_per_span = {
            evaluation.index: len(evaluation.annotations)
            for evaluation in evaluations
            if evaluation.annotations
        }
        return cls(budgets=budgets, used_total=used_total, used_per_span=used_per_span)

    def can_consume(self, span_index: int) -> bool:
        if self.budgets.max_total_edits is not None and self.used_total >= self.budgets.max_total_edits:
            return False
        if self.budgets.max_edits_per_span is not None:
            used = self.used_per_span.get(span_index, 0)
            if used >= self.budgets.max_edits_per_span:
                return False
        return True

    def consume(self, span_index: int) -> None:
        self.used_total += 1
        self.used_per_span[span_index] = self.used_per_span.get(span_index, 0) + 1


def evaluate_spans(
    spans: Sequence[PhraseSpan],
    instrument: InstrumentRange,
    *,
    enable_memetic_dp: bool = False,
    folding_settings: FoldingSettings | None = None,
    budgets: LocalSearchBudgets | None = None,
    annotations: Sequence[Sequence[str]] | None = None,
    grace_settings: GraceSettings | None = None,
) -> Tuple[SpanEvaluation, ...]:
    """Evaluate spans for playability, optionally running memetic local search."""

    if annotations is not None and len(annotations) != len(spans):
        raise ValueError("annotations must align with the provided spans")

    evaluations: list[SpanEvaluation] = []
    for index, span in enumerate(spans):
        existing_annotations = tuple(annotations[index]) if annotations else ()
        summary = summarize_difficulty(
            span, instrument, grace_settings=grace_settings
        )
        evaluations.append(
            SpanEvaluation(
                index=index,
                span=span,
                difficulty=summary,
                annotations=existing_annotations,
                grace_settings=grace_settings,
            )
        )

    if not enable_memetic_dp or not evaluations:
        return tuple(evaluations)

    applied_budgets = budgets or LocalSearchBudgets()
    tracker = _BudgetTracker.from_evaluations(applied_budgets, evaluations)

    candidate = max(
        evaluations,
        key=lambda evaluation: (evaluation.playability_penalty, -evaluation.index),
    )

    if candidate.playability_penalty <= 0.0:
        return tuple(evaluations)

    if not tracker.can_consume(candidate.index):
        return tuple(evaluations)

    folding_result = fold_octaves_with_slack(
        candidate.span,
        instrument,
        settings=folding_settings,
    )
    if folding_result.span == candidate.span:
        return tuple(evaluations)

    updated_summary = summarize_difficulty(
        folding_result.span, instrument, grace_settings=grace_settings
    )
    updated_penalty = difficulty_score(
        updated_summary, grace_settings=grace_settings
    )
    if updated_penalty > candidate.playability_penalty + 1e-9:
        return tuple(evaluations)

    annotations_with_memetic = candidate.annotations + ("memetic-dp:fold-octaves",)
    tracker.consume(candidate.index)
    evaluations[candidate.index] = candidate.with_updates(
        span=folding_result.span,
        difficulty=updated_summary,
        annotations=annotations_with_memetic,
        folding=folding_result,
        grace_settings=grace_settings,
    )

    return tuple(evaluations)


@dataclass(frozen=True)
class EngineState:
    """Snapshot of the evolutionary loop at a particular generation."""

    generation: int
    population: Tuple[Individual, ...]
    archive: Tuple[Individual, ...]
    elapsed_seconds: float


LocalSearchHook = Callable[[Tuple[Individual, ...], Tuple[Individual, ...], EngineState], Tuple[Tuple[Individual, ...], Tuple[Individual, ...]]]
TerminationHook = Callable[[EngineState], str | None]
VariationHook = Callable[[Tuple[Individual, ...], EngineState], Sequence[Individual]]
SelectionHook = Callable[[Tuple[Individual, ...], Sequence[Individual], Tuple[Individual, ...], EngineState], Tuple[Tuple[Individual, ...], Tuple[Individual, ...]]]
InitializationHook = Callable[[], Tuple[Tuple[Individual, ...], Tuple[Individual, ...]]]
LogHook = Callable[[EngineState, Tuple[Individual, ...], Tuple[Individual, ...]], GenerationLog]


@dataclass(frozen=True)
class EngineConfig:
    """Configuration flags governing the GP engine loop."""

    generations: int
    time_budget_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.generations <= 0:
            raise ValueError("generations must be positive")
        if self.time_budget_seconds is not None and self.time_budget_seconds < 0:
            raise ValueError("time_budget_seconds cannot be negative")


@dataclass(frozen=True)
class EngineHooks:
    """Composable hooks controlling each stage of the GP loop."""

    initialize: InitializationHook
    variation: VariationHook
    selection: SelectionHook
    log_generation: LogHook
    local_search: LocalSearchHook | None = None
    termination: TerminationHook | None = None


@dataclass(frozen=True)
class EngineResult:
    """Outcome of a GP engine run."""

    population: Tuple[Individual, ...]
    archive: Tuple[Individual, ...]
    generations: int
    elapsed_seconds: float
    logs: Tuple[GenerationLog, ...]
    termination_reason: str


def run_engine(config: EngineConfig, hooks: EngineHooks) -> EngineResult:
    """Execute a GP loop using ``hooks`` until ``config`` terminates it."""

    start = time.monotonic()
    population, archive = hooks.initialize()
    if not population:
        raise RuntimeError("GP engine requires a non-empty initial population")

    population = tuple(population)
    archive = tuple(archive)
    logs: list[GenerationLog] = []
    termination_reason = "generation_limit"

    for generation in range(config.generations):
        elapsed = time.monotonic() - start
        if generation > 0 and config.time_budget_seconds is not None and elapsed >= config.time_budget_seconds:
            termination_reason = "time_budget_exceeded"
            break

        state = EngineState(
            generation=generation,
            population=population,
            archive=archive,
            elapsed_seconds=elapsed,
        )

        if hooks.local_search is not None:
            population, archive = hooks.local_search(population, archive, state)
            population = tuple(population)
            archive = tuple(archive)
            state = EngineState(
                generation=generation,
                population=population,
                archive=archive,
                elapsed_seconds=elapsed,
            )

        logs.append(hooks.log_generation(state, population, archive))

        elapsed_after_log = time.monotonic() - start
        if config.time_budget_seconds is not None and elapsed_after_log >= config.time_budget_seconds:
            termination_reason = "time_budget_exceeded"
            break

        if generation == config.generations - 1:
            termination_reason = "generation_limit"
            break

        if hooks.termination is not None:
            reason = hooks.termination(state)
            if reason:
                termination_reason = reason
                break

        offspring = hooks.variation(population, state)
        population, archive = hooks.selection(population, offspring, archive, state)
        population = tuple(population)
        archive = tuple(archive)

    elapsed_total = time.monotonic() - start
    return EngineResult(
        population=population,
        archive=archive,
        generations=len(logs),
        elapsed_seconds=elapsed_total,
        logs=tuple(logs),
        termination_reason=termination_reason,
    )


__all__ = [
    "EngineConfig",
    "EngineHooks",
    "EngineResult",
    "EngineState",
    "LocalSearchBudgets",
    "SpanEvaluation",
    "evaluate_spans",
    "run_engine",
]
