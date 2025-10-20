from __future__ import annotations

from pathlib import Path

import json
import zipfile

import pytest

from ocarina_gui.conversion import ConversionResult
from ocarina_gui.pdf_export.types import PdfExportOptions
from ocarina_gui.settings import GraceTransformSettings, TransformSettings
from services.project_service import (
    LoadedProject,
    ProjectPersistenceError,
    ProjectService,
    ProjectSnapshot,
    PreviewPlaybackSnapshot,
)
from viewmodels.arranger_models import ArrangerBudgetSettings, ArrangerGPSettings


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
    grace_settings = GraceTransformSettings(
        policy="steal",
        fractions=(0.2, 0.1, 0.05),
        max_chain=2,
        anchor_min_fraction=0.4,
        fold_out_of_range=False,
        drop_out_of_range=False,
        slow_tempo_bpm=72.0,
        fast_tempo_bpm=180.0,
        grace_bonus=0.6,
    )
    settings = TransformSettings(
        prefer_mode="auto",
        range_min="C4",
        range_max="C6",
        prefer_flats=True,
        collapse_chords=True,
        favor_lower=False,
        transpose_offset=2,
        instrument_id="alto",
        selected_part_ids=("P1",),
        grace_settings=grace_settings,
    )
    pdf_options = PdfExportOptions.with_defaults(page_size="A4", orientation="landscape")
    arranger_budgets = ArrangerBudgetSettings(
        max_octave_edits=2,
        max_rhythm_edits=3,
        max_substitutions=4,
        max_steps_per_span=5,
    )
    arranger_gp_settings = ArrangerGPSettings(
        generations=7,
        population_size=18,
        time_budget_seconds=12.5,
        archive_size=6,
        random_program_count=5,
        crossover_rate=0.7,
        mutation_rate=0.3,
        log_best_programs=4,
        random_seed=42,
        playability_weight=1.1,
        fidelity_weight=1.9,
        tessitura_weight=1.2,
        program_size_weight=1.3,
        contour_weight=0.4,
        lcs_weight=0.6,
        pitch_weight=0.5,
        fidelity_priority_weight=4.8,
        range_clamp_penalty=820.0,
        range_clamp_melody_bias=1.4,
        melody_shift_weight=2.6,
        rhythm_simplify_weight=1.2,
        apply_program_preference="session_winner",
    )
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
                volume=0.65,
            )
        },
        arranger_mode="best_effort",
        arranger_strategy="starred-best",
        starred_instrument_ids=("alto", "tenor"),
        arranger_dp_slack_enabled=False,
        arranger_budgets=arranger_budgets,
        arranger_gp_settings=arranger_gp_settings,
        grace_settings=settings.grace_settings,
    )

    service = ProjectService()
    archive_path = tmp_path / "song.ocarina"
    saved_path = service.save(snapshot, archive_path)
    assert saved_path == archive_path

    with zipfile.ZipFile(saved_path, "r") as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))

    assert manifest["settings"]["selected_part_ids"] == ["P1"]
    arranger_manifest = manifest.get("arranger", {})
    assert arranger_manifest["mode"] == "best_effort"
    assert arranger_manifest["strategy"] == "starred-best"
    assert arranger_manifest["starred_instrument_ids"] == ["alto", "tenor"]
    assert arranger_manifest["dp_slack_enabled"] is False
    assert arranger_manifest["budgets"] == {
        "max_octave_edits": 2,
        "max_rhythm_edits": 3,
        "max_substitutions": 4,
        "max_steps_per_span": 5,
    }
    assert arranger_manifest["gp_settings"]["generations"] == 7
    assert arranger_manifest["gp_settings"]["population_size"] == 18
    assert arranger_manifest["gp_settings"]["time_budget_seconds"] == pytest.approx(12.5)
    assert arranger_manifest["gp_settings"]["fidelity_priority_weight"] == pytest.approx(4.8)
    assert arranger_manifest["gp_settings"]["range_clamp_penalty"] == pytest.approx(820.0)
    assert (
        arranger_manifest["gp_settings"]["range_clamp_melody_bias"]
        == pytest.approx(1.4)
    )
    assert arranger_manifest["gp_settings"]["melody_shift_weight"] == pytest.approx(2.6)
    assert (
        arranger_manifest["gp_settings"]["rhythm_simplify_weight"]
        == pytest.approx(1.2)
    )
    assert (
        arranger_manifest["gp_settings"]["apply_program_preference"]
        == "session_winner"
    )

    grace_manifest = manifest["settings"]["grace_settings"]
    assert grace_manifest["policy"] == "steal"
    assert grace_manifest["max_chain"] == 2
    assert grace_manifest["fold_out_of_range"] is False
    assert grace_manifest["drop_out_of_range"] is False
    assert grace_manifest["fractions"] == pytest.approx([0.2, 0.1, 0.05])
    assert grace_manifest["anchor_min_fraction"] == pytest.approx(0.4)
    assert grace_manifest["slow_tempo_bpm"] == pytest.approx(72.0)
    assert grace_manifest["fast_tempo_bpm"] == pytest.approx(180.0)
    assert grace_manifest["grace_bonus"] == pytest.approx(0.6)

    preview_manifest = manifest["preview_settings"]["arranged"]
    assert preview_manifest["tempo_bpm"] == pytest.approx(96.0)
    assert preview_manifest["metronome_enabled"] is True
    assert preview_manifest["loop_enabled"] is True
    assert preview_manifest["loop_start"] == pytest.approx(1.5)
    assert preview_manifest["loop_end"] == pytest.approx(3.0)
    assert preview_manifest["volume"] == pytest.approx(0.65)

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
    assert restored_preview.volume == pytest.approx(0.65)

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
    assert loaded.arranger_mode == "best_effort"
    assert loaded.arranger_strategy == "starred-best"
    assert loaded.starred_instrument_ids == ("alto", "tenor")
    assert loaded.arranger_dp_slack_enabled is False
    assert loaded.arranger_budgets == arranger_budgets.normalized()
    assert loaded.arranger_gp_settings == arranger_gp_settings.normalized()
    assert loaded.grace_settings == settings.grace_settings.normalized()


def test_project_service_requires_existing_input(tmp_path: Path) -> None:
    settings = TransformSettings(
        prefer_mode="auto",
        range_min="C4",
        range_max="C6",
        prefer_flats=True,
        collapse_chords=True,
        favor_lower=False,
        selected_part_ids=(),
    )
    snapshot = ProjectSnapshot(
        input_path=tmp_path / "missing.musicxml",
        settings=settings,
        pdf_options=None,
        pitch_list=[],
        pitch_entries=[],
        status_message="",
        conversion=None,
        preview_settings={},
        grace_settings=settings.grace_settings,
    )

    service = ProjectService()
    with pytest.raises(ProjectPersistenceError):
        service.save(snapshot, tmp_path / "invalid.ocarina")


def test_project_manifest_includes_manual_transpose_options(tmp_path: Path) -> None:
    input_path = tmp_path / "input.musicxml"
    input_path.write_text("<score/>", encoding="utf-8")
    manual_settings = TransformSettings(
        prefer_mode="auto",
        range_min="C4",
        range_max="C6",
        prefer_flats=True,
        collapse_chords=True,
        favor_lower=False,
        transpose_offset=-5,
        instrument_id="alto",
        selected_part_ids=(),
    )
    snapshot = ProjectSnapshot(
        input_path=input_path,
        settings=manual_settings,
        pdf_options=None,
        pitch_list=[],
        pitch_entries=[],
        status_message="",
        conversion=None,
        preview_settings={
            "arranged": PreviewPlaybackSnapshot(loop_start_beat=0.0, loop_end_beat=4.0)
        },
        grace_settings=manual_settings.grace_settings,
    )

    service = ProjectService()
    archive_path = tmp_path / "song.ocarina"
    service.save(snapshot, archive_path)

    with zipfile.ZipFile(archive_path, "r") as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))

    assert manifest["settings"]["transpose_offset"] == -5
    assert manifest["settings"]["selected_part_ids"] == []
    assert manifest["preview_settings"]["arranged"]["loop_end"] == 4.0


def test_project_service_loads_missing_selected_parts_as_empty(tmp_path: Path) -> None:
    archive_path = tmp_path / "legacy.ocarina"
    manifest = {
        "input": {"filename": "song.musicxml"},
        "settings": {
            "prefer_mode": "auto",
            "range_min": "",
            "range_max": "",
            "prefer_flats": True,
            "collapse_chords": True,
            "favor_lower": False,
            "transpose_offset": 0,
            "instrument_id": "",
        },
    }

    original_dir = tmp_path / "original"
    original_dir.mkdir()
    original_path = original_dir / "song.musicxml"
    original_path.write_text("<score/>", encoding="utf-8")

    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest).encode("utf-8"))
        archive.write(original_path, arcname="original/song.musicxml")

    service = ProjectService()
    loaded = service.load(archive_path, tmp_path / "extract")

    assert loaded.settings.selected_part_ids == ()


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
