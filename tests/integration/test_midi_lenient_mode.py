"""Integration coverage for salvage/lenient MIDI decoding."""
from __future__ import annotations

from pathlib import Path

import pytest

from ocarina_tools import get_tempo_changes, read_midi

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "midi" / "adagio-2-100.mid"


def test_regression_fixture_requires_lenient_mode() -> None:
    with pytest.raises(ValueError):
        read_midi(str(FIXTURE), mode="strict")

    song, report = read_midi(str(FIXTURE))

    notes = list(song.root.findall("part/measure/note"))
    assert notes, "Lenient import should salvage at least one note"
    assert report.mode == "lenient"
    assert report.synthetic_eot_tracks == ()
    assert any("Ignored data byte" in issue.detail for issue in report.issues)
    tempo_changes = get_tempo_changes(song.root)
    assert tempo_changes
    assert tempo_changes[0].tempo_bpm == pytest.approx(report.assumed_tempo_bpm)

    song_lenient, report_lenient = read_midi(str(FIXTURE), mode="lenient")
    assert [n.tag for n in song_lenient.root.findall("part/measure/note")] == [
        n.tag for n in notes
    ]
    assert report_lenient.mode == "lenient"
    assert report_lenient.issues == report.issues
