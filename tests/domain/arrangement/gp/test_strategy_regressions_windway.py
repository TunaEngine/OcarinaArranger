from __future__ import annotations

from domain.arrangement.config import GraceSettings
from domain.arrangement.gp.ops import GlobalTranspose
from domain.arrangement.gp.strategy import (
    _difficulty_sort_key,
    _evaluate_program_candidate,
    _score_instrument,
)
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentWindwayRange

from tests.domain.arrangement.gp.gp_test_helpers import gp_config


def _fast_switch_phrase() -> PhraseSpan:
    sixteenth = 120
    notes = [
        PhraseNote(onset=index * sixteenth, duration=sixteenth, midi=midi)
        for index, midi in enumerate((68, 71, 68, 71))
    ]
    return PhraseSpan(tuple(notes), pulses_per_quarter=480)


def _fast_switch_instrument() -> InstrumentWindwayRange:
    return InstrumentWindwayRange(
        min_midi=60,
        max_midi=80,
        windway_ids=("primary", "secondary"),
        windway_map={
            60: (0,),
            61: (0,),
            62: (0,),
            63: (0,),
            64: (0,),
            65: (0,),
            66: (0,),
            67: (0,),
            68: (0,),
            69: (0,),
            70: (1,),
            71: (1,),
            72: (1,),
            73: (1,),
            74: (1,),
            75: (1,),
            76: (1,),
            77: (1,),
            78: (1,),
            79: (1,),
            80: (1,),
        },
    )


def test_difficulty_sort_key_penalizes_fast_windway_switches() -> None:
    instrument = _fast_switch_instrument()
    phrase = _fast_switch_phrase()

    heavy = GraceSettings(fast_windway_switch_weight=3.0)
    muted = GraceSettings(fast_windway_switch_weight=0.0)

    fast_candidate, _ = _evaluate_program_candidate(
        (),
        instrument_id="windway",
        instrument=instrument,
        phrase=phrase,
        beats_per_measure=4,
        fitness_config=None,
        grace_settings=heavy,
    )
    shifted_candidate, _ = _evaluate_program_candidate(
        (GlobalTranspose(-2),),
        instrument_id="windway",
        instrument=instrument,
        phrase=phrase,
        beats_per_measure=4,
        fitness_config=None,
        grace_settings=heavy,
    )

    assert fast_candidate.difficulty.fast_windway_switch_exposure > 0.0
    assert (
        shifted_candidate.difficulty.fast_windway_switch_exposure
        < fast_candidate.difficulty.fast_windway_switch_exposure
    )

    heavy_fast_key = _difficulty_sort_key(fast_candidate, grace_settings=heavy)
    heavy_shifted_key = _difficulty_sort_key(shifted_candidate, grace_settings=heavy)

    expected_penalty = round(
        fast_candidate.difficulty.fast_windway_switch_exposure
        * heavy.fast_windway_switch_weight,
        12,
    )
    assert heavy_fast_key[2] == expected_penalty
    assert heavy_shifted_key[2] == 0.0
    assert heavy_shifted_key < heavy_fast_key

    muted_fast_key = _difficulty_sort_key(fast_candidate, grace_settings=muted)
    muted_shifted_key = _difficulty_sort_key(shifted_candidate, grace_settings=muted)

    assert muted_fast_key[2] == muted_shifted_key[2] == 0.0


def test_score_instrument_prefers_windway_safe_transpose_when_weighted(
    monkeypatch,
) -> None:
    instrument = _fast_switch_instrument()
    phrase = _fast_switch_phrase()
    config = gp_config()
    programs = (tuple(), (GlobalTranspose(-2),))

    def _fixed_candidates(base_programs, **_kwargs):
        return [tuple(program) for program in base_programs], ()

    monkeypatch.setattr(
        "domain.arrangement.gp.strategy_instrument.generate_candidate_programs",
        _fixed_candidates,
    )

    muted = GraceSettings(fast_windway_switch_weight=0.0)
    heavy = GraceSettings(fast_windway_switch_weight=3.0)

    muted_candidate, _, _ = _score_instrument(
        instrument_id="windway",
        instrument=instrument,
        phrase=phrase,
        programs=programs,
        fitness_config=config.fitness_config,
        beats_per_measure=4,
        penalties=config.scoring_penalties,
        grace_settings=muted,
    )
    heavy_candidate, _, _ = _score_instrument(
        instrument_id="windway",
        instrument=instrument,
        phrase=phrase,
        programs=programs,
        fitness_config=config.fitness_config,
        beats_per_measure=4,
        penalties=config.scoring_penalties,
        grace_settings=heavy,
    )

    assert muted_candidate.program == tuple()
    assert heavy_candidate.program
    first_op = heavy_candidate.program[0]
    assert isinstance(first_op, GlobalTranspose)
    assert first_op.semitones == -2
