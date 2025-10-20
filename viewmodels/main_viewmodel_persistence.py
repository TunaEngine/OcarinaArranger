"""Helpers for persisting and restoring main view-model state."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from services.project_models import LoadedProject, ProjectSnapshot

if TYPE_CHECKING:  # pragma: no cover - used only for type checking
    from .main_viewmodel import MainViewModel


def build_project_snapshot(view_model: "MainViewModel") -> ProjectSnapshot:
    """Produce a snapshot capturing the state required to save a project."""

    state = view_model.state
    return ProjectSnapshot(
        input_path=Path(state.input_path),
        settings=view_model.settings(),
        pdf_options=view_model._last_pdf_options,
        pitch_list=list(state.pitch_list),
        pitch_entries=view_model.pitch_entries(),
        status_message=state.status_message,
        conversion=view_model._last_conversion,
        preview_settings=view_model.preview_settings(),
        arranger_mode=state.arranger_mode,
        arranger_strategy=state.arranger_strategy,
        starred_instrument_ids=state.starred_instrument_ids,
        arranger_dp_slack_enabled=state.arranger_dp_slack_enabled,
        arranger_budgets=state.arranger_budgets,
        arranger_gp_settings=state.arranger_gp_settings,
        grace_settings=state.grace_settings,
    )


def apply_loaded_project(view_model: "MainViewModel", loaded: LoadedProject) -> None:
    """Populate the view-model with data retrieved from a saved project."""

    settings = loaded.settings
    update_kwargs: dict[str, object] = {
        "input_path": str(loaded.input_path),
        "prefer_mode": settings.prefer_mode,
        "prefer_flats": settings.prefer_flats,
        "collapse_chords": settings.collapse_chords,
        "favor_lower": settings.favor_lower,
        "range_min": settings.range_min,
        "range_max": settings.range_max,
        "transpose_offset": settings.transpose_offset,
        "instrument_id": settings.instrument_id,
        "selected_part_ids": settings.selected_part_ids,
        "grace_settings": settings.grace_settings,
    }
    if loaded.arranger_mode is not None:
        update_kwargs["arranger_mode"] = loaded.arranger_mode
    if loaded.arranger_strategy is not None:
        update_kwargs["arranger_strategy"] = loaded.arranger_strategy
    if loaded.starred_instrument_ids is not None:
        update_kwargs["starred_instrument_ids"] = loaded.starred_instrument_ids
    if loaded.arranger_dp_slack_enabled is not None:
        update_kwargs["arranger_dp_slack_enabled"] = loaded.arranger_dp_slack_enabled
    if loaded.arranger_budgets is not None:
        update_kwargs["arranger_budgets"] = loaded.arranger_budgets
    if loaded.arranger_gp_settings is not None:
        update_kwargs["arranger_gp_settings"] = loaded.arranger_gp_settings

    view_model.update_settings(**update_kwargs)
    view_model.state.pitch_list = list(loaded.pitch_list)
    view_model._pitch_entries = list(loaded.pitch_entries)
    view_model._last_pdf_options = loaded.pdf_options
    view_model._last_conversion = loaded.conversion
    if loaded.conversion is not None:
        view_model.state.pitch_list = list(loaded.conversion.used_pitches)
    view_model.state.status_message = loaded.status_message or "Project loaded."
    view_model.state.preview_settings = dict(loaded.preview_settings)
