"""Helpers for capturing and restoring preview state snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ocarina_tools.parts import MusicXmlPartInfo
from services.project_service import PreviewPlaybackSnapshot

from viewmodels.arranger_models import (
    ArrangerExplanationRow,
    ArrangerInstrumentSummary,
    ArrangerResultSummary,
    ArrangerTelemetryHint,
)

from .main_viewmodel_state import MainViewModelState


@dataclass(frozen=True)
class PreviewStateSnapshot:
    """Persisted copy of the most recent successful preview state."""

    input_path: str
    available_parts: tuple[MusicXmlPartInfo, ...]
    selected_part_ids: tuple[str, ...]
    preview_settings: dict[str, PreviewPlaybackSnapshot]
    arranger_strategy_summary: tuple[ArrangerInstrumentSummary, ...]
    arranger_result_summary: ArrangerResultSummary | None
    arranger_explanations: tuple[ArrangerExplanationRow, ...]
    arranger_telemetry: tuple[ArrangerTelemetryHint, ...]
    pitch_list: tuple[str, ...]
    pitch_entries: tuple[str, ...]


def capture_preview_state(
    state: MainViewModelState, pitch_entries: Sequence[str]
) -> PreviewStateSnapshot:
    """Return a snapshot representing the current preview-related state."""

    return PreviewStateSnapshot(
        input_path=state.input_path,
        available_parts=tuple(state.available_parts),
        selected_part_ids=tuple(state.selected_part_ids),
        preview_settings=dict(state.preview_settings),
        arranger_strategy_summary=tuple(state.arranger_strategy_summary),
        arranger_result_summary=state.arranger_result_summary,
        arranger_explanations=tuple(state.arranger_explanations),
        arranger_telemetry=tuple(state.arranger_telemetry),
        pitch_list=tuple(state.pitch_list),
        pitch_entries=tuple(pitch_entries),
    )


def restore_preview_state(
    state: MainViewModelState, snapshot: PreviewStateSnapshot
) -> list[str]:
    """Restore the view-model state from ``snapshot`` and return pitch entries."""

    state.input_path = snapshot.input_path
    state.available_parts = snapshot.available_parts
    state.selected_part_ids = snapshot.selected_part_ids
    state.preview_settings = dict(snapshot.preview_settings)
    state.arranger_strategy_summary = snapshot.arranger_strategy_summary
    state.arranger_result_summary = snapshot.arranger_result_summary
    state.arranger_explanations = snapshot.arranger_explanations
    state.arranger_telemetry = snapshot.arranger_telemetry
    state.pitch_list = list(snapshot.pitch_list)
    return list(snapshot.pitch_entries)

