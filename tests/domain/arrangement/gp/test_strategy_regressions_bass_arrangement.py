"""Regression tests covering bass GP arrangement orchestration."""

from __future__ import annotations

from domain.arrangement.config import register_instrument_range
from domain.arrangement.gp.fitness import FitnessVector
from domain.arrangement.gp.ops import GlobalTranspose, LocalOctave, SimplifyRhythm, SpanDescriptor
from domain.arrangement.gp.selection import Individual
from domain.arrangement.gp.strategy import arrange_v3_gp
from domain.arrangement.soft_key import InstrumentRange

from tests.domain.arrangement.gp.bass_test_helpers import (
    MELODY_MIDIS,
    assert_constant_offset,
    bass_session,
)
from tests.domain.arrangement.gp.gp_test_helpers import bass_phrase, gp_config, make_span


def test_gp_strategy_preserves_melody_for_bass_c_sample(monkeypatch) -> None:
    """Regression: keep melody intact for the Bass C sample despite low bass."""

    instrument = InstrumentRange(min_midi=57, max_midi=77, comfort_center=67)
    register_instrument_range("bass", instrument)

    phrase = bass_phrase()

    config = gp_config()
    total_duration = len(phrase.notes) * 240
    winner_program = (
        LocalOctave(span=SpanDescriptor(0, total_duration), octaves=2),
        SimplifyRhythm(span=SpanDescriptor(0, total_duration), subdivisions=3),
        SimplifyRhythm(span=SpanDescriptor(0, total_duration), subdivisions=3),
    )
    winner = Individual(
        program=winner_program,
        fitness=FitnessVector(
            playability=0.2,
            fidelity=0.2,
            tessitura=0.2,
            program_size=3.0,
        ),
    )
    fake_result = bass_session(winner, config)

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
    assert chosen_program and isinstance(chosen_program[0], GlobalTranspose)
    assert chosen_program[0].semitones == 12

    grouped: dict[int, list[int]] = {}
    for note in result.chosen.span.notes:
        grouped.setdefault(note.onset, []).append(note.midi)

    top_voice_notes = [max(grouped[onset]) for onset in sorted(grouped)]
    expected_top = [midi + 12 for midi in MELODY_MIDIS]
    offsets = [
        actual - expected
        for actual, expected in zip(top_voice_notes[-len(expected_top) :], expected_top)
    ]
    assert all(abs(offset) <= 5 for offset in offsets)
    assert top_voice_notes[0] >= instrument.min_midi


def test_gp_strategy_adds_transpose_when_intro_is_only_bass(monkeypatch) -> None:
    """Regression: melody after a bass-only intro should still drive auto-range."""

    instrument = InstrumentRange(min_midi=57, max_midi=77, comfort_center=67)
    register_instrument_range("bass", instrument)

    phrase = bass_phrase(intro_eighths=4)

    config = gp_config()
    total_duration = len(phrase.notes) * 240
    winner_program = (
        LocalOctave(span=SpanDescriptor(0, total_duration), octaves=2),
        SimplifyRhythm(span=SpanDescriptor(0, total_duration), subdivisions=3),
        SimplifyRhythm(span=SpanDescriptor(0, total_duration), subdivisions=3),
    )
    winner = Individual(
        program=winner_program,
        fitness=FitnessVector(
            playability=0.2,
            fidelity=0.2,
            tessitura=0.2,
            program_size=3.0,
        ),
    )
    fake_result = bass_session(winner, config)

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
    assert chosen_program and isinstance(chosen_program[0], GlobalTranspose)
    assert chosen_program[0].semitones == 12

    grouped: dict[int, list[int]] = {}
    for note in result.chosen.span.notes:
        grouped.setdefault(note.onset, []).append(note.midi)

    top_voice_notes = [max(grouped[onset]) for onset in sorted(grouped)]
    expected_top = [midi + 12 for midi in MELODY_MIDIS]
    offsets = [
        actual - expected
        for actual, expected in zip(top_voice_notes[-len(expected_top) :], expected_top)
    ]
    assert all(abs(offset) <= 5 for offset in offsets)
    assert any(min(group) == instrument.min_midi for group in grouped.values())


def test_arranger_keeps_uniform_offset_between_bass_and_alto() -> None:
    """Bass and Alto arrangements should differ by a constant semitone shift."""

    bass_range = InstrumentRange(min_midi=57, max_midi=77, comfort_center=67)
    alto_range = InstrumentRange(min_midi=69, max_midi=89, comfort_center=79)
    register_instrument_range("bass_c_12", bass_range)
    register_instrument_range("alto_c_12", alto_range)

    phrase = bass_phrase()

    bass_result = arrange_v3_gp(
        phrase,
        instrument_id="bass_c_12",
        config=gp_config(),
    )
    alto_result = arrange_v3_gp(
        phrase,
        instrument_id="alto_c_12",
        config=gp_config(),
    )

    melody_length = len(MELODY_MIDIS)
    expected_offset = alto_range.min_midi - bass_range.min_midi
    assert_constant_offset(
        bass_result.chosen,
        alto_result.chosen,
        melody_length,
        expected_offset,
    )
    assert_constant_offset(
        bass_result.winner_candidate,
        alto_result.winner_candidate,
        melody_length,
        expected_offset,
    )


def test_arranger_keeps_uniform_offset_for_longer_phrase() -> None:
    """Long phrases keep a stable offset between bass and alto winners."""

    bass_range = InstrumentRange(min_midi=57, max_midi=77, comfort_center=67)
    alto_range = InstrumentRange(min_midi=69, max_midi=89, comfort_center=79)
    register_instrument_range("bass_c_12", bass_range)
    register_instrument_range("alto_c_12", alto_range)

    melody = [
        74,
        76,
        78,
        81,
        78,
        76,
        78,
        76,
        74,
        78,
        81,
        83,
        86,
        85,
        81,
        78,
        79,
        78,
        76,
        74,
        76,
        78,
        81,
        78,
        76,
        74,
        78,
        74,
        78,
        81,
        83,
        81,
        78,
        81,
        78,
        76,
        74,
        76,
        74,
        74,
        76,
        78,
        78,
        78,
        81,
        76,
        74,
        76,
        69,
        71,
        73,
        73,
        74,
        71,
        66,
        69,
        64,
        74,
        76,
        78,
        78,
        81,
        78,
        76,
        74,
        76,
        73,
        73,
        71,
        78,
        83,
        85,
        86,
        85,
        81,
        78,
        79,
        78,
        76,
        74,
        76,
        78,
        78,
        79,
        81,
        76,
        74,
        76,
        78,
        78,
        78,
        76,
        78,
        80,
        80,
        80,
        80,
        78,
        80,
        82,
        82,
        82,
        82,
        82,
        82,
    ]

    phrase = make_span(melody)

    bass_result = arrange_v3_gp(
        phrase,
        instrument_id="bass_c_12",
        config=gp_config(),
    )
    alto_result = arrange_v3_gp(
        phrase,
        instrument_id="alto_c_12",
        config=gp_config(),
    )

    melody_length = len(melody)
    expected_offset = alto_range.min_midi - bass_range.min_midi
    assert_constant_offset(
        bass_result.chosen,
        alto_result.chosen,
        melody_length,
        expected_offset,
    )
    assert_constant_offset(
        bass_result.winner_candidate,
        alto_result.winner_candidate,
        melody_length,
        expected_offset,
    )
