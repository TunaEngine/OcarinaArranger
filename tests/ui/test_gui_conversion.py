from __future__ import annotations

import os
from tkinter import filedialog, messagebox

from helpers import make_linear_score
from ocarina_gui.conversion import ConversionResult
from ocarina_gui.pdf_export.types import PdfExportOptions
from ocarina_tools import collect_used_pitches, load_score, transform_to_ocarina


def _write_score(tmp_path, tree):
    path = tmp_path / "sample.musicxml"
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path


def test_convert_exports_files_and_reports_success(gui_app, tmp_path, monkeypatch):
    tree, _ = make_linear_score()
    input_path = _write_score(tmp_path, tree)
    gui_app.input_path.set(str(input_path))

    saved = {}
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kwargs: str(tmp_path / "converted.musicxml"))

    monkeypatch.setattr(
        "ui.main_window.preview.commands.ask_pdf_export_options",
        lambda *_args, **_kwargs: PdfExportOptions.with_defaults(),
    )

    exp_tree, exp_root = load_score(str(input_path))
    transform_to_ocarina(
        exp_tree,
        exp_root,
        prefer_mode=gui_app.prefer_mode.get(),
        range_min=gui_app.range_min.get(),
        range_max=gui_app.range_max.get(),
        prefer_flats=gui_app.prefer_flats.get(),
        collapse_chords=gui_app.collapse_chords.get(),
        transpose_offset=gui_app.transpose_offset.get(),
    )
    expected_pitches = collect_used_pitches(exp_root, flats=gui_app.prefer_flats.get())

    opened = []
    monkeypatch.setattr(gui_app, "_open_path", lambda path: opened.append(path))

    def _fake_convert(self, path: str, output_xml_path: str, settings, pdf_options):
        export_folder = os.path.splitext(output_xml_path)[0]
        saved["folder"] = export_folder
        saved["xml"] = os.path.join(export_folder, os.path.basename(output_xml_path))
        saved["mxl"] = os.path.join(export_folder, os.path.basename(output_xml_path).replace(".musicxml", ".mxl"))
        saved["mid"] = os.path.join(export_folder, os.path.basename(output_xml_path).replace(".musicxml", ".mid"))
        saved["pdf"] = {
            "A4 Portrait": os.path.join(
                export_folder,
                os.path.basename(output_xml_path).replace(".musicxml", "-A4-portrait.pdf"),
            ),
        }
        return ConversionResult(
            summary={"range_names": {"min": "C4", "max": "G5"}},
            shifted_notes=0,
            used_pitches=expected_pitches,
            output_xml_path=saved["xml"],
            output_mxl_path=saved["mxl"],
            output_midi_path=saved["mid"],
            output_pdf_paths=saved["pdf"],
            output_folder=export_folder,
        )

    monkeypatch.setattr(type(gui_app._viewmodel._score_service), "convert", _fake_convert)

    infos = []
    errors = []
    monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: infos.append((args, kwargs)))
    monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: errors.append((args, kwargs)))

    gui_app.convert()
    gui_app.update_idletasks()

    assert not errors
    expected_folder = str(tmp_path / "converted")
    assert saved["folder"] == expected_folder
    assert saved["xml"] == str(tmp_path / "converted" / "converted.musicxml")
    assert saved["mxl"] == str(tmp_path / "converted" / "converted.mxl")
    assert saved["mid"] == str(tmp_path / "converted" / "converted.mid")
    assert saved["pdf"]["A4 Portrait"] == str(tmp_path / "converted" / "converted-A4-portrait.pdf")
    assert gui_app.status.get() == "Converted OK."
    assert gui_app.pitch_list == expected_pitches
    assert opened == [expected_folder]
    assert infos
    assert len(infos) == 1
    title, message = infos[0][0]
    assert title == "Success"
    assert "converted" in message
    assert "converted.musicxml" in message
    assert "converted.mxl" in message
    assert "converted.mid" in message
    assert "converted-A4-portrait.pdf" in message


def test_after_conversion_updates_state_and_message(gui_app, monkeypatch):
    infos = []
    monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: infos.append((args, kwargs)))
    monkeypatch.setattr(
        "ui.main_window.preview.commands.ask_pdf_export_options",
        lambda *_args, **_kwargs: PdfExportOptions.with_defaults(),
    )

    result = ConversionResult(
        summary={"range_names": {"min": "A4", "max": "C6"}},
        shifted_notes=2,
        used_pitches=["A4", "B4"],
        output_xml_path="out.musicxml",
        output_mxl_path="out.mxl",
        output_midi_path="out.mid",
        output_pdf_paths={"A4 Portrait": "out-A4-portrait.pdf"},
        output_folder="/tmp/export-folder",
    )
    gui_app._after_conversion(result)
    assert gui_app.pitch_list == ["A4", "B4"]
    assert gui_app.status.get() == "Converted OK."
    assert infos
    assert len(infos) == 1
    title, message = infos[0][0]
    assert title == "Success"
    assert "export-folder" in message
    assert "out.musicxml" in message
    assert "out.mxl" in message
    assert "out.mid" in message
    assert "A4" in message
    assert "C6" in message
    assert "out-A4-portrait.pdf" in message


def test_require_input_path_validates_presence(gui_app, tmp_path, monkeypatch):
    errors = []
    monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: errors.append((args, kwargs)))
    missing_path = tmp_path / "missing.musicxml"
    gui_app.input_path.set(str(missing_path))
    assert gui_app._require_input_path("Choose a file first.") is None
    assert errors
    args, _ = errors[0]
    assert args[0] == "Error"
    assert "Choose a file first." in args[1]

    tree, _ = make_linear_score()
    valid_path = _write_score(tmp_path, tree)
    gui_app.input_path.set(str(valid_path))
    errors.clear()
    assert gui_app._require_input_path("Should not show") == str(valid_path)
    assert not errors
