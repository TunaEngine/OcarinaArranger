from __future__ import annotations

from dataclasses import replace

from domain.arrangement.config import register_instrument_range
from domain.arrangement.difficulty import DifficultySummary, summarize_difficulty
from domain.arrangement.gp.fitness import compute_fitness, melody_pitch_penalty
from domain.arrangement.gp.ops import GlobalTranspose, LocalOctave, SpanDescriptor
from domain.arrangement.gp.penalties import ScoringPenalties
from domain.arrangement.gp.session import GPSessionConfig
from domain.arrangement.gp.strategy import (
    GPInstrumentCandidate,
    _difficulty_sort_key,
    _evaluate_program_candidate,
    _score_instrument,
    _melody_shift_penalty,
)
from domain.arrangement.melody import MelodyIsolationResult
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.range_guard import enforce_instrument_range
from domain.arrangement.soft_key import InstrumentRange

from tests.domain.arrangement.gp.gp_test_helpers import make_span


BASS_CONFLICT_MIDIS = [
    57,
    56,
    57,
    59,
    60,
    57,
    53,
    57,
    56,
    57,
    60,
    64,
    69,
    65,
    67,
    65,
    64,
    64,
    63,
    61,
    62,
    59,
    60,
    59,
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
    58,
    59,
    65,
    64,
    65,
    68,
    62,
    65,
    64,
    63,
    64,
    62,
    61,
    62,
    61,
    62,
    65,
    64,
    56,
    57,
    60,
    59,
    62,
    61,
    64,
    62,
    67,
    65,
    64,
    65,
    68,
    62,
    65,
    64,
    69,
    57,
    69,
    72,
    68,
    63,
    65,
    64,
    63,
    64,
    65,
    64,
    63,
    64,
    69,
    72,
    68,
    63,
    65,
    64,
    76,
    72,
    75,
    74,
    71,
    72,
    69,
]


def test_melody_shift_penalty_ignores_accompaniment_clamps() -> None:
    """Only melody drift should affect the shift penalty, not accomp clamps."""

    instrument = InstrumentRange(min_midi=57, max_midi=80, comfort_center=69)
    register_instrument_range("bass", instrument)

    melody = [52, 55, 57, 60, 62, 64, 62, 60, 59, 57]
    accompaniment = [40, 43, 45, 48, 50, 52, 50, 48, 47, 45]
    notes: list[PhraseNote] = []
    for index, (melody_midi, accompaniment_midi) in enumerate(
        zip(melody, accompaniment)
    ):
        onset = index * 240
        notes.append(PhraseNote(onset=onset, duration=240, midi=melody_midi))
        notes.append(PhraseNote(onset=onset, duration=360, midi=accompaniment_midi))

    phrase = PhraseSpan(tuple(notes), pulses_per_quarter=480)
    transposed = phrase.transpose(12)

    adjusted, _, _ = enforce_instrument_range(
        transposed,
        instrument,
        beats_per_measure=4,
    )

    penalty = _melody_shift_penalty(
        phrase,
        adjusted,
        beats_per_measure=4,
    )

    assert penalty == 0.0


def test_melody_shift_penalty_penalizes_top_voice_drift_when_isolation_drops_note(
    monkeypatch,
) -> None:
    """Top voice jumps must be penalized even if melody isolation misses them."""

    phrase = make_span([52, 55, 57, 60])
    candidate = phrase.transpose(12)
    candidate_notes = list(candidate.notes)
    candidate_notes[0] = candidate_notes[0].with_midi(candidate_notes[0].midi + 12)
    candidate = candidate.with_notes(candidate_notes)

    def _fake_isolate(span: PhraseSpan, *, beats_per_measure: int = 4) -> MelodyIsolationResult:
        del beats_per_measure
        if len(span.notes) <= 1:
            return MelodyIsolationResult(span=span, events=tuple(), actions=tuple())
        trimmed = span.with_notes(span.notes[1:])
        return MelodyIsolationResult(span=trimmed, events=tuple(), actions=tuple())

    monkeypatch.setattr(
        "domain.arrangement.gp.strategy.isolate_melody",
        _fake_isolate,
    )

    penalty = _melody_shift_penalty(
        phrase,
        candidate,
        beats_per_measure=4,
    )

    assert penalty > 0.0


def test_melody_shift_penalty_penalizes_sparse_octave_leaps() -> None:
    """Even a few octave jumps should incur a heavy drift penalty."""

    phrase = make_span([60, 59, 60, 59])
    adjusted_notes = list(phrase.notes)
    adjusted_notes[1] = adjusted_notes[1].with_midi(adjusted_notes[1].midi + 12)
    adjusted = phrase.with_notes(tuple(adjusted_notes))

    penalty = _melody_shift_penalty(
        phrase,
        adjusted,
        beats_per_measure=4,
    )

    assert penalty >= 0.9


def test_conflicting_local_octaves_are_penalized_in_scoring() -> None:
    """Mixing opposing local octave shifts should rank behind consistent edits."""

    instrument = InstrumentRange(min_midi=57, max_midi=81, comfort_center=69)
    register_instrument_range("octave_conflict", instrument)

    phrase = make_span([57, 60, 64, 67])
    full_span = SpanDescriptor(0, len(phrase.notes) * 240)

    consistent_program = (LocalOctave(span=full_span, octaves=1),)
    conflicting_program = (
        LocalOctave(span=full_span, octaves=1),
        LocalOctave(span=full_span, octaves=-1),
    )

    consistent_candidate, _ = _evaluate_program_candidate(
        consistent_program,
        instrument_id="octave_conflict",
        instrument=instrument,
        phrase=phrase,
        beats_per_measure=4,
        fitness_config=None,
    )
    conflicting_candidate, _ = _evaluate_program_candidate(
        conflicting_program,
        instrument_id="octave_conflict",
        instrument=instrument,
        phrase=phrase,
        beats_per_measure=4,
        fitness_config=None,
    )

    consistent_key = _difficulty_sort_key(consistent_candidate)
    conflicting_key = _difficulty_sort_key(conflicting_candidate)

    assert conflicting_key > consistent_key


def test_conflicting_local_octaves_remain_penalized_when_easier() -> None:
    """Even easier programs with mixed octaves must rank behind intact melody."""

    instrument = InstrumentRange(min_midi=57, max_midi=77, comfort_center=67)
    register_instrument_range("bass_conflict_bias", instrument)

    notes = [
        PhraseNote(onset=index * 240, duration=240, midi=midi)
        for index, midi in enumerate(BASS_CONFLICT_MIDIS)
    ]
    phrase = PhraseSpan(tuple(notes), pulses_per_quarter=480)

    full_span = SpanDescriptor(0, phrase.total_duration)
    half_span = SpanDescriptor(0, phrase.total_duration // 2)

    identity_candidate, _ = _evaluate_program_candidate(
        tuple(),
        instrument_id="bass_conflict_bias",
        instrument=instrument,
        phrase=phrase,
        beats_per_measure=4,
        fitness_config=None,
    )
    conflicting_candidate, _ = _evaluate_program_candidate(
        (
            LocalOctave(span=full_span, octaves=1),
            LocalOctave(span=half_span, octaves=-1),
        ),
        instrument_id="bass_conflict_bias",
        instrument=instrument,
        phrase=phrase,
        beats_per_measure=4,
        fitness_config=None,
    )

    easier_conflicting = replace(
        conflicting_candidate,
        difficulty=DifficultySummary(
            easy=conflicting_candidate.difficulty.easy + 2400.0,
            medium=max(0.0, conflicting_candidate.difficulty.medium - 2400.0),
            hard=0.0,
            very_hard=0.0,
            tessitura_distance=max(
                0.0, conflicting_candidate.difficulty.tessitura_distance - 1.5
            ),
            leap_exposure=max(0.0, conflicting_candidate.difficulty.leap_exposure / 2.0),
        ),
    )

    identity_key = _difficulty_sort_key(identity_candidate)
    conflicting_key = _difficulty_sort_key(easier_conflicting)

    assert conflicting_key > identity_key


def test_difficulty_sort_key_penalizes_non_octave_transpose() -> None:
    """Non-octave global transposes should rank behind octave-aligned shifts."""

    instrument = InstrumentRange(min_midi=57, max_midi=77, comfort_center=67)
    register_instrument_range("bass_penalty", instrument)

    melody = [52, 55, 57, 60, 62, 64, 62, 60, 59, 57]
    accompaniment = [40, 43, 45, 48, 50, 52, 50, 48, 47, 45]
    notes: list[PhraseNote] = []
    for index, (melody_midi, accompaniment_midi) in enumerate(
        zip(melody, accompaniment)
    ):
        onset = index * 240
        notes.append(PhraseNote(onset=onset, duration=240, midi=melody_midi))
        notes.append(PhraseNote(onset=onset, duration=360, midi=accompaniment_midi))

    phrase = PhraseSpan(tuple(notes), pulses_per_quarter=480)

    transpose_12 = phrase.transpose(12)
    transpose_17 = phrase.transpose(17)

    clamped_12, _, _ = enforce_instrument_range(
        transpose_12,
        instrument,
        beats_per_measure=4,
    )
    clamped_17, _, _ = enforce_instrument_range(
        transpose_17,
        instrument,
        beats_per_measure=4,
    )

    fitness_12 = compute_fitness(
        original=phrase,
        candidate=clamped_12,
        instrument=instrument,
        program=(GlobalTranspose(semitones=12),),
    )
    fitness_17 = compute_fitness(
        original=phrase,
        candidate=clamped_17,
        instrument=instrument,
        program=(GlobalTranspose(semitones=17),),
    )

    candidate_12 = GPInstrumentCandidate(
        instrument_id="bass_penalty",
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
    )
    candidate_17 = GPInstrumentCandidate(
        instrument_id="bass_penalty",
        instrument=instrument,
        program=(GlobalTranspose(semitones=17),),
        span=clamped_17,
        difficulty=summarize_difficulty(clamped_17, instrument),
        fitness=fitness_17,
        melody_penalty=melody_pitch_penalty(
            phrase, clamped_17, beats_per_measure=4
        ),
        melody_shift_penalty=_melody_shift_penalty(
            phrase, clamped_17, beats_per_measure=4
        ),
    )

    key_octave = _difficulty_sort_key(candidate_12)
    key_non_octave = _difficulty_sort_key(candidate_17)

    assert key_octave < key_non_octave
    assert key_non_octave[1] > key_octave[1]


def test_bass_floor_clamp_prefers_uniform_transpose() -> None:
    """Bass phrase hugging the floor should promote a uniform register shift."""

    instrument = InstrumentRange(min_midi=57, max_midi=77, comfort_center=67)
    register_instrument_range("bass_floor_shape", instrument)

    notes = [
        PhraseNote(onset=index * 240, duration=240, midi=midi)
        for index, midi in enumerate(BASS_CONFLICT_MIDIS)
    ]
    phrase = PhraseSpan(tuple(notes), pulses_per_quarter=480)

    config = GPSessionConfig()
    tuned_penalties = replace(
        config.scoring_penalties,
        range_clamp_penalty=4.9,
        range_clamp_melody_bias=4.0,
    )
    config = replace(config, scoring_penalties=tuned_penalties)

    full_span = SpanDescriptor(0, phrase.total_duration)
    half_span = SpanDescriptor(0, phrase.total_duration // 2)
    conflicting_program = (
        LocalOctave(span=full_span, octaves=1),
        LocalOctave(span=half_span, octaves=-1),
    )

    best_candidate, _, _ = _score_instrument(
        instrument_id="bass_floor_shape",
        instrument=instrument,
        phrase=phrase,
        programs=[tuple(), conflicting_program],
        fitness_config=config.fitness_config,
        beats_per_measure=4,
        penalties=config.scoring_penalties,
    )

    assert best_candidate.program
    first_op = best_candidate.program[0]
    assert isinstance(first_op, GlobalTranspose)
    assert first_op.semitones == 12


def test_zero_transpose_prefix_penalised_for_floor_clamp() -> None:
    """A zero-magnitude transpose should not dodge clamp penalties."""

    instrument = InstrumentRange(min_midi=57, max_midi=77, comfort_center=67)
    register_instrument_range("bass_zero_transpose", instrument)

    notes = [
        PhraseNote(onset=index * 240, duration=240, midi=midi)
        for index, midi in enumerate(BASS_CONFLICT_MIDIS)
    ]
    phrase = PhraseSpan(tuple(notes), pulses_per_quarter=480)

    tuned_penalties = ScoringPenalties(
        range_clamp_penalty=4.9,
        range_clamp_melody_bias=4.0,
    )
    config = GPSessionConfig(scoring_penalties=tuned_penalties)

    zero_prefix = (
        GlobalTranspose(semitones=0, span=SpanDescriptor(0, None)),
        LocalOctave(span=SpanDescriptor(0, phrase.total_duration), octaves=1),
    )

    best_candidate, _, _ = _score_instrument(
        instrument_id="bass_zero_transpose",
        instrument=instrument,
        phrase=phrase,
        programs=[tuple(), zero_prefix],
        fitness_config=config.fitness_config,
        beats_per_measure=4,
        penalties=config.scoring_penalties,
    )

    assert best_candidate.program
    first_op = best_candidate.program[0]
    assert isinstance(first_op, GlobalTranspose)
    assert first_op.semitones == 12

