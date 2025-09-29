from __future__ import annotations

from pathlib import Path

import json
import zipfile

import pytest

from ocarina_gui.conversion import ConversionResult
from ocarina_gui.pdf_export.types import PdfExportOptions
from ocarina_gui.settings import TransformSettings
from services.project_service import (
    LoadedProject,
    ProjectPersistenceError,
    ProjectService,
    ProjectSnapshot,
    PreviewPlaybackSnapshot,
)


def _create_conversion_artifacts(tmp_path: Path) -> ConversionResult:
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    xml_path = export_dir / "song.musicxml"
    xml_path.write_text("<arranged/>", encoding="utf-8")
    mxl_path = export_dir / "song.mxl"
    mxl_path.write_text("mxl-bytes", encoding="utf-8")
    midi_path = export_dir / "song.mid"
    midi_path.write_text("midi-bytes", encoding="utf-8")
    pdf_path = export_dir / "song-A4-portrait.pdf"
    pdf_path.write_text("pdf-bytes", encoding="utf-8")
    return ConversionResult(
        summary={"notes": 42},
        shifted_notes=3,
        used_pitches=["C4", "E4"],
        output_xml_path=str(xml_path),
        output_mxl_path=str(mxl_path),
        output_midi_path=str(midi_path),
        output_pdf_paths={"A4 Portrait": str(pdf_path)},
        output_folder=str(export_dir),
    )


def test_project_service_save_and_load_round_trip(tmp_path: Path) -> None:
    input_path = tmp_path / "input.musicxml"
    input_path.write_text("<score/>", encoding="utf-8")
    conversion = _create_conversion_artifacts(tmp_path)
    settings = TransformSettings(
        prefer_mode="auto",
        range_min="C4",
        range_max="C6",
        prefer_flats=True,
        collapse_chords=True,
        favor_lower=False,
        transpose_offset=2,
        instrument_id="alto",
    )
    pdf_options = PdfExportOptions.with_defaults(page_size="A4", orientation="landscape")
    snapshot = ProjectSnapshot(
        input_path=input_path,
        settings=settings,
        pdf_options=pdf_options,
        pitch_list=["C4", "E4"],
        pitch_entries=["C4", "E4"],
        status_message="Converted OK.",
        conversion=conversion,
        preview_settings={
            "arranged": PreviewPlaybackSnapshot(
                tempo_bpm=96.0,
                metronome_enabled=True,
                loop_enabled=True,
                loop_start_beat=1.5,
                loop_end_beat=3.0,
            )
        },
    )

    service = ProjectService()
    archive_path = tmp_path / "song.ocarina"
    saved_path = service.save(snapshot, archive_path)
    assert saved_path == archive_path

    extract_dir = tmp_path / "extracted"
    loaded = service.load(saved_path, extract_dir)
    assert isinstance(loaded, LoadedProject)
    assert loaded.archive_path == archive_path
    assert loaded.settings == settings
    assert loaded.pdf_options == pdf_options
    assert loaded.pitch_list == ["C4", "E4"]
    assert loaded.pitch_entries == ["C4", "E4"]
    assert loaded.status_message == "Converted OK."
    assert loaded.input_path.read_text(encoding="utf-8") == "<score/>"
    assert "arranged" in loaded.preview_settings
    restored_preview = loaded.preview_settings["arranged"]
    assert restored_preview.tempo_bpm == pytest.approx(96.0)
    assert restored_preview.metronome_enabled is True
    assert restored_preview.loop_enabled is True
    assert restored_preview.loop_start_beat == pytest.approx(1.5)
    assert restored_preview.loop_end_beat == pytest.approx(3.0)

    restored_conversion = loaded.conversion
    assert restored_conversion is not None
    assert restored_conversion.summary == conversion.summary
    assert restored_conversion.shifted_notes == conversion.shifted_notes
    assert restored_conversion.used_pitches == conversion.used_pitches
    assert Path(restored_conversion.output_xml_path).read_text(encoding="utf-8") == "<arranged/>"
    assert Path(restored_conversion.output_mxl_path).read_text(encoding="utf-8") == "mxl-bytes"
    assert Path(restored_conversion.output_midi_path).read_text(encoding="utf-8") == "midi-bytes"
    pdf_key = next(iter(restored_conversion.output_pdf_paths))
    assert pdf_key == "A4 Portrait"
    assert Path(restored_conversion.output_pdf_paths[pdf_key]).read_text(encoding="utf-8") == "pdf-bytes"
    assert Path(restored_conversion.output_folder).is_dir()


def test_project_service_requires_existing_input(tmp_path: Path) -> None:
    snapshot = ProjectSnapshot(
        input_path=tmp_path / "missing.musicxml",
        settings=TransformSettings(
            prefer_mode="auto",
            range_min="C4",
            range_max="C6",
            prefer_flats=True,
            collapse_chords=True,
            favor_lower=False,
        ),
        pdf_options=None,
        pitch_list=[],
        pitch_entries=[],
        status_message="",
        conversion=None,
        preview_settings={},
    )

    service = ProjectService()
    with pytest.raises(ProjectPersistenceError):
        service.save(snapshot, tmp_path / "invalid.ocarina")


def test_project_manifest_includes_manual_transpose_options(tmp_path: Path) -> None:
    input_path = tmp_path / "input.musicxml"
    input_path.write_text("<score/>", encoding="utf-8")
    snapshot = ProjectSnapshot(
        input_path=input_path,
        settings=TransformSettings(
            prefer_mode="auto",
            range_min="C4",
            range_max="C6",
            prefer_flats=True,
            collapse_chords=True,
            favor_lower=False,
            transpose_offset=-5,
            instrument_id="alto",
        ),
        pdf_options=None,
        pitch_list=[],
        pitch_entries=[],
        status_message="",
        conversion=None,
        preview_settings={
            "arranged": PreviewPlaybackSnapshot(loop_start_beat=0.0, loop_end_beat=4.0)
        },
    )

    service = ProjectService()
    archive_path = tmp_path / "song.ocarina"
    service.save(snapshot, archive_path)

    with zipfile.ZipFile(archive_path, "r") as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))

    assert manifest["settings"]["transpose_offset"] == -5
    assert manifest["preview_settings"]["arranged"]["loop_end"] == 4.0


def test_project_service_rejects_unsafe_archive_entries(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.ocarina"
    manifest = {
        "input": {"filename": "input.musicxml"},
        "settings": {},
    }
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest).encode("utf-8"))
        archive.writestr("../evil.txt", b"malicious")

    service = ProjectService()
    with pytest.raises(ProjectPersistenceError) as exc:
        service.load(archive_path, tmp_path / "extract")

    assert "unsafe" in str(exc.value)
    assert not (tmp_path / "evil.txt").exists()
