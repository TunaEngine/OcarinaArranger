from __future__ import annotations

from pathlib import Path

import pytest

from ocarina_gui.conversion import convert_score, derive_export_folder
from ocarina_gui.settings import TransformSettings
from ocarina_gui.pdf_export.types import PdfExportOptions


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
    )


@pytest.fixture(autouse=True)
def _stub_transform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ocarina_gui.conversion.load_score",
        lambda path: (object(), object()),
    )
    monkeypatch.setattr(
        "ocarina_gui.conversion.transform_to_ocarina",
        lambda *args, **kwargs: {"range_names": {"min": "C4", "max": "C6"}},
    )
    monkeypatch.setattr(
        "ocarina_gui.conversion.collect_used_pitches",
        lambda root, flats: ["C4"],
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
