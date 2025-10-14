from __future__ import annotations

from pathlib import Path

import pytest

from ocarina_gui.fingering import FingeringLibrary, InstrumentSpec
from ocarina_gui.pdf_export import export_arranged_pdf
from ocarina_gui.pdf_export.types import PdfExportOptions
from tests.helpers import make_linear_score, make_score_with_tempo_changes


def _install_test_instrument(monkeypatch: pytest.MonkeyPatch) -> None:
    instrument = InstrumentSpec.from_dict(
        {
            "id": "test",
            "name": "Test",
            "title": "Test Instrument",
            "canvas": {"width": 160, "height": 120},
            "holes": [
                {"id": "h1", "x": 40, "y": 40, "radius": 10},
                {"id": "h2", "x": 80, "y": 40, "radius": 10},
                {"id": "h3", "x": 120, "y": 40, "radius": 10},
            ],
            "note_order": ["C4", "D4", "E4"],
            "note_map": {
                "C4": [2, 2, 2],
                "D4": [2, 2, 0],
                "E4": [2, 0, 0],
            },
        }
    )
    monkeypatch.setattr("ocarina_gui.fingering._LIBRARY", FingeringLibrary([instrument]))


def test_export_arranged_pdf_writes_expected_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _tree, root = make_linear_score()
    _install_test_instrument(monkeypatch)

    pdf_path = tmp_path / "arranged.pdf"
    export_arranged_pdf(
        root,
        str(pdf_path),
        "A4",
        "portrait",
        4,
        prefer_flats=True,
        include_piano_roll=True,
        include_staff=True,
        include_text=True,
        include_fingerings=True,
    )

    data = pdf_path.read_bytes()
    assert data.startswith(b"%PDF")
    assert b"TunaEngine OcarinaArranger" in data
    assert b"https://github.com/TunaEngine/OcarinaArranger" in data
    assert b"/Subtype /Link" in data
    assert b"/C [0 0 1]" in data
    assert b"/URI (https://github.com/TunaEngine/OcarinaArranger)" in data
    assert b"Arranged piano roll" in data
    assert b"Quarter" not in data
    assert b"Quarter note" not in data
    assert b"Eighth" not in data
    for label in (b"h1", b"h2", b"h3"):
        assert label in data
    assert b"Arranged staff view" in data
    assert b"Used fingerings visuals" in data
    assert b"C4" in data


def test_export_arranged_pdf_includes_tempo_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _tree, root = make_score_with_tempo_changes()
    _install_test_instrument(monkeypatch)

    pdf_path = tmp_path / "tempo.pdf"
    export_arranged_pdf(
        root,
        str(pdf_path),
        "A4",
        "portrait",
        4,
        prefer_flats=True,
        include_piano_roll=True,
        include_staff=True,
        include_text=True,
        include_fingerings=False,
    )

    data = pdf_path.read_bytes()
    assert b"Tempo map" not in data
    assert b"= 180" in data
    assert b"= 120" in data
    assert b"= 210" in data


def test_export_arranged_pdf_skips_disabled_sections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _tree, root = make_linear_score()
    _install_test_instrument(monkeypatch)

    pdf_path = tmp_path / "arranged.pdf"
    export_arranged_pdf(
        root,
        str(pdf_path),
        "A4",
        "portrait",
        4,
        prefer_flats=True,
        include_piano_roll=False,
        include_staff=False,
        include_text=False,
        include_fingerings=True,
    )

    data = pdf_path.read_bytes()
    assert data.startswith(b"%PDF")
    assert b"Arranged piano roll" not in data
    assert b"Arranged staff view" not in data
    assert b"001   C4" not in data
    assert b"Used fingerings visuals" in data


def test_export_arranged_pdf_rejects_unknown_page_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _tree, root = make_linear_score()
    _install_test_instrument(monkeypatch)

    pdf_path = tmp_path / "invalid.pdf"
    with pytest.raises(ValueError):
        export_arranged_pdf(root, str(pdf_path), "Letter", "portrait", 4, prefer_flats=False)


@pytest.mark.parametrize(
    "orientation, expected_columns",
    (("portrait", 2), ("landscape", 4)),
)
def test_pdf_export_options_default_columns(orientation: str, expected_columns: int) -> None:
    options = PdfExportOptions(page_size="A6", orientation=orientation)
    assert options.columns == expected_columns


def test_pdf_export_options_custom_columns() -> None:
    options = PdfExportOptions(page_size="A4", orientation="portrait", columns=3)
    assert options.columns == 3


def test_pdf_export_options_enable_sections_by_default() -> None:
    options = PdfExportOptions(page_size="A6", orientation="portrait")
    assert options.include_piano_roll is True
    assert options.include_staff is True
    assert options.include_text is True
    assert options.include_fingerings is True
