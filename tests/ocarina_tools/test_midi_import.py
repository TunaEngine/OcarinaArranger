from __future__ import annotations

import struct
from pathlib import Path

import pytest

from ocarina_tools import export_midi_poly, get_tempo_changes, load_score, read_midi
from ocarina_tools.midi_import import DEFAULT_TIME_SIGNATURE

from tests.helpers import make_linear_score


def _write_midi(path: Path, track_bytes: bytes) -> None:
    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, 480)
    track_chunk = b"MTrk" + struct.pack(">I", len(track_bytes)) + track_bytes
    path.write_bytes(header + track_chunk)


def _vlq(value: int) -> bytes:
    buffer = [value & 0x7F]
    value >>= 7
    while value:
        buffer.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(buffer))


def _tempo_payload(bpm: int) -> bytes:
    micros = max(1, int(round(60_000_000 / max(1, bpm))))
    return micros.to_bytes(3, "big")


def test_read_midi_returns_song_and_report(tmp_path: Path) -> None:
    tree, root = make_linear_score()
    midi_path = tmp_path / "strict.mid"
    export_midi_poly(root, midi_path, tempo_bpm=96)

    song, report = read_midi(str(midi_path))

    assert song.root is song.tree.getroot()
    assert song.pulses_per_quarter >= 1
    assert report.mode == "strict"
    assert report.issues == ()
    assert report.synthetic_eot_tracks == ()
    assert report.assumed_tempo_bpm == 96
    assert report.assumed_time_signature == DEFAULT_TIME_SIGNATURE

    tempo_changes = get_tempo_changes(song.root)
    assert tempo_changes[0].tempo_bpm == pytest.approx(96)

    tree_loaded, root_loaded = load_score(str(midi_path))
    assert tree_loaded.getroot().find("part/measure/note") is not None
    assert root_loaded is tree_loaded.getroot()


def test_read_midi_lenient_reports_issues(tmp_path: Path) -> None:
    midi_path = tmp_path / "lenient.mid"
    # Leading stray data byte (0x40) causes the strict decoder to fail.
    # The lenient decoder should recover, emit the note, and insert a synthetic
    # end-of-track marker because the original data lacks it.
    track_bytes = bytes(
        [
            0x00,  # delta time
            0x40,  # stray data byte without status
            0x00, 0x90, 60, 0x40,  # note-on C4 velocity 64
            0x81, 0x00, 0x80, 60, 0x00,  # delta 128, note-off C4
        ]
    )
    _write_midi(midi_path, track_bytes)

    song, report = read_midi(str(midi_path))

    notes = list(song.root.findall("part/measure/note"))
    assert notes, "Expected lenient import to produce MusicXML notes"
    assert report.mode == "lenient"
    assert report.synthetic_eot_tracks == (0,)
    assert any("Ignored data byte" in issue.detail for issue in report.issues)
    assert any("Running status" in issue.detail for issue in report.issues)
    assert any(
        issue.detail == "Inserted synthetic end-of-track" for issue in report.issues
    )


def test_read_midi_strict_mode_raises_on_invalid_track(tmp_path: Path) -> None:
    midi_path = tmp_path / "strict_error.mid"
    track_bytes = bytes([0x00, 0x40])
    _write_midi(midi_path, track_bytes)

    with pytest.raises(ValueError):
        read_midi(str(midi_path), mode="strict")


def test_read_midi_exposes_tempo_changes(tmp_path: Path) -> None:
    midi_path = tmp_path / "tempo.mid"

    track = bytearray()
    track.extend(_vlq(0))
    track.extend([0xFF, 0x51, 0x03])
    track.extend(_tempo_payload(150))
    track.extend(_vlq(0))
    track.extend([0x90, 60, 0x40])
    track.extend(_vlq(240))
    track.extend([0xFF, 0x51, 0x03])
    track.extend(_tempo_payload(90))
    track.extend(_vlq(240))
    track.extend([0x80, 60, 0x00])
    track.extend(_vlq(0))
    track.extend([0xFF, 0x2F, 0x00])

    _write_midi(midi_path, bytes(track))

    song, report = read_midi(str(midi_path))

    assert report.mode == "strict"
    assert report.assumed_tempo_bpm == 150

    tempo_changes = get_tempo_changes(song.root)
    assert [
        (change.tick, round(change.tempo_bpm)) for change in tempo_changes
    ] == [(0, 150), (240, 90)]


def test_read_midi_reports_tempo_changes_from_fixture() -> None:
    midi_path = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "midi"
        / "tempo-changes.mid"
    )

    song, report = read_midi(str(midi_path))

    assert report.mode == "strict"
    assert report.assumed_tempo_bpm == pytest.approx(80.0)

    tempo_changes = get_tempo_changes(song.root)

    assert [change.tick for change in tempo_changes] == [0, 1920, 3840, 5760]
    assert [
        change.tempo_bpm for change in tempo_changes
    ] == pytest.approx([80.0, 40.0, 120.0, 220.0], abs=1e-3)
