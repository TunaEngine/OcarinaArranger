"""Tests for ``ocarina_gui.preview`` helper functions."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import ocarina_gui.preview as preview
from ocarina_gui.settings import TransformSettings
from ocarina_tools import NoteEvent


def test_build_preview_data_loads_score_once(monkeypatch) -> None:
    calls: list[str] = []

    def fake_load(path: str):
        calls.append(path)
        root = ET.Element("score")
        return ET.ElementTree(root), root

    monkeypatch.setattr(preview, "load_score", fake_load)
    monkeypatch.setattr(
        preview,
        "get_note_events",
        lambda _root: ([NoteEvent(0, 1, 60, 79)], 480),
    )
    monkeypatch.setattr(preview, "get_time_signature", lambda _root: (4, 4))
    monkeypatch.setattr(preview, "transform_to_ocarina", lambda *args, **kwargs: None)
    monkeypatch.setattr(preview, "favor_lower_register", lambda _root, range_min=None: None)

    settings = TransformSettings(
        prefer_mode="auto",
        range_min="A4",
        range_max="F6",
        prefer_flats=True,
        collapse_chords=True,
        favor_lower=False,
    )
    data = preview.build_preview_data("dummy-path.musicxml", settings)

    assert len(calls) == 1
    assert data.original_events == [NoteEvent(0, 1, 60, 79)]
    assert data.arranged_events == [NoteEvent(0, 1, 60, 79)]
    assert data.pulses_per_quarter == 480
    assert data.beats == 4
    assert data.beat_type == 4


def test_build_preview_data_trims_arranged_leading_silence(monkeypatch) -> None:
    call_count = 0

    def fake_get_note_events(_root: ET.Element):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ([NoteEvent(0, 1, 60, 79)], 480)
        return ([NoteEvent(240, 2, 65, 79), NoteEvent(480, 2, 67, 79)], 480)

    monkeypatch.setattr(preview, "load_score", lambda _path: (ET.ElementTree(ET.Element("score")), ET.Element("score")))
    monkeypatch.setattr(preview, "get_note_events", fake_get_note_events)
    monkeypatch.setattr(preview, "get_time_signature", lambda _root: (4, 4))
    monkeypatch.setattr(preview, "transform_to_ocarina", lambda *args, **kwargs: None)
    monkeypatch.setattr(preview, "favor_lower_register", lambda _root, range_min=None: None)
    settings = TransformSettings(
        prefer_mode="auto",
        range_min="A4",
        range_max="F6",
        prefer_flats=True,
        collapse_chords=True,
        favor_lower=False,
    )

    data = preview.build_preview_data("dummy-path.musicxml", settings)

    assert data.arranged_events == [
        NoteEvent(0, 2, 65, 79),
        NoteEvent(240, 2, 67, 79),
    ]
