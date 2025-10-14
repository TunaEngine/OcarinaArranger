import pytest

from domain.arrangement.gp.ops import GlobalTranspose, LocalOctave, SimplifyRhythm, SpanDescriptor
from domain.arrangement.gp.repair import repair_program
from domain.arrangement.gp.validation import (
    ParameterValidationError,
    ProgramConstraints,
    ProgramLengthError,
    SpanLimitError,
    SpanResolutionError,
    WindowLimitError,
    validate_program,
)
from domain.arrangement.phrase import PhraseNote, PhraseSpan


@pytest.fixture
def phrase() -> PhraseSpan:
    notes = (
        PhraseNote(onset=0, duration=240, midi=60),
        PhraseNote(onset=240, duration=240, midi=62),
        PhraseNote(onset=480, duration=240, midi=64),
        PhraseNote(onset=720, duration=240, midi=67),
    )
    return PhraseSpan(notes, pulses_per_quarter=480)


def test_validate_program_accepts_well_formed_program(phrase: PhraseSpan) -> None:
    program = [
        GlobalTranspose(semitones=2),
        LocalOctave(span=SpanDescriptor(start_onset=0, end_onset=480, label="motif"), octaves=1),
        SimplifyRhythm(span=SpanDescriptor(start_onset=480, end_onset=phrase.total_duration, label="motif"), subdivisions=2),
    ]

    validate_program(program, phrase, span_limits={"motif": 2})


def test_validate_program_rejects_parameter_out_of_range(phrase: PhraseSpan) -> None:
    program = [GlobalTranspose(semitones=20)]

    with pytest.raises(ParameterValidationError):
        validate_program(program, phrase)


def test_validate_program_rejects_span_outside_phrase(phrase: PhraseSpan) -> None:
    program = [
        LocalOctave(
            span=SpanDescriptor(start_onset=0, end_onset=phrase.total_duration + 240, label="motif"),
            octaves=1,
        )
    ]

    with pytest.raises(SpanResolutionError):
        validate_program(program, phrase)


def test_validate_program_enforces_span_limit(phrase: PhraseSpan) -> None:
    descriptor = SpanDescriptor(start_onset=0, end_onset=480, label="motif")
    program = [
        LocalOctave(span=descriptor, octaves=1),
        LocalOctave(span=descriptor, octaves=-1),
    ]

    with pytest.raises(SpanLimitError):
        validate_program(program, phrase, span_limits={"motif": 1})


def test_validate_program_enforces_max_operation_cap(phrase: PhraseSpan) -> None:
    program = [
        GlobalTranspose(semitones=1),
        LocalOctave(span=SpanDescriptor(start_onset=0, end_onset=480), octaves=1),
        SimplifyRhythm(span=SpanDescriptor(start_onset=0, end_onset=phrase.total_duration), subdivisions=2),
    ]

    constraints = ProgramConstraints(max_operations=2)

    with pytest.raises(ProgramLengthError):
        validate_program(program, phrase, constraints=constraints)


def test_validate_program_enforces_window_limits(phrase: PhraseSpan) -> None:
    descriptor = SpanDescriptor(start_onset=0, end_onset=480, label="motif")
    overlapping = SpanDescriptor(start_onset=240, end_onset=720, label="motif")
    program = [
        SimplifyRhythm(span=descriptor, subdivisions=2),
        LocalOctave(span=overlapping, octaves=1),
    ]

    constraints = ProgramConstraints(
        max_operations=5,
        max_operations_per_window=1,
        window_bars=1,
    )

    with pytest.raises(WindowLimitError):
        validate_program(program, phrase, constraints=constraints)


def test_repair_program_trims_merges_and_drops_invalid_ops(phrase: PhraseSpan) -> None:
    program = [
        LocalOctave(span=SpanDescriptor(start_onset=-240, end_onset=2400, label="riff"), octaves=1),
        LocalOctave(span=SpanDescriptor(start_onset=0, end_onset=2400, label="riff"), octaves=2),
        GlobalTranspose(semitones=7),
        GlobalTranspose(semitones=7),
        SimplifyRhythm(span=SpanDescriptor(start_onset=0, end_onset=2400, label="riff"), subdivisions=3),
        SimplifyRhythm(span=SpanDescriptor(start_onset=480, end_onset=960, label="riff"), subdivisions=6),
    ]

    repaired = repair_program(program, phrase, span_limits={"riff": 3})

    assert len(repaired) == 3

    local_octave, transpose, rhythm = repaired
    assert local_octave.span == SpanDescriptor(
        start_onset=0, end_onset=phrase.total_duration, label="riff"
    )
    assert local_octave.octaves == 2

    assert transpose.semitones == 12

    assert rhythm.span == SpanDescriptor(
        start_onset=0, end_onset=phrase.total_duration, label="riff"
    )
    assert rhythm.subdivisions == 3


def test_repair_program_respects_span_limits(phrase: PhraseSpan) -> None:
    descriptor = SpanDescriptor(start_onset=0, end_onset=480, label="motif")
    program = [
        SimplifyRhythm(span=descriptor, subdivisions=2),
        SimplifyRhythm(span=descriptor, subdivisions=1),
    ]

    repaired = repair_program(program, phrase, span_limits={"motif": 1})

    assert len(repaired) == 1
    assert repaired[0].subdivisions == 2


def test_repair_program_enforces_max_operations(phrase: PhraseSpan) -> None:
    descriptor = SpanDescriptor(start_onset=0, end_onset=phrase.total_duration)
    program = [
        GlobalTranspose(semitones=1),
        SimplifyRhythm(span=descriptor, subdivisions=2),
        LocalOctave(span=descriptor, octaves=1),
    ]

    repaired = repair_program(
        program,
        phrase,
        constraints=ProgramConstraints(max_operations=2),
    )

    assert len(repaired) == 2


def test_repair_program_reenables_limits_when_merge_cancels(phrase: PhraseSpan) -> None:
    descriptor = SpanDescriptor(start_onset=0, end_onset=phrase.total_duration, label="motif")
    program = [
        LocalOctave(span=descriptor, octaves=1),
        LocalOctave(span=descriptor, octaves=-1),
        LocalOctave(span=descriptor, octaves=1),
    ]

    constraints = ProgramConstraints(max_operations_per_window=1, window_bars=1)

    repaired = repair_program(
        program,
        phrase,
        span_limits={"motif": 1},
        constraints=constraints,
    )

    assert repaired == [LocalOctave(span=descriptor, octaves=1)]
