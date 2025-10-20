"""Utilities for turning GP programs into scored individuals."""

from __future__ import annotations

from typing import Mapping, Sequence

from domain.arrangement.difficulty import summarize_difficulty
from domain.arrangement.phrase import PhraseSpan
from domain.arrangement.soft_key import InstrumentRange

from .fitness import FitnessConfig, FitnessVector, compute_fitness
from .ops import GPPrimitive, SimplifyRhythm
from .penalties import ScoringPenalties
from .selection import Individual


def evaluate_program(
    program: Sequence[GPPrimitive],
    *,
    phrase: PhraseSpan,
    instrument: InstrumentRange,
    fitness_config: FitnessConfig | None,
    metadata: Mapping[str, object] | None = None,
    penalties: ScoringPenalties | None = None,
) -> Individual:
    """Evaluate *program* and return a scored individual."""

    from .program_ops import apply_program

    candidate = apply_program(program, phrase)
    difficulty = summarize_difficulty(candidate, instrument)
    fitness = compute_fitness(
        original=phrase,
        candidate=candidate,
        instrument=instrument,
        program=program,
        difficulty=difficulty,
        config=fitness_config,
    )
    penalties = penalties or ScoringPenalties()
    simplify_count = sum(
        1 for operation in program if isinstance(operation, SimplifyRhythm)
    )
    rhythm_weight = penalties.rhythm_simplify_weight
    if simplify_count and rhythm_weight != 1.0:
        delta = simplify_count * abs(rhythm_weight - 1.0)
        playability, fidelity, tessitura, program_size = fitness.as_tuple()
        if rhythm_weight >= 1.0:
            fidelity += delta
            program_size += delta
        else:
            fidelity = max(0.0, fidelity - delta)
            program_size = max(0.0, program_size - delta)
        fitness = FitnessVector(
            playability=playability,
            fidelity=fidelity,
            tessitura=tessitura,
            program_size=program_size,
        )
    metadata_dict = dict(metadata or {})
    if simplify_count and "simplify_ops" not in metadata_dict:
        metadata_dict["simplify_ops"] = simplify_count
    return Individual(program=tuple(program), fitness=fitness, metadata=metadata_dict)


__all__ = ["evaluate_program"]

