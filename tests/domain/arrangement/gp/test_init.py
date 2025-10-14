import random

from domain.arrangement.difficulty import difficulty_score, summarize_difficulty
from domain.arrangement.gp import (
    LocalOctave,
    SpanDescriptor,
    generate_random_program,
    seed_programs,
    translate_salvage_trace,
)
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
