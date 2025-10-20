from __future__ import annotations

import os
import struct
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from ocarina_tools import (
    collect_used_pitches,
    export_midi,
    export_midi_poly,
    load_score,
    transform_to_ocarina,
)
from ocarina_tools.exporters import OCARINA_GM_PROGRAM
from ocarina_tools.midi_import import _parse_midi_events, _read_chunk

from ..helpers import make_chord_score, make_linear_score


def _read_midi_events(path: Path) -> list[tuple[int, int, int, int]]:
    events: list[tuple[int, int, int, int]] = []
    with path.open("rb") as handle:
        chunk_type, header = _read_chunk(handle)
        assert chunk_type == b"MThd"
        _, num_tracks, _ = struct.unpack(">HHH", header[:6])
        for _ in range(num_tracks or 1):
            try:
                chunk_type, data = _read_chunk(handle)
            except ValueError:
                break
            if chunk_type != b"MTrk":
                continue
            track_events, _ = _parse_midi_events(data)
            events.extend(track_events)
    return sorted(events)


def _read_first_track(path: Path) -> bytes:
    with path.open("rb") as handle:
        chunk_type, header = _read_chunk(handle)
        assert chunk_type == b"MThd"
        _, num_tracks, _ = struct.unpack(">HHH", header[:6])
        track_count = num_tracks or 1
        for _ in range(track_count):
            chunk_type, data = _read_chunk(handle)
            if chunk_type == b"MTrk":
                return data
    raise AssertionError("No MIDI track chunk found")


def test_export_midi_writes_header(tmp_path):
    tree, root = make_chord_score()
    transform_to_ocarina(tree, root, range_min="A4", range_max="F6")
    mid_path = tmp_path / "mono.mid"
    export_midi(root, mid_path, tempo_bpm=100)
    data = mid_path.read_bytes()
    assert data.startswith(b"MThd")
    assert b"MTrk" in data


def test_export_midi_detects_tempo_when_unspecified(tmp_path):
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
              <direction>
                <sound tempo="90" />
              </direction>
              <note>
                <pitch>
                  <step>C</step>
                  <octave>4</octave>
                </pitch>
                <duration>1</duration>
              </note>
            </measure>
          </part>
        </score-partwise>
        """
    ).strip()
    tree = ET.ElementTree(ET.fromstring(xml))
    root = tree.getroot()

    mid_path = tmp_path / "detected.mid"
    export_midi(root, mid_path)

    track = _read_first_track(mid_path)

    assert track.startswith(b"\x00\xff\x51\x03\n,*")


def test_export_midi_poly_writes_header(tmp_path):
    tree, root = make_chord_score()
    mid_path = tmp_path / "poly.mid"
    export_midi_poly(root, mid_path, tempo_bpm=90)
    data = mid_path.read_bytes()
    assert data.startswith(b"MThd")
    assert b"MTrk" in data


def test_load_score_reads_midi(tmp_path):
    tree, root = make_linear_score()
    mid_path = tmp_path / "linear.mid"
    export_midi_poly(root, mid_path, tempo_bpm=120)

    tree_loaded, root_loaded = load_score(str(mid_path))

    assert tree_loaded.getroot() is root_loaded
    pitches_original = collect_used_pitches(root, flats=True)
    pitches_loaded = collect_used_pitches(root_loaded, flats=True)
    assert pitches_loaded == pitches_original

    notes = list(root_loaded.findall("part/measure/note"))
    assert any(note.find("rest") is not None for note in notes)


def test_export_midi_poly_sets_ocarina_program(tmp_path):
    tree, root = make_chord_score()
    mid_path = tmp_path / "poly.mid"
    export_midi_poly(root, mid_path)

    track = _read_first_track(mid_path)

    assert bytes([0x00, 0xC0, OCARINA_GM_PROGRAM]) in track


def test_export_midi_poly_preserves_original_programs(tmp_path):
    xml = textwrap.dedent(
        """
        <score-partwise version="3.1">
          <part-list>
            <score-part id="P1">
              <part-name>Strings</part-name>
              <midi-instrument id="P1-I1">
                <midi-channel>1</midi-channel>
                <midi-program>49</midi-program>
              </midi-instrument>
            </score-part>
            <score-part id="P2">
              <part-name>Flute</part-name>
              <midi-instrument id="P2-I1">
                <midi-channel>2</midi-channel>
                <midi-program>75</midi-program>
              </midi-instrument>
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
              </note>
            </measure>
          </part>
          <part id="P2">
            <measure number="1">
              <note>
                <pitch>
                  <step>E</step>
                  <octave>4</octave>
                </pitch>
                <duration>1</duration>
              </note>
            </measure>
          </part>
        </score-partwise>
        """
    ).strip()
    tree = ET.ElementTree(ET.fromstring(xml))
    root = tree.getroot()

    mid_path = tmp_path / "orig.mid"
    export_midi_poly(root, mid_path, use_original_instruments=True)

    track = _read_first_track(mid_path)

    # midi-program is 1-based in MusicXML; expect 48 and 74 after conversion to MIDI (0-based)
    assert bytes([0x00, 0xC0, 48]) in track
    assert bytes([0x00, 0xC1, 74]) in track


def test_load_midi_preserves_original_programs(tmp_path):
    xml = textwrap.dedent(
        """
        <score-partwise version="3.1">
          <part-list>
            <score-part id="P1">
              <part-name>Piano</part-name>
              <midi-instrument id="P1-I1">
                <midi-channel>1</midi-channel>
                <midi-program>1</midi-program>
              </midi-instrument>
            </score-part>
            <score-part id="P2">
              <part-name>Trumpet</part-name>
              <midi-instrument id="P2-I1">
                <midi-channel>2</midi-channel>
                <midi-program>57</midi-program>
              </midi-instrument>
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
              </note>
            </measure>
          </part>
          <part id="P2">
            <measure number="1">
              <note>
                <pitch>
                  <step>E</step>
                  <octave>4</octave>
                </pitch>
                <duration>1</duration>
              </note>
            </measure>
          </part>
        </score-partwise>
        """
    ).strip()
    tree = ET.ElementTree(ET.fromstring(xml))
    root = tree.getroot()

    original_mid = tmp_path / "original.mid"
    export_midi_poly(root, original_mid, use_original_instruments=True)

    _loaded_tree, loaded_root = load_score(str(original_mid))

    roundtrip_mid = tmp_path / "roundtrip.mid"
    export_midi_poly(loaded_root, roundtrip_mid, use_original_instruments=True)

    track = _read_first_track(roundtrip_mid)

    assert bytes([0x00, 0xC0, 0]) in track
    assert bytes([0x00, 0xC1, 56]) in track


def test_polyphonic_midi_roundtrip_preserves_events(tmp_path):
    asset_env = os.environ.get("OCARINA_TEST_POLYPHONIC_MIDI")
    if not asset_env:
        pytest.skip(
            "Set OCARINA_TEST_POLYPHONIC_MIDI to a local polyphonic MIDI file to run this regression"
        )

    asset_path = Path(asset_env).expanduser()
    if not asset_path.exists():
        pytest.skip(f"Polyphonic MIDI fixture not found at {asset_path}")

    original_events = _read_midi_events(asset_path)

    _tree, root = load_score(str(asset_path))

    out_path = tmp_path / "roundtrip.mid"
    export_midi_poly(root, out_path)

    roundtrip_events = _read_midi_events(out_path)

    assert original_events
    assert roundtrip_events == original_events
