from pathlib import Path

from ocarina_gui.preview import PreviewData
from services.project_service import PreviewPlaybackSnapshot
from tests.viewmodels._fakes import FakeDialogs, StubScoreService
from viewmodels.main_viewmodel import MainViewModel


def test_browse_for_input_updates_state(tmp_path: Path) -> None:
    file_path = tmp_path / "picked.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs(open_path=str(file_path))
    viewmodel = MainViewModel(dialogs=dialogs, score_service=StubScoreService())
    viewmodel.state.pitch_list = ["C4"]
    viewmodel.update_preview_settings({"arranged": PreviewPlaybackSnapshot()})

    viewmodel.browse_for_input()

    assert viewmodel.state.input_path == str(file_path)
    assert viewmodel.state.pitch_list == []
    assert viewmodel.state.preview_settings == {}
    assert viewmodel.state.status_message == "Ready."


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
    assert viewmodel.state.status_message == "Preview failed."


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


def test_new_input_path_clears_preview_settings(tmp_path: Path) -> None:
    first = tmp_path / "first.musicxml"
    first.write_text("<score />", encoding="utf-8")
    second = tmp_path / "second.musicxml"
    second.write_text("<score />", encoding="utf-8")

    dialogs = FakeDialogs()
    service = StubScoreService()
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)

    viewmodel.update_settings(input_path=str(first))
    viewmodel.update_preview_settings(
        {
            "arranged": PreviewPlaybackSnapshot(
                tempo_bpm=150.0,
                metronome_enabled=True,
                loop_enabled=True,
                loop_start_beat=1.0,
                loop_end_beat=3.0,
            )
        }
    )

    # Updating with the same path should preserve the snapshot
    viewmodel.update_settings(input_path=str(first))
    assert "arranged" in viewmodel.state.preview_settings

    # Selecting a different file clears any prior playback adjustments
    viewmodel.update_settings(input_path=str(second))
    assert viewmodel.state.preview_settings == {}
