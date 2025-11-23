from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from ocarina_gui.conversion import convert_score, derive_export_folder
from ocarina_gui.settings import TransformSettings
from ocarina_gui.pdf_export.types import PdfExportOptions
from ocarina_tools import NoteEvent, ScoreLoadResult, filter_parts


def test_derive_export_folder_returns_base_name(tmp_path: Path) -> None:
    base = tmp_path / "output.musicxml"
    folder = derive_export_folder(str(base))
    assert folder == str(tmp_path / "output")


def test_derive_export_folder_appends_index_when_exists(tmp_path: Path) -> None:
    existing = tmp_path / "output"
    existing.mkdir()
    folder = derive_export_folder(str(tmp_path / "output.musicxml"))
    assert folder == str(tmp_path / "output (2)")


def _fake_settings() -> TransformSettings:
    return TransformSettings(
        prefer_mode="auto",
        range_min="C4",
        range_max="C6",
        prefer_flats=True,
        collapse_chords=True,
        favor_lower=False,
        transpose_offset=0,
        instrument_id="",
        selected_part_ids=(),
    )


@pytest.fixture(autouse=True)
def _stub_transform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ocarina_gui.conversion.load_score",
        lambda path, *, midi_mode="auto": ScoreLoadResult(
            tree=object(),
            root=object(),
        ),
    )
    monkeypatch.setattr(
        "ocarina_gui.conversion.transform_to_ocarina",
        lambda *args, **kwargs: {"range_names": {"min": "C4", "max": "C6"}},
    )
    monkeypatch.setattr(
        "ocarina_gui.conversion.collect_used_pitches",
        lambda root, flats: ["C4"],
    )
    monkeypatch.setattr(
        "ocarina_gui.conversion.get_note_events",
        lambda _root, *, grace_settings=None: ([], 480),
    )
    monkeypatch.setattr(
        "ocarina_gui.conversion.get_time_signature",
        lambda _root: (4, 4),
    )


def test_convert_score_exports_into_unique_folder(tmp_path: Path) -> None:
    written: dict[str, str] = {}

    def _record(path_key: str):
        def _recorder(_tree: object, path: str, *args, **kwargs) -> None:
            written[path_key] = path
            Path(path).write_text(path_key)

        return _recorder

    result = convert_score(
        input_path="ignored",
        output_xml_path=str(tmp_path / "song.musicxml"),
        settings=_fake_settings(),
        export_musicxml=_record("xml"),
        export_mxl=_record("mxl"),
        export_midi=_record("mid"),
        export_pdf=_record("pdf"),
        pdf_options=PdfExportOptions.with_defaults(),
    )

    expected_folder = tmp_path / "song"
    assert expected_folder.exists()
    assert Path(written["xml"]).parent == expected_folder
    assert Path(written["mxl"]).parent == expected_folder
    assert Path(written["mid"]).parent == expected_folder
    assert result.output_xml_path == written["xml"]
    assert result.output_mxl_path == written["mxl"]
    assert result.output_midi_path == written["mid"]
    assert list(result.output_pdf_paths.values())[0].startswith(str(expected_folder))
    assert result.output_folder == str(expected_folder)


def test_convert_score_increments_export_folder(tmp_path: Path) -> None:
    (tmp_path / "song").mkdir()

    result = convert_score(
        input_path="ignored",
        output_xml_path=str(tmp_path / "song.musicxml"),
        settings=_fake_settings(),
        export_musicxml=lambda *_args, **_kwargs: None,
        export_mxl=lambda *_args, **_kwargs: None,
        export_midi=lambda *_args, **_kwargs: None,
        export_pdf=lambda *_args, **_kwargs: None,
        pdf_options=PdfExportOptions.with_defaults(),
    )

    assert result.output_folder == str(tmp_path / "song (2)")


def test_convert_score_respects_selected_parts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
            ET.SubElement(pitch, "step").text = "D"
            ET.SubElement(pitch, "octave").text = "5"
        return root

    base_root = _make_score_root()
    expected_note_count = 0
    for part in base_root.findall("part"):
        if part.get("id") != "P2":
            continue
        for measure in part.findall("measure"):
            expected_note_count += len(measure.findall("note"))

    exporters_parts: dict[str, list[str]] = {}
    summary: dict[str, object] = {"expected_count": expected_note_count}

    def fake_load_score(_path: str, *, midi_mode: str = "auto"):
        root = _make_score_root()
        return ScoreLoadResult(tree=ET.ElementTree(root), root=root)

    def fake_transform(tree, root, **kwargs):
        selected = kwargs.get("selected_part_ids")
        assert selected == ("P2",)
        if selected:
            filter_parts(root, selected)
        part_ids = [part.get("id") for part in root.findall("part")]
        summary["transform_part_ids"] = part_ids
        summary["arranged_count"] = sum(
            len(measure.findall("note"))
            for part in root.findall("part")
            for measure in part.findall("measure")
        )
        return {"range_names": {"min": "C4", "max": "C6"}}

    def fake_collect_used_pitches(root, flats: bool):
        part_ids = [part.get("id") for part in root.findall("part")]
        summary["collect_part_ids"] = part_ids
        return ["P2"]

    def _record_tree(label: str):
        def _export(tree, path, *args, **kwargs):
            exporters_parts[label] = [
                part.get("id") for part in tree.getroot().findall("part")
            ]
            Path(path).write_text(label, encoding="utf-8")

        return _export

    def _record_root(label: str):
        def _export(root, path, *args, **kwargs):
            exporters_parts[label] = [part.get("id") for part in root.findall("part")]
            Path(path).write_text(label, encoding="utf-8")

        return _export

    monkeypatch.setattr("ocarina_gui.conversion.load_score", fake_load_score)
    monkeypatch.setattr("ocarina_gui.conversion.transform_to_ocarina", fake_transform)
    monkeypatch.setattr("ocarina_gui.conversion.collect_used_pitches", fake_collect_used_pitches)
    monkeypatch.setattr(
        "ocarina_gui.conversion.favor_lower_register", lambda *_args, **_kwargs: 0
    )

    settings = TransformSettings(
        prefer_mode="auto",
        range_min="C4",
        range_max="C6",
        prefer_flats=True,
        collapse_chords=True,
        favor_lower=False,
        transpose_offset=0,
        instrument_id="",
        selected_part_ids=("P2",),
    )

    result = convert_score(
        input_path="ignored",
        output_xml_path=str(tmp_path / "subset.musicxml"),
        settings=settings,
        export_musicxml=_record_tree("xml"),
        export_mxl=_record_tree("mxl"),
        export_midi=_record_root("mid"),
        export_pdf=_record_root("pdf"),
        pdf_options=PdfExportOptions.with_defaults(),
    )

    assert summary["transform_part_ids"] == ["P2"]
    assert summary["arranged_count"] == summary["expected_count"]
    assert summary["collect_part_ids"] == ["P2"]
    for label in ("xml", "mxl", "mid", "pdf"):
        assert exporters_parts[label] == ["P2"]
    assert result.used_pitches == ["P2"]


def test_convert_score_trims_arranged_events_for_pdf_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    root = ET.Element("score-partwise")

    def fake_load_score(_path: str, *, midi_mode: str = "auto"):
        return ScoreLoadResult(tree=ET.ElementTree(root), root=root)

    def fake_export_tree(_tree: object, path: str, *args, **kwargs):
        Path(path).write_text("tree", encoding="utf-8")

    def fake_export_root(_root: object, path: str, *args, **kwargs):
        Path(path).write_text("root", encoding="utf-8")

    def fake_transform(*_args, **_kwargs):
        return {"range_names": {"min": "C4", "max": "C6"}}

    def fake_get_note_events(_root: object, *, grace_settings=None):
        return ([NoteEvent(240, 120, 60, 0), NoteEvent(360, 120, 64, 0)], 960)

    def fake_export_pdf(
        _root: object,
        _path: str,
        _page_size: str,
        _orientation: str,
        _columns: int,
        _prefer_flats: bool,
        *,
        events,
        pulses_per_quarter,
        beats,
        beat_type,
        **_kwargs,
    ) -> None:
        captured["events"] = events
        captured["ppq"] = pulses_per_quarter
        captured["beats"] = beats
        captured["beat_type"] = beat_type
        Path(_path).write_text("pdf", encoding="utf-8")

    monkeypatch.setattr("ocarina_gui.conversion.load_score", fake_load_score)
    monkeypatch.setattr("ocarina_gui.conversion.transform_to_ocarina", fake_transform)
    monkeypatch.setattr("ocarina_gui.conversion.collect_used_pitches", lambda *_args, **_kwargs: [])
    monkeypatch.setattr("ocarina_gui.conversion.favor_lower_register", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr("ocarina_gui.conversion.get_note_events", fake_get_note_events)
    monkeypatch.setattr("ocarina_gui.conversion.get_time_signature", lambda _root: (3, 8))

    result = convert_score(
        input_path="ignored",
        output_xml_path=str(tmp_path / "song.musicxml"),
        settings=_fake_settings(),
        export_musicxml=fake_export_tree,
        export_mxl=fake_export_tree,
        export_midi=fake_export_root,
        export_pdf=fake_export_pdf,
        pdf_options=PdfExportOptions.with_defaults(),
    )

    assert result.output_pdf_paths
    trimmed_events = captured.get("events", [])
    assert [event.onset for event in trimmed_events] == [0, 120]
    assert captured["ppq"] == 960
    assert captured["beats"] == 3
    assert captured["beat_type"] == 8


def test_convert_score_uses_supplied_arranged_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    root = ET.Element("score-partwise")

    def fake_load_score(_path: str, *, midi_mode: str = "auto"):
        return ScoreLoadResult(tree=ET.ElementTree(root), root=root)

    def fake_export_tree(_tree: object, path: str, *args, **kwargs):
        Path(path).write_text("tree", encoding="utf-8")

    def fake_export_root(_root: object, path: str, *args, **kwargs):
        Path(path).write_text("root", encoding="utf-8")

    def fake_transform(*_args, **_kwargs):
        return {"range_names": {"min": "C4", "max": "C6"}}

    def fake_export_pdf(
        _root: object,
        _path: str,
        _page_size: str,
        _orientation: str,
        _columns: int,
        _prefer_flats: bool,
        *,
        events,
        pulses_per_quarter,
        beats,
        beat_type,
        **_kwargs,
    ) -> None:
        captured["events"] = events
        captured["ppq"] = pulses_per_quarter
        captured["beats"] = beats
        captured["beat_type"] = beat_type
        Path(_path).write_text("pdf", encoding="utf-8")

    monkeypatch.setattr("ocarina_gui.conversion.load_score", fake_load_score)
    monkeypatch.setattr("ocarina_gui.conversion.transform_to_ocarina", fake_transform)
    monkeypatch.setattr(
        "ocarina_gui.conversion.collect_used_pitches", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr("ocarina_gui.conversion.favor_lower_register", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(
        "ocarina_gui.conversion.get_note_events",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("get_note_events should not be called")
        ),
    )
    monkeypatch.setattr("ocarina_gui.conversion.get_time_signature", lambda _root: (4, 4))

    arranged_events = (NoteEvent(0, 120, 64, 0),)

    result = convert_score(
        input_path="ignored",
        output_xml_path=str(tmp_path / "song.musicxml"),
        settings=_fake_settings(),
        export_musicxml=fake_export_tree,
        export_mxl=fake_export_tree,
        export_midi=fake_export_root,
        export_pdf=fake_export_pdf,
        pdf_options=PdfExportOptions.with_defaults(),
        arranged_events=arranged_events,
        arranged_pulses_per_quarter=720,
    )

    assert result.output_pdf_paths
    events = captured.get("events", [])
    assert [event.midi for event in events] == [64]
    assert captured["ppq"] == 720
    assert captured["beats"] == 4
    assert captured["beat_type"] == 4
