from __future__ import annotations

import textwrap
from pathlib import Path
import xml.etree.ElementTree as ET

from ocarina_tools import GraceSettings, NoteEvent, get_note_events, get_time_signature
from shared.ottava import OttavaShift

from helpers import make_linear_score


ASSETS = Path(__file__).parent / "integration" / "assets"


def test_get_note_events_returns_sorted_sequence():
    _, root = make_linear_score()
    events, ppq = get_note_events(root)
    assert ppq == 480
    assert events == [
        NoteEvent(0, 480, 60, 79, (480,)),
        NoteEvent(960, 960, 62, 79, (960,)),
    ]


def test_get_note_events_uses_part_programs():
    tree, root = make_linear_score()
    part_list = root.find('part-list')
    assert part_list is not None
    score_part = part_list.find('score-part')
    assert score_part is not None
    midi_inst = ET.SubElement(score_part, 'midi-instrument', attrib={'id': 'P1-I1'})
    ET.SubElement(midi_inst, 'midi-program').text = '1'

    events, _ = get_note_events(root)

    assert events[0].program == 0


def test_get_time_signature_defaults_to_four_four():
    _, root = make_linear_score()
    assert get_time_signature(root) == (4, 4)


def test_get_note_events_merges_tied_notes():
    xml = textwrap.dedent(
        """
        <score-partwise version="3.1">
          <part-list>
            <score-part id="P1">
              <part-name>Solo</part-name>
            </score-part>
          </part-list>
          <part id="P1">
            <measure number="1">
              <attributes>
                <divisions>2</divisions>
              </attributes>
              <note>
                <pitch>
                  <step>C</step>
                  <octave>4</octave>
                </pitch>
                <duration>2</duration>
                <voice>1</voice>
                <tie type="start" />
                <notations>
                  <tied type="start" />
                </notations>
              </note>
            </measure>
            <measure number="2">
              <note>
                <pitch>
                  <step>C</step>
                  <octave>4</octave>
                </pitch>
                <duration>2</duration>
                <voice>1</voice>
                <tie type="stop" />
                <notations>
                  <tied type="stop" />
                </notations>
              </note>
              <note>
                <pitch>
                  <step>E</step>
                  <octave>4</octave>
                </pitch>
                <duration>2</duration>
                <voice>1</voice>
              </note>
            </measure>
          </part>
        </score-partwise>
        """
    ).strip()
    root = ET.fromstring(xml)

    events, _ = get_note_events(root)

    assert events == [
        NoteEvent(0, 960, 60, 79, (480, 480)),
        NoteEvent(960, 480, 64, 79, (480,)),
    ]
    assert events[0].tie_offsets == (480,)


def test_get_note_events_realizes_grace_chain():
    xml = textwrap.dedent(
        """
        <score-partwise version="3.1">
          <part-list>
            <score-part id="P1">
              <part-name>Solo</part-name>
            </score-part>
          </part-list>
          <part id="P1">
            <measure number="1">
              <attributes>
                <divisions>4</divisions>
              </attributes>
              <note>
                <grace slash="yes"/>
                <pitch>
                  <step>E</step>
                  <octave>4</octave>
                </pitch>
                <duration>0</duration>
                <voice>1</voice>
              </note>
              <note>
                <grace/>
                <pitch>
                  <step>F</step>
                  <octave>4</octave>
                </pitch>
                <duration>0</duration>
                <voice>1</voice>
              </note>
              <note>
                <pitch>
                  <step>G</step>
                  <octave>4</octave>
                </pitch>
                <duration>8</duration>
                <voice>1</voice>
              </note>
            </measure>
          </part>
        </score-partwise>
        """
    ).strip()
    root = ET.fromstring(xml)

    settings = GraceSettings(policy="steal", fractions=(0.125, 0.08333333333333333))
    events, _ = get_note_events(root, grace_settings=settings)

    assert len(events) == 3
    grace_one, grace_two, principal = events

    assert grace_one.is_grace
    assert grace_one.grace_type == "acciaccatura"
    assert grace_one.midi == 64

    assert grace_two.is_grace
    assert grace_two.grace_type == "appoggiatura"
    assert grace_two.midi == 65
    assert grace_two.onset == grace_one.onset + grace_one.duration

    assert principal.onset == grace_two.onset + grace_two.duration
    assert principal.duration == max(1, 960 - grace_one.duration - grace_two.duration)
    assert not principal.is_grace


def test_get_note_events_scales_grace_duration_with_tempo_weighted_policy():
    root = ET.parse(ASSETS / "04_subhole_speed_expected.musicxml").getroot()

    events, _ = get_note_events(root)

    assert len(events) == 2
    grace, anchor = events
    assert grace.is_grace
    assert grace.duration == 70
    assert anchor.onset == grace.onset + grace.duration
    assert anchor.duration == 960 - grace.duration
    assert anchor.duration == 890


def test_get_note_events_honours_non_tempo_weighted_policy():
    root = ET.parse(ASSETS / "04_subhole_speed_expected.musicxml").getroot()

    events, _ = get_note_events(root, grace_settings=GraceSettings(policy="steal"))

    assert len(events) == 2
    grace, anchor = events
    assert grace.duration == 120
    assert anchor.onset == 120
    assert anchor.duration == 840


def test_get_note_events_allocates_grace_chain_by_fraction():
    xml = textwrap.dedent(
        """
        <score-partwise version="3.1">
          <part-list>
            <score-part id="P1"><part-name>Solo</part-name></score-part>
          </part-list>
          <part id="P1">
            <measure number="1">
              <attributes><divisions>4</divisions></attributes>
              <direction placement="above"><sound tempo="180" /></direction>
              <note><grace slash="yes"/><pitch><step>D</step><octave>4</octave></pitch><duration>0</duration><voice>1</voice></note>
              <note><grace/><pitch><step>E</step><octave>4</octave></pitch><duration>0</duration><voice>1</voice></note>
              <note><grace/><pitch><step>F</step><octave>4</octave></pitch><duration>0</duration><voice>1</voice></note>
              <note><pitch><step>G</step><octave>4</octave></pitch><duration>8</duration><voice>1</voice></note>
            </measure>
          </part>
        </score-partwise>
        """
    ).strip()
    root = ET.fromstring(xml)

    events, _ = get_note_events(root)

    assert [event.midi for event in events] == [62, 64, 65, 67]
    assert [event.duration for event in events[:3]] == [60, 40, 30]
    assert events[3].onset == sum(event.duration for event in events[:3])
    assert events[3].duration == 830


def test_get_note_events_normalizes_octave_shift_direction():
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
                <divisions>4</divisions>
              </attributes>
              <direction>
                <direction-type>
                  <octave-shift type="up" size="8" number="1"/>
                </direction-type>
              </direction>
              <note>
                <pitch>
                  <step>C</step>
                  <octave>4</octave>
                </pitch>
                <duration>4</duration>
                <voice>1</voice>
              </note>
              <direction>
                <direction-type>
                  <octave-shift type="stop" number="1"/>
                </direction-type>
              </direction>
              <note>
                <pitch>
                  <step>D</step>
                  <octave>4</octave>
                </pitch>
                <duration>4</duration>
                <voice>1</voice>
              </note>
            </measure>
          </part>
        </score-partwise>
        """
    ).strip()
    root = ET.fromstring(xml)
    events, _ = get_note_events(root)
    assert len(events) == 2
    first = events[0]
    assert first.midi == 72
    assert first.ottava_shifts == (
        OttavaShift(source="octave-shift", direction="up", size=8, number="1"),
    )
    second = events[1]
    assert second.midi == 62
    assert second.ottava_shifts == ()


def test_get_note_events_normalizes_notation_ottava():
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
                <divisions>4</divisions>
              </attributes>
              <note>
                <pitch>
                  <step>E</step>
                  <octave>4</octave>
                </pitch>
                <duration>2</duration>
                <voice>1</voice>
                <notations>
                  <technical>
                    <ottava type="up" number="1" size="8"/>
                  </technical>
                </notations>
              </note>
              <note>
                <pitch>
                  <step>F</step>
                  <octave>4</octave>
                </pitch>
                <duration>2</duration>
                <voice>1</voice>
                <notations>
                  <technical>
                    <ottava type="stop" number="1"/>
                  </technical>
                </notations>
              </note>
            </measure>
          </part>
        </score-partwise>
        """
    ).strip()
    root = ET.fromstring(xml)
    events, _ = get_note_events(root)
    assert len(events) == 2
    first = events[0]
    assert first.midi == 76
    assert first.ottava_shifts == (
        OttavaShift(source="ottava", direction="up", size=8, number="1"),
    )
    second = events[1]
    assert second.midi == 77
    assert second.ottava_shifts == first.ottava_shifts
