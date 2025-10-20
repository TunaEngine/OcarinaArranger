from pathlib import Path

from pathlib import Path

import pytest

from ocarina_gui.preview import PreviewData
from ocarina_tools.parts import MusicXmlPartInfo
from tests.viewmodels._fakes import FakeDialogs, StubScoreService
from viewmodels.main_viewmodel import MainViewModel


def test_render_previews_sets_status(preview_data: PreviewData, tmp_path: Path) -> None:
    file_path = tmp_path / "score.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs()
    service = StubScoreService(preview=preview_data)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    viewmodel.update_settings(input_path=str(file_path))

    result = viewmodel.render_previews()

    assert result.is_ok()
    assert viewmodel.state.status_message == "Preview rendered."
    assert service.last_preview_settings is not None
    assert service.last_preview_settings.transpose_offset == 0
    assert service.last_midi_mode == "auto"
    assert viewmodel.state.midi_import_error is None


def test_render_previews_propagates_error(tmp_path: Path) -> None:
    file_path = tmp_path / "score.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs()
    service = StubScoreService(preview_error=RuntimeError("boom"))
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    viewmodel.update_settings(input_path=str(file_path))

    result = viewmodel.render_previews()

    assert result.is_err()
    assert result.error == "boom"
    assert viewmodel.state.status_message == "Preview failed: boom"
    assert viewmodel.state.midi_import_error == "boom"


def test_load_part_metadata_records_error(tmp_path: Path) -> None:
    file_path = tmp_path / "score.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs()
    service = StubScoreService(metadata_error=RuntimeError("invalid midi"))
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    viewmodel.update_settings(input_path=str(file_path))

    parts = viewmodel.load_part_metadata()

    assert parts == ()
    assert viewmodel.state.midi_import_error == "invalid midi"


def test_render_previews_passes_manual_transpose(preview_data: PreviewData, tmp_path: Path) -> None:
    file_path = tmp_path / "score.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs()
    service = StubScoreService(preview=preview_data)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    viewmodel.update_settings(input_path=str(file_path), transpose_offset=-4)

    result = viewmodel.render_previews()

    assert result.is_ok()
    assert service.last_preview_settings is not None
    assert service.last_preview_settings.transpose_offset == -4


def test_render_previews_honours_strict_midi_setting(
    preview_data: PreviewData, tmp_path: Path
) -> None:
    file_path = tmp_path / "score.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs()
    service = StubScoreService(preview=preview_data)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    viewmodel.update_settings(input_path=str(file_path), lenient_midi_import=False)

    result = viewmodel.render_previews()

    assert result.is_ok()
    assert service.last_midi_mode == "strict"


def test_render_previews_passes_filtered_part_selection(
    preview_data: PreviewData, tmp_path: Path
) -> None:
    file_path = tmp_path / "score.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs()
    service = StubScoreService(preview=preview_data)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    parts = (
        MusicXmlPartInfo(
            part_id="P1",
            name="Lead",
            midi_program=None,
            note_count=0,
            min_midi=None,
            max_midi=None,
            min_pitch=None,
            max_pitch=None,
        ),
        MusicXmlPartInfo(
            part_id="P2",
            name="Harmony",
            midi_program=None,
            note_count=0,
            min_midi=None,
            max_midi=None,
            min_pitch=None,
            max_pitch=None,
        ),
    )
    viewmodel.update_settings(input_path=str(file_path), available_parts=parts)
    viewmodel.apply_part_selection(["P2", "PX"])

    result = viewmodel.render_previews()

    assert result.is_ok()
    assert viewmodel.state.selected_part_ids == ("P2",)
    assert service.last_preview_settings is not None
    assert service.last_preview_settings.selected_part_ids == ("P2",)


