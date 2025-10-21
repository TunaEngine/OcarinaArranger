from __future__ import annotations

import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from ocarina_gui.conversion import convert_score
from ocarina_gui.pdf_export.types import PdfExportOptions
from ocarina_gui.preview import build_preview_data
from ocarina_gui.settings import TransformSettings
from services.project_service import ProjectService, ProjectSnapshot


ASSET_DIR = Path(__file__).parent / "assets"
TWO_PART_SCORE = ASSET_DIR / "06_selected_part_filter_input.musicxml"


def _write_tree(tree, output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _write_placeholder(output_path: str, label: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(label, encoding="utf-8")


def test_selected_parts_flow_filters_previews_and_exports(tmp_path: Path) -> None:
    settings = TransformSettings(
        prefer_mode="auto",
        range_min="C4",
        range_max="C6",
        prefer_flats=False,
        collapse_chords=False,
        favor_lower=False,
        transpose_offset=0,
        instrument_id="",
        selected_part_ids=("P1",),
    )

    preview = build_preview_data(str(TWO_PART_SCORE), settings)

    original_midis = [event.midi for event in preview.original_events]
    arranged_midis = [event.midi for event in preview.arranged_events]
    assert original_midis == [60]
    assert len(arranged_midis) == 1

    output_xml_path = tmp_path / "selected.musicxml"
    pdf_options = PdfExportOptions.with_defaults()

    result = convert_score(
        str(TWO_PART_SCORE),
        str(output_xml_path),
        settings,
        export_musicxml=_write_tree,
        export_mxl=_write_tree,
        export_midi=lambda root, path, tempo_bpm=None, **_: _write_placeholder(path, "midi"),
        export_pdf=lambda root, path, page_size, orientation, columns, prefer_flats, **_: _write_placeholder(path, "pdf"),
        pdf_options=pdf_options,
    )

    exported_root = ET.parse(result.output_xml_path).getroot()
    kept_part_ids = [part.get("id") for part in exported_root.findall("part")]
    part_list = exported_root.find("part-list")
    assert part_list is not None
    kept_score_part_ids = [
        score_part.get("id") for score_part in part_list.findall("score-part")
    ]
    assert kept_part_ids == ["P1"]
    assert kept_score_part_ids == ["P1"]

    project = ProjectService()
    snapshot = ProjectSnapshot(
        input_path=TWO_PART_SCORE,
        settings=settings,
        pdf_options=pdf_options,
        pitch_list=[],
        pitch_entries=[],
        status_message="Ready.",
        conversion=result,
        preview_settings={},
        grace_settings=settings.grace_settings,
        subhole_settings=settings.subhole_settings,
    )
    archive_path = tmp_path / "selected.ocarina"
    saved = project.save(snapshot, archive_path)

    with zipfile.ZipFile(saved, "r") as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))

    assert manifest["settings"]["selected_part_ids"] == ["P1"]
