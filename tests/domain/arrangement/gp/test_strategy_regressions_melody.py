from __future__ import annotations

from domain.arrangement.config import register_instrument_range
from domain.arrangement.difficulty import summarize_difficulty
from domain.arrangement.gp.fitness import compute_fitness, melody_pitch_penalty
from domain.arrangement.gp.ops import GlobalTranspose
from domain.arrangement.gp.strategy import (
    GPInstrumentCandidate,
    _difficulty_sort_key,
    _melody_shift_penalty,
)
from domain.arrangement.melody import MelodyIsolationResult
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.range_guard import enforce_instrument_range
from domain.arrangement.soft_key import InstrumentRange

from tests.domain.arrangement.gp.gp_test_helpers import make_span


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

