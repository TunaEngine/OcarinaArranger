"""Fixtures for viewmodel tests."""

from __future__ import annotations

from pathlib import Path
from typing import List

from tests.helpers import require_ttkbootstrap

require_ttkbootstrap()

import pytest

from ocarina_gui.conversion import ConversionResult
from ocarina_gui.fingering import InstrumentSpec
from ocarina_gui.preview import PreviewData


@pytest.fixture
def preview_data() -> PreviewData:
    return PreviewData(
        original_events=[],
        arranged_events=[],
        pulses_per_quarter=480,
        beats=4,
        beat_type=4,
        original_range=(60, 72),
        arranged_range=(60, 72),
        tempo_bpm=120,
    )


@pytest.fixture
def conversion_result(tmp_path: Path) -> ConversionResult:
    return ConversionResult(
        summary={"range_names": {"min": "C4", "max": "G5"}},
        shifted_notes=0,
        used_pitches=["C4", "D4"],
        output_xml_path=str(tmp_path / "out.musicxml"),
        output_mxl_path=str(tmp_path / "out.mxl"),
        output_midi_path=str(tmp_path / "out.mid"),
        output_pdf_paths={
            "A4 Portrait": str(tmp_path / "out-A4-portrait.pdf"),
        },
        output_folder=str(tmp_path),
    )


@pytest.fixture
def layout_editor_specs() -> List[InstrumentSpec]:
    """Synthetic instrument specifications for layout editor tests."""

    soprano = InstrumentSpec.from_dict(
        {
            "id": "soprano_c",
            "name": "Soprano C",
            "title": "Soprano C",
            "canvas": {"width": 240, "height": 120},
            "style": {
                "background_color": "#ffeecc",
                "outline_color": "#552200",
                "outline_width": 3.0,
                "outline_smooth": True,
                "outline_spline_steps": 32,
                "hole_outline_color": "#331100",
                "covered_fill_color": "#995500",
            },
            "outline": {
                "points": [[20, 20], [220, 20], [200, 80], [40, 90]],
                "closed": True,
            },
            "holes": [
                {"id": "LH1", "x": 60.0, "y": 60.0, "radius": 7.0},
                {"id": "LH2", "x": 100.0, "y": 55.0, "radius": 7.5},
            ],
            "windways": [
                {"id": "Chamber A", "x": 40.0, "y": 28.0, "width": 18.0, "height": 10.0}
            ],
            "note_order": ["C5", "Db5", "D5", "E5"],
            "note_map": {
                "C5": [1, 1, 2],
                "Db5": [1, 1, 2],
                "D5": [1, 0, 2],
                "E5": [0, 0, 2],
            },
            "preferred_range": {"min": "C5", "max": "E5"},
            "candidate_range": {"min": "A#4", "max": "G6"},
        }
    )

    alto = InstrumentSpec.from_dict(
        {
            "id": "alto_f",
            "name": "Alto F",
            "title": "Alto F",
            "canvas": {"width": 260, "height": 140},
            "style": {
                "background_color": "#f0f0ff",
                "outline_color": "#000044",
                "outline_width": 2.5,
                "outline_smooth": False,
                "outline_spline_steps": 24,
                "hole_outline_color": "#111166",
                "covered_fill_color": "#333388",
            },
            "outline": None,
            "holes": [
                {"id": "RH1", "x": 70.0, "y": 85.0, "radius": 8.0},
                {"id": "RH2", "x": 110.0, "y": 80.0, "radius": 8.5},
                {"id": "RH3", "x": 150.0, "y": 78.0, "radius": 8.0},
            ],
            "windways": [
                {"id": "Chamber B", "x": 60.0, "y": 32.0, "width": 20.0, "height": 12.0}
            ],
            "note_order": ["F4", "G4", "A4", "Bb4"],
            "note_map": {
                "F4": [1, 1, 1, 2],
                "G4": [1, 1, 0, 2],
                "A4": [1, 0, 0, 2],
                "Bb4": [0, 0, 0, 2],
            },
            "preferred_range": {"min": "F4", "max": "Bb4"},
            "candidate_range": {"min": "E4", "max": "D6"},
        }
    )

    return [soprano, alto]

