"""Integration-style tests for the GP arrangement strategy helpers."""

from __future__ import annotations

from dataclasses import replace

from domain.arrangement.api import arrange
from domain.arrangement.gp import arrange_v3_gp
from domain.arrangement.gp.fitness import FitnessConfig, FitnessObjective, FitnessVector
from domain.arrangement.gp.ops import GlobalTranspose
from domain.arrangement.gp.program_utils import apply_program
from domain.arrangement.gp.selection import Individual
from domain.arrangement.gp.session import GPSessionResult
from domain.arrangement.gp.session_logging import GPSessionLog
from domain.arrangement.soft_key import InstrumentRange
from ocarina_tools import midi_to_name
from domain.arrangement.melody import isolate_melody

from tests.domain.arrangement.gp._strategy_test_utils import (
    _gp_config,
    _make_poly_span,
    _make_span,
    _register_instruments,
    clear_registry,
)


def setup_function() -> None:
    clear_registry()


def test_gp_strategy_matches_v2_ranking_when_winner_shared() -> None:
    phrase = _make_span([84, 72, 60, 67])
    _register_instruments(
        (
            ("current", InstrumentRange(min_midi=60, max_midi=84, comfort_center=72)),
            ("star_a", InstrumentRange(min_midi=55, max_midi=79, comfort_center=67)),
            ("star_b", InstrumentRange(min_midi=62, max_midi=86, comfort_center=74)),
        )
    )

    starred = ("star_a", "current", "star_b")
    config = _gp_config()
    v2_result = arrange(
        phrase,
        instrument_id="current",
        starred_ids=starred,
        strategy="starred-best",
    )

    gp_result = arrange_v3_gp(
        phrase,
        instrument_id="current",
        starred_ids=starred,
        config=config,
    )

    v2_ids = [candidate.instrument_id for candidate in v2_result.comparisons]
    gp_ids = [candidate.instrument_id for candidate in gp_result.comparisons]
    assert gp_ids[0] == v2_ids[0] == "current"
    assert set(gp_ids[1:]) == set(v2_ids[1:])
    assert gp_result.chosen.instrument_id == v2_result.chosen.instrument_id
    # Fidelity weighting keeps the unmodified instrument ahead of easier but
    # octave-shifted options so the melody stays in tune.
    assert gp_result.chosen.instrument_id == "current"
    assert gp_result.comparisons[0].fitness.fidelity <= gp_result.comparisons[1].fitness.fidelity
    assert gp_result.termination_reason == "generation_limit"
    assert gp_result.session.generations == config.generations
    assert len(gp_result.archive_summary) <= config.archive_size
    assert gp_result.fallback is None
    assert gp_result.winner_candidate.program == tuple(gp_result.session.winner.program)
    assert gp_result.winner_candidate.instrument_id == "current"


def test_gp_strategy_preserves_v2_tie_break_order() -> None:
    phrase = _make_span([72, 74, 76, 77])
    shared_range = InstrumentRange(min_midi=60, max_midi=84, comfort_center=72)
    _register_instruments(
        (
            ("current", shared_range),
            ("star_a", shared_range),
            ("star_b", shared_range),
        )
    )

    starred = ("star_a", "star_b")
    v2_result = arrange(
        phrase,
        instrument_id="current",
        starred_ids=starred,
        strategy="starred-best",
    )

    gp_result = arrange_v3_gp(
        phrase,
        instrument_id="current",
        starred_ids=starred,
        config=_gp_config(),
    )

    v2_ids = [candidate.instrument_id for candidate in v2_result.comparisons]
    gp_ids = [candidate.instrument_id for candidate in gp_result.comparisons]
    assert gp_ids == v2_ids
    assert "current" not in gp_ids


def test_gp_strategy_includes_current_when_starred() -> None:
    phrase = _make_span([72, 74, 76])
    shared_range = InstrumentRange(min_midi=60, max_midi=84, comfort_center=72)
    _register_instruments((("current", shared_range), ("starred", shared_range)))

    starred = ("starred", "current", "starred")
    v2_result = arrange(
        phrase,
        instrument_id="current",
        starred_ids=starred,
        strategy="starred-best",
    )

    gp_result = arrange_v3_gp(
        phrase,
        instrument_id="current",
        starred_ids=starred,
        config=_gp_config(),
    )

    v2_ids = [candidate.instrument_id for candidate in v2_result.comparisons]
    gp_ids = [candidate.instrument_id for candidate in gp_result.comparisons]
    assert gp_ids == v2_ids
    assert gp_ids[0] == "current"
    assert gp_result.chosen.instrument_id == v2_result.chosen.instrument_id


def test_gp_strategy_respects_generation_limit() -> None:
    phrase = _make_span([67, 69, 71])
    _register_instruments((("ocarina", InstrumentRange(min_midi=60, max_midi=84, comfort_center=72)),))

    config = replace(_gp_config(), generations=2, population_size=5, archive_size=5)
    result = arrange_v3_gp(
        phrase,
        instrument_id="ocarina",
        config=config,
    )

    assert result.session.generations == 2
    assert len(result.session.log.generations) == 2
    assert result.termination_reason == "generation_limit"
    assert result.winner_candidate.program == tuple(result.session.winner.program)


def test_gp_strategy_time_budget_triggers_fallback() -> None:
    phrase = _make_span([60, 62, 64, 65])
    _register_instruments((("ocarina", InstrumentRange(min_midi=60, max_midi=84, comfort_center=72)),))

    config = replace(_gp_config(), time_budget_seconds=0.0, generations=3)

    result = arrange_v3_gp(
        phrase,
        instrument_id="ocarina",
        config=config,
    )

    assert result.termination_reason == "time_budget_exceeded"
    assert result.fallback is not None
    expected_fallback = arrange(
        phrase,
        instrument_id="ocarina",
        strategy="starred-best",
    )
    assert result.fallback.chosen.instrument_id == expected_fallback.chosen.instrument_id
    assert [candidate.instrument_id for candidate in result.fallback.comparisons] == [
        candidate.instrument_id for candidate in expected_fallback.comparisons
    ]


def test_gp_strategy_archive_summary_matches_archive_size() -> None:
    phrase = _make_span([64, 65, 67, 69])
    _register_instruments((("ocarina", InstrumentRange(min_midi=60, max_midi=84, comfort_center=72)),))

    config = replace(_gp_config(), archive_size=2)
    result = arrange_v3_gp(
        phrase,
        instrument_id="ocarina",
        config=config,
    )

    assert len(result.archive_summary) <= 2
    assert all(summary.metadata for summary in result.archive_summary)


def test_gp_strategy_clamps_out_of_range_candidates(monkeypatch) -> None:
    phrase = _make_span([60, 64])
    base_range = InstrumentRange(min_midi=60, max_midi=84, comfort_center=72)
    star_range = InstrumentRange(min_midi=55, max_midi=60, comfort_center=58)
    _register_instruments(
        (
            ("current", base_range),
            ("star", star_range),
        )
    )

    config = _gp_config()
    program = (GlobalTranspose(semitones=12),)
    fitness = FitnessVector(playability=0.1, fidelity=0.2, tessitura=0.3, program_size=0.4)
    winner = Individual(program=program, fitness=fitness)
    session_log = GPSessionLog(seed=config.random_seed, config={}, generations=[])
    fake_result = GPSessionResult(
        winner=winner,
        log=session_log,
        archive=(winner,),
        population=(winner,),
        generations=1,
        elapsed_seconds=0.01,
        termination_reason="generation_limit",
    )

    def _fake_session(*args, **kwargs) -> GPSessionResult:
        return fake_result

    monkeypatch.setattr("domain.arrangement.gp.strategy.run_gp_session", _fake_session)

    result = arrange_v3_gp(
        phrase,
        instrument_id="current",
        starred_ids=("star", "current"),
        config=config,
    )

    comparisons = {candidate.instrument_id: candidate for candidate in result.comparisons}
    current_candidate = comparisons["current"]
    star_candidate = comparisons["star"]

    assert any(note.midi > star_range.max_midi for note in current_candidate.span.notes)
    assert all(star_range.min_midi <= note.midi <= star_range.max_midi for note in star_candidate.span.notes)
    assert all(event.reason_code != "range-clamp" for event in star_candidate.explanations)


