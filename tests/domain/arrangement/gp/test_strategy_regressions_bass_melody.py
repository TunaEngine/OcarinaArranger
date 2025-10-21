"""Regression tests focused on melody shape consistency for bass arrangements."""

from __future__ import annotations

from domain.arrangement.config import register_instrument_range
from domain.arrangement.gp.strategy import arrange_v3_gp
from domain.arrangement.soft_key import InstrumentRange

from tests.domain.arrangement.gp.bass_melody_data import (
    COMPLEX_BASS_SHAPE,
    COMPLEX_MELODY,
    CONSISTENCY_MELODY,
    EXTENDED_MELODY,
    EXTENDED_MELODY_VARIANT,
)
from tests.domain.arrangement.gp.bass_test_helpers import assert_constant_offset, top_voice
from tests.domain.arrangement.gp.gp_test_helpers import gp_config, make_span


def _configure_instruments() -> tuple[InstrumentRange, InstrumentRange]:
    bass_range = InstrumentRange(min_midi=57, max_midi=77, comfort_center=67)
    alto_range = InstrumentRange(min_midi=69, max_midi=89, comfort_center=79)
    register_instrument_range("bass_c_12", bass_range)
    register_instrument_range("alto_c_12", alto_range)
    return bass_range, alto_range


def test_arranger_preserves_shape_for_complex_melody() -> None:
    """Complex phrases should keep a uniform bass/alto offset for winners."""

    bass_range, alto_range = _configure_instruments()

    phrase = make_span(COMPLEX_MELODY)
    phrase_grouped: dict[int, list[int]] = {}
    for note in phrase.notes:
        phrase_grouped.setdefault(note.onset, []).append(note.midi)
    phrase_top = [max(phrase_grouped[onset]) for onset in sorted(phrase_grouped)]

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

    melody_length = len(COMPLEX_BASS_SHAPE)
    expected_offset = alto_range.min_midi - bass_range.min_midi

    bass_top = top_voice(bass_result.chosen)
    assert bass_top[-melody_length:] == list(COMPLEX_BASS_SHAPE)
    assert_constant_offset(
        bass_result.chosen,
        alto_result.chosen,
        melody_length,
        expected_offset,
    )
    bass_top = top_voice(bass_result.chosen)
    alto_top = top_voice(alto_result.chosen)
    assert [
        alto - bass for bass, alto in zip(bass_top[-melody_length:], alto_top[-melody_length:])
    ] == [expected_offset] * melody_length

    winner_bass_top = top_voice(bass_result.winner_candidate)
    assert winner_bass_top[-melody_length:] == list(COMPLEX_BASS_SHAPE)
    assert_constant_offset(
        bass_result.winner_candidate,
        alto_result.winner_candidate,
        melody_length,
        expected_offset,
    )
    winner_alto_top = top_voice(alto_result.winner_candidate)
    assert [
        alto - bass
        for bass, alto in zip(
            winner_bass_top[-melody_length:], winner_alto_top[-melody_length:]
        )
    ] == [expected_offset] * melody_length

    def _assert_alto_top_voice_near_constant(candidate) -> None:
        alto_top = top_voice(candidate)
        sample = min(len(alto_top), len(phrase_top))
        assert sample
        alto_segment = alto_top[-sample:]
        phrase_segment = phrase_top[-sample:]
        deltas = [alto - original for alto, original in zip(alto_segment, phrase_segment)]
        spread = max(deltas) - min(deltas)
        assert spread <= 12
        assert max(deltas) <= min(deltas) + 12

    _assert_alto_top_voice_near_constant(alto_result.chosen)
    _assert_alto_top_voice_near_constant(alto_result.winner_candidate)


def test_arranger_preserves_shape_for_extended_melody() -> None:
    """A long melody must keep a consistent bass/alto offset for winners."""

    bass_range, alto_range = _configure_instruments()

    phrase = make_span(EXTENDED_MELODY)

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

    melody_length = len(EXTENDED_MELODY)
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


def test_arranger_preserves_shape_for_extended_melody_variant() -> None:
    """A dense melody should keep Bass/Alto offsets within a narrow band."""

    bass_range, alto_range = _configure_instruments()

    phrase = make_span(EXTENDED_MELODY_VARIANT)

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

    melody_length = len(EXTENDED_MELODY_VARIANT)
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


def test_arranger_preserves_shape_for_consistency_melody() -> None:
    """Bass and Alto should share the same melody contour for complex tracks."""

    bass_range, alto_range = _configure_instruments()

    phrase = make_span(CONSISTENCY_MELODY)

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

    melody_length = len(CONSISTENCY_MELODY)
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

    bass_top = top_voice(bass_result.chosen)
    alto_top = top_voice(alto_result.chosen)
    sample = min(len(bass_top), len(alto_top), melody_length)
    assert sample
    bass_segment = bass_top[-sample:]
    alto_segment = alto_top[-sample:]
    assert [alto - bass for bass, alto in zip(bass_segment, alto_segment)] == [
        expected_offset
    ] * sample
    assert len(set(alto_segment)) > 4

    winner_bass_top = top_voice(bass_result.winner_candidate)
    winner_alto_top = top_voice(alto_result.winner_candidate)
    winner_sample = min(len(winner_bass_top), len(winner_alto_top), melody_length)
    assert winner_sample
    winner_bass_segment = winner_bass_top[-winner_sample:]
    winner_alto_segment = winner_alto_top[-winner_sample:]
    assert [
        alto - bass for bass, alto in zip(winner_bass_segment, winner_alto_segment)
    ] == [expected_offset] * winner_sample
    assert len(set(winner_alto_segment)) > 4
