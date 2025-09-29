from __future__ import annotations

import pytest

from ocarina_tools import midi_to_name, midi_to_pitch, parse_note_name, pitch_to_midi


def test_pitch_conversions_are_inverse():
    midi = pitch_to_midi("C", 1, 4)
    assert midi == 61
    assert midi_to_pitch(midi, prefer_flats=False) == ("C", 1, 4)
    assert midi_to_name(midi, flats=True) == "Db4"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("A4", 69),
        ("Bb4", 70),
        ("C#5", 73),
    ],
)
def test_parse_note_name_matches_midi(name: str, expected: int) -> None:
    assert parse_note_name(name) == expected


def test_parse_note_name_rejects_bad_token() -> None:
    with pytest.raises(ValueError):
        parse_note_name("H2")


def test_midi_to_name_respects_accidental_flag() -> None:
    midi = parse_note_name("Bb4")
    assert midi_to_name(midi, flats=True) == "Bb4"
    assert midi_to_name(midi, flats=False) == "A#4"
