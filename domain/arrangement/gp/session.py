"""End-to-end orchestration helpers for arrangement GP sessions."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Sequence, Tuple

from domain.arrangement.config import GraceSettings
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
from .session_logging import (
    GPSessionLog,
    GenerationLog,
    IndividualSummary,
    fitness_sort_key,
    log_generation,
    serialize_individual,
)
from .penalties import ScoringPenalties
from .validation import ProgramConstraints


logger = logging.getLogger(__name__)


def _describe_individual_summary(summary: IndividualSummary) -> str:
    """Return a concise textual description of a logged individual."""

    fitness = summary.fitness
    metadata = summary.metadata
    origin = metadata.get("origin", "?") if isinstance(metadata, Mapping) else "?"
    generation = metadata.get("generation") if isinstance(metadata, Mapping) else None
    index = metadata.get("index") if isinstance(metadata, Mapping) else None
    program_size = len(summary.program)
    playability = fitness.get("playability", 0.0)
    fidelity = fitness.get("fidelity", 0.0)
    tessitura = fitness.get("tessitura", 0.0)
    size_suffix = f" ops={program_size}" if program_size else ""
    origin_suffix = f" origin={origin}" if origin != "?" else ""
    slot_suffix = (
        f" gen={generation} idx={index}"
        if generation is not None and index is not None
        else ""
    )
    return (
        f"play={playability:.3f} fid={fidelity:.3f} tess={tessitura:.3f}{size_suffix}"
        f"{origin_suffix}{slot_suffix}"
    )


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
    population_size: int = 15
    archive_size: int = 8
    random_seed: int = 0
    random_program_count: int = 8
    crossover_rate: float = 0.8
    mutation_rate: float = 0.2
    log_best_programs: int = 3
    log_markdown_generations: bool = False
    span_limits: Mapping[str, int] | None = None
    constraints: ProgramConstraints | None = None
    fitness_config: FitnessConfig | None = field(default_factory=_default_fitness_config)
    time_budget_seconds: float | None = None
    scoring_penalties: ScoringPenalties = field(default_factory=ScoringPenalties)

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
            "log_markdown_generations": self.log_markdown_generations,
            "scoring_penalties": {
                "fidelity_weight": self.scoring_penalties.fidelity_weight,
                "range_clamp_penalty": self.scoring_penalties.range_clamp_penalty,
                "range_clamp_melody_bias": self.scoring_penalties.range_clamp_melody_bias,
                "melody_shift_weight": self.scoring_penalties.melody_shift_weight,
                "rhythm_simplify_weight": self.scoring_penalties.rhythm_simplify_weight,
            },
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


def _program_description(entries: Sequence[Mapping[str, object]]) -> str:
    if not entries:
        return "<identity>"
    parts: list[str] = []
    for entry in entries:
        entry_type = entry.get("type", "<unknown>")
        span_info = entry.get("span", {}) if isinstance(entry.get("span"), Mapping) else {}
        label = span_info.get("label", "phrase")
        parameters = [
            f"{key}={value}"
            for key, value in entry.items()
            if key not in {"type", "span"}
        ]
        parameter_text = ", ".join(parameters)
        if parameter_text:
            parts.append(f"{entry_type}({parameter_text}@{label})")
        else:
            parts.append(f"{entry_type}@{label}")
    return " -> ".join(parts)


def _markdown_generation_table(rows: Sequence[tuple[str, IndividualSummary, int]]) -> str:
    header = "| Gen | Rank | Program | Play | Fidelity | Tessitura | Size | Origin |\n"
    header += "| --- | --- | --- | --- | --- | --- | --- | --- |"
    formatted_rows: list[str] = [header]
    for label, summary, rank in rows:
        fitness = summary.fitness
        program_desc = _program_description(summary.program)
        play = fitness.get("playability", 0.0)
        fidelity = fitness.get("fidelity", 0.0)
        tessitura = fitness.get("tessitura", 0.0)
        size = fitness.get("program_size", 0.0)
        metadata = summary.metadata
        origin = metadata.get("origin", "?") if isinstance(metadata, Mapping) else "?"
        formatted_rows.append(
            f"| {label} | {rank} | {program_desc} | {play:.3f} | {fidelity:.3f} | {tessitura:.3f} | {size:.3f} | {origin} |"
        )
    return "\n".join(formatted_rows)


def run_gp_session(
    phrase: PhraseSpan,
    instrument: InstrumentRange,
    *,
    config: GPSessionConfig,
    salvage_events: Sequence[ExplanationEvent] | None = None,
    transposition: int = 0,
    progress_callback: Callable[[int, int], None] | None = None,
    grace_settings: GraceSettings | None = None,
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
        penalties=config.scoring_penalties,
    )

    initial_pool = ensure_population(
        seeded,
        required=config.population_size,
        phrase=phrase,
        instrument=instrument,
        rng=rng,
        span_limits=span_limits,
        penalties=config.scoring_penalties,
    )

    population = [
        evaluate_program(
            program,
            phrase=phrase,
            instrument=instrument,
            fitness_config=config.fitness_config,
            metadata={"origin": "seed", "generation": 0, "index": index},
            penalties=config.scoring_penalties,
            grace_settings=grace_settings,
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

    markdown_rows: list[tuple[str, IndividualSummary, int]] = []

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
        if logger.isEnabledFor(logging.DEBUG):
            best_programs = ", ".join(
                _describe_individual_summary(summary)
                for summary in generation_log.best_programs
            )
            logger.debug(
                "run_gp_session:generation index=%d best=[%s] archive=%d",
                state.generation,
                best_programs or "",
                len(generation_log.archive),
            )
        if config.log_markdown_generations:
            markdown_rows.extend(
                (
                    str(state.generation),
                    summary,
                    rank,
                )
                for rank, summary in enumerate(generation_log.best_programs, start=1)
            )
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
            penalties=config.scoring_penalties,
            mutation_rate=config.mutation_rate,
            crossover_rate=config.crossover_rate,
            population_size=config.population_size,
            constraints=config.constraints,
            grace_settings=grace_settings,
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
    final_summary = serialize_individual(winner)
    log.final_best = final_summary

    if config.log_markdown_generations and markdown_rows and logger.isEnabledFor(logging.DEBUG):
        markdown_rows.append(("final", final_summary, 1))
        table = _markdown_generation_table(markdown_rows)
        logger.debug("run_gp_session:best programs markdown\n%s", table)

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

