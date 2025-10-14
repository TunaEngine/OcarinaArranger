import random

import pytest

from domain.arrangement.gp import (
    GlobalTranspose,
    LocalOctave,
    SimplifyRhythm,
    SpanDescriptor,
    crossover_by_span,
    mutate_delete,
    mutate_insert,
    mutate_program,
    mutate_tweak,
    one_point_crossover,
)
from domain.arrangement.gp.validation import validate_program
from domain.arrangement.phrase import PhraseNote, PhraseSpan


@pytest.fixture
def phrase() -> PhraseSpan:
    notes = (
        PhraseNote(onset=0, duration=240, midi=60),
        PhraseNote(onset=240, duration=240, midi=62),
        PhraseNote(onset=480, duration=240, midi=64),
        PhraseNote(onset=720, duration=240, midi=65),
    )
    return PhraseSpan(notes, pulses_per_quarter=480)


def _span(label: str, start: int, end: int) -> SpanDescriptor:
    return SpanDescriptor(start_onset=start, end_onset=end, label=label)


def test_crossover_by_span_swaps_matching_operations(phrase: PhraseSpan) -> None:
    shared_span = _span("phrase", 0, 480)
    unique_span = _span("phrase", 480, 960)
    full_span = _span("phrase", 0, 960)

    parent_a = [
        LocalOctave(span=shared_span, octaves=1),
        SimplifyRhythm(span=unique_span, subdivisions=4),
    ]
    parent_b = [
        LocalOctave(span=shared_span, octaves=-1),
        GlobalTranspose(semitones=3),
    ]

    rng = random.Random(3)

    child_a, child_b = crossover_by_span(
        parent_a,
        parent_b,
        phrase,
        rng=rng,
        span_limits={"phrase": 2},
    )

    assert child_a[0] == parent_b[0]
    assert child_a[1] == parent_a[1]

    assert child_b[0] == parent_a[0]
    assert child_b[1] == GlobalTranspose(semitones=3, span=full_span)

    validate_program(child_a, phrase, span_limits={"phrase": 2})
    validate_program(child_b, phrase, span_limits={"phrase": 2})


def test_one_point_crossover_is_reproducible_with_seed(phrase: PhraseSpan) -> None:
    span_a = _span("phrase", 0, 480)
    span_b = _span("phrase", 480, 960)
    full_span = _span("phrase", 0, 960)

    parent_a = [
        GlobalTranspose(semitones=2),
        LocalOctave(span=span_a, octaves=1),
        SimplifyRhythm(span=span_b, subdivisions=3),
    ]
    parent_b = [
        GlobalTranspose(semitones=-1),
        SimplifyRhythm(span=span_b, subdivisions=2),
        LocalOctave(span=span_a, octaves=-1),
    ]

    rng = random.Random(9)

    child_a, child_b = one_point_crossover(
        parent_a,
        parent_b,
        phrase,
        rng=rng,
        span_limits={"phrase": 2},
    )

    expected_child_a = [
        GlobalTranspose(semitones=2, span=full_span),
        LocalOctave(span=span_a, octaves=1),
    ]
    expected_child_b = [
        GlobalTranspose(semitones=-1, span=full_span),
        SimplifyRhythm(span=span_b, subdivisions=2),
        LocalOctave(span=span_a, octaves=-1),
        SimplifyRhythm(span=span_b, subdivisions=3),
    ]

    assert child_a == expected_child_a
    assert child_b == expected_child_b

    validate_program(child_a, phrase, span_limits={"phrase": 2})
    validate_program(child_b, phrase, span_limits={"phrase": 2})


def test_mutation_helpers_respect_validation(phrase: PhraseSpan) -> None:
    span_a = _span("phrase", 0, 480)
    program = [LocalOctave(span=span_a, octaves=1)]

    invalid = GlobalTranspose(semitones=99)
    mutated = mutate_insert(program, invalid, phrase, span_limits={"phrase": 2})
    assert mutated == program

    valid = SimplifyRhythm(span=span_a, subdivisions=2)
    mutated = mutate_insert(program, valid, phrase, index=0, span_limits={"phrase": 2})
    assert mutated[0] == valid

    mutated = mutate_delete(mutated, phrase, span_limits={"phrase": 2})
    assert mutated == [valid]

    tweaked = mutate_tweak(mutated, LocalOctave(span=span_a, octaves=-1), phrase, index=0)
    assert tweaked[0] == LocalOctave(span=span_a, octaves=-1)

    validate_program(tweaked, phrase, span_limits={"phrase": 2})


def test_mutate_program_random_strategy(phrase: PhraseSpan) -> None:
    span_a = _span("phrase", 0, 480)
    base = [LocalOctave(span=span_a, octaves=1)]

    counter = {"count": 0}

    def generator() -> LocalOctave:
        counter["count"] += 1
        return LocalOctave(span=span_a, octaves=(-1 if counter["count"] % 2 else 1))

    rng = random.Random(2)
    mutated = mutate_program(base, phrase, rng=rng, span_limits={"phrase": 2}, generator=generator)

    validate_program(mutated, phrase, span_limits={"phrase": 2})
    assert counter["count"] >= 1
