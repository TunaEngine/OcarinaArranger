from __future__ import annotations

from domain.arrangement.api import arrange_span
from domain.arrangement.config import FeatureFlags, GraceSettings as DomainGraceSettings
from domain.arrangement.soft_key import InstrumentRange
from ocarina_tools import GraceSettings as ImporterGraceSettings

from .test_arranger_polyphonic import _phrase_from_xml


def test_polyphonic_grace_chain_normalized() -> None:
    phrase = _phrase_from_xml(
        """
        <score-partwise version="3.1">
          <part-list>
            <score-part id="P1"><part-name>Solo</part-name></score-part>
          </part-list>
          <part id="P1">
            <measure number="1">
              <attributes><divisions>4</divisions></attributes>
              <note><grace/><pitch><step>E</step><octave>4</octave></pitch><duration>0</duration><voice>1</voice></note>
              <note><pitch><step>F</step><octave>4</octave></pitch><duration>8</duration><voice>1</voice></note>
            </measure>
          </part>
        </score-partwise>
        """,
        importer_settings=ImporterGraceSettings(policy="steal"),
    )
    instrument = InstrumentRange(min_midi=50, max_midi=90, comfort_center=60)
    settings = DomainGraceSettings(policy="steal")

    result = arrange_span(
        phrase,
        instrument=instrument,
        flags=FeatureFlags(dp_slack=False),
        grace_settings=settings,
    )

    grace_events = [event for event in result.preprocessing if event.action == "GRACE_NORMALIZE"]
    assert grace_events, "expected grace normalization explanation"
    assert "Normalized grace notes" in grace_events[0].reason

    assert len(result.span.notes) == 2
    normalized_grace, anchor = result.span.notes
    assert "grace" in normalized_grace.tags
    assert anchor.onset == normalized_grace.onset + normalized_grace.duration


def test_polyphonic_graces_dropped_when_anchor_short() -> None:
    phrase = _phrase_from_xml(
        """
        <score-partwise version="3.1">
          <part-list>
            <score-part id="P1"><part-name>Solo</part-name></score-part>
          </part-list>
          <part id="P1">
            <measure number="1">
              <attributes><divisions>4</divisions></attributes>
              <note><grace slash="yes"/><pitch><step>D</step><octave>4</octave></pitch><duration>0</duration><voice>1</voice></note>
              <note><grace/><pitch><step>E</step><octave>4</octave></pitch><duration>0</duration><voice>1</voice></note>
              <note><pitch><step>G</step><octave>4</octave></pitch><duration>2</duration><voice>1</voice></note>
            </measure>
          </part>
        </score-partwise>
        """,
        importer_settings=ImporterGraceSettings(policy="steal"),
    )
    instrument = InstrumentRange(min_midi=50, max_midi=90, comfort_center=60)
    settings = DomainGraceSettings(anchor_min_fraction=0.75, policy="steal")

    result = arrange_span(
        phrase,
        instrument=instrument,
        flags=FeatureFlags(dp_slack=False),
        grace_settings=settings,
    )

    assert len(result.span.notes) == 1
    event = next((evt for evt in result.preprocessing if evt.action == "GRACE_NORMALIZE"), None)
    assert event is not None
    assert "Dropped graces to protect anchor duration" in event.reason


def test_polyphonic_graces_pruned_for_fast_tempo() -> None:
    phrase = _phrase_from_xml(
        """
        <score-partwise version="3.1">
          <part-list>
            <score-part id="P1"><part-name>Solo</part-name></score-part>
          </part-list>
          <part id="P1">
            <measure number="1">
              <attributes><divisions>4</divisions></attributes>
              <note><grace slash="yes"/><pitch><step>D</step><octave>4</octave></pitch><duration>0</duration><voice>1</voice></note>
              <note><grace/><pitch><step>E</step><octave>4</octave></pitch><duration>0</duration><voice>1</voice></note>
              <note><pitch><step>G</step><octave>4</octave></pitch><duration>8</duration><voice>1</voice></note>
            </measure>
          </part>
        </score-partwise>
        """,
        importer_settings=ImporterGraceSettings(),
    )
    instrument = InstrumentRange(min_midi=50, max_midi=90, comfort_center=60)
    settings = DomainGraceSettings(fast_tempo_bpm=150.0, slow_tempo_bpm=60.0)

    result = arrange_span(
        phrase,
        instrument=instrument,
        flags=FeatureFlags(dp_slack=False),
        tempo_bpm=180.0,
        grace_settings=settings,
    )

    assert len(result.span.notes) == 1
    event = next((evt for evt in result.preprocessing if evt.action == "GRACE_NORMALIZE"), None)
    assert event is not None
    assert "Removed grace chain above 150 BPM" in event.reason
