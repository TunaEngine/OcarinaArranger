"""End-to-end orchestration helpers for arrangement GP sessions."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Sequence, Tuple

from domain.arrangement.explanations import ExplanationEvent
from domain.arrangement.phrase import PhraseSpan
from domain.arrangement.soft_key import InstrumentRange

from .engine import EngineConfig, EngineHooks, EngineState, run_engine
from .evaluation import evaluate_program
from .fitness import FidelityConfig, FitnessConfig, FitnessObjective
from .init import seed_programs
from .offspring import produce_offspring
from .program_ops import ensure_population
from .selection import Individual, SelectionConfig, advance_generation, update_archive
from .session_logging import GPSessionLog, fitness_sort_key, log_generation, serialize_individual
from .validation import ProgramConstraints


logger = logging.getLogger(__name__)
def _default_fitness_config() -> FitnessConfig:
    """Return the tuned fitness defaults emphasising melodic fidelity."""

    return FitnessConfig(
        playability=FitnessObjective(weight=1.0),
        fidelity=FitnessObjective(weight=1.8),
        tessitura=FitnessObjective(weight=1.0),
        program_size=FitnessObjective(weight=1.0),
        fidelity_components=FidelityConfig(
            contour_weight=0.3,
            lcs_weight=0.4,
            pitch_weight=0.3,
        ),
    )


@dataclass(frozen=True)
class GPSessionConfig:
    """Configuration controlling a GP optimisation session."""

    generations: int = 10
    population_size: int = 16
    archive_size: int = 8
    random_seed: int = 0
    random_program_count: int = 8
    crossover_rate: float = 0.8
    mutation_rate: float = 0.2
    log_best_programs: int = 3
    span_limits: Mapping[str, int] | None = None
    constraints: ProgramConstraints | None = None
    fitness_config: FitnessConfig | None = field(default_factory=_default_fitness_config)
    time_budget_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.generations <= 0:
            raise ValueError("generations must be positive")
        if self.population_size <= 0:
            raise ValueError("population_size must be positive")
        if self.archive_size < 0:
            raise ValueError("archive_size cannot be negative")
        if self.random_program_count < 0:
            raise ValueError("random_program_count cannot be negative")
        if not (0.0 <= self.crossover_rate <= 1.0):
            raise ValueError("crossover_rate must be between 0 and 1")
        if not (0.0 <= self.mutation_rate <= 1.0):
            raise ValueError("mutation_rate must be between 0 and 1")
        if self.crossover_rate == 0.0 and self.mutation_rate == 0.0:
            raise ValueError("At least one of crossover_rate or mutation_rate must be positive")
        if self.log_best_programs <= 0:
            raise ValueError("log_best_programs must be positive")
        if self.time_budget_seconds is not None and self.time_budget_seconds < 0:
            raise ValueError("time_budget_seconds cannot be negative")

    def as_serializable_dict(self) -> dict[str, object]:
        constraints = self.constraints
        constraints_dict = (
            {
                "max_operations": constraints.max_operations,
                "span_limits": dict(constraints.span_limits or {}),
                "max_operations_per_window": constraints.max_operations_per_window,
                "window_bars": constraints.window_bars,
                "beats_per_measure": constraints.beats_per_measure,
            }
            if constraints
            else None
        )
        return {
            "generations": self.generations,
            "population_size": self.population_size,
            "archive_size": self.archive_size,
            "random_seed": self.random_seed,
            "random_program_count": self.random_program_count,
            "crossover_rate": self.crossover_rate,
            "mutation_rate": self.mutation_rate,
            "log_best_programs": self.log_best_programs,
            "span_limits": dict(self.span_limits or {}),
            "constraints": constraints_dict,
            "time_budget_seconds": self.time_budget_seconds,
        }


@dataclass(frozen=True)
class GPSessionResult:
    winner: Individual
    log: GPSessionLog
    archive: Tuple[Individual, ...]
    population: Tuple[Individual, ...]
    generations: int
    elapsed_seconds: float
    termination_reason: str
def _report_progress(
    callback: Callable[[int, int], None] | None, generation: int, total_generations: int
) -> None:
    if callback is None:
        return
    try:
        callback(generation, total_generations)
    except Exception:  # pragma: no cover - defensive guard
        logger.exception("GP session progress callback failed")


def run_gp_session(
    phrase: PhraseSpan,
    instrument: InstrumentRange,
    *,
    config: GPSessionConfig,
    salvage_events: Sequence[ExplanationEvent] | None = None,
    transposition: int = 0,
    progress_callback: Callable[[int, int], None] | None = None,
) -> GPSessionResult:
    rng = random.Random(config.random_seed)
    span_limits = dict(config.span_limits or {})

    seeded = seed_programs(
        phrase,
        instrument,
        salvage_events=salvage_events,
        transposition=transposition,
        random_count=config.random_program_count,
        rng=rng,
        span_limits=span_limits,
    )

    initial_pool = ensure_population(
        seeded,
        required=config.population_size,
        phrase=phrase,
        instrument=instrument,
        rng=rng,
        span_limits=span_limits,
    )

    population = [
        evaluate_program(
            program,
            phrase=phrase,
            instrument=instrument,
            fitness_config=config.fitness_config,
            metadata={"origin": "seed", "generation": 0, "index": index},
        )
        for index, program in enumerate(initial_pool)
    ]

    selection_config = SelectionConfig(
        population_size=config.population_size,
        archive_size=config.archive_size,
    )

    log = GPSessionLog(
        seed=config.random_seed,
        config=config.as_serializable_dict(),
    )

    def _initialize() -> tuple[tuple[Individual, ...], tuple[Individual, ...]]:
        return (tuple(population), tuple())

    def _log_hook(
        state: EngineState,
        current_population: tuple[Individual, ...],
        current_archive: tuple[Individual, ...],
    ) -> GenerationLog:
        generation_log = log_generation(
            state.generation,
            current_population,
            current_archive,
            best_count=config.log_best_programs,
        )
        _report_progress(progress_callback, state.generation, config.generations)
        return generation_log

    def _local_search(
        current_population: tuple[Individual, ...],
        current_archive: tuple[Individual, ...],
        _state: EngineState,
    ) -> tuple[tuple[Individual, ...], tuple[Individual, ...]]:
        updated_archive = tuple(
            update_archive(
                list(current_archive),
                list(current_population),
                max_size=config.archive_size,
            )
        )
        return (current_population, updated_archive)

    def _variation(
        current_population: tuple[Individual, ...],
        state: EngineState,
    ) -> Sequence[Individual]:
        return produce_offspring(
            current_population,
            rng=rng,
            generation_index=state.generation,
            phrase=phrase,
            instrument=instrument,
            span_limits=span_limits,
            fitness_config=config.fitness_config,
            mutation_rate=config.mutation_rate,
            crossover_rate=config.crossover_rate,
            population_size=config.population_size,
            constraints=config.constraints,
        )

    def _selection(
        current_population: tuple[Individual, ...],
        offspring: Sequence[Individual],
        current_archive: tuple[Individual, ...],
        _state: EngineState,
    ) -> tuple[tuple[Individual, ...], tuple[Individual, ...]]:
        next_population, next_archive = advance_generation(
            list(current_population),
            list(offspring),
            list(current_archive),
            config=selection_config,
        )
        return (tuple(next_population), tuple(next_archive))

    engine_config = EngineConfig(
        generations=config.generations,
        time_budget_seconds=config.time_budget_seconds,
    )
    engine_hooks = EngineHooks(
        initialize=_initialize,
        variation=_variation,
        selection=_selection,
        log_generation=_log_hook,
        local_search=_local_search,
    )

    engine_result = run_engine(engine_config, engine_hooks)
    log.generations = list(engine_result.logs)

    final_archive = list(engine_result.archive)
    final_population = list(engine_result.population)
    final_candidates = final_archive if final_archive else final_population
    if not final_candidates:
        raise RuntimeError("GP session ended without any candidates")

    winner = min(final_candidates, key=fitness_sort_key)
    log.final_best = serialize_individual(winner)

    return GPSessionResult(
        winner=winner,
        log=log,
        archive=tuple(final_archive),
        population=tuple(final_population),
        generations=engine_result.generations,
        elapsed_seconds=engine_result.elapsed_seconds,
        termination_reason=engine_result.termination_reason,
    )


__all__ = [
    "GPSessionConfig",
    "GPSessionLog",
    "GPSessionResult",
    "run_gp_session",
]

