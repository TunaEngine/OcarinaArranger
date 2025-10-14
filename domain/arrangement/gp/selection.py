"""Selection helpers for the arrangement genetic programming engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from .fitness import FitnessVector
from .ops import GPPrimitive


@dataclass(frozen=True)
class Individual:
    """Representation of a GP candidate paired with its fitness vector."""

    program: tuple[GPPrimitive, ...]
    fitness: FitnessVector
    metadata: Mapping[str, object] | None = field(default=None, compare=False, hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "program", tuple(self.program))


@dataclass(frozen=True)
class SelectionConfig:
    """Configuration controlling population and archive sizes."""

    population_size: int
    archive_size: int

    def __post_init__(self) -> None:
        if self.population_size <= 0:
            raise ValueError("population_size must be positive")
        if self.archive_size < 0:
            raise ValueError("archive_size cannot be negative")


def dominates(left: FitnessVector, right: FitnessVector) -> bool:
    """Return ``True`` when *left* Pareto dominates *right*."""

    left_values = left.as_tuple()
    right_values = right.as_tuple()

    if not left_values or not right_values:
        return False

    no_worse = all(l <= r for l, r in zip(left_values, right_values))
    strictly_better = any(l < r for l, r in zip(left_values, right_values))
    return no_worse and strictly_better


def nondominated_sort(population: Sequence[Individual]) -> list[list[Individual]]:
    """Group *population* into Pareto fronts using fast non-dominated sorting."""

    if not population:
        return []

    individuals = list(population)
    domination_counts: dict[Individual, int] = {}
    domination_sets: dict[Individual, list[Individual]] = {}
    first_front: list[Individual] = []

    for p in individuals:
        domination_sets[p] = []
        domination_counts[p] = 0
        for q in individuals:
            if p is q:
                continue
            if dominates(p.fitness, q.fitness):
                domination_sets[p].append(q)
            elif dominates(q.fitness, p.fitness):
                domination_counts[p] += 1
        if domination_counts[p] == 0:
            first_front.append(p)

    fronts: list[list[Individual]] = []
    current = first_front

    while current:
        fronts.append(current)
        next_front: list[Individual] = []
        added: set[Individual] = set()
        for p in current:
            for dominated in domination_sets[p]:
                domination_counts[dominated] -= 1
                if domination_counts[dominated] == 0 and dominated not in added:
                    added.add(dominated)
                    next_front.append(dominated)
        current = next_front

    return fronts


def crowding_distance(front: Sequence[Individual]) -> dict[Individual, float]:
    """Compute crowding distances for *front* following NSGA-II heuristics."""

    count = len(front)
    if count == 0:
        return {}
    if count <= 2:
        return {individual: float("inf") for individual in front}

    vectors = {individual: individual.fitness.as_tuple() for individual in front}
    objectives = len(next(iter(vectors.values())))
    distances = {individual: 0.0 for individual in front}
    indexed_front = list(enumerate(front))

    for objective in range(objectives):
        sorted_front = sorted(
            indexed_front,
            key=lambda item: (vectors[item[1]][objective], item[0]),
        )
        min_value = vectors[sorted_front[0][1]][objective]
        max_value = vectors[sorted_front[-1][1]][objective]
        distances[sorted_front[0][1]] = float("inf")
        distances[sorted_front[-1][1]] = float("inf")

        if max_value == min_value:
            continue

        scale = max_value - min_value
        for index in range(1, count - 1):
            current_individual = sorted_front[index][1]
            next_value = vectors[sorted_front[index + 1][1]][objective]
            previous_value = vectors[sorted_front[index - 1][1]][objective]
            distances[current_individual] += (next_value - previous_value) / scale

    return distances


def _deduplicate(individuals: Iterable[Individual]) -> list[Individual]:
    """Remove duplicate programs while keeping Pareto-superior entries."""

    seen: dict[tuple[GPPrimitive, ...], Individual] = {}
    order: list[tuple[GPPrimitive, ...]] = []

    for individual in individuals:
        key = individual.program
        existing = seen.get(key)
        if existing is None:
            seen[key] = individual
            order.append(key)
            continue
        if dominates(individual.fitness, existing.fitness) and not dominates(
            existing.fitness, individual.fitness
        ):
            seen[key] = individual

    return [seen[key] for key in order]


def _sorted_by_crowding(front: Sequence[Individual], distances: Mapping[Individual, float]) -> list[Individual]:
    indexed_front = list(enumerate(front))
    indexed_front.sort(key=lambda item: (-distances[item[1]], item[0]))
    return [individual for _, individual in indexed_front]


def select_population(candidates: Sequence[Individual], population_size: int) -> list[Individual]:
    """Select the next generation from *candidates* using NSGA-II selection."""

    if population_size <= 0:
        return []

    selected: list[Individual] = []
    for front in nondominated_sort(candidates):
        remaining = population_size - len(selected)
        if remaining <= 0:
            break
        if len(front) <= remaining:
            selected.extend(front)
            continue
        distances = crowding_distance(front)
        ranked = _sorted_by_crowding(front, distances)
        selected.extend(ranked[:remaining])
        break
    return selected


def update_archive(
    archive: Sequence[Individual],
    candidates: Sequence[Individual],
    *,
    max_size: int,
) -> list[Individual]:
    """Update the elitist archive with *candidates* bounded by ``max_size``."""

    if max_size <= 0:
        return []

    combined = _deduplicate(list(archive) + list(candidates))
    if len(combined) <= max_size:
        return combined

    updated: list[Individual] = []
    for front in nondominated_sort(combined):
        space = max_size - len(updated)
        if space <= 0:
            break
        if len(front) <= space:
            updated.extend(front)
            continue
        distances = crowding_distance(front)
        ranked = _sorted_by_crowding(front, distances)
        updated.extend(ranked[:space])
        break

    return updated


def advance_generation(
    parents: Sequence[Individual],
    offspring: Sequence[Individual],
    archive: Sequence[Individual],
    *,
    config: SelectionConfig,
) -> tuple[list[Individual], list[Individual]]:
    """Advance the GP population by one generation while maintaining the archive."""

    combined = _deduplicate(list(parents) + list(offspring))
    next_archive = update_archive(archive, combined, max_size=config.archive_size)
    selection_pool = _deduplicate(combined + next_archive)
    next_population = select_population(selection_pool, config.population_size)
    if len(next_population) < config.population_size:
        augmented = _deduplicate(next_population + next_archive)
        next_population = select_population(augmented, config.population_size)
    return (next_population, next_archive)


__all__ = [
    "Individual",
    "SelectionConfig",
    "advance_generation",
    "crowding_distance",
    "nondominated_sort",
    "select_population",
    "update_archive",
]
