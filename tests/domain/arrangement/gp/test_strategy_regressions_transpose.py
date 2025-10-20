from __future__ import annotations

from typing import Dict, List

from domain.arrangement.config import register_instrument_range
from domain.arrangement.difficulty import DifficultySummary, summarize_difficulty
from domain.arrangement.gp import GPSessionConfig, arrange_v3_gp
from domain.arrangement.gp.fitness import (
    FitnessVector,
    compute_fitness,
    melody_pitch_penalty,
)
from domain.arrangement.gp.ops import (
    GlobalTranspose,
    LocalOctave,
    SpanDescriptor,
)
from domain.arrangement.gp.program_utils import apply_program, auto_range_programs
from domain.arrangement.gp.selection import Individual
from domain.arrangement.gp.session import GPSessionResult
from domain.arrangement.gp.session_logging import GPSessionLog
from domain.arrangement.gp.strategy import (
    GPInstrumentCandidate,
    _difficulty_sort_key,
    _melody_shift_penalty,
    _score_instrument,
)
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.range_guard import enforce_instrument_range
from domain.arrangement.soft_key import InstrumentRange

from domain.arrangement.gp.strategy_scoring import ScoringPenalties

from tests.domain.arrangement.gp.gp_test_helpers import gp_config, make_span


def test_gp_strategy_prefers_global_transpose_over_range_clamp(monkeypatch) -> None:
    instrument = InstrumentRange(min_midi=69, max_midi=89, comfort_center=78)
    register_instrument_range("alto", instrument)
    melody = [59, 60, 62, 64, 67]
    phrase = make_span(melody)

    config = gp_config()
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
    assert chosen_program, "expected a transformation program"
    grouped: Dict[int, List[int]] = {}
    for note in result.chosen.span.notes:
        grouped.setdefault(note.onset, []).append(note.midi)

    top_voice = [max(grouped[onset]) for onset in sorted(grouped)]
    expected = [midi + 12 for midi in melody]
    offsets = [actual - expected_midi for actual, expected_midi in zip(top_voice, expected)]
    assert all(abs(offset) <= 12 for offset in offsets)
    assert chosen_program[0].semitones == 12
    arranged_midis = [note.midi for note in result.chosen.span.notes]
    expected_midis = [midi + 12 for midi in [59, 60, 62, 64, 67]]
    assert arranged_midis == expected_midis


def test_auto_range_programs_accepts_preferred_shift() -> None:
    instrument = InstrumentRange(min_midi=60, max_midi=83, comfort_center=72)
    phrase = make_span([79, 81, 83])

    without_hint = auto_range_programs(
        phrase,
        instrument,
        beats_per_measure=4,
    )
    assert without_hint == ()

    hinted = auto_range_programs(
        phrase,
        instrument,
        beats_per_measure=4,
        preferred_shift=-2,
    )
    assert (GlobalTranspose(-2),) in hinted


def test_gp_strategy_respects_preferred_register_shift(monkeypatch) -> None:
    instrument = InstrumentRange(min_midi=60, max_midi=83, comfort_center=72)
    register_instrument_range("alto_hint", instrument)
    phrase = make_span([79, 81, 83])

    config = gp_config()
    winner = Individual(
        program=tuple(),
        fitness=FitnessVector(
            playability=0.2,
            fidelity=0.2,
            tessitura=0.2,
            program_size=0.0,
        ),
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

    captured: dict[str, object] = {}

    def _fake_auto_range(*_args, preferred_shift=None, **_kwargs):
        captured["preferred_shift"] = preferred_shift
        if preferred_shift in (None, 0):
            return ()
        return ((GlobalTranspose(preferred_shift),),)

    monkeypatch.setattr(
        "domain.arrangement.gp.strategy._auto_range_programs",
        _fake_auto_range,
    )

    result = arrange_v3_gp(
        phrase,
        instrument_id="alto_hint",
        config=config,
        preferred_register_shift=-2,
    )

    assert captured.get("preferred_shift") == -2
    hinted_programs = [
        program
        for program in result.programs
        if program and isinstance(program[0], GlobalTranspose)
    ]
    assert hinted_programs, "expected hinted global transpose to be tracked"
    assert any(program[0].semitones == -2 for program in hinted_programs)
    hinted = next(program for program in hinted_programs if program[0].semitones == -2)
    arranged_span = apply_program(hinted, phrase)
    assert [note.midi for note in arranged_span.notes] == [midi - 2 for midi in (79, 81, 83)]

def test_gp_strategy_retains_low_melody_after_clamp(monkeypatch) -> None:

    instrument = InstrumentRange(min_midi=69, max_midi=89, comfort_center=78)
    register_instrument_range("alto", instrument)
    melody = [59, 62, 59, 64]
    accompaniment = [55, 43, 55, 47]
    notes: List[PhraseNote] = []
    for index, melody_midi in enumerate(melody):
        onset = index * 240
        notes.append(PhraseNote(onset=onset, duration=240, midi=melody_midi))
        notes.append(PhraseNote(onset=onset, duration=480, midi=accompaniment[index]))
    phrase = PhraseSpan(tuple(notes), pulses_per_quarter=480)

    config = gp_config()
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

    grouped: Dict[int, List[int]] = {}
    for note in result.chosen.span.notes:
        grouped.setdefault(note.onset, []).append(note.midi)

    top_voice = [max(grouped[onset]) for onset in sorted(grouped)]
    expected = [midi + 12 for midi in melody]
    offsets = [actual - expected_midi for actual, expected_midi in zip(top_voice, expected)]
    assert all(abs(offset) <= 12 for offset in offsets)
    floor_distance = min(min(group) - instrument.min_midi for group in grouped.values())
    assert floor_distance <= 12


def test_gp_strategy_prefers_transpose_without_range_clamp(monkeypatch) -> None:

    instrument = InstrumentRange(min_midi=69, max_midi=89, comfort_center=78)
    register_instrument_range("alto", instrument)

    melody = [59, 62, 64, 67, 72]
    guide = [53, 55, 53, 57, 60]
    notes: List[PhraseNote] = []
    for index, (melody_midi, guide_midi) in enumerate(zip(melody, guide)):
        onset = index * 240
        notes.append(PhraseNote(onset=onset, duration=240, midi=melody_midi))
        notes.append(PhraseNote(onset=onset, duration=360, midi=guide_midi))
    phrase = PhraseSpan(tuple(notes), pulses_per_quarter=480)

    config = gp_config()
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


def test_gp_strategy_prefers_uniform_transpose_for_bass(monkeypatch) -> None:

    instrument = InstrumentRange(min_midi=57, max_midi=77, comfort_center=67)
    register_instrument_range("bass", instrument)
    source = [52, 55, 57, 60, 62, 64, 62, 60, 59, 57]
    melody = list(source)
    phrase = make_span(source)

    config = gp_config()
    bad_program = (
        LocalOctave(span=SpanDescriptor(0, 240), octaves=1),
        LocalOctave(span=SpanDescriptor(240, 480), octaves=1),
    )
    winner = Individual(
        program=bad_program,
        fitness=FitnessVector(
            playability=0.2,
            fidelity=0.2,
            tessitura=0.2,
            program_size=2.0,
        ),
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
        instrument_id="bass",
        config=config,
    )

    chosen_program = result.chosen.program
    assert chosen_program, "expected a transformation program"
    grouped: Dict[int, List[int]] = {}
    for note in result.chosen.span.notes:
        grouped.setdefault(note.onset, []).append(note.midi)

    top_voice = [max(grouped[onset]) for onset in sorted(grouped)]
    expected = [midi + 12 for midi in melody]
    offsets = [actual - expected_midi for actual, expected_midi in zip(top_voice, expected)]
    assert all(abs(offset) <= 12 for offset in offsets)
    assert chosen_program[0].semitones == 12
    arranged_midis = [note.midi for note in result.chosen.span.notes]
    expected_midis = [midi + 12 for midi in source]
    assert arranged_midis == expected_midis
    assert min(note.midi for note in result.chosen.span.notes) >= instrument.min_midi


def test_gp_strategy_prefers_top_voice_transpose_when_low_voices_clamp(monkeypatch) -> None:

    instrument = InstrumentRange(min_midi=57, max_midi=77, comfort_center=67)
    register_instrument_range("bass", instrument)

    melody = [52, 55, 57, 60, 62, 64, 62, 60, 59, 57]
    accompaniment = [midi - 12 for midi in melody]
    notes: List[PhraseNote] = []
    for index, (melody_midi, accompaniment_midi) in enumerate(
        zip(melody, accompaniment)
    ):
        onset = index * 240
        notes.append(PhraseNote(onset=onset, duration=240, midi=melody_midi))
        notes.append(PhraseNote(onset=onset, duration=360, midi=accompaniment_midi))

    phrase = PhraseSpan(tuple(notes), pulses_per_quarter=480)

    config = gp_config()
    total_duration = len(melody) * 240
    winner_program = (
        LocalOctave(span=SpanDescriptor(0, total_duration), octaves=2),
    )
    winner = Individual(
        program=winner_program,
        fitness=FitnessVector(
            playability=0.2,
            fidelity=0.2,
            tessitura=0.2,
            program_size=1.0,
        ),
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
        instrument_id="bass",
        config=config,
    )

    chosen_program = result.chosen.program
    assert chosen_program, "expected a transformation program"

    grouped: Dict[int, List[int]] = {}
    for note in result.chosen.span.notes:
        grouped.setdefault(note.onset, []).append(note.midi)

    top_voice = [max(grouped[onset]) for onset in sorted(grouped)]
    expected = [midi + 12 for midi in melody]
    offsets = [actual - expected_midi for actual, expected_midi in zip(top_voice, expected)]
    assert all(abs(offset) <= 12 for offset in offsets)
    floor_distance = min(min(group) - instrument.min_midi for group in grouped.values())
    assert floor_distance <= 12


def test_gp_strategy_prefers_consistent_melody_shift() -> None:

    instrument = InstrumentRange(min_midi=57, max_midi=77, comfort_center=67)
    register_instrument_range("bass_consistent", instrument)
    phrase = make_span([52, 55, 57, 60, 62, 64, 62, 60, 59, 57])

    uniform_span = phrase.transpose(12)
    mixed_notes = list(uniform_span.notes)
    mixed_notes[0] = mixed_notes[0].with_midi(mixed_notes[0].midi + 12)
    mixed_span = uniform_span.with_notes(mixed_notes)

    fitness_uniform = compute_fitness(
        original=phrase,
        candidate=uniform_span,
        instrument=instrument,
        program=(GlobalTranspose(semitones=12),),
    )
    fitness_mixed = compute_fitness(
        original=phrase,
        candidate=mixed_span,
        instrument=instrument,
        program=(),
    )

    candidate_uniform = GPInstrumentCandidate(
        instrument_id="bass_consistent",
        instrument=instrument,
        program=(GlobalTranspose(semitones=12),),
        span=uniform_span,
        difficulty=summarize_difficulty(uniform_span, instrument),
        fitness=fitness_uniform,
        melody_penalty=melody_pitch_penalty(
            phrase, uniform_span, beats_per_measure=4
        ),
        melody_shift_penalty=_melody_shift_penalty(
            phrase, uniform_span, beats_per_measure=4
        ),
    )
    candidate_mixed = GPInstrumentCandidate(
        instrument_id="bass_consistent",
        instrument=instrument,
        program=(),
        span=mixed_span,
        difficulty=summarize_difficulty(mixed_span, instrument),
        fitness=fitness_mixed,
        melody_penalty=melody_pitch_penalty(
            phrase, mixed_span, beats_per_measure=4
        ),
        melody_shift_penalty=_melody_shift_penalty(
            phrase, mixed_span, beats_per_measure=4
        ),
    )

    key_uniform = _difficulty_sort_key(candidate_uniform)
    key_mixed = _difficulty_sort_key(candidate_mixed)

    assert key_uniform < key_mixed
    assert key_uniform[1] <= key_mixed[1]


