"""Crossover and mutation helpers for arrangement GP programs."""

from __future__ import annotations

import random
from typing import Callable, Iterable, Mapping, Sequence

from domain.arrangement.phrase import PhraseSpan

from .ops import GPPrimitive
from .repair import repair_program
from .validation import (
    ProgramConstraints,
    ProgramValidationError,
    merge_constraints,
    validate_program,
)

GPProgram = Sequence[GPPrimitive]
ProgramFactory = Callable[[], GPPrimitive]


def _span_key(operation: GPPrimitive, phrase: PhraseSpan) -> tuple[str, tuple[int, int]]:
    resolved = operation.span.resolve(phrase)
    return (operation.span.label, resolved)


def _swap_for_key(
    program: Sequence[GPPrimitive],
    replacement: Iterable[GPPrimitive],
    key: tuple[str, tuple[int, int]],
    phrase: PhraseSpan,
) -> list[GPPrimitive]:
    result: list[GPPrimitive] = []
    inserted = False
    replacement = list(replacement)

    for operation in program:
        if _span_key(operation, phrase) == key:
            if not inserted:
                result.extend(replacement)
                inserted = True
            continue
        result.append(operation)

    if not inserted:
        result.extend(replacement)

    return result


def crossover_by_span(
    parent_a: GPProgram,
    parent_b: GPProgram,
    phrase: PhraseSpan,
    *,
    rng: random.Random | None = None,
    span_limits: Mapping[str, int] | None = None,
    constraints: ProgramConstraints | None = None,
    validator: Callable[[Sequence[GPPrimitive], PhraseSpan], None] | None = None,
    repairer: Callable[[Sequence[GPPrimitive], PhraseSpan], list[GPPrimitive]] | None = None,
) -> tuple[list[GPPrimitive], list[GPPrimitive]]:
    """Swap operations targeting the same concrete span between two parents."""

    rng = rng or random.Random()
    applied_constraints = merge_constraints(constraints, span_limits)
    validator = validator or (
        lambda program, target: validate_program(program, target, constraints=applied_constraints)
    )
    repairer = repairer or (
        lambda program, target: repair_program(program, target, constraints=applied_constraints)
    )

    keys_a = {_span_key(operation, phrase) for operation in parent_a}
    keys_b = {_span_key(operation, phrase) for operation in parent_b}
    shared = sorted(keys_a & keys_b)

    if not shared:
        return (list(parent_a), list(parent_b))

    key = rng.choice(shared)

    child_a = _swap_for_key(parent_a, _extract_for_key(parent_b, key, phrase), key, phrase)
    child_b = _swap_for_key(parent_b, _extract_for_key(parent_a, key, phrase), key, phrase)

    child_a = repairer(child_a, phrase)
    child_b = repairer(child_b, phrase)

    try:
        validator(child_a, phrase)
        validator(child_b, phrase)
    except ProgramValidationError:
        return (list(parent_a), list(parent_b))

    return (child_a, child_b)


def _extract_for_key(
    program: Sequence[GPPrimitive],
    key: tuple[str, tuple[int, int]],
    phrase: PhraseSpan,
) -> list[GPPrimitive]:
    return [operation for operation in program if _span_key(operation, phrase) == key]


def one_point_crossover(
    parent_a: GPProgram,
    parent_b: GPProgram,
    phrase: PhraseSpan,
    *,
    rng: random.Random | None = None,
    span_limits: Mapping[str, int] | None = None,
    constraints: ProgramConstraints | None = None,
    validator: Callable[[Sequence[GPPrimitive], PhraseSpan], None] | None = None,
    repairer: Callable[[Sequence[GPPrimitive], PhraseSpan], list[GPPrimitive]] | None = None,
    max_attempts: int = 10,
) -> tuple[list[GPPrimitive], list[GPPrimitive]]:
    """Perform a one-point crossover that respects operation boundaries."""

    rng = rng or random.Random()
    applied_constraints = merge_constraints(constraints, span_limits)
    validator = validator or (
        lambda program, target: validate_program(program, target, constraints=applied_constraints)
    )
    repairer = repairer or (
        lambda program, target: repair_program(program, target, constraints=applied_constraints)
    )

    if not parent_a or not parent_b:
        return (list(parent_a), list(parent_b))

    indices_a = list(range(1, len(parent_a) + 1))
    indices_b = list(range(1, len(parent_b) + 1))

    attempts = 0
    while attempts < max_attempts:
        attempts += 1
        cut_a = rng.choice(indices_a)
        cut_b = rng.choice(indices_b)

        child_a = list(parent_a[:cut_a]) + list(parent_b[cut_b:])
        child_b = list(parent_b[:cut_b]) + list(parent_a[cut_a:])

        child_a = repairer(child_a, phrase)
        child_b = repairer(child_b, phrase)

        try:
            validator(child_a, phrase)
            validator(child_b, phrase)
        except ProgramValidationError:
            continue

        return (child_a, child_b)

    return (list(parent_a), list(parent_b))


def mutate_insert(
    program: GPProgram,
    operation: GPPrimitive,
    phrase: PhraseSpan,
    *,
    index: int | None = None,
    span_limits: Mapping[str, int] | None = None,
    constraints: ProgramConstraints | None = None,
    validator: Callable[[Sequence[GPPrimitive], PhraseSpan], None] | None = None,
    repairer: Callable[[Sequence[GPPrimitive], PhraseSpan], list[GPPrimitive]] | None = None,
) -> list[GPPrimitive]:
    """Insert *operation* into *program* if the result can be validated."""

    applied_constraints = merge_constraints(constraints, span_limits)
    validator = validator or (
        lambda program, target: validate_program(program, target, constraints=applied_constraints)
    )
    repairer = repairer or (
        lambda program, target: repair_program(program, target, constraints=applied_constraints)
    )

    candidate = list(program)
    insertion_index = len(candidate) if index is None else max(0, min(len(candidate), index))
    candidate.insert(insertion_index, operation)

    candidate = repairer(candidate, phrase)

    try:
        validator(candidate, phrase)
    except ProgramValidationError:
        return list(program)

    return candidate


def mutate_delete(
    program: GPProgram,
    phrase: PhraseSpan,
    *,
    index: int | None = None,
    span_limits: Mapping[str, int] | None = None,
    constraints: ProgramConstraints | None = None,
    validator: Callable[[Sequence[GPPrimitive], PhraseSpan], None] | None = None,
    repairer: Callable[[Sequence[GPPrimitive], PhraseSpan], list[GPPrimitive]] | None = None,
) -> list[GPPrimitive]:
    """Remove an operation and return the repaired, validated program."""

    if not program:
        return []

    applied_constraints = merge_constraints(constraints, span_limits)
    validator = validator or (
        lambda program, target: validate_program(program, target, constraints=applied_constraints)
    )
    repairer = repairer or (
        lambda program, target: repair_program(program, target, constraints=applied_constraints)
    )

    candidate = list(program)
    removal_index = len(candidate) - 1 if index is None else index
    if removal_index < 0 or removal_index >= len(candidate):
        return list(program)

    del candidate[removal_index]

    candidate = repairer(candidate, phrase)

    try:
        validator(candidate, phrase)
    except ProgramValidationError:
        return list(program)

    return candidate


def mutate_tweak(
    program: GPProgram,
    operation: GPPrimitive,
    phrase: PhraseSpan,
    *,
    index: int,
    span_limits: Mapping[str, int] | None = None,
    constraints: ProgramConstraints | None = None,
    validator: Callable[[Sequence[GPPrimitive], PhraseSpan], None] | None = None,
    repairer: Callable[[Sequence[GPPrimitive], PhraseSpan], list[GPPrimitive]] | None = None,
) -> list[GPPrimitive]:
    """Replace an operation at *index* if the tweak survives validation."""

    applied_constraints = merge_constraints(constraints, span_limits)
    validator = validator or (
        lambda program, target: validate_program(program, target, constraints=applied_constraints)
    )
    repairer = repairer or (
        lambda program, target: repair_program(program, target, constraints=applied_constraints)
    )

    if index < 0 or index >= len(program):
        return list(program)

    candidate = list(program)
    candidate[index] = operation

    candidate = repairer(candidate, phrase)

    try:
        validator(candidate, phrase)
    except ProgramValidationError:
        return list(program)

    return candidate


def mutate_program(
    program: GPProgram,
    phrase: PhraseSpan,
    *,
    rng: random.Random | None = None,
    span_limits: Mapping[str, int] | None = None,
    constraints: ProgramConstraints | None = None,
    generator: ProgramFactory | None = None,
) -> list[GPPrimitive]:
    """Apply a random mutation (insert/delete/tweak) to *program*."""

    rng = rng or random.Random()

    if generator is None:
        raise ValueError("mutate_program requires a primitive generator")

    operation = generator()

    if not program:
        return mutate_insert(
            program,
            operation,
            phrase,
            span_limits=span_limits,
            constraints=constraints,
        )

    mutation = rng.choice(["insert", "delete", "tweak"])

    if mutation == "insert":
        index = rng.randint(0, len(program))
        return mutate_insert(
            program,
            operation,
            phrase,
            index=index,
            span_limits=span_limits,
            constraints=constraints,
        )

    if mutation == "delete":
        index = rng.randrange(len(program))
        return mutate_delete(
            program,
            phrase,
            index=index,
            span_limits=span_limits,
            constraints=constraints,
        )

    index = rng.randrange(len(program))
    return mutate_tweak(
        program,
        operation,
        phrase,
        index=index,
        span_limits=span_limits,
        constraints=constraints,
    )


__all__ = [
    "GPProgram",
    "crossover_by_span",
    "mutate_delete",
    "mutate_insert",
    "mutate_program",
    "mutate_tweak",
    "one_point_crossover",
]
