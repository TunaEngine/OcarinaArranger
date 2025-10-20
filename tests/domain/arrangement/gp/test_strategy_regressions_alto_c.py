"""Alto C regression scenarios covering penalty tuning behaviour."""

from __future__ import annotations

from domain.arrangement.config import GraceSettings, register_instrument_range
from domain.arrangement.difficulty import summarize_difficulty
from domain.arrangement.gp import GPSessionConfig, arrange_v3_gp
from domain.arrangement.gp.fitness import FitnessVector
from dataclasses import replace

from domain.arrangement.gp.ops import GlobalTranspose, SimplifyRhythm, SpanDescriptor
from domain.arrangement.gp.program_utils import apply_program
from domain.arrangement.gp.strategy import (
    GPInstrumentCandidate,
    _difficulty_sort_key,
    _score_instrument,
)
from domain.arrangement.gp.strategy_scoring import ScoringPenalties
from domain.arrangement.range_guard import enforce_instrument_range
from domain.arrangement.soft_key import InstrumentRange
from ocarina_tools.pitch import parse_note_name
from tests.domain.arrangement.gp.gp_test_helpers import make_span


def test_alto_c_excerpt_prefers_uniform_plus_sixteen() -> None:
    instrument = InstrumentRange(min_midi=69, max_midi=89, comfort_center=79)
    register_instrument_range("alto_c_excerpt", instrument)
    base_midis = [57, 56, 57, 59, 60, 57, 53, 57, 56, 57, 60, 64, 69, 65]
    phrase = make_span(base_midis)

    config = GPSessionConfig(
        generations=20,
        population_size=32,
        archive_size=8,
        random_seed=0,
        random_program_count=8,
        crossover_rate=0.8,
        mutation_rate=0.2,
        log_best_programs=3,
    )

    result = arrange_v3_gp(
        phrase,
        instrument_id="alto_c_excerpt",
        config=config,
    )

    chosen = result.chosen.program
    assert chosen and isinstance(chosen[0], GlobalTranspose)
    assert chosen[0].semitones == 16
    arranged_midis = [note.midi for note in result.chosen.span.notes[: len(base_midis)]]
    assert arranged_midis == [midi + 16 for midi in base_midis]


def test_melody_shift_weight_can_unlock_higher_transpose(monkeypatch) -> None:
    instrument = InstrumentRange(min_midi=69, max_midi=89, comfort_center=79)
    register_instrument_range("alto_c_shift_weight", instrument)
    phrase = make_span([57, 56, 57, 59, 60, 57, 53, 57, 56, 57, 60, 64, 69, 65, 30])

    programs = (
        (GlobalTranspose(12),),
        (GlobalTranspose(16),),
    )

    monkeypatch.setattr(
        "domain.arrangement.gp.strategy._auto_range_programs",
        lambda *_args, **_kwargs: (),
    )

    base_config = GPSessionConfig()

    base_penalties = ScoringPenalties(
        range_clamp_penalty=4.0,
        range_clamp_melody_bias=4.0,
    )

    default_candidate, default_key, _ = _score_instrument(
        instrument_id="alto_c_shift_weight",
        instrument=instrument,
        phrase=phrase,
        programs=programs,
        fitness_config=base_config.fitness_config,
        beats_per_measure=4,
        penalties=base_penalties,
    )
    assert default_candidate.program[0].semitones == 12

    tuned_candidate, tuned_key, _ = _score_instrument(
        instrument_id="alto_c_shift_weight",
        instrument=instrument,
        phrase=phrase,
        programs=programs,
        fitness_config=base_config.fitness_config,
        beats_per_measure=4,
        penalties=replace(base_penalties, melody_shift_weight=0.1),
    )
    assert tuned_candidate.program[0].semitones == 12
    assert tuned_key < default_key


def test_score_instrument_threads_grace_settings(monkeypatch) -> None:
    instrument = InstrumentRange(min_midi=69, max_midi=89, comfort_center=79)
    register_instrument_range("alto_c_grace_forward", instrument)
    phrase = make_span([60, 62, 64, 65])

    programs = (tuple(),)
    expected_grace = GraceSettings(policy="tempo-weighted", fractions=(0.5, 0.25))

    from domain.arrangement.gp import strategy as strategy_module

    original_evaluate = strategy_module._evaluate_program_candidate
    captured: dict[str, GraceSettings | None] = {}

    def _capture_evaluate(program, **kwargs):
        captured["grace"] = kwargs.get("grace_settings")
        return original_evaluate(program, **kwargs)

    monkeypatch.setattr(strategy_module, "_evaluate_program_candidate", _capture_evaluate)

    candidate, _, _ = _score_instrument(
        instrument_id="alto_c_grace_forward",
        instrument=instrument,
        phrase=phrase,
        programs=programs,
        fitness_config=None,
        beats_per_measure=4,
        grace_settings=expected_grace,
    )

    assert candidate.instrument_id == "alto_c_grace_forward"
    assert captured["grace"] is expected_grace


def test_rhythm_simplify_weight_penalises_simplification_programs() -> None:
    instrument = InstrumentRange(min_midi=60, max_midi=84, comfort_center=72)
    span = make_span([72, 74, 76, 77])
    difficulty = summarize_difficulty(span, instrument)
    candidate = GPInstrumentCandidate(
        instrument_id="test",
        instrument=instrument,
        program=(SimplifyRhythm(SpanDescriptor(), subdivisions=3),),
        span=span,
        difficulty=difficulty,
        fitness=FitnessVector(
            playability=0.5,
            fidelity=0.6,
            tessitura=0.4,
            program_size=0.3,
        ),
        melody_penalty=0.25,
        melody_shift_penalty=0.0,
        explanations=(),
    )

    baseline_penalties = ScoringPenalties(rhythm_simplify_weight=1.0)
    default_key = _difficulty_sort_key(
        candidate,
        baseline_fidelity=None,
        fidelity_importance=1.0,
        baseline_melody=None,
        melody_importance=1.0,
        penalties=baseline_penalties,
    )
    heavy_key = _difficulty_sort_key(
        candidate,
        baseline_fidelity=None,
        fidelity_importance=1.0,
        baseline_melody=None,
        melody_importance=1.0,
        penalties=ScoringPenalties(rhythm_simplify_weight=4.0),
    )
    light_key = _difficulty_sort_key(
        candidate,
        baseline_fidelity=None,
        fidelity_importance=1.0,
        baseline_melody=None,
        melody_importance=1.0,
        penalties=ScoringPenalties(rhythm_simplify_weight=0.25),
    )

    clean_candidate = replace(candidate, program=tuple())
    heavy_clean_key = _difficulty_sort_key(
        clean_candidate,
        baseline_fidelity=None,
        fidelity_importance=1.0,
        baseline_melody=None,
        melody_importance=1.0,
        penalties=ScoringPenalties(rhythm_simplify_weight=4.0),
    )

    assert heavy_key[2] > default_key[2]
    assert light_key[2] <= default_key[2]
    assert heavy_key[2] > heavy_clean_key[2]


def _note_sequence_to_midis(note_block: str) -> list[int]:
    tokens = [token.strip() for token in note_block.replace("\n", ",").split(",")]
    return [parse_note_name(token) for token in tokens if token]


def test_rhythm_penalty_discourages_session_winner_simplification() -> None:
    instrument = InstrumentRange(min_midi=69, max_midi=89, comfort_center=79)
    register_instrument_range("alto_c_rhythm_session", instrument)
    phrase = make_span(
        _note_sequence_to_midis(
            """
            A3, G#3, A3, B3, C4, A3, F3, A3, G#3, A3, C4, E4, A4, F4, G4, F4,
            E4, E4, D#4, C#4, D4, B3, C4, B3, A3, G#3, A3, B3, C4, A3, F3,
            A3, G#3, B3, D4, E4, A4, F4, G4, F4, E4, E4, D#4, C#4, D4, B3,
            C4, A#3, B3, F4, E4, F4, F4, G#4, D4, F4, E4, D#4, E4, D4, C#4,
            D4, C#4, D4, F4, E4, G#3, A3, C4, B3, D4, C#4, E4, D4, G4, F4,
            E4, F4, F4, G#4, D4, F4, E4, A4, A3, A4, C5, G#4, D#4, F4, E4,
            D#4, E4, F4, E4, D#4, E4, A4, C5, G#4, D#4, F4, E4, E5, C5, Eb5,
            D5, B4, C5, A4
            """
        )
    )

    base_config = GPSessionConfig(
        generations=5,
        population_size=16,
        random_seed=0,
        scoring_penalties=ScoringPenalties(rhythm_simplify_weight=1.0),
    )
    default_result = arrange_v3_gp(
        phrase,
        instrument_id="alto_c_rhythm_session",
        config=base_config,
    )
    assert any(
        isinstance(operation, SimplifyRhythm)
        for operation in default_result.winner_candidate.program
    )

    tuned_config = replace(
        base_config,
        scoring_penalties=ScoringPenalties(rhythm_simplify_weight=12.0),
    )
    tuned_result = arrange_v3_gp(
        phrase,
        instrument_id="alto_c_rhythm_session",
        config=tuned_config,
    )

    assert not any(
        isinstance(operation, SimplifyRhythm)
        for operation in tuned_result.winner_candidate.program
    )
    assert not any(
        isinstance(operation, SimplifyRhythm)
        for operation in tuned_result.chosen.program
    )


def test_alto_c_full_track_range_ceiling_blocks_plus_sixteen() -> None:
    instrument = InstrumentRange(min_midi=69, max_midi=89, comfort_center=79)
    register_instrument_range("alto_c_full", instrument)
    phrase = make_span(
        _note_sequence_to_midis(
            """
            A3, G#3, A3, B3, C4, A3, F3, A3, G#3, A3, C4, E4, A4, F4, G4, F4,
            E4, E4, D#4, C#4, D4, B3, C4, B3, A3, G#3, A3, B3, C4, A3, F3,
            A3, G#3, B3, D4, E4, A4, F4, G4, F4, E4, E4, D#4, C#4, D4, B3,
            C4, A#3, B3, F4, E4, F4, F4, G#4, D4, F4, E4, D#4, E4, D4, C#4,
            D4, C#4, D4, F4, E4, G#3, A3, C4, B3, D4, C#4, E4, D4, G4, F4,
            E4, F4, F4, G#4, D4, F4, E4, A4, A3, A4, C5, G#4, D#4, F4, E4,
            D#4, E4, F4, E4, D#4, E4, A4, C5, G#4, D#4, F4, E4, E5, C5, Eb5,
            D5, B4, C5, A4
            """
        )
    )

    programs = (
        (GlobalTranspose(12),),
        (GlobalTranspose(16),),
    )

    candidate, _, used_programs = _score_instrument(
        instrument_id="alto_c_full",
        instrument=instrument,
        phrase=phrase,
        programs=programs,
        fitness_config=GPSessionConfig().fitness_config,
        beats_per_measure=4,
        penalties=ScoringPenalties(),
    )

    assert candidate.program and isinstance(candidate.program[0], GlobalTranspose)
    assert candidate.program[0].semitones == 12

    plus_sixteen = next(
        program
        for program in used_programs
        if program and isinstance(program[0], GlobalTranspose)
        and program[0].semitones == 16
    )

    raw_shift = apply_program(plus_sixteen, phrase)
    assert max(note.midi for note in raw_shift.notes) > instrument.max_midi

    clamped_span, range_event, _ = enforce_instrument_range(
        raw_shift, instrument, beats_per_measure=4
    )
    assert range_event is not None
    assert max(note.midi for note in clamped_span.notes) <= instrument.max_midi

    extended = InstrumentRange(min_midi=69, max_midi=95, comfort_center=82)
    register_instrument_range("alto_c_full_extended", extended)
    extended_candidate, _, _ = _score_instrument(
        instrument_id="alto_c_full_extended",
        instrument=extended,
        phrase=phrase,
        programs=programs,
        fitness_config=GPSessionConfig().fitness_config,
        beats_per_measure=4,
        penalties=ScoringPenalties(),
    )
    assert extended_candidate.program[0].semitones == 16


__all__ = [
    "test_alto_c_excerpt_prefers_uniform_plus_sixteen",
    "test_alto_c_full_track_range_ceiling_blocks_plus_sixteen",
    "test_melody_shift_weight_can_unlock_higher_transpose",
    "test_rhythm_simplify_weight_penalises_simplification_programs",
]
