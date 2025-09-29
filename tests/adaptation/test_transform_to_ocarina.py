from __future__ import annotations

import textwrap
import xml.etree.ElementTree as ET

import pytest

from ocarina_tools import transform_to_ocarina

from ..helpers import make_chord_score


def test_transform_to_ocarina_collapses_and_transposes():
    tree, root = make_chord_score()
    summary = transform_to_ocarina(
        tree,
        root,
        prefer_mode="auto",
        range_min="A4",
        range_max="F6",
        prefer_flats=True,
        collapse_chords=True,
    )
    parts = root.findall("part")
    assert len(parts) == 1
    measure1_notes = parts[0].findall("measure")[0].findall("note")
    assert len(measure1_notes) == 1
    pitch = measure1_notes[0].find("pitch")
    assert pitch.find("step").text == "A"
    assert pitch.find("octave").text == "5"
    assert pitch.find("alter") is None
    assert summary["transpose_semitones"] == 10
    assert summary["register_shift_semitones"] == 0
    assert summary["range_names"]["min"] == "A5"
    assert summary["range_names"]["max"] == "D6"
    part_list = root.find("part-list")
    name_groups = [[el.text for el in sp.findall("part-name")] for sp in part_list.findall("score-part")]
    assert all(group and group[-1] == "Ocarina" for group in name_groups)
    for score_part in part_list.findall("score-part"):
        midi_inst = score_part.find("midi-instrument")
        assert midi_inst is not None
        assert midi_inst.findtext("midi-program") == "80"


def test_transform_to_ocarina_accepts_manual_transpose_offset():
    tree, root = make_chord_score()
    summary = transform_to_ocarina(
        tree,
        root,
        prefer_mode="auto",
        range_min="A4",
        range_max="F6",
        prefer_flats=False,
        collapse_chords=True,
        transpose_offset=-3,
    )
    parts = root.findall("part")
    measure1_notes = parts[0].findall("measure")[0].findall("note")
    assert len(measure1_notes) == 1
    pitch = measure1_notes[0].find("pitch")
    assert pitch.find("step").text == "F"
    assert pitch.find("alter").text == "1"
    assert pitch.find("octave").text == "5"
    assert summary["auto_transpose_semitones"] == 10
    assert summary["manual_transpose_offset"] == -3
    assert summary["transpose_semitones"] == 7


def test_transform_to_ocarina_without_chord_collapse_retains_chord():
    tree, root = make_chord_score()
    transform_to_ocarina(
        tree,
        root,
        prefer_mode="auto",
        range_min="A4",
        range_max="F6",
        prefer_flats=True,
        collapse_chords=False,
    )
    measure1_notes = root.findall("part")[0].findall("measure")[0].findall("note")
    assert len(measure1_notes) == 2
    second = measure1_notes[1]
    assert second.find("chord") is not None
    chord_pitch = second.find("pitch")
    assert chord_pitch.find("step").text == "A"
    assert chord_pitch.find("octave").text == "5"


def test_transform_to_ocarina_uses_sharps_when_requested():
    xml = textwrap.dedent(
        """
        <score-partwise version="3.1">
          <part-list>
            <score-part id="P1">
              <part-name>Lead</part-name>
            </score-part>
          </part-list>
          <part id="P1">
            <measure number="1">
              <attributes>
                <divisions>1</divisions>
                <key>
                  <fifths>2</fifths>
                  <mode>major</mode>
                </key>
              </attributes>
              <note>
                <pitch>
                  <step>F</step>
                  <octave>4</octave>
                </pitch>
                <duration>1</duration>
                <voice>1</voice>
              </note>
            </measure>
          </part>
        </score-partwise>
        """
    ).strip()
    tree = ET.ElementTree(ET.fromstring(xml))
    root = tree.getroot()
    transform_to_ocarina(
        tree,
        root,
        prefer_mode="major",
        range_min="A4",
        range_max="F6",
        prefer_flats=False,
        collapse_chords=False,
    )
    note = root.findall("part")[0].findall("measure")[0].find("note")
    pitch = note.find("pitch")
    assert pitch.find("step").text == "D"
    assert pitch.find("alter").text == "1"


def test_transform_to_ocarina_wraps_high_notes_into_range():
    xml = textwrap.dedent(
        """
        <score-partwise version="3.1">
          <part-list>
            <score-part id="P1">
              <part-name>Lead</part-name>
            </score-part>
          </part-list>
          <part id="P1">
            <measure number="1">
              <attributes>
                <divisions>1</divisions>
                <key>
                  <fifths>2</fifths>
                  <mode>major</mode>
                </key>
              </attributes>
              <note>
                <pitch>
                  <step>G</step>
                  <octave>7</octave>
                </pitch>
                <duration>1</duration>
                <voice>1</voice>
              </note>
            </measure>
          </part>
        </score-partwise>
        """
    ).strip()
    tree = ET.ElementTree(ET.fromstring(xml))
    root = tree.getroot()
    summary = transform_to_ocarina(
        tree,
        root,
        prefer_mode="major",
        range_min="A4",
        range_max="F6",
    )
    note = root.findall("part")[0].findall("measure")[0].find("note")
    pitch = note.find("pitch")
    assert pitch.find("step").text == "F"
    assert pitch.find("octave").text == "5"
    assert summary["register_shift_semitones"] <= -12


def test_transform_to_ocarina_prefers_middle_lower_register_when_possible():
    xml = textwrap.dedent(
        """
        <score-partwise version="3.1">
          <part-list>
            <score-part id="P1">
              <part-name>Lead</part-name>
            </score-part>
          </part-list>
          <part id="P1">
            <measure number="1">
              <attributes>
                <divisions>1</divisions>
                <key>
                  <fifths>0</fifths>
                  <mode>major</mode>
                </key>
              </attributes>
              <note>
                <pitch>
                  <step>D</step>
                  <octave>6</octave>
                </pitch>
                <duration>1</duration>
                <voice>1</voice>
              </note>
              <note>
                <pitch>
                  <step>E</step>
                  <octave>6</octave>
                </pitch>
                <duration>1</duration>
                <voice>1</voice>
              </note>
            </measure>
          </part>
        </score-partwise>
        """
    ).strip()
    tree = ET.ElementTree(ET.fromstring(xml))
    root = tree.getroot()
    summary = transform_to_ocarina(
        tree,
        root,
        prefer_mode="major",
        range_min="A4",
        range_max="F6",
        collapse_chords=False,
    )
    notes = root.findall("part")[0].findall("measure")[0].findall("note")
    assert {n.find("pitch").find("octave").text for n in notes} == {"5"}
    assert summary["register_shift_semitones"] == -12


def test_transform_to_ocarina_rejects_inverted_range():
    tree, root = make_chord_score()
    with pytest.raises(ValueError):
        transform_to_ocarina(tree, root, range_min="F6", range_max="A4")
