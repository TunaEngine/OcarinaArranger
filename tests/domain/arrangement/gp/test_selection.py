from __future__ import annotations

import pytest

from domain.arrangement.gp.fitness import FitnessVector
from domain.arrangement.gp.ops import GlobalTranspose
from domain.arrangement.gp.selection import (
    Individual,
    SelectionConfig,
    advance_generation,
    crowding_distance,
    nondominated_sort,
    update_archive,
)


def _individual(program_id: int, fitness: tuple[float, float, float, float]) -> Individual:
    primitive = GlobalTranspose(semitones=program_id)
    return Individual(program=(primitive,), fitness=FitnessVector(*fitness))


def test_nondominated_sort_preserves_ties_in_front_order() -> None:
    elite_a = _individual(1, (0.1, 0.1, 0.2, 0.3))
    elite_b = _individual(2, (0.1, 0.1, 0.2, 0.3))
    dominated = _individual(3, (0.2, 0.3, 0.4, 0.5))

    fronts = nondominated_sort([elite_a, elite_b, dominated])

    assert fronts[0] == [elite_a, elite_b]
    assert fronts[1] == [dominated]


def test_crowding_distance_marks_boundary_candidates() -> None:
    front = [
        _individual(1, (0.1, 0.5, 0.6, 0.4)),
        _individual(2, (0.15, 0.4, 0.7, 0.45)),
        _individual(3, (0.2, 0.3, 0.65, 0.5)),
        _individual(4, (0.25, 0.2, 0.8, 0.55)),
    ]

    distances = crowding_distance(front)

    assert distances[front[0]] == pytest.approx(float("inf"), rel=0, abs=0)
    assert distances[front[-1]] == pytest.approx(float("inf"), rel=0, abs=0)
    assert distances[front[1]] > 0
    assert distances[front[2]] > 0


def test_update_archive_rolls_over_capacity() -> None:
    archive = [
        _individual(1, (0.1, 0.2, 0.3, 0.4)),
        _individual(2, (0.18, 0.25, 0.32, 0.42)),
    ]
    new_candidates = [
        _individual(3, (0.12, 0.18, 0.28, 0.35)),
        _individual(4, (0.3, 0.4, 0.5, 0.6)),
    ]

    updated = update_archive(archive, new_candidates, max_size=2)

    assert _individual(3, (0.12, 0.18, 0.28, 0.35)) in updated
    assert all(individual.program[0].semitones != 2 for individual in updated)
    assert len(updated) == 2


def test_advance_generation_preserves_elites_from_archive() -> None:
    config = SelectionConfig(population_size=3, archive_size=2)
    archive = [_individual(1, (0.05, 0.1, 0.08, 0.12))]
    parents = [
        _individual(2, (0.2, 0.25, 0.3, 0.35)),
        _individual(3, (0.22, 0.24, 0.28, 0.34)),
        _individual(4, (0.21, 0.26, 0.27, 0.36)),
    ]
    offspring = [
        _individual(5, (0.3, 0.35, 0.33, 0.4)),
        _individual(6, (0.28, 0.32, 0.31, 0.38)),
    ]

    next_population, next_archive = advance_generation(parents, offspring, archive, config=config)

    elite = archive[0]
    assert elite in next_population
    assert elite in next_archive
    assert len(next_population) == config.population_size

    repeat_population, repeat_archive = advance_generation(
        next_population,
        offspring,
        next_archive,
        config=config,
    )

    assert elite in repeat_population
    assert elite in repeat_archive
    assert repeat_population[0] == next_population[0]
