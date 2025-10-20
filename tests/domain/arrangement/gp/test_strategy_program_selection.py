"""Tests covering program selection heuristics for the GP arranger."""

from __future__ import annotations

from dataclasses import replace

from domain.arrangement.gp import arrange_v3_gp
from domain.arrangement.gp.fitness import FitnessConfig, FitnessObjective, FitnessVector
from domain.arrangement.gp.ops import GlobalTranspose, LocalOctave, SpanDescriptor
from domain.arrangement.gp.selection import Individual
from domain.arrangement.gp.session import GPSessionResult
from domain.arrangement.gp.session_logging import GPSessionLog
from domain.arrangement.phrase import PhraseSpan
from domain.arrangement.soft_key import InstrumentRange

from tests.domain.arrangement.gp._strategy_test_utils import (
    _gp_config,
    _make_poly_span,
    _make_span,
    _register_instruments,
    clear_registry,
)


def setup_function() -> None:
    clear_registry()


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


def test_gp_strategy_evaluates_prefix_variants_for_conflicting_local_octaves(
    monkeypatch,
) -> None:
    """Ensure conflicting octave winners consider simpler prefixes during scoring."""

    phrase = _make_span(
        [
            57,
            56,
            57,
            59,
            60,
            57,
            53,
            57,
            56,
            59,
            62,
            64,
            69,
            65,
            64,
            65,
            67,
            64,
            63,
            61,
            62,
            59,
            60,
            59,
            57,
        ]
    )
    instrument_range = InstrumentRange(min_midi=57, max_midi=77, comfort_center=67)
    _register_instruments((("bass", instrument_range),))

    config = _gp_config()
    full_span = SpanDescriptor(0, phrase.total_duration)
    trailing_span = SpanDescriptor(phrase.total_duration // 2, phrase.total_duration)
    conflicting_program = (
        LocalOctave(span=full_span, octaves=1),
        LocalOctave(span=trailing_span, octaves=-1),
    )
    winner = Individual(
        program=conflicting_program,
        fitness=FitnessVector(playability=0.1, fidelity=0.2, tessitura=0.3, program_size=0.4),
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

    monkeypatch.setattr("domain.arrangement.gp.strategy.run_gp_session", lambda *_, **__: fake_result)

    result = arrange_v3_gp(
        phrase,
        instrument_id="bass",
        config=config,
    )

    assert conflicting_program in result.programs
    assert any(
        len(program) == 1 and isinstance(program[0], LocalOctave)
        for program in result.programs
    )

    chosen_program = result.chosen.program
    local_octave_shifts = [
        operation.octaves
        for operation in chosen_program
        if isinstance(operation, LocalOctave)
    ]
    assert not (
        local_octave_shifts
        and min(local_octave_shifts) < 0 < max(local_octave_shifts)
    )

    arranged_notes = [note.midi for note in result.chosen.span.notes[:3]]
    assert len(arranged_notes) == 3
    first_interval = arranged_notes[1] - arranged_notes[0]
    assert abs(first_interval) <= 5

