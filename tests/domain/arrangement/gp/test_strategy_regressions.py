"""Focused regression tests for edge cases in the GP arrangement strategy."""

from __future__ import annotations

from typing import Sequence

from domain.arrangement.config import (
    clear_instrument_registry,
    register_instrument_range,
)
from domain.arrangement.gp import GPSessionConfig, ProgramConstraints, arrange_v3_gp
from domain.arrangement.gp.fitness import FitnessVector
from domain.arrangement.gp.ops import GlobalTranspose, LocalOctave, SpanDescriptor
from domain.arrangement.gp.selection import Individual
from domain.arrangement.gp.session import GPSessionResult
from domain.arrangement.gp.session_logging import GPSessionLog
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange


def setup_function() -> None:
    clear_instrument_registry()


def _make_span(midis: Sequence[int]) -> PhraseSpan:
    notes = [
        PhraseNote(onset=index * 240, duration=240, midi=midi)
        for index, midi in enumerate(midis)
    ]
    return PhraseSpan(tuple(notes), pulses_per_quarter=480)


def _gp_config() -> GPSessionConfig:
    return GPSessionConfig(
        generations=1,
        population_size=4,
        archive_size=4,
        random_seed=7,
        random_program_count=2,
        crossover_rate=0.0,
        mutation_rate=1.0,
        log_best_programs=1,
        constraints=ProgramConstraints(max_operations=3),
    )


def test_gp_strategy_prefers_global_transpose_over_range_clamp(monkeypatch) -> None:
    instrument = InstrumentRange(min_midi=69, max_midi=89, comfort_center=78)
    register_instrument_range("alto", instrument)
    phrase = _make_span([59, 60, 62, 64, 67])

    config = _gp_config()
    winner_program = (
        LocalOctave(span=SpanDescriptor(0, len(phrase.notes) * 240), octaves=2),
    )
    winner = Individual(
        program=winner_program,
        fitness=FitnessVector(
            playability=0.1,
            fidelity=0.4,
            tessitura=0.2,
            program_size=1.0,
        ),
    )
    session_log = GPSessionLog(seed=config.random_seed, config={})
    fake_result = GPSessionResult(
        winner=winner,
        log=session_log,
        archive=(winner,),
        population=(winner,),
        generations=config.generations,
        elapsed_seconds=0.01,
        termination_reason="generation_limit",
    )

    def _fake_session(*_args, **_kwargs) -> GPSessionResult:
        return fake_result

    monkeypatch.setattr(
        "domain.arrangement.gp.strategy.run_gp_session",
        _fake_session,
    )

    result = arrange_v3_gp(
        phrase,
        instrument_id="alto",
        config=config,
    )

    chosen_program = result.chosen.program
    assert chosen_program and isinstance(chosen_program[0], GlobalTranspose)
    assert chosen_program[0].semitones == 12
    arranged_midis = [note.midi for note in result.chosen.span.notes]
    expected_midis = [midi + 12 for midi in [59, 60, 62, 64, 67]]
    assert arranged_midis == expected_midis

    # Global transpose candidates should still be evaluated for diagnostics.
    assert any(
        program
        and isinstance(program[0], GlobalTranspose)
        and program[0].semitones == 12
        for program in result.programs
    )


def test_gp_strategy_retains_low_melody_after_clamp(monkeypatch) -> None:
    """Regression: melody below range should rise by octaves, not flatten."""

    instrument = InstrumentRange(min_midi=69, max_midi=89, comfort_center=78)
    register_instrument_range("alto", instrument)
    melody = [59, 62, 59, 64]
    accompaniment = [55, 43, 55, 47]
    notes: list[PhraseNote] = []
    for index, melody_midi in enumerate(melody):
        onset = index * 240
        notes.append(PhraseNote(onset=onset, duration=240, midi=melody_midi))
        notes.append(PhraseNote(onset=onset, duration=480, midi=accompaniment[index]))
    phrase = PhraseSpan(tuple(notes), pulses_per_quarter=480)

    config = _gp_config()
    winner = Individual(
        program=tuple(),
        fitness=FitnessVector(playability=0.1, fidelity=0.1, tessitura=0.1, program_size=0.0),
    )
    fake_result = GPSessionResult(
        winner=winner,
        log=GPSessionLog(seed=config.random_seed, config={}),
        archive=(winner,),
        population=(winner,),
        generations=config.generations,
        elapsed_seconds=0.01,
        termination_reason="generation_limit",
    )

    monkeypatch.setattr(
        "domain.arrangement.gp.strategy.run_gp_session",
        lambda *_args, **_kwargs: fake_result,
    )

    result = arrange_v3_gp(
        phrase,
        instrument_id="alto",
        config=config,
    )

    grouped: dict[int, list[int]] = {}
    for note in result.chosen.span.notes:
        grouped.setdefault(note.onset, []).append(note.midi)

    top_voice = [max(grouped[onset]) for onset in sorted(grouped)]
    assert top_voice == [midi + 12 for midi in melody]
    assert any(min(group) == instrument.min_midi for group in grouped.values())


def test_gp_strategy_prefers_transpose_without_range_clamp(monkeypatch) -> None:
    """Prefer auto-transpose candidates that eliminate clamping entirely."""

    instrument = InstrumentRange(min_midi=69, max_midi=89, comfort_center=78)
    register_instrument_range("alto", instrument)

    melody = [59, 62, 64, 67, 72]
    guide = [53, 55, 53, 57, 60]
    notes: list[PhraseNote] = []
    for index, (melody_midi, guide_midi) in enumerate(zip(melody, guide)):
        onset = index * 240
        notes.append(PhraseNote(onset=onset, duration=240, midi=melody_midi))
        notes.append(PhraseNote(onset=onset, duration=360, midi=guide_midi))
    phrase = PhraseSpan(tuple(notes), pulses_per_quarter=480)

    config = _gp_config()
    winner = Individual(
        program=(GlobalTranspose(semitones=12),),
        fitness=FitnessVector(playability=0.2, fidelity=0.4, tessitura=0.3, program_size=1.0),
    )
    fake_result = GPSessionResult(
        winner=winner,
        log=GPSessionLog(seed=config.random_seed, config={}),
        archive=(winner,),
        population=(winner,),
        generations=config.generations,
        elapsed_seconds=0.01,
        termination_reason="generation_limit",
    )

    monkeypatch.setattr(
        "domain.arrangement.gp.strategy.run_gp_session",
        lambda *_args, **_kwargs: fake_result,
    )

    result = arrange_v3_gp(
        phrase,
        instrument_id="alto",
        config=config,
    )

    chosen_program = result.chosen.program
    assert chosen_program, "Expected a transposition program to be selected"
    assert isinstance(chosen_program[0], GlobalTranspose)
    assert chosen_program[0].semitones in {16, 17}
    assert all(event.reason_code != "range-clamp" for event in result.chosen.explanations)
    assert min(note.midi for note in result.chosen.span.notes) >= instrument.min_midi
