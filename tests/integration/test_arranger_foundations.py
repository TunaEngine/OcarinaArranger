from __future__ import annotations

import textwrap
import xml.etree.ElementTree as ET

from domain.arrangement.importers import phrase_from_note_events
from domain.arrangement.micro_edits import (
    drop_ornamental_eighth,
    lengthen_pivotal_note,
    shift_short_phrase_octave,
)
from ocarina_tools import get_note_events


def test_foundations_pipeline_normalizes_and_applies_micro_edits() -> None:
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
                <pitch><step>C</step><octave>4</octave></pitch>
                <duration>2</duration>
                <voice>1</voice>
              </note>
              <note>
                <pitch><step>D</step><octave>4</octave></pitch>
                <duration>2</duration>
                <voice>1</voice>
              </note>
              <direction>
                <direction-type>
                  <octave-shift type="stop" number="1"/>
                </direction-type>
              </direction>
              <note>
                <pitch><step>E</step><octave>4</octave></pitch>
                <duration>2</duration>
                <voice>1</voice>
                <notations>
                  <technical>
                    <ottava type="up" number="2" size="8"/>
                  </technical>
                </notations>
              </note>
              <note>
                <pitch><step>F</step><octave>4</octave></pitch>
                <duration>2</duration>
                <voice>1</voice>
                <notations>
                  <technical>
                    <ottava type="stop" number="2"/>
                  </technical>
                </notations>
              </note>
              <note>
                <pitch><step>G</step><octave>4</octave></pitch>
                <duration>4</duration>
                <voice>1</voice>
              </note>
              <note>
                <rest />
                <duration>2</duration>
                <voice>1</voice>
              </note>
              <note>
                <pitch><step>A</step><octave>4</octave></pitch>
                <duration>2</duration>
                <voice>1</voice>
              </note>
            </measure>
          </part>
        </score-partwise>
        """
    ).strip()
    root = ET.fromstring(xml)
    events, pulses_per_quarter = get_note_events(root)
    span = phrase_from_note_events(events, pulses_per_quarter)

    notes = list(span.notes)
    notes[0] = notes[0].with_tags([])
    notes[1] = notes[1].with_tags(["ornamental", "octave-shiftable"])
    notes[2] = notes[2].with_tags(["octave-shiftable"])
    notes[3] = notes[3].with_tags(["octave-shiftable"])
    notes[4] = notes[4].with_tags(["pivotal"])
    span = span.with_notes(notes)

    span = drop_ornamental_eighth(span)
    span = shift_short_phrase_octave(span, direction="down")
    span = lengthen_pivotal_note(span)

    midis = [note.midi for note in span.notes]
    durations = [note.duration for note in span.notes]

    assert midis[:3] == [72, 64, 65]
    assert durations[0] == 480
    assert durations[1] == 240
    assert durations[2] == 240
    assert span.notes[-2].duration == 720
    assert span.notes[1].ottava_shifts[-1].source == "micro-edit"
    assert span.notes[2].ottava_shifts[-1].source == "micro-edit"
