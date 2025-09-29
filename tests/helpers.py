from __future__ import annotations

import textwrap
import xml.etree.ElementTree as ET


def make_chord_score() -> tuple[ET.ElementTree, ET.Element]:
    xml = textwrap.dedent(
        """
        <score-partwise version="3.1">
          <part-list>
            <score-part id="P1">
              <part-name>Flute</part-name>
            </score-part>
            <score-part id="P2">
              <part-name>Piano</part-name>
            </score-part>
          </part-list>
          <part id="P1">
            <measure number="1">
              <attributes>
                <divisions>2</divisions>
                <key>
                  <fifths>2</fifths>
                  <mode>major</mode>
                </key>
                <time>
                  <beats>4</beats>
                  <beat-type>4</beat-type>
                </time>
                <clef>
                  <sign>G</sign>
                  <line>2</line>
                </clef>
              </attributes>
              <note>
                <pitch>
                  <step>G</step>
                  <octave>4</octave>
                </pitch>
                <duration>2</duration>
                <voice>1</voice>
                <type>quarter</type>
              </note>
              <note>
                <chord/>
                <pitch>
                  <step>B</step>
                  <octave>4</octave>
                </pitch>
                <duration>2</duration>
                <voice>1</voice>
              </note>
              <note>
                <pitch>
                  <step>D</step>
                  <alter>1</alter>
                  <octave>5</octave>
                </pitch>
                <duration>2</duration>
                <voice>2</voice>
              </note>
            </measure>
            <measure number="2">
              <note>
                <rest/>
                <duration>2</duration>
                <voice>1</voice>
              </note>
              <note>
                <pitch>
                  <step>E</step>
                  <octave>5</octave>
                </pitch>
                <duration>2</duration>
                <voice>1</voice>
              </note>
            </measure>
          </part>
          <part id="P2">
            <measure number="1">
              <note>
                <rest/>
                <duration>2</duration>
              </note>
            </measure>
          </part>
        </score-partwise>
        """
    ).strip()
    tree = ET.ElementTree(ET.fromstring(xml))
    return tree, tree.getroot()


def make_linear_score() -> tuple[ET.ElementTree, ET.Element]:
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
                <divisions>1</divisions>
              </attributes>
              <note>
                <pitch>
                  <step>C</step>
                  <octave>4</octave>
                </pitch>
                <duration>1</duration>
                <voice>1</voice>
              </note>
              <note>
                <rest/>
                <duration>1</duration>
                <voice>1</voice>
              </note>
              <note>
                <pitch>
                  <step>D</step>
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
    tree = ET.ElementTree(ET.fromstring(xml))
    return tree, tree.getroot()


def make_linear_score_with_tempo(tempo: int = 96) -> tuple[ET.ElementTree, ET.Element]:
    xml = textwrap.dedent(
        f"""
        <score-partwise version="3.1">
          <part-list>
            <score-part id="P1">
              <part-name>Solo</part-name>
            </score-part>
          </part-list>
          <part id="P1">
            <measure number="1">
              <attributes>
                <divisions>1</divisions>
              </attributes>
              <direction placement="above">
                <sound tempo="{tempo}" />
              </direction>
              <note>
                <pitch>
                  <step>C</step>
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
    return tree, tree.getroot()


__all__ = ["make_chord_score", "make_linear_score", "make_linear_score_with_tempo"]
