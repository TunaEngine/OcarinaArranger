"""Unit coverage for arranger-specific state on the main view-model."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from adapters.file_dialog import FileDialogAdapter
from services.project_service import LoadedProject, ProjectSnapshot
from services.score_service import ScoreService
from ocarina_gui.settings import TransformSettings
from ocarina_tools.parts import MusicXmlPartInfo
from viewmodels.arranger_models import ArrangerBudgetSettings, ArrangerGPSettings
from viewmodels.main_viewmodel import MainViewModel, MainViewModelState


class _StubDialogs(FileDialogAdapter):
    """Minimal dialog adapter satisfying the protocol for tests."""

    def ask_open_path(self) -> str | None:  # noqa: D401 - protocol compliance
        return None

    def ask_save_path(self, suggested_name: str) -> str | None:  # noqa: D401
        return None

    def ask_open_project_path(self) -> str | None:  # noqa: D401
        return None

    def ask_save_project_path(self, suggested_name: str) -> str | None:  # noqa: D401
        return None

    def ask_select_parts(
        self,
        parts,
        preselected,
    ) -> tuple[str, ...]:  # noqa: D401 - protocol compliance
        return tuple(preselected)


@dataclass(slots=True)
class _StubProjectService:
    """No-op project service implementation for view-model tests."""

    saved_snapshots: list[ProjectSnapshot] = field(default_factory=list)

    def save(self, snapshot, destination):  # noqa: D401 - signature compatibility
        self.saved_snapshots.append(snapshot)
        return Path(destination)

    def load(self, source, extract_dir):  # noqa: D401 - signature compatibility
        raise NotImplementedError


def _make_viewmodel(
    *, project_service: _StubProjectService | None = None
) -> MainViewModel:
    """Create a view-model instance with stubbed dependencies."""

    stub_score_service = ScoreService(
        load_score=lambda path: (None, None),
        build_preview_data=lambda path, settings: None,
        convert_score=lambda *args, **kwargs: None,
        export_musicxml=lambda *args, **kwargs: None,
        export_mxl=lambda *args, **kwargs: None,
        export_midi=lambda *args, **kwargs: None,
        export_pdf=lambda *args, **kwargs: None,
    )
    viewmodel = MainViewModel(
        dialogs=_StubDialogs(),
        score_service=stub_score_service,
        project_service=project_service or _StubProjectService(),
    )
    # Sanity check to ensure defaults align with expectations for tests.
    assert isinstance(viewmodel.state, MainViewModelState)
    return viewmodel


def test_update_settings_switches_arranger_mode() -> None:
    viewmodel = _make_viewmodel()

    assert viewmodel.state.arranger_mode == "gp"

    viewmodel.update_settings(arranger_mode="best_effort")

    assert viewmodel.state.arranger_mode == "best_effort"

    viewmodel.update_settings(arranger_mode="classic")

    assert viewmodel.state.arranger_mode == "classic"

    viewmodel.update_settings(arranger_mode="gp")

    assert viewmodel.state.arranger_mode == "gp"


def test_update_settings_tracks_starred_instruments() -> None:
    viewmodel = _make_viewmodel()

    selections = ("alto_c", "tenor_g", "alto_c")
    viewmodel.update_settings(starred_instrument_ids=selections)

    assert viewmodel.state.starred_instrument_ids == ("alto_c", "tenor_g")


def test_update_settings_persists_dp_slack_flag() -> None:
    viewmodel = _make_viewmodel()

    assert viewmodel.state.arranger_dp_slack_enabled is True

    viewmodel.update_settings(arranger_dp_slack_enabled=False)

    assert viewmodel.state.arranger_dp_slack_enabled is False

    viewmodel.update_settings(arranger_dp_slack_enabled=True)

    assert viewmodel.state.arranger_dp_slack_enabled is True


def test_reset_arranger_budgets_restores_defaults() -> None:
    viewmodel = _make_viewmodel()
    custom = ArrangerBudgetSettings(
        max_octave_edits=2,
        max_rhythm_edits=3,
        max_substitutions=4,
        max_steps_per_span=5,
    )
    viewmodel.update_settings(arranger_budgets=custom)
    assert viewmodel.state.arranger_budgets == custom.normalized()

    viewmodel.reset_arranger_budgets()

    assert viewmodel.state.arranger_budgets == ArrangerBudgetSettings()


def test_update_settings_tracks_gp_configuration() -> None:
    viewmodel = _make_viewmodel()

    defaults = ArrangerGPSettings()
    assert viewmodel.state.arranger_gp_settings == defaults

    custom = ArrangerGPSettings(generations=7, population_size=24, time_budget_seconds=15.5)
    viewmodel.update_settings(arranger_gp_settings=custom)

    assert viewmodel.state.arranger_gp_settings == custom.normalized()


def test_update_settings_normalizes_parts_and_selections() -> None:
    viewmodel = _make_viewmodel()

    parts = [
        MusicXmlPartInfo(
            part_id=" P1 ",
            name=" Part 1 ",
            midi_program=41,
            note_count=3,
            min_midi=60,
            max_midi=72,
            min_pitch="C4",
            max_pitch="C5",
        ),
        MusicXmlPartInfo(
            part_id="P1",
            name="Duplicate",
            midi_program=42,
            note_count=2,
            min_midi=None,
            max_midi=None,
            min_pitch=None,
            max_pitch=None,
        ),
    ]

    viewmodel.update_settings(available_parts=parts)

    assert len(viewmodel.state.available_parts) == 1
    normalized_part = viewmodel.state.available_parts[0]
    assert normalized_part.part_id == "P1"
    assert normalized_part.name == "Part 1"
    assert normalized_part.midi_program == 41

    viewmodel.update_settings(selected_part_ids=("P1", "P3", "P1"))
    assert viewmodel.state.selected_part_ids == ("P1",)

    viewmodel.update_settings(
        available_parts=[
            {
                "part_id": "P2",
                "name": "Second",
                "midi_program": "38",
                "note_count": "5",
                "min_midi": "55",
                "max_midi": "77",
                "min_pitch": "G3",
                "max_pitch": "F5",
            }
        ]
    )

    assert len(viewmodel.state.available_parts) == 1
    replacement = viewmodel.state.available_parts[0]
    assert replacement.part_id == "P2"
    assert replacement.name == "Second"
    assert replacement.midi_program == 38
    assert viewmodel.state.selected_part_ids == ()


def test_save_project_to_includes_arranger_settings(tmp_path: Path) -> None:
    stub_service = _StubProjectService()
    viewmodel = _make_viewmodel(project_service=stub_service)
    input_path = tmp_path / "song.musicxml"
    input_path.write_text("<score/>", encoding="utf-8")
    viewmodel.update_settings(
        input_path=str(input_path),
        arranger_mode="best_effort",
        arranger_strategy="starred-best",
        starred_instrument_ids=("alto", "tenor"),
        arranger_dp_slack_enabled=False,
        arranger_budgets=ArrangerBudgetSettings(
            max_octave_edits=2,
            max_rhythm_edits=3,
            max_substitutions=4,
            max_steps_per_span=5,
        ),
        arranger_gp_settings=ArrangerGPSettings(
            generations=6,
            population_size=14,
            time_budget_seconds=8.5,
        ),
    )
    viewmodel.state.status_message = "Ready."

    result = viewmodel.save_project_to(tmp_path / "project.ocarina")

    assert result.is_ok()
    assert stub_service.saved_snapshots
    snapshot = stub_service.saved_snapshots[-1]
    assert snapshot.arranger_mode == "best_effort"
    assert snapshot.arranger_strategy == "starred-best"
    assert snapshot.starred_instrument_ids == ("alto", "tenor")
    assert snapshot.arranger_dp_slack_enabled is False
    assert snapshot.arranger_budgets == ArrangerBudgetSettings(
        max_octave_edits=2,
        max_rhythm_edits=3,
        max_substitutions=4,
        max_steps_per_span=5,
    ).normalized()
    assert snapshot.arranger_gp_settings == ArrangerGPSettings(
        generations=6,
        population_size=14,
        time_budget_seconds=8.5,
    ).normalized()


def test_apply_loaded_project_restores_arranger_settings(tmp_path: Path) -> None:
    viewmodel = _make_viewmodel()
    working_dir = tmp_path / "work"
    working_dir.mkdir()
    original_dir = working_dir / "original"
    original_dir.mkdir()
    input_path = original_dir / "song.musicxml"
    input_path.write_text("<score/>", encoding="utf-8")
    loaded = LoadedProject(
        archive_path=tmp_path / "archive.ocarina",
        working_directory=working_dir,
        input_path=input_path,
        settings=TransformSettings(
            prefer_mode="auto",
            range_min="C4",
            range_max="C6",
            prefer_flats=True,
            collapse_chords=True,
            favor_lower=False,
            selected_part_ids=("P1",),
        ),
        pdf_options=None,
        pitch_list=["C4"],
        pitch_entries=["C4"],
        status_message="Saved.",
        conversion=None,
        preview_settings={},
        arranger_mode="gp",
        arranger_strategy="starred-best",
        starred_instrument_ids=("alto", "tenor"),
        arranger_dp_slack_enabled=True,
        arranger_budgets=ArrangerBudgetSettings(
            max_octave_edits=4,
            max_rhythm_edits=5,
            max_substitutions=6,
            max_steps_per_span=7,
        ),
        arranger_gp_settings=ArrangerGPSettings(
            generations=8,
            population_size=20,
            time_budget_seconds=15.0,
        ),
    )

    viewmodel._apply_loaded_project(loaded)

    assert viewmodel.state.arranger_mode == "gp"
    assert viewmodel.state.arranger_strategy == "starred-best"
    assert viewmodel.state.starred_instrument_ids == ("alto", "tenor")
    assert viewmodel.state.arranger_dp_slack_enabled is True
    assert viewmodel.state.arranger_budgets == ArrangerBudgetSettings(
        max_octave_edits=4,
        max_rhythm_edits=5,
        max_substitutions=6,
        max_steps_per_span=7,
    ).normalized()
    assert viewmodel.state.arranger_gp_settings == ArrangerGPSettings(
        generations=8,
        population_size=20,
        time_budget_seconds=15.0,
    ).normalized()


def test_apply_loaded_project_clears_starred_instruments_when_empty(
    tmp_path: Path,
) -> None:
    viewmodel = _make_viewmodel()
    viewmodel.update_settings(starred_instrument_ids=("alto",))

    working_dir = tmp_path / "work"
    working_dir.mkdir()
    original_dir = working_dir / "original"
    original_dir.mkdir()
    input_path = original_dir / "song.musicxml"
    input_path.write_text("<score/>", encoding="utf-8")

    loaded = LoadedProject(
        archive_path=tmp_path / "archive.ocarina",
        working_directory=working_dir,
        input_path=input_path,
        settings=TransformSettings(
            prefer_mode="auto",
            range_min="C4",
            range_max="C6",
            prefer_flats=False,
            collapse_chords=False,
            favor_lower=False,
        ),
        pdf_options=None,
        pitch_list=[],
        pitch_entries=[],
        status_message="",
        conversion=None,
        preview_settings={},
        arranger_mode=None,
        arranger_strategy=None,
        starred_instrument_ids=(),
    )

    viewmodel._apply_loaded_project(loaded)

    assert viewmodel.state.starred_instrument_ids == ()
