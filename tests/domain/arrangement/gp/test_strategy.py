"""Integration-style tests for the GP arrangement strategy helpers."""

from __future__ import annotations

from typing import Iterable, Sequence

from dataclasses import replace

from domain.arrangement.api import arrange
from domain.arrangement.config import clear_instrument_registry, register_instrument_range
from domain.arrangement.gp import (
    GPSessionConfig,
    ProgramConstraints,
    arrange_v3_gp,
)
from domain.arrangement.gp.fitness import FitnessConfig, FitnessObjective, FitnessVector
from domain.arrangement.gp.ops import GlobalTranspose, LocalOctave, SpanDescriptor
from domain.arrangement.gp.selection import Individual
from domain.arrangement.gp.session import GPSessionResult
from domain.arrangement.gp.session_logging import GPSessionLog
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange
from domain.arrangement.melody import isolate_melody


def setup_function() -> None:
    clear_instrument_registry()


def _make_span(midis: Sequence[int]) -> PhraseSpan:
    notes = [
        PhraseNote(onset=index * 240, duration=240, midi=midi)
        for index, midi in enumerate(midis)
    ]
    return PhraseSpan(tuple(notes), pulses_per_quarter=480)


def _make_poly_span(top: Sequence[int], bottom: Sequence[int]) -> PhraseSpan:
    notes: list[PhraseNote] = []
    for index, melody_midi in enumerate(top):
        onset = index * 240
        notes.append(PhraseNote(onset=onset, duration=240, midi=melody_midi))
        if index < len(bottom):
            notes.append(PhraseNote(onset=onset, duration=240, midi=bottom[index]))
    return PhraseSpan(tuple(notes), pulses_per_quarter=480)


def _register_instruments(mapping: Iterable[tuple[str, InstrumentRange]]) -> None:
    for instrument_id, instrument in mapping:
        register_instrument_range(instrument_id, instrument)


def _gp_config() -> GPSessionConfig:
    return GPSessionConfig(
        generations=1,
        population_size=4,
        archive_size=4,
        random_seed=11,
        random_program_count=2,
        crossover_rate=0.0,
        mutation_rate=1.0,
        log_best_programs=1,
        constraints=ProgramConstraints(max_operations=3),
    )


def test_gp_strategy_matches_v2_ranking_when_winner_shared() -> None:
    phrase = _make_span([84, 72, 60, 67])
    _register_instruments(
        (
            ("current", InstrumentRange(min_midi=60, max_midi=84, comfort_center=72)),
            ("star_a", InstrumentRange(min_midi=55, max_midi=79, comfort_center=67)),
            ("star_b", InstrumentRange(min_midi=62, max_midi=86, comfort_center=74)),
        )
    )

    starred = ("star_a", "star_b")
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

    assert v2_result.chosen.instrument_id == "current"
    assert gp_result.comparisons[0].instrument_id == "current"
    assert {
        candidate.instrument_id for candidate in gp_result.comparisons[1:]
    } == {"star_a", "star_b"}
    assert {
        candidate.instrument_id for candidate in gp_result.comparisons
    } == {
        candidate.instrument_id for candidate in v2_result.comparisons
    }
    # Fidelity weighting keeps the unmodified instrument ahead of easier but
    # octave-shifted options so the melody stays in tune.
    assert gp_result.chosen.instrument_id == "current"
    assert gp_result.comparisons[0].fitness.fidelity <= gp_result.comparisons[1].fitness.fidelity
    assert gp_result.termination_reason == "generation_limit"
    assert gp_result.session.generations == config.generations
    assert len(gp_result.archive_summary) <= config.archive_size
    assert gp_result.fallback is None


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

    assert [candidate.instrument_id for candidate in v2_result.comparisons] == [
        "current",
        "star_a",
        "star_b",
    ]
    assert [candidate.instrument_id for candidate in gp_result.comparisons] == [
        "current",
        "star_a",
        "star_b",
    ]


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
        starred_ids=("star",),
        config=config,
    )

    comparisons = {candidate.instrument_id: candidate for candidate in result.comparisons}
    current_candidate = comparisons["current"]
    star_candidate = comparisons["star"]

    assert any(note.midi > star_range.max_midi for note in current_candidate.span.notes)
    assert all(star_range.min_midi <= note.midi <= star_range.max_midi for note in star_candidate.span.notes)
    assert all(event.reason_code != "range-clamp" for event in star_candidate.explanations)


def test_gp_strategy_prefers_identity_when_winner_shifts_register(monkeypatch) -> None:
    phrase = _make_span([74, 76, 78, 76])
    instrument_range = InstrumentRange(min_midi=69, max_midi=89, comfort_center=79)
    _register_instruments((("ocarina", instrument_range),))

    config = _gp_config()
    local_octave = LocalOctave(span=SpanDescriptor(), octaves=1)
    program = (local_octave,)
    fitness = FitnessVector(playability=0.1, fidelity=0.9, tessitura=0.2, program_size=1.0)
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
        instrument_id="ocarina",
        config=config,
    )

    assert result.session.winner.program == program
    chosen_program = result.chosen.program
    assert chosen_program == tuple()
    assert [note.midi for note in result.chosen.span.notes] == [
        note.midi for note in phrase.notes
    ]
    assert tuple() in result.programs
    assert program in result.programs


def test_gp_strategy_melody_penalty_blocks_out_of_tune_winner(monkeypatch) -> None:
    top_voice = [86, 85, 81, 78, 79, 78, 76]
    harmony = [50, 47, 45, 43, 42, 40, 38]
    phrase = _make_poly_span(top_voice, harmony)
    instrument_range = InstrumentRange(min_midi=69, max_midi=89, comfort_center=79)
    _register_instruments((("ocarina", instrument_range),))

    config = _gp_config()
    local_octave = LocalOctave(span=SpanDescriptor(), octaves=1)
    program = (local_octave,)
    winner = Individual(
        program=program,
        fitness=FitnessVector(playability=0.1, fidelity=0.2, tessitura=0.2, program_size=1.0),
    )
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

    def _fake_session(*_args, **_kwargs) -> GPSessionResult:
        return fake_result

    monkeypatch.setattr("domain.arrangement.gp.strategy.run_gp_session", _fake_session)

    result = arrange_v3_gp(
        phrase,
        instrument_id="ocarina",
        config=config,
    )

    def _melody_signature(span: PhraseSpan) -> list[int]:
        grouped: dict[int, list[int]] = {}
        for note in span.notes:
            grouped.setdefault(note.onset, []).append(note.midi)
        return [max(midis) for onset, midis in sorted(grouped.items())]

    assert result.session.winner.program == program
    assert result.chosen.program == tuple()
    assert _melody_signature(result.chosen.span) == top_voice
    assert tuple() in result.programs
    assert program in result.programs


def test_gp_strategy_honours_fidelity_weight(monkeypatch) -> None:
    phrase = _make_span([86, 85, 81, 78, 79, 78, 76])
    instrument_range = InstrumentRange(min_midi=69, max_midi=89, comfort_center=79)
    _register_instruments((("ocarina", instrument_range),))

    base_config = _gp_config()
    config = replace(
        base_config,
        fitness_config=FitnessConfig(
            playability=FitnessObjective(weight=1.0),
            fidelity=FitnessObjective(weight=6.0),
            tessitura=FitnessObjective(weight=1.0),
            program_size=FitnessObjective(weight=1.0),
        ),
    )

    local_octave = LocalOctave(span=SpanDescriptor(), octaves=1)
    program = (local_octave,)
    winner = Individual(
        program=program,
        fitness=FitnessVector(playability=0.0, fidelity=0.0, tessitura=0.0, program_size=1.0),
    )
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

    def _fake_session(*_args, **_kwargs) -> GPSessionResult:
        return fake_result

    def _fake_fitness(
        *,
        original,
        candidate,
        instrument,
        program,
        difficulty,
        config: FitnessConfig | None,
    ) -> FitnessVector:
        base_playability = 0.25 if program else 0.4
        base_fidelity = 0.18 if program else 0.15
        weight = config.fidelity.weight if config is not None else 1.0
        fidelity_value = round(base_fidelity * weight, 12)
        return FitnessVector(
            playability=base_playability,
            fidelity=fidelity_value,
            tessitura=0.1,
            program_size=float(len(program)),
        )

    monkeypatch.setattr("domain.arrangement.gp.strategy.run_gp_session", _fake_session)
    monkeypatch.setattr("domain.arrangement.gp.strategy.compute_fitness", _fake_fitness)

    result = arrange_v3_gp(
        phrase,
        instrument_id="ocarina",
        config=config,
    )

    assert result.session.winner.program == program
    assert result.chosen.program == tuple()
    assert tuple() in result.programs
    assert program in result.programs


def test_gp_strategy_transposes_low_melody_instead_of_flattening(monkeypatch) -> None:
    """Ensure low phrases are lifted by octaves instead of being clamped flat."""

    melody = [59, 60, 59, 60, 62, 63, 62]
    phrase = _make_span(melody)
    instrument_range = InstrumentRange(min_midi=69, max_midi=89, comfort_center=79)
    _register_instruments((("ocarina", instrument_range),))

    config = _gp_config()

    winner = Individual(
        program=tuple(),
        fitness=FitnessVector(playability=0.0, fidelity=0.0, tessitura=0.0, program_size=0.0),
    )
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

    def _fake_session(*_args, **_kwargs) -> GPSessionResult:
        return fake_result

    monkeypatch.setattr("domain.arrangement.gp.strategy.run_gp_session", _fake_session)

    result = arrange_v3_gp(
        phrase,
        instrument_id="ocarina",
        config=config,
    )

    arranged_midis = [note.midi for note in result.chosen.span.notes]
    offsets = {arranged - original for arranged, original in zip(arranged_midis, melody)}
    assert len(offsets) == 1
    offset = offsets.pop()
    assert offset % 12 == 0 and offset > 0
    assert min(arranged_midis) >= instrument_range.min_midi
    assert max(arranged_midis) <= instrument_range.max_midi
    assert all(
        event.reason_code != "range-clamp" for event in result.chosen.explanations
    )
    chosen_program = result.chosen.program
    assert chosen_program and isinstance(chosen_program[0], GlobalTranspose)
    assert tuple() in result.programs
    assert (GlobalTranspose(semitones=12),) in result.programs
