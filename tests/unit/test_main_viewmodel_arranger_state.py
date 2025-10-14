"""Unit coverage for arranger-specific state on the main view-model."""

from __future__ import annotations

from dataclasses import dataclass

from adapters.file_dialog import FileDialogAdapter
from services.score_service import ScoreService
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

    def save(self, snapshot, destination):  # noqa: D401 - signature compatibility
        raise NotImplementedError

    def load(self, source, extract_dir):  # noqa: D401 - signature compatibility
        raise NotImplementedError


def _make_viewmodel() -> MainViewModel:
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
        project_service=_StubProjectService(),
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
