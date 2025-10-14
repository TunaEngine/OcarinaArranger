"""Logging helpers for arrangement GP sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .ops import GPPrimitive
from .selection import Individual


def fitness_sort_key(individual: Individual) -> tuple[float, float, float, float, int]:
    """Sort key that prefers fitter, smaller programs."""

    fitness = individual.fitness.as_tuple()
    return (fitness[0], fitness[1], fitness[2], fitness[3], len(individual.program))


def _serialize_primitive(operation: GPPrimitive) -> dict[str, object]:
    parameters = {
        name: getattr(operation, name)
        for name in operation.parameter_domains()
    }
    span_descriptor = {
        "label": operation.span.label,
        "start": operation.span.start_onset,
        "end": operation.span.end_onset,
    }
    return {
        "type": type(operation).__name__,
        "span": span_descriptor,
        **parameters,
    }


@dataclass
class IndividualSummary:
    fitness: Mapping[str, float]
    program: Sequence[Mapping[str, object]]
    metadata: Mapping[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "fitness": dict(self.fitness),
            "program": [dict(entry) for entry in self.program],
            "metadata": dict(self.metadata),
        }


def serialize_individual(individual: Individual) -> IndividualSummary:
    fitness = {
        "playability": individual.fitness.playability,
        "fidelity": individual.fitness.fidelity,
        "tessitura": individual.fitness.tessitura,
        "program_size": individual.fitness.program_size,
    }
    program = [_serialize_primitive(operation) for operation in individual.program]
    metadata = dict(individual.metadata or {})
    return IndividualSummary(fitness=fitness, program=program, metadata=metadata)


def _population_metrics(population: Sequence[Individual]) -> dict[str, object]:
    if not population:
        return {"count": 0}

    best = min(population, key=fitness_sort_key)
    average_length = sum(len(candidate.program) for candidate in population) / len(population)
    return {
        "count": len(population),
        "best_playability": best.fitness.playability,
        "best_fidelity": best.fitness.fidelity,
        "best_tessitura": best.fitness.tessitura,
        "best_program_size": best.fitness.program_size,
        "avg_program_length": round(average_length, 6),
    }


@dataclass
class GenerationLog:
    index: int
    metrics: Mapping[str, object]
    best_programs: Sequence[IndividualSummary]
    archive: Sequence[IndividualSummary]

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "metrics": dict(self.metrics),
            "best_programs": [summary.to_dict() for summary in self.best_programs],
            "archive": [summary.to_dict() for summary in self.archive],
        }


@dataclass
class GPSessionLog:
    seed: int
    config: Mapping[str, object]
    generations: list[GenerationLog] = field(default_factory=list)
    final_best: IndividualSummary | None = None

    def to_dict(self) -> dict[str, object]:
        data = {
            "seed": self.seed,
            "config": dict(self.config),
            "generations": [generation.to_dict() for generation in self.generations],
        }
        if self.final_best is not None:
            data["final_best"] = self.final_best.to_dict()
        return data


def log_generation(
    index: int,
    population: Sequence[Individual],
    archive: Sequence[Individual],
    *,
    best_count: int,
) -> GenerationLog:
    metrics = _population_metrics(population)
    best = sorted(population, key=fitness_sort_key)[:best_count]
    best_summaries = [serialize_individual(individual) for individual in best]
    archive_summaries = [
        serialize_individual(individual)
        for individual in sorted(archive, key=fitness_sort_key)
    ]
    return GenerationLog(
        index=index,
        metrics=metrics,
        best_programs=best_summaries,
        archive=archive_summaries,
    )


__all__ = [
    "GPSessionLog",
    "GenerationLog",
    "IndividualSummary",
    "fitness_sort_key",
    "log_generation",
    "serialize_individual",
]

