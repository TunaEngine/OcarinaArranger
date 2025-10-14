from __future__ import annotations

import textwrap
import xml.etree.ElementTree as ET

from ocarina_tools.musicxml import qname
from ocarina_tools.parts import MusicXmlPartInfo, filter_parts, list_parts


def _score_from_string(xml: str) -> ET.Element:
    return ET.fromstring(textwrap.dedent(xml).strip())


def test_list_parts_single_part() -> None:
    root = _score_from_string(
        """
        <score-partwise version="3.1">
          <part-list>
            <score-part id="P1">
              <part-name>Flute</part-name>
              <midi-instrument id="P1-I1">
                <midi-program>41</midi-program>
              </midi-instrument>
            </score-part>
          </part-list>
          <part id="P1">
            <measure number="1">
              <note>
                <pitch><step>C</step><octave>4</octave></pitch>
                <duration>1</duration>
              </note>
              <note>
                <pitch><step>G</step><octave>4</octave></pitch>
                <duration>1</duration>
              </note>
            </measure>
          </part>
        </score-partwise>
        """
    )

    infos = list_parts(root)

    assert infos == [
        MusicXmlPartInfo(
            part_id="P1",
            name="Flute",
            midi_program=40,
            note_count=2,
            min_midi=60,
            max_midi=67,
            min_pitch="C4",
            max_pitch="G4",
        )
    ]


def test_list_parts_skips_missing_part_id() -> None:
    root = _score_from_string(
        """
        <score-partwise version="3.1">
          <part-list>
            <score-part id="P1"><part-name>Piano RH</part-name></score-part>
            <score-part id="P2"><part-name>Piano LH</part-name></score-part>
            <score-part id="P3"><part-name>Ghost</part-name></score-part>
          </part-list>
          <part id="P1"><measure number="1"><note><pitch><step>D</step><octave>5</octave></pitch><duration>1</duration></note></measure></part>
          <part id="P2"><measure number="1"><note><pitch><step>C</step><octave>3</octave></pitch><duration>1</duration></note></measure></part>
        </score-partwise>
        """
    )

    infos = list_parts(root)

    assert [info.part_id for info in infos] == ["P1", "P2"]
    assert infos[0].min_pitch == "D5"
    assert infos[1].max_pitch == "C3"


def test_filter_parts_keeps_requested_order() -> None:
    root = _score_from_string(
        """
        <score-partwise version="3.1">
          <part-list>
            <score-part id="P1"><part-name>Piano RH</part-name></score-part>
            <score-part id="P2"><part-name>Piano LH</part-name></score-part>
            <score-part id="P3"><part-name>Strings</part-name></score-part>
          </part-list>
          <part id="P1"/>
          <part id="P2"/>
          <part id="P3"/>
        </score-partwise>
        """
    )

    filter_parts(root, ["P3", "P1", "PX"])

    q = lambda tag: qname(root, tag)

    score_part_ids = [el.get("id") for el in root.find(q("part-list")).findall(q("score-part"))]
    part_ids = [el.get("id") for el in root.findall(q("part"))]

    assert score_part_ids == ["P3", "P1"]
    assert part_ids == ["P3", "P1"]


def test_filter_parts_with_empty_selection_removes_all() -> None:
    root = _score_from_string(
        """
        <score-partwise version="3.1">
          <part-list>
            <score-part id="P1" />
          </part-list>
          <part id="P1" />
        </score-partwise>
        """
    )

    filter_parts(root, [])

    q = lambda tag: qname(root, tag)
    part_list = root.find(q("part-list"))
    if part_list is not None:
        assert not part_list.findall(q("score-part"))
    assert not root.findall(q("part"))
