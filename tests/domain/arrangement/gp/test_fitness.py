"""Unit tests for the arrangement GP fitness evaluation helpers."""

from __future__ import annotations

import pytest

from domain.arrangement.difficulty import summarize_difficulty
from domain.arrangement.gp.fitness import (
    FidelityConfig,
    FitnessConfig,
    FitnessObjective,
    compute_fitness,
    melody_pitch_penalty,
)
from domain.arrangement.gp.ops import GlobalTranspose, LocalOctave, SimplifyRhythm, SpanDescriptor
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange


def _span_for(midis: list[int]) -> PhraseSpan:
    return PhraseSpan(
        tuple(
            PhraseNote(onset=index * 480, duration=480, midi=midi)
            for index, midi in enumerate(midis)
        )
    )


def _poly_span(top: list[int], bottom: list[int]) -> PhraseSpan:
    notes: list[PhraseNote] = []
    for index, melody_midi in enumerate(top):
        onset = index * 480
        notes.append(PhraseNote(onset=onset, duration=480, midi=melody_midi))
        if index < len(bottom):
            notes.append(PhraseNote(onset=onset, duration=480, midi=bottom[index]))
    return PhraseSpan(tuple(notes))


def test_baseline_span_has_zero_penalties() -> None:
    instrument = InstrumentRange(60, 72, comfort_center=66)
    original = _span_for([66, 66, 66])
    summary = summarize_difficulty(original, instrument)

    fitness = compute_fitness(
        original=original,
        candidate=original,
        instrument=instrument,
        difficulty=summary,
        program=(),
    )

    assert fitness.as_tuple() == pytest.approx((0.0, 0.0, 0.0, 0.0))


def test_regression_matches_v2_reference_outputs() -> None:
    instrument = InstrumentRange(60, 72, comfort_center=66)
    original = _span_for([60, 62, 64, 65])
    arranged = _span_for([60, 62, 64, 67])
    summary = summarize_difficulty(arranged, instrument)
    program = [
        GlobalTranspose(semitones=2),
        SimplifyRhythm(span=SpanDescriptor(start_onset=0, end_onset=960), subdivisions=2),
    ]

    fitness = compute_fitness(
        original=original,
        candidate=arranged,
        instrument=instrument,
        difficulty=summary,
        program=program,
    )

    expected = (
        pytest.approx(0.25, rel=1e-6),
        pytest.approx(0.175, rel=1e-6),
        pytest.approx(0.2708333333, rel=1e-6),
        pytest.approx(2.0, rel=1e-6),
    )
    assert fitness.as_tuple() == expected


def test_out_of_range_edits_are_penalised_and_scaled() -> None:
    instrument = InstrumentRange(60, 72, comfort_center=66)
    original = _span_for([60, 60, 60])
    arranged = _span_for([75, 76, 77])
    summary = summarize_difficulty(arranged, instrument)
    program = [
        GlobalTranspose(semitones=7),
        LocalOctave(span=SpanDescriptor(start_onset=0, end_onset=480), octaves=1),
        SimplifyRhythm(span=SpanDescriptor(start_onset=0, end_onset=1440), subdivisions=3),
    ]
    config = FitnessConfig(
        playability=FitnessObjective(weight=2.0),
        fidelity=FitnessObjective(),
        tessitura=FitnessObjective(normalizer=lambda value: min(1.0, value)),
        program_size=FitnessObjective(normalizer=lambda value: value / 5.0),
        fidelity_components=FidelityConfig(contour_weight=0.7, lcs_weight=0.3),
    )

    fitness = compute_fitness(
        original=original,
        candidate=arranged,
        instrument=instrument,
        difficulty=summary,
        program=program,
        config=config,
    )

    assert fitness.playability == pytest.approx(2.0, rel=1e-6)
    assert fitness.fidelity == pytest.approx(1.0, rel=1e-6)
    assert fitness.tessitura == pytest.approx(0.8333333333, rel=1e-6)
    assert fitness.program_size == pytest.approx(0.8, rel=1e-6)


def test_parsimony_penalty_increases_for_repeated_spans() -> None:
    instrument = InstrumentRange(60, 72, comfort_center=66)
    original = _span_for([60, 62, 64, 65])
    arranged = _span_for([61, 63, 64, 65])
    summary = summarize_difficulty(arranged, instrument)

    shared_span = SpanDescriptor(start_onset=0, end_onset=original.total_duration)
    program = [
        GlobalTranspose(semitones=1),
        SimplifyRhythm(span=shared_span, subdivisions=2),
        SimplifyRhythm(span=shared_span, subdivisions=3),
    ]

    fitness = compute_fitness(
        original=original,
        candidate=arranged,
        instrument=instrument,
        difficulty=summary,
        program=program,
    )

    # Three operations, all on the same span, add two extra penalties (3 + 2 = 5)
    assert fitness.program_size == pytest.approx(5.0, rel=1e-6)


def test_pitch_penalty_discourages_semitone_substitutions() -> None:
    instrument = InstrumentRange(60, 84, comfort_center=72)
    original = _span_for([72, 74, 76, 77])
    sharp_variant = _span_for([72, 74, 76, 78])

    default_fitness = compute_fitness(
        original=original,
        candidate=sharp_variant,
        instrument=instrument,
        program=(),
    )

    no_pitch_weight = compute_fitness(
        original=original,
        candidate=sharp_variant,
        instrument=instrument,
        program=(),
        config=FitnessConfig(
            fidelity_components=FidelityConfig(
                contour_weight=0.4,
                lcs_weight=0.6,
                pitch_weight=0.0,
            )
        ),
    )

    assert default_fitness.fidelity > no_pitch_weight.fidelity


def test_melody_pitch_penalty_focuses_on_primary_voice() -> None:
    top_voice = [86, 85, 81, 78, 79, 78, 76]
    harmony_a = [50, 47, 45, 43, 42, 40, 38]
    harmony_b = [52, 49, 47, 45, 44, 42, 40]

    original = _poly_span(top_voice, harmony_a)
    same_melody = _poly_span(top_voice, harmony_b)
    shifted_melody = _poly_span([midi + 2 for midi in top_voice], harmony_a)

    same_penalty = melody_pitch_penalty(original, same_melody, beats_per_measure=4)
    shifted_penalty = melody_pitch_penalty(original, shifted_melody, beats_per_measure=4)

    assert shifted_penalty > same_penalty
    assert shifted_penalty > 0.0


def test_melody_pitch_penalty_penalises_octave_shifts() -> None:
    melody = [62, 64, 65, 67]
    original = _poly_span(melody, [])
    shifted = _poly_span([midi + 12 for midi in melody], [])

    penalty = melody_pitch_penalty(original, shifted, beats_per_measure=4)

    assert penalty > 0.0
