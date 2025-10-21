from domain.arrangement.config import GraceSettings, FAST_WINDWAY_SWITCH_WEIGHT_MAX
from domain.arrangement.gp.evaluation import evaluate_program
from domain.arrangement.gp.strategy_evaluation import _evaluate_program_candidate
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentWindwayRange


def _windway_phrase() -> PhraseSpan:
    return PhraseSpan(
        (
            PhraseNote(onset=0, duration=6, midi=60),
            PhraseNote(onset=6, duration=6, midi=62),
        ),
        pulses_per_quarter=24,
    )


def _windway_instrument() -> InstrumentWindwayRange:
    return InstrumentWindwayRange(
        min_midi=55,
        max_midi=72,
        windway_ids=("primary", "secondary"),
        windway_map={60: (0,), 62: (1,)},
    )


def test_fast_switch_weight_affects_candidate_playability() -> None:
    instrument = _windway_instrument()
    phrase = _windway_phrase()

    moderate = GraceSettings(fast_windway_switch_weight=1.0)
    boosted = GraceSettings(fast_windway_switch_weight=FAST_WINDWAY_SWITCH_WEIGHT_MAX)
    muted = GraceSettings(fast_windway_switch_weight=0.0)

    moderate_candidate, _ = _evaluate_program_candidate(
        (),
        instrument_id="windway",
        instrument=instrument,
        phrase=phrase,
        beats_per_measure=4,
        fitness_config=None,
        grace_settings=moderate,
    )
    boosted_candidate, _ = _evaluate_program_candidate(
        (),
        instrument_id="windway",
        instrument=instrument,
        phrase=phrase,
        beats_per_measure=4,
        fitness_config=None,
        grace_settings=boosted,
    )
    muted_candidate, _ = _evaluate_program_candidate(
        (),
        instrument_id="windway",
        instrument=instrument,
        phrase=phrase,
        beats_per_measure=4,
        fitness_config=None,
        grace_settings=muted,
    )

    assert moderate_candidate.difficulty.fast_windway_switch_exposure > 0.0
    assert moderate_candidate.fitness.playability > muted_candidate.fitness.playability
    assert boosted_candidate.fitness.playability > moderate_candidate.fitness.playability


def test_evaluate_program_threads_grace_settings_into_fitness() -> None:
    instrument = _windway_instrument()
    phrase = _windway_phrase()

    heavy = GraceSettings(fast_windway_switch_weight=FAST_WINDWAY_SWITCH_WEIGHT_MAX)
    muted = GraceSettings(fast_windway_switch_weight=0.0)

    heavy_individual = evaluate_program(
        (),
        phrase=phrase,
        instrument=instrument,
        fitness_config=None,
        penalties=None,
        grace_settings=heavy,
    )
    muted_individual = evaluate_program(
        (),
        phrase=phrase,
        instrument=instrument,
        fitness_config=None,
        penalties=None,
        grace_settings=muted,
    )

    assert heavy_individual.fitness.playability > muted_individual.fitness.playability
