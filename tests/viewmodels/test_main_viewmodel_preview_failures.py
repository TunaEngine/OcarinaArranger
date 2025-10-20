from pathlib import Path

from ocarina_gui.preview import PreviewData
from ocarina_tools.parts import MusicXmlPartInfo
from services.project_service import PreviewPlaybackSnapshot

from tests.viewmodels._fakes import FakeDialogs, StubScoreService
from viewmodels.main_viewmodel import MainViewModel


def test_render_previews_failure_restores_previous_state(
    preview_data: PreviewData, tmp_path: Path
) -> None:
    first_path = tmp_path / "first.musicxml"
    first_path.write_text("<score />", encoding="utf-8")
    second_path = tmp_path / "second.musicxml"
    second_path.write_text("<score />", encoding="utf-8")
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
    viewmodel.update_settings(
        input_path=str(first_path),
        available_parts=parts,
        selected_part_ids=("P2",),
    )
    viewmodel.update_preview_settings(
        {
            "original": PreviewPlaybackSnapshot(
                tempo_bpm=96.0,
                metronome_enabled=True,
                loop_enabled=True,
                loop_start_beat=1.0,
                loop_end_beat=5.0,
                volume=0.75,
            )
        }
    )
    viewmodel.state.pitch_list = ["G4", "A4"]
    viewmodel._pitch_entries = ["G4", "A4"]

    success = viewmodel.render_previews()

    assert success.is_ok()
    expected_preview_settings = dict(viewmodel.state.preview_settings)
    expected_available_parts = viewmodel.state.available_parts
    expected_selected_parts = viewmodel.state.selected_part_ids
    expected_pitch_list = list(viewmodel.state.pitch_list)
    expected_pitch_entries = list(viewmodel._pitch_entries)
    expected_input_path = viewmodel.state.input_path
    assert viewmodel._pending_input_confirmation is False

    service.preview_error = RuntimeError("preview boom")
    viewmodel.update_settings(input_path=str(second_path))

    assert viewmodel.state.input_path == str(second_path)
    assert viewmodel.state.preview_settings == {}
    assert viewmodel.state.selected_part_ids == ()

    failure = viewmodel.render_previews()

    assert failure.is_err()
    assert failure.error == "preview boom"
    assert viewmodel.state.status_message == "Preview failed: preview boom"
    assert viewmodel.state.input_path == expected_input_path
    assert viewmodel.state.preview_settings == expected_preview_settings
    assert viewmodel.state.available_parts == expected_available_parts
    assert viewmodel.state.selected_part_ids == expected_selected_parts
    assert viewmodel.state.pitch_list == expected_pitch_list
    assert viewmodel._pitch_entries == expected_pitch_entries
    assert viewmodel._pending_input_confirmation is True


def test_browse_allows_same_path_after_preview_failure(
    preview_data: PreviewData, tmp_path: Path
) -> None:
    score_path = tmp_path / "score.musicxml"
    score_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs(open_path=str(score_path))
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
    )
    viewmodel.update_settings(
        input_path=str(score_path),
        available_parts=parts,
        selected_part_ids=("P1",),
    )

    success = viewmodel.render_previews()

    assert success.is_ok()
    assert viewmodel._pending_input_confirmation is False

    service.preview_error = RuntimeError("preview busted")

    failure = viewmodel.render_previews()

    assert failure.is_err()
    assert viewmodel._pending_input_confirmation is True

    dialogs._open_path = str(score_path)

    reloaded = viewmodel.browse_for_input()

    assert reloaded is True
    assert viewmodel._pending_input_confirmation is True


def test_apply_part_selection_preserves_pending_confirmation_after_failure(
    preview_data: PreviewData, tmp_path: Path
) -> None:
    score_path = tmp_path / "score.musicxml"
    score_path.write_text("<score />", encoding="utf-8")
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
    )
    viewmodel.update_settings(
        input_path=str(score_path),
        available_parts=parts,
        selected_part_ids=("P1",),
    )

    success = viewmodel.render_previews()

    assert success.is_ok()
    assert viewmodel._pending_input_confirmation is False

    service.preview_error = RuntimeError("preview busted")

    failure = viewmodel.render_previews()

    assert failure.is_err()
    assert viewmodel._pending_input_confirmation is True

    viewmodel.apply_part_selection(("P1",))

    assert viewmodel._pending_input_confirmation is True

