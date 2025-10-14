from __future__ import annotations

from typing import Dict, List

from domain.arrangement.config import register_instrument_range
from domain.arrangement.difficulty import summarize_difficulty
from domain.arrangement.gp import arrange_v3_gp
from domain.arrangement.gp.fitness import (
    FitnessVector,
    compute_fitness,
    melody_pitch_penalty,
)
from domain.arrangement.gp.ops import GlobalTranspose, LocalOctave, SimplifyRhythm, SpanDescriptor
from domain.arrangement.gp.selection import Individual
from domain.arrangement.gp.session import GPSessionResult
from domain.arrangement.gp.session_logging import GPSessionLog
from domain.arrangement.gp.strategy import (
    GPInstrumentCandidate,
    _difficulty_sort_key,
    _melody_shift_penalty,
)
from domain.arrangement.range_guard import enforce_instrument_range
from domain.arrangement.soft_key import InstrumentRange

from tests.domain.arrangement.gp.gp_test_helpers import bass_phrase, gp_config


MELODY_MIDIS = [52, 55, 57, 60, 62, 64, 62, 60, 59, 57]


def _bass_session(winner: Individual, config) -> GPSessionResult:
    return GPSessionResult(
        winner=winner,
        log=GPSessionLog(seed=config.random_seed, config={}),
        archive=(winner,),
        population=(winner,),
        generations=config.generations,
        elapsed_seconds=0.01,
        termination_reason="generation_limit",
    )


def test_gp_strategy_preserves_melody_for_bass_c_sample(monkeypatch) -> None:
    """Regression: keep melody intact for the Bass C sample despite low bass."""

    instrument = InstrumentRange(min_midi=57, max_midi=77, comfort_center=67)
    register_instrument_range("bass", instrument)

    phrase = bass_phrase()

    config = gp_config()
    total_duration = len(phrase.notes) * 240
    winner_program = (
        LocalOctave(span=SpanDescriptor(0, total_duration), octaves=2),
        SimplifyRhythm(span=SpanDescriptor(0, total_duration), subdivisions=3),
        SimplifyRhythm(span=SpanDescriptor(0, total_duration), subdivisions=3),
    )
    winner = Individual(
        program=winner_program,
        fitness=FitnessVector(
            playability=0.2,
            fidelity=0.2,
            tessitura=0.2,
            program_size=3.0,
        ),
    )
    fake_result = _bass_session(winner, config)

    monkeypatch.setattr(
        "domain.arrangement.gp.strategy.run_gp_session",
        lambda *_args, **_kwargs: fake_result,
    )

    result = arrange_v3_gp(
        phrase,
        instrument_id="bass",
        config=config,
    )

    chosen_program = result.chosen.program
    assert chosen_program and isinstance(chosen_program[0], GlobalTranspose)
    assert chosen_program[0].semitones == 12

    grouped: Dict[int, List[int]] = {}
    for note in result.chosen.span.notes:
        grouped.setdefault(note.onset, []).append(note.midi)

    top_voice = [max(grouped[onset]) for onset in sorted(grouped)]
    expected_top = [midi + 12 for midi in MELODY_MIDIS]
    assert top_voice[-len(expected_top) :] == expected_top
    assert top_voice[0] >= instrument.min_midi


def test_gp_strategy_adds_transpose_when_intro_is_only_bass(monkeypatch) -> None:
    """Regression: melody after a bass-only intro should still drive auto-range."""

    instrument = InstrumentRange(min_midi=57, max_midi=77, comfort_center=67)
    register_instrument_range("bass", instrument)

    phrase = bass_phrase(intro_eighths=4)

    config = gp_config()
    total_duration = len(phrase.notes) * 240
    winner_program = (
        LocalOctave(span=SpanDescriptor(0, total_duration), octaves=2),
        SimplifyRhythm(span=SpanDescriptor(0, total_duration), subdivisions=3),
        SimplifyRhythm(span=SpanDescriptor(0, total_duration), subdivisions=3),
    )
    winner = Individual(
        program=winner_program,
        fitness=FitnessVector(
            playability=0.2,
            fidelity=0.2,
            tessitura=0.2,
            program_size=3.0,
        ),
    )
    fake_result = _bass_session(winner, config)

    monkeypatch.setattr(
        "domain.arrangement.gp.strategy.run_gp_session",
        lambda *_args, **_kwargs: fake_result,
    )

    result = arrange_v3_gp(
        phrase,
        instrument_id="bass",
        config=config,
    )

    chosen_program = result.chosen.program
    assert chosen_program and isinstance(chosen_program[0], GlobalTranspose)
    assert chosen_program[0].semitones == 12

    grouped: Dict[int, List[int]] = {}
    for note in result.chosen.span.notes:
        grouped.setdefault(note.onset, []).append(note.midi)

    top_voice = [max(grouped[onset]) for onset in sorted(grouped)]
    expected_top = [midi + 12 for midi in MELODY_MIDIS]
    assert top_voice[-len(expected_top) :] == expected_top
    assert any(min(group) == instrument.min_midi for group in grouped.values())


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

