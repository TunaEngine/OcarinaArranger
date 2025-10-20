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
        lambda _root, **_kwargs: ([NoteEvent(0, 1, 60, 79)], 480),
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
        selected_part_ids=(),
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

    def fake_get_note_events(_root: ET.Element, **_kwargs):
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
        selected_part_ids=(),
    )

    data = preview.build_preview_data("dummy-path.musicxml", settings)

    assert data.arranged_events == [
        NoteEvent(0, 2, 65, 79),
        NoteEvent(240, 2, 67, 79),
    ]


def test_build_preview_respects_selected_parts(monkeypatch) -> None:
    def _make_score_root() -> ET.Element:
        root = ET.Element("score-partwise")
        part_list = ET.SubElement(root, "part-list")
        for part_id in ("P1", "P2"):
            score_part = ET.SubElement(part_list, "score-part", id=part_id)
            ET.SubElement(score_part, "part-name").text = f"Part {part_id}"
        for part_id in ("P1", "P2"):
            part = ET.SubElement(root, "part", id=part_id)
            measure = ET.SubElement(part, "measure", number="1")
            note = ET.SubElement(measure, "note")
            ET.SubElement(note, "duration").text = "1"
            ET.SubElement(note, "voice").text = "1"
            ET.SubElement(note, "type").text = "quarter"
            pitch = ET.SubElement(note, "pitch")
            ET.SubElement(pitch, "step").text = "C"
            ET.SubElement(pitch, "octave").text = "4"
        return root

    def fake_load_score(_path: str):
        root = _make_score_root()
        return ET.ElementTree(root), root

    def fake_get_note_events(root: ET.Element, **_kwargs):
        midi_lookup = {"P1": 60, "P2": 72}
        events = []
        for index, part in enumerate(root.findall("part")):
            part_id = part.get("id", "")
            midi = midi_lookup.get(part_id, 84)
            events.append(NoteEvent(index * 120, 120, midi, 80))
        return events, 480

    monkeypatch.setattr(preview, "load_score", fake_load_score)
    monkeypatch.setattr(preview, "get_note_events", fake_get_note_events)
    monkeypatch.setattr(preview, "get_time_signature", lambda _root: (4, 4))
    monkeypatch.setattr(preview, "detect_tempo_bpm", lambda _root: 120)
    monkeypatch.setattr(preview, "get_tempo_changes", lambda _root, default_bpm: [])

    def fake_transform(tree, root, **kwargs):
        part_ids = [part.get("id") for part in root.findall("part")]
        assert part_ids == ["P2"]
        return {}

    monkeypatch.setattr(preview, "transform_to_ocarina", fake_transform)
    monkeypatch.setattr(preview, "favor_lower_register", lambda *_args, **_kwargs: None)

    settings = TransformSettings(
        prefer_mode="auto",
        range_min="A4",
        range_max="F6",
        prefer_flats=True,
        collapse_chords=True,
        favor_lower=False,
        selected_part_ids=("P2",),
    )

    data = preview.build_preview_data("subset.musicxml", settings)

    assert [event.midi for event in data.original_events] == [72]
    assert [event.midi for event in data.arranged_events] == [72]
