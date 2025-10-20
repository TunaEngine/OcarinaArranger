from __future__ import annotations

from pathlib import Path

from ocarina_gui.conversion import ConversionResult

from tests.viewmodels._fakes import FakeDialogs, StubScoreService
from viewmodels.main_viewmodel import MainViewModel


def test_convert_requires_input_path(tmp_path: Path, conversion_result: ConversionResult) -> None:
    dialogs = FakeDialogs(save_path=str(tmp_path / "out.musicxml"))
    service = StubScoreService(conversion=conversion_result)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    outcome = viewmodel.convert()
    assert outcome is not None and outcome.is_err()
    assert outcome.error == "Please choose a valid input file (.musicxml/.xml, .mxl, or .mid)."


def test_convert_success_updates_state(tmp_path: Path, conversion_result: ConversionResult) -> None:
    input_path = tmp_path / "score.musicxml"
    input_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs(save_path=str(tmp_path / "saved.musicxml"))
    service = StubScoreService(conversion=conversion_result)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    viewmodel.update_settings(input_path=str(input_path))
    result = viewmodel.convert()
    assert result is not None and result.is_ok()
    assert viewmodel.state.status_message == "Converted OK."
    assert viewmodel.state.pitch_list == conversion_result.used_pitches
    assert viewmodel.state.midi_import_error is None


def test_convert_handles_cancellation(tmp_path: Path, conversion_result: ConversionResult) -> None:
    input_path = tmp_path / "score.musicxml"
    input_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs(save_path=None)
    service = StubScoreService(conversion=conversion_result)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    viewmodel.update_settings(input_path=str(input_path))
    result = viewmodel.convert()
    assert result is None
    assert viewmodel.state.pitch_list == []


def test_convert_propagates_error(tmp_path: Path, conversion_result: ConversionResult) -> None:
    input_path = tmp_path / "score.musicxml"
    input_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs(save_path=str(tmp_path / "saved.musicxml"))
    service = StubScoreService(conversion=conversion_result, convert_error=RuntimeError("boom"))
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    viewmodel.update_settings(input_path=str(input_path))
    result = viewmodel.convert()
    assert result is not None and result.is_err()
    assert result.error == "boom"
    assert viewmodel.state.status_message == "Conversion failed."
    assert viewmodel.state.midi_import_error == "boom"


def test_convert_passes_manual_transpose_setting(tmp_path: Path, conversion_result: ConversionResult) -> None:
    input_path = tmp_path / "score.musicxml"
    input_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs(save_path=str(tmp_path / "saved.musicxml"))
    service = StubScoreService(conversion=conversion_result)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    viewmodel.update_settings(input_path=str(input_path), transpose_offset=3)
    outcome = viewmodel.convert()
    assert outcome is not None and outcome.is_ok()
    assert service.last_convert_settings is not None
    assert service.last_convert_settings.transpose_offset == 3
