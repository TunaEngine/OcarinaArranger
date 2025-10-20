"""Regression tests covering scoring heuristics for bass arrangements."""

from __future__ import annotations

from domain.arrangement.config import register_instrument_range
from domain.arrangement.difficulty import summarize_difficulty
from domain.arrangement.gp.fitness import FitnessVector, compute_fitness, melody_pitch_penalty
from domain.arrangement.gp.ops import GlobalTranspose, LocalOctave, SpanDescriptor
from domain.arrangement.gp.strategy import (
    GPInstrumentCandidate,
    _difficulty_sort_key,
    _evaluate_program_candidate,
)
from domain.arrangement.gp.strategy_scoring import ScoringPenalties, _melody_shift_penalty
from domain.arrangement.range_guard import enforce_instrument_range
from domain.arrangement.soft_key import InstrumentRange

from tests.domain.arrangement.gp.gp_test_helpers import bass_phrase, gp_config


def test_sort_key_demotes_multi_octave_uniform_shifts() -> None:
    """Pure two-octave shifts should rank below moderate global transposes."""

    instrument = InstrumentRange(min_midi=69, max_midi=89, comfort_center=79)
    register_instrument_range("alto_rank_penalty", instrument)

    phrase = bass_phrase()
    config = gp_config()

    total_duration = phrase.total_duration
    local_program = (
        LocalOctave(span=SpanDescriptor(0, total_duration, "phrase"), octaves=2),
    )
    moderate_program = (GlobalTranspose(semitones=16),)

    penalties = ScoringPenalties(range_clamp_penalty=4.9, range_clamp_melody_bias=4.0)

    local_candidate, _ = _evaluate_program_candidate(
        local_program,
        instrument_id="alto_rank_penalty",
        instrument=instrument,
        phrase=phrase,
        beats_per_measure=4,
        fitness_config=config.fitness_config,
    )
    moderate_candidate, _ = _evaluate_program_candidate(
        moderate_program,
        instrument_id="alto_rank_penalty",
        instrument=instrument,
        phrase=phrase,
        beats_per_measure=4,
        fitness_config=config.fitness_config,
    )

    local_key = _difficulty_sort_key(local_candidate, penalties=penalties)
    moderate_key = _difficulty_sort_key(moderate_candidate, penalties=penalties)

    assert moderate_key < local_key


def test_gp_strategy_prefers_octave_transpose_with_upper_extensions() -> None:
    """High accompaniment tones should not outrank the uniform octave shift."""

    instrument = InstrumentRange(min_midi=57, max_midi=77, comfort_center=67)
    register_instrument_range("bass_bias", instrument)

    phrase = bass_phrase(extra_upper_midi=69)

    transpose_12 = phrase.transpose(12)
    transpose_8 = phrase.transpose(8)

    clamped_12, event_12, _ = enforce_instrument_range(
        transpose_12,
        instrument,
        beats_per_measure=4,
    )
    clamped_8, event_8, _ = enforce_instrument_range(
        transpose_8,
        instrument,
        beats_per_measure=4,
    )

    fitness_12 = compute_fitness(
        original=phrase,
        candidate=clamped_12,
        instrument=instrument,
        program=(GlobalTranspose(semitones=12),),
    )
    fitness_8 = compute_fitness(
        original=phrase,
        candidate=clamped_8,
        instrument=instrument,
        program=(GlobalTranspose(semitones=8),),
    )

    candidate_12 = GPInstrumentCandidate(
        instrument_id="bass_bias",
        instrument=instrument,
        program=(GlobalTranspose(semitones=12),),
        span=clamped_12,
        difficulty=summarize_difficulty(clamped_12, instrument),
        fitness=fitness_12,
        melody_penalty=melody_pitch_penalty(
            phrase, clamped_12, beats_per_measure=4
        ),
        melody_shift_penalty=_melody_shift_penalty(
            phrase, clamped_12, beats_per_measure=4
        ),
        explanations=(event_12,) if event_12 is not None else tuple(),
    )
    candidate_8 = GPInstrumentCandidate(
        instrument_id="bass_bias",
        instrument=instrument,
        program=(GlobalTranspose(semitones=8),),
        span=clamped_8,
        difficulty=summarize_difficulty(clamped_8, instrument),
        fitness=fitness_8,
        melody_penalty=melody_pitch_penalty(
            phrase, clamped_8, beats_per_measure=4
        ),
        melody_shift_penalty=_melody_shift_penalty(
            phrase, clamped_8, beats_per_measure=4
        ),
        explanations=(event_8,) if event_8 is not None else tuple(),
    )

    key_octave = _difficulty_sort_key(candidate_12)
    key_non_octave = _difficulty_sort_key(candidate_8)

    assert key_octave[1] <= key_non_octave[1]
    assert key_octave[2] <= key_non_octave[2]


def test_sort_key_favours_global_transpose_with_clamped_bass() -> None:
    """Global transpose with only bass clamps should outrank the identity."""

    instrument = InstrumentRange(min_midi=57, max_midi=77, comfort_center=67)
    register_instrument_range("bass_bias_fidelity", instrument)

    phrase = bass_phrase()

    clamped_identity, identity_event, _ = enforce_instrument_range(
        phrase,
        instrument,
        beats_per_measure=4,
    )
    transposed = phrase.transpose(12)
    clamped_transpose, transpose_event, _ = enforce_instrument_range(
        transposed,
        instrument,
        beats_per_measure=4,
    )

    identity_fitness = compute_fitness(
        original=phrase,
        candidate=clamped_identity,
        instrument=instrument,
        program=(),
    )
    transpose_fitness = compute_fitness(
        original=phrase,
        candidate=clamped_transpose,
        instrument=instrument,
        program=(GlobalTranspose(semitones=12),),
    )

    identity_melody = melody_pitch_penalty(
        phrase, clamped_identity, beats_per_measure=4
    )
    transpose_melody = melody_pitch_penalty(
        phrase, clamped_transpose, beats_per_measure=4
    )

    candidate_identity = GPInstrumentCandidate(
        instrument_id="bass_bias_fidelity",
        instrument=instrument,
        program=(),
        span=clamped_identity,
        difficulty=summarize_difficulty(clamped_identity, instrument),
        fitness=identity_fitness,
        melody_penalty=identity_melody,
        melody_shift_penalty=_melody_shift_penalty(
            phrase, clamped_identity, beats_per_measure=4
        ),
        explanations=(identity_event,) if identity_event is not None else tuple(),
    )
    candidate_transpose = GPInstrumentCandidate(
        instrument_id="bass_bias_fidelity",
        instrument=instrument,
        program=(GlobalTranspose(semitones=12),),
        span=clamped_transpose,
        difficulty=summarize_difficulty(clamped_transpose, instrument),
        fitness=transpose_fitness,
        melody_penalty=transpose_melody,
        melody_shift_penalty=_melody_shift_penalty(
            phrase, clamped_transpose, beats_per_measure=4
        ),
        explanations=(transpose_event,) if transpose_event is not None else tuple(),
    )

    baseline_fidelity = candidate_identity.fitness.fidelity
    baseline_melody = candidate_identity.melody_penalty

    key_identity = _difficulty_sort_key(
        candidate_identity,
        baseline_fidelity=baseline_fidelity,
        fidelity_importance=1.0,
        baseline_melody=baseline_melody,
        melody_importance=1.0,
    )
    key_transpose = _difficulty_sort_key(
        candidate_transpose,
        baseline_fidelity=baseline_fidelity,
        fidelity_importance=1.0,
        baseline_melody=baseline_melody,
        melody_importance=1.0,
    )

    assert key_transpose < key_identity
    assert key_transpose[0] < key_identity[0]
