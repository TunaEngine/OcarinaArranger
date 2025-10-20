"""Generation of offspring for GP sessions."""

from __future__ import annotations

import random
from typing import Mapping, Sequence

from domain.arrangement.phrase import PhraseSpan
from domain.arrangement.soft_key import InstrumentRange

from .evaluation import evaluate_program
from .fitness import FitnessConfig
from .penalties import ScoringPenalties
from .selection import Individual
from .program_ops import primitive_sampler
from .variation import mutate_program, one_point_crossover


def produce_offspring(
    population: Sequence[Individual],
    *,
    rng: random.Random,
    generation_index: int,
    phrase: PhraseSpan,
    instrument: InstrumentRange,
    span_limits: Mapping[str, int] | None,
    fitness_config: FitnessConfig | None,
    penalties: ScoringPenalties,
    mutation_rate: float,
    crossover_rate: float,
    population_size: int,
    constraints,
) -> list[Individual]:
    """Generate a population of offspring from *population*."""

    if not population:
        return []

    sampler = primitive_sampler(
        rng,
        phrase,
        instrument,
        span_limits,
        penalties=penalties,
    )
    offspring: list[Individual] = []
    while len(offspring) < population_size:
        perform_crossover = len(population) >= 2 and rng.random() < crossover_rate
        if perform_crossover:
            parent_a, parent_b = rng.sample(list(population), 2)
            children = one_point_crossover(
                list(parent_a.program),
                list(parent_b.program),
                phrase,
                rng=rng,
                span_limits=span_limits,
                constraints=constraints,
            )
            for child_program in children:
                metadata = {
                    "origin": "crossover",
                    "generation": generation_index + 1,
                }
                offspring.append(
                    evaluate_program(
                        child_program,
                        phrase=phrase,
                        instrument=instrument,
                        fitness_config=fitness_config,
                        penalties=penalties,
                        metadata=metadata,
                    )
                )
                if len(offspring) >= population_size:
                    break
            continue

        if rng.random() >= mutation_rate:
            continue

        parent = rng.choice(list(population))
        try:
            mutated_program = mutate_program(
                list(parent.program),
                phrase,
                rng=rng,
                span_limits=span_limits,
                constraints=constraints,
                generator=sampler,
            )
        except RuntimeError:
            continue

        metadata = {
            "origin": "mutation",
            "generation": generation_index + 1,
        }
        offspring.append(
            evaluate_program(
                mutated_program,
                phrase=phrase,
                instrument=instrument,
                fitness_config=fitness_config,
                penalties=penalties,
                metadata=metadata,
            )
        )

    return offspring


__all__ = ["produce_offspring"]

