"""Utilities for turning GP programs into scored individuals."""

from __future__ import annotations

from typing import Mapping, Sequence

from domain.arrangement.difficulty import summarize_difficulty
from domain.arrangement.phrase import PhraseSpan
from domain.arrangement.soft_key import InstrumentRange

from .fitness import FitnessConfig, compute_fitness
from .ops import GPPrimitive
from .selection import Individual


def evaluate_program(
    program: Sequence[GPPrimitive],
    *,
    phrase: PhraseSpan,
    instrument: InstrumentRange,
    fitness_config: FitnessConfig | None,
    metadata: Mapping[str, object] | None = None,
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
    metadata_dict = dict(metadata or {})
    return Individual(program=tuple(program), fitness=fitness, metadata=metadata_dict)


__all__ = ["evaluate_program"]

