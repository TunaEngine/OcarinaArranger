import random

from domain.arrangement.difficulty import difficulty_score, summarize_difficulty
from domain.arrangement.gp import (
    GlobalTranspose,
    LocalOctave,
    SimplifyRhythm,
    SpanDescriptor,
    generate_random_program,
    seed_programs,
    translate_salvage_trace,
)
from domain.arrangement.gp.penalties import ScoringPenalties
from domain.arrangement.gp.program_ops import ensure_population
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.salvage import default_salvage_cascade
from domain.arrangement.soft_key import InstrumentRange
from domain.arrangement.gp.validation import validate_program


def _make_span(midis: list[int], *, pulses: int = 480) -> PhraseSpan:
    return PhraseSpan(
        tuple(
            PhraseNote(
                onset=index * (pulses // 2),
                duration=pulses // 2,
                midi=midi,
                tags=frozenset({"octave-shiftable"}),
            )
            for index, midi in enumerate(midis)
        ),
        pulses_per_quarter=pulses,
    )


def _difficulty(span: PhraseSpan, instrument: InstrumentRange) -> float:
    return difficulty_score(summarize_difficulty(span, instrument))


def test_salvage_translation_reproduces_octave_shift() -> None:
    span = _make_span([84, 85, 86, 87])
    instrument = InstrumentRange(72, 84)
    cascade = default_salvage_cascade(threshold=0.6)

    result = cascade.run(span, lambda s: _difficulty(s, instrument))

    program = translate_salvage_trace(result.explanations, span=span)

    expected = [
        LocalOctave(
            span=SpanDescriptor(start_onset=0, end_onset=960, label="phrase"),
            octaves=-1,
        )
    ]

    assert program == expected


def test_random_program_generation_is_validated() -> None:
    span = _make_span([60, 62, 64, 65, 67])
    instrument = InstrumentRange(60, 72)
    rng = random.Random(42)
    limits = {"phrase": 2}

    for _ in range(10):
        program = generate_random_program(
            span,
            instrument,
            rng=rng,
            max_length=2,
            span_limits=limits,
        )
        if program:
            validate_program(program, span, span_limits=limits)


def test_seed_programs_include_salvage_and_recipes() -> None:
    span = _make_span([84, 85, 86, 87])
    instrument = InstrumentRange(72, 84)
    cascade = default_salvage_cascade(threshold=0.6)
    result = cascade.run(span, lambda s: _difficulty(s, instrument))

    programs = seed_programs(
        span,
        instrument,
        salvage_events=result.explanations,
        rng=random.Random(7),
        random_count=3,
        span_limits={"phrase": 2},
    )

    assert programs
    assert programs[0] == [
        LocalOctave(
            span=SpanDescriptor(start_onset=0, end_onset=960, label="phrase"),
            octaves=-1,
        )
    ]

    for program in programs:
        validate_program(program, span, span_limits={"phrase": 2})


def test_high_rhythm_penalty_blocks_simplify_generation() -> None:
    span = _make_span([60, 62, 64, 65, 67, 69])
    instrument = InstrumentRange(60, 84)
    penalties = ScoringPenalties(rhythm_simplify_weight=10.0)

    programs = seed_programs(
        span,
        instrument,
        rng=random.Random(3),
        random_count=4,
        penalties=penalties,
    )

    assert programs
    for program in programs:
        assert all(not isinstance(op, SimplifyRhythm) for op in program)

    rng = random.Random(11)
    for _ in range(5):
        program = generate_random_program(
            span,
            instrument,
            rng=rng,
            max_length=2,
            penalties=penalties,
        )
        if program:
            assert all(not isinstance(op, SimplifyRhythm) for op in program)


def test_high_melody_shift_penalty_blocks_local_octaves() -> None:
    span = _make_span([60, 62, 64, 65, 67, 69])
    instrument = InstrumentRange(60, 84)
    penalties = ScoringPenalties(melody_shift_weight=6.0)

    programs = seed_programs(
        span,
        instrument,
        rng=random.Random(13),
        random_count=4,
        penalties=penalties,
    )

    assert programs
    for program in programs:
        assert all(not isinstance(op, LocalOctave) for op in program)

    rng = random.Random(17)
    for _ in range(5):
        program = generate_random_program(
            span,
            instrument,
            rng=rng,
            max_length=2,
            penalties=penalties,
        )
        if program:
            assert all(not isinstance(op, LocalOctave) for op in program)


def test_high_fidelity_penalty_blocks_non_transpose_edits() -> None:
    span = _make_span([60, 62, 64, 65, 67, 69])
    instrument = InstrumentRange(60, 84)
    penalties = ScoringPenalties(fidelity_weight=5.0)

    programs = seed_programs(
        span,
        instrument,
        rng=random.Random(19),
        random_count=4,
        penalties=penalties,
    )

    assert programs
    for program in programs:
        assert all(
            isinstance(op, GlobalTranspose)
            for op in program
        )

    rng = random.Random(23)
    for _ in range(5):
        program = generate_random_program(
            span,
            instrument,
            rng=rng,
            max_length=2,
            penalties=penalties,
        )
        if program:
            assert all(isinstance(op, GlobalTranspose) for op in program)


def test_ensure_population_falls_back_to_duplicates(monkeypatch) -> None:
    span = _make_span([60, 62, 64])
    instrument = InstrumentRange(60, 72)
    descriptor = SpanDescriptor(
        start_onset=0, end_onset=span.total_duration, label="phrase"
    )
    base_program = [LocalOctave(span=descriptor, octaves=1)]

    def _always_fail(*_, **__):
        raise RuntimeError

    monkeypatch.setattr(
        "domain.arrangement.gp.init.generate_random_program", _always_fail
    )

    penalties = ScoringPenalties(rhythm_simplify_weight=10.0)

    population = ensure_population(
        [base_program],
        required=4,
        phrase=span,
        instrument=instrument,
        rng=random.Random(9),
        span_limits={"phrase": 8},
        penalties=penalties,
    )

    assert len(population) == 4
    assert all(program == base_program for program in population)
