from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from ocarina_tools.musicxml import (
    PitchData,
    build_pitch_element,
    constrain_midi,
    first_divisions,
    get_pitch_data,
    is_voice_one,
    iter_pitched_notes_first_part,
    make_qname_getter,
    qname,
    write_pitch,
)


def make_note(*, step: str | None = None, alter: int | None = 0, octave: int | None = None,
              duration: int = 0, voice: int | None = None, rest: bool = False) -> ET.Element:
    note = ET.Element("note")
    if rest:
        ET.SubElement(note, "rest")
    elif step is not None and octave is not None:
        pitch = ET.SubElement(note, "pitch")
        ET.SubElement(pitch, "step").text = step
        if alter:
            ET.SubElement(pitch, "alter").text = str(alter)
        ET.SubElement(pitch, "octave").text = str(octave)
    if duration is not None:
        ET.SubElement(note, "duration").text = str(duration)
    if voice is not None:
        ET.SubElement(note, "voice").text = str(voice)
    return note


def test_qname_handles_namespaced_and_plain_roots():
    # Ensure qname returns the fully-qualified tag name for both plain and namespaced roots.
    plain_root = ET.Element("score-partwise")
    assert qname(plain_root, "note") == "note"

    ns_root = ET.Element("{urn:dummy}score-partwise")
    assert qname(ns_root, "note") == "{urn:dummy}note"


def test_make_qname_getter_returns_namespace_aware_callable():
    plain_root = ET.Element("score-partwise")
    plain_q = make_qname_getter(plain_root)
    assert plain_q("measure") == "measure"

    ns_root = ET.Element("{urn:test}score-partwise")
    ns_q = make_qname_getter(ns_root)
    assert ns_q("note") == "{urn:test}note"


def test_write_pitch_adds_and_removes_elements():
    # Confirm write_pitch writes all pitch children and removes alter when writing a natural.
    pitch = ET.Element("pitch")
    q = lambda t: t

    write_pitch(pitch, q, "A", 1, 4)
    assert pitch.find("step").text == "A"
    assert pitch.find("alter").text == "1"
    assert pitch.find("octave").text == "4"

    # Updating with a natural pitch should remove the alter element
    write_pitch(pitch, q, "A", 0, 5)
    assert pitch.find("alter") is None
    assert pitch.find("octave").text == "5"


def test_get_pitch_data_returns_pitchdata_and_none_for_incomplete():
    # Validate get_pitch_data returns populated PitchData or None if the note is incomplete.
    note = make_note(step="C", alter=None, octave=4, duration=2)
    q = lambda t: t
    data = get_pitch_data(note, q)
    assert isinstance(data, PitchData)
    assert data.step == "C"
    assert data.alter == 0
    assert data.octave == 4
    assert data.midi == 60

    incomplete_note = ET.Element("note")
    assert get_pitch_data(incomplete_note, q) is None


def test_pitchdata_update_from_midi_respects_preferred_accidentals():
    # Check update_from_midi emits flats or sharps based on prefer_flats preference.
    note = make_note(step="C", alter=0, octave=4, duration=1)
    pitch_el = note.find("pitch")
    q = lambda t: t
    data = PitchData(pitch_el, "C", 0, 4)

    data.update_from_midi(61, q, prefer_flats=True)
    assert (data.step, data.alter, data.octave) == ("D", -1, 4)
    assert pitch_el.find("alter").text == "-1"

    data.update_from_midi(61, q, prefer_flats=False)
    assert (data.step, data.alter, data.octave) == ("C", 1, 4)
    assert pitch_el.find("alter").text == "1"


@pytest.mark.parametrize(
    "midi, prefer_flats, expected",
    [
        (61, True, ("D", -1, "4")),
        (61, False, ("C", "1", "4")),
    ],
)
def test_build_pitch_element_uses_midi_conversion(midi, prefer_flats, expected):
    # Ensure build_pitch_element reflects MIDI conversion respecting accidental preference.
    q = lambda t: t
    element = build_pitch_element(q, midi, prefer_flats=prefer_flats)
    step, alter, octave = expected
    assert element.find("step").text == step
    alter_el = element.find("alter")
    if alter:
        assert alter_el.text == alter if isinstance(alter, str) else str(alter)
    else:
        assert alter_el is None
    assert element.find("octave").text == octave


def test_constrain_midi_wraps_within_range():
    # Verify constrain_midi wraps MIDI values into the inclusive min/max range.
    assert constrain_midi(53, 60, 72) == 65
    assert constrain_midi(85, 60, 72) == 61


def test_constrain_midi_rejects_inverted_range():
    # Guard against invalid bounds that would cause an infinite loop.
    with pytest.raises(ValueError):
        constrain_midi(60, 72, 60)


def test_is_voice_one_defaults_and_checks_value():
    # Confirm is_voice_one defaults missing voices to True and respects explicit voice numbers.
    q = lambda t: t
    note_default = make_note(step="C", octave=4, duration=1)
    assert is_voice_one(note_default, q)

    note_voice_two = make_note(step="C", octave=4, duration=1, voice=2)
    assert not is_voice_one(note_voice_two, q)


def test_first_divisions_finds_first_valid_value():
    # Ensure first_divisions locates the earliest divisions attribute in reading order.
    root = ET.Element("score-partwise")
    q = lambda t: t
    part1 = ET.SubElement(root, "part")
    measure1 = ET.SubElement(part1, "measure")
    ET.SubElement(measure1, "attributes")
    measure2 = ET.SubElement(part1, "measure")
    attrs = ET.SubElement(measure2, "attributes")
    ET.SubElement(attrs, "divisions").text = "4"

    part2 = ET.SubElement(root, "part")
    measure3 = ET.SubElement(part2, "measure")
    attrs2 = ET.SubElement(measure3, "attributes")
    ET.SubElement(attrs2, "divisions").text = "8"

    assert first_divisions(root) == 4


def test_iter_pitched_notes_first_part_yields_sequence():
    # Check iter_pitched_notes_first_part yields pitched notes/rests from first part and skips invalid notes.
    root = ET.Element("score-partwise")
    q = lambda t: t
    part1 = ET.SubElement(root, "part")
    measure1 = ET.SubElement(part1, "measure")
    measure1.append(make_note(step="C", octave=4, duration=2, voice=1))
    measure1.append(make_note(rest=True, duration=3))
    # Missing pitch data should be skipped
    bad_note = ET.Element("note")
    ET.SubElement(bad_note, "duration").text = "1"
    measure1.append(bad_note)

    part2 = ET.SubElement(root, "part")
    measure2 = ET.SubElement(part2, "measure")
    measure2.append(make_note(step="E", octave=5, duration=1))

    events = list(iter_pitched_notes_first_part(root))
    assert events == [
        {"rest": False, "midi": 60, "duration": 2},
        {"rest": True, "duration": 3},
    ]

