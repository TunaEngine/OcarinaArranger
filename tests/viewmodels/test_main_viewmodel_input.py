from pathlib import Path

from ocarina_tools.parts import MusicXmlPartInfo
from services.project_service import PreviewPlaybackSnapshot
from shared.melody_part import select_melody_candidate
from tests.viewmodels._fakes import FakeDialogs, StubScoreService
from viewmodels.main_viewmodel import MainViewModel


def test_browse_for_input_updates_state(tmp_path: Path) -> None:
    file_path = tmp_path / "picked.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs(open_path=str(file_path))
    viewmodel = MainViewModel(dialogs=dialogs, score_service=StubScoreService())
    viewmodel.state.pitch_list = ["C4"]
    viewmodel.update_preview_settings({"arranged": PreviewPlaybackSnapshot()})
    viewmodel.state.available_parts = (
        MusicXmlPartInfo(
            part_id="P1",
            name="Part 1",
            midi_program=None,
            note_count=0,
            min_midi=None,
            max_midi=None,
            min_pitch=None,
            max_pitch=None,
        ),
    )
    viewmodel.state.selected_part_ids = ("P1",)

    assert viewmodel.browse_for_input() is True

    assert viewmodel.state.input_path == str(file_path)
    assert viewmodel.state.pitch_list == []
    assert viewmodel.state.available_parts == ()
    assert viewmodel.state.selected_part_ids == ()
    assert viewmodel.state.preview_settings == {}
    assert viewmodel.state.status_message == "Ready."


def test_browse_for_input_cancel_retains_state(tmp_path: Path) -> None:
    existing = tmp_path / "existing.musicxml"
    existing.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs(open_path=None)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=StubScoreService())
    viewmodel.update_settings(input_path=str(existing))
    viewmodel.state.pitch_list = ["D4"]

    assert viewmodel.browse_for_input() is False

    assert viewmodel.state.input_path == str(existing)
    assert viewmodel.state.pitch_list == ["D4"]


def test_browse_for_input_allows_retry_after_cancelled_part_selection(tmp_path: Path) -> None:
    file_path = tmp_path / "retry.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs(open_path=str(file_path))
    viewmodel = MainViewModel(dialogs=dialogs, score_service=StubScoreService())

    first_attempt = viewmodel.browse_for_input()
    assert first_attempt is True
    assert viewmodel.state.selected_part_ids == ()

    second_attempt = viewmodel.browse_for_input()

    assert second_attempt is True
    assert len(dialogs.open_calls) == 2


def test_browse_for_input_skips_when_selection_confirmed(tmp_path: Path) -> None:
    file_path = tmp_path / "confirmed.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs(open_path=str(file_path))
    viewmodel = MainViewModel(dialogs=dialogs, score_service=StubScoreService())

    assert viewmodel.browse_for_input() is True

    viewmodel.apply_part_selection(["P1"])

    skipped = viewmodel.browse_for_input()

    assert skipped is False
    assert len(dialogs.open_calls) == 2


def test_load_part_metadata_updates_state(tmp_path: Path) -> None:
    file_path = tmp_path / "parts.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs()
    parts = (
        MusicXmlPartInfo(
            part_id="P1",
            name="Solo",
            midi_program=None,
            note_count=10,
            min_midi=60,
            max_midi=72,
            min_pitch="C4",
            max_pitch="C5",
        ),
        MusicXmlPartInfo(
            part_id="P2",
            name="Accompaniment",
            midi_program=None,
            note_count=5,
            min_midi=55,
            max_midi=67,
            min_pitch="G3",
            max_pitch="G4",
        ),
    )
    service = StubScoreService(part_metadata=parts)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    viewmodel.update_settings(input_path=str(file_path))

    loaded = viewmodel.load_part_metadata()

    assert loaded == parts
    assert viewmodel.state.available_parts == parts
    expected_default = select_melody_candidate(parts) or parts[0].part_id
    assert viewmodel.state.selected_part_ids == (expected_default,)
    assert service.part_metadata_calls == [str(file_path)]


def test_apply_part_selection_filters_unknown_parts() -> None:
    dialogs = FakeDialogs()
    service = StubScoreService()
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    available = (
        MusicXmlPartInfo(
            part_id="P1",
            name="Solo",
            midi_program=None,
            note_count=0,
            min_midi=None,
            max_midi=None,
            min_pitch=None,
            max_pitch=None,
        ),
        MusicXmlPartInfo(
            part_id="P2",
            name="Piano",
            midi_program=None,
            note_count=0,
            min_midi=None,
            max_midi=None,
            min_pitch=None,
            max_pitch=None,
        ),
    )
    viewmodel.update_settings(available_parts=available)

    selection = viewmodel.apply_part_selection(["P1", "P3", "P2"])

    assert selection == ("P1", "P2")
    assert viewmodel.state.selected_part_ids == ("P1", "P2")


def test_ask_select_parts_propagates_cancel() -> None:
    dialogs = FakeDialogs(part_selection=None)
    service = StubScoreService()
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    parts = (
        MusicXmlPartInfo(
            part_id="P1",
            name="Solo",
            midi_program=None,
            note_count=0,
            min_midi=None,
            max_midi=None,
            min_pitch=None,
            max_pitch=None,
        ),
    )

    result = viewmodel.ask_select_parts(parts, ("P1",))

    assert result is None


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
