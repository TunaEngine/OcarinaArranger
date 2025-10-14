"""End-to-end orchestration helpers for arrangement GP sessions."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Sequence, Tuple

from shared.ottava import OttavaShift

from domain.arrangement.difficulty import summarize_difficulty
from domain.arrangement.explanations import ExplanationEvent
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange

from .engine import EngineConfig, EngineHooks, EngineState, run_engine
from .fitness import FidelityConfig, FitnessConfig, FitnessObjective, compute_fitness
from .init import generate_random_program, seed_programs
from .ops import GPPrimitive, GlobalTranspose, LocalOctave, SimplifyRhythm
from .selection import Individual, SelectionConfig, advance_generation, update_archive
from .session_logging import GPSessionLog, fitness_sort_key, log_generation, serialize_individual
from .validation import ProgramConstraints
from .variation import mutate_program, one_point_crossover


def _apply_program(program: Sequence[GPPrimitive], span: PhraseSpan) -> PhraseSpan:
    current = span
    for operation in program:
        current = _apply_primitive(operation, current)
    return current


def _apply_primitive(operation: GPPrimitive, span: PhraseSpan) -> PhraseSpan:
    if isinstance(operation, GlobalTranspose):
        return span.transpose(operation.semitones)
    if isinstance(operation, LocalOctave):
        return _apply_local_octave(operation, span)
    if isinstance(operation, SimplifyRhythm):
        return _apply_simplify_rhythm(operation, span)
    return span


def _apply_local_octave(operation: LocalOctave, span: PhraseSpan) -> PhraseSpan:
    try:
        start, end = operation.span.resolve(span)
    except ValueError:
        return span

    if operation.octaves == 0:
        return span

    semitones = operation.octaves * 12
    direction = "up" if semitones > 0 else "down"
    shift = OttavaShift(
        source="octave-shift",
        direction=direction,
        size=8 * abs(operation.octaves),
    )

    updated: list[PhraseNote] = []
    for note in span.notes:
        if start <= note.onset < end:
            updated.append(note.with_midi(note.midi + semitones).add_ottava_shift(shift))
            continue
        updated.append(note)
    return span.with_notes(updated)


def _apply_simplify_rhythm(operation: SimplifyRhythm, span: PhraseSpan) -> PhraseSpan:
    try:
        start, end = operation.span.resolve(span)
    except ValueError:
        return span

    subdivisions = max(1, int(operation.subdivisions))
    unit = max(1, span.pulses_per_quarter // subdivisions)
    updated: list[PhraseNote] = []

    for note in span.notes:
        if not (start <= note.onset < end):
            updated.append(note)
            continue

        quantized = max(unit, round(note.duration / unit) * unit)
        max_duration = max(1, end - note.onset)
        updated_duration = min(quantized, max_duration)
        updated.append(note.with_duration(updated_duration))

    return span.with_notes(updated)


def _ensure_population(
    programs: Iterable[Sequence[GPPrimitive]],
    *,
    required: int,
    phrase: PhraseSpan,
    instrument: InstrumentRange,
    rng: random.Random,
    span_limits: Mapping[str, int] | None,
) -> list[list[GPPrimitive]]:
    pool = [list(program) for program in programs][:required]
    seen = {tuple(program) for program in pool}

    attempts = 0
    max_attempts = max(10, required * 5)
    while len(pool) < required and attempts < max_attempts:
        attempts += 1
        try:
            candidate = generate_random_program(
                phrase,
                instrument,
                rng=rng,
                max_length=3,
                span_limits=span_limits,
            )
        except RuntimeError:
            continue

        key = tuple(candidate)
        if not candidate or key in seen:
            continue
        pool.append(candidate)
        seen.add(key)

    if len(pool) < required:
        raise RuntimeError("Unable to seed initial GP population with the requested size")

    return pool


def _primitive_sampler(
    rng: random.Random,
    phrase: PhraseSpan,
    instrument: InstrumentRange,
    span_limits: Mapping[str, int] | None,
) -> Callable[[], GPPrimitive]:
    def _generator() -> GPPrimitive:
        attempts = 0
        while True:
            attempts += 1
            try:
                program = generate_random_program(
                    phrase,
                    instrument,
                    rng=rng,
                    max_length=1,
                    span_limits=span_limits,
                )
            except RuntimeError:
                program = []
            if program:
                return program[0]
            if attempts >= 5:
                raise RuntimeError("Unable to generate primitive for mutation")

    return _generator


def _evaluate_program(
    program: Sequence[GPPrimitive],
    *,
    phrase: PhraseSpan,
    instrument: InstrumentRange,
    fitness_config: FitnessConfig | None,
    metadata: Mapping[str, object] | None = None,
) -> Individual:
    candidate = _apply_program(program, phrase)
    difficulty = summarize_difficulty(candidate, instrument)
    fitness = compute_fitness(
        original=phrase,
        candidate=candidate,
        instrument=instrument,
        program=program,
        difficulty=difficulty,
        config=fitness_config,
    )
    metadata_dict = dict(metadata or {})
    return Individual(program=tuple(program), fitness=fitness, metadata=metadata_dict)


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


def _produce_offspring(
    population: Sequence[Individual],
    *,
    rng: random.Random,
    config: GPSessionConfig,
    generation_index: int,
    phrase: PhraseSpan,
    instrument: InstrumentRange,
    span_limits: Mapping[str, int] | None,
    fitness_config: FitnessConfig | None,
) -> list[Individual]:
    if not population:
        return []

    sampler = _primitive_sampler(rng, phrase, instrument, span_limits)
    offspring: list[Individual] = []

    while len(offspring) < config.population_size:
        perform_crossover = len(population) >= 2 and rng.random() < config.crossover_rate
        if perform_crossover:
            parent_a, parent_b = rng.sample(list(population), 2)
            children = one_point_crossover(
                list(parent_a.program),
                list(parent_b.program),
                phrase,
                rng=rng,
                span_limits=span_limits,
                constraints=config.constraints,
            )
            for child_program in children:
                metadata = {
                    "origin": "crossover",
                    "generation": generation_index + 1,
                }
                offspring.append(
                    _evaluate_program(
                        child_program,
                        phrase=phrase,
                        instrument=instrument,
                        fitness_config=fitness_config,
                        metadata=metadata,
                    )
                )
                if len(offspring) >= config.population_size:
                    break
            continue

        parent = rng.choice(list(population))
        try:
            mutated_program = mutate_program(
                list(parent.program),
                phrase,
                rng=rng,
                span_limits=span_limits,
                constraints=config.constraints,
                generator=sampler,
            )
        except RuntimeError:
            continue

        metadata = {
            "origin": "mutation",
            "generation": generation_index + 1,
        }
        offspring.append(
            _evaluate_program(
                mutated_program,
                phrase=phrase,
                instrument=instrument,
                fitness_config=fitness_config,
                metadata=metadata,
            )
        )

    return offspring


def run_gp_session(
    phrase: PhraseSpan,
    instrument: InstrumentRange,
    *,
    config: GPSessionConfig,
    salvage_events: Sequence[ExplanationEvent] | None = None,
    transposition: int = 0,
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

    initial_pool = _ensure_population(
        seeded,
        required=config.population_size,
        phrase=phrase,
        instrument=instrument,
        rng=rng,
        span_limits=span_limits,
    )

    population = [
        _evaluate_program(
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
        return log_generation(
            state.generation,
            current_population,
            current_archive,
            best_count=config.log_best_programs,
        )

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
        return _produce_offspring(
            current_population,
            rng=rng,
            config=config,
            generation_index=state.generation,
            phrase=phrase,
            instrument=instrument,
            span_limits=span_limits,
            fitness_config=config.fitness_config,
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

