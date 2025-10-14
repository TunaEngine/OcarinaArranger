"""Shared constants and state container for the main view-model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from ocarina_gui.constants import DEFAULT_MAX, DEFAULT_MIN
from ocarina_gui.preferences import DEFAULT_ARRANGER_MODE
from services.project_service import PreviewPlaybackSnapshot

from viewmodels.arranger_models import (
    ArrangerBudgetSettings,
    ArrangerExplanationRow,
    ArrangerGPSettings,
    ArrangerInstrumentSummary,
    ArrangerResultSummary,
    ArrangerTelemetryHint,
)


ARRANGER_STRATEGY_CURRENT = "current"
ARRANGER_STRATEGY_STARRED_BEST = "starred-best"
ARRANGER_STRATEGIES = (
    ARRANGER_STRATEGY_CURRENT,
    ARRANGER_STRATEGY_STARRED_BEST,
)
DEFAULT_ARRANGER_STRATEGY = ARRANGER_STRATEGY_CURRENT


@dataclass(slots=True)
class MainViewModelState:
    input_path: str = ""
    prefer_mode: str = "auto"
    prefer_flats: bool = True
    collapse_chords: bool = True
    favor_lower: bool = False
    range_min: str = DEFAULT_MIN
    range_max: str = DEFAULT_MAX
    status_message: str = "Ready."
    pitch_list: list[str] = field(default_factory=list)
    transpose_offset: int = 0
    instrument_id: str = ""
    preview_settings: dict[str, PreviewPlaybackSnapshot] = field(default_factory=dict)
    arranger_mode: str = DEFAULT_ARRANGER_MODE
    arranger_strategy: str = DEFAULT_ARRANGER_STRATEGY
    starred_instrument_ids: Tuple[str, ...] = field(default_factory=tuple)
    arranger_strategy_summary: Tuple[ArrangerInstrumentSummary, ...] = field(
        default_factory=tuple
    )
    arranger_dp_slack_enabled: bool = True
    arranger_budgets: ArrangerBudgetSettings = field(
        default_factory=ArrangerBudgetSettings
    )
    arranger_gp_settings: ArrangerGPSettings = field(
        default_factory=ArrangerGPSettings
    )
    arranger_result_summary: ArrangerResultSummary | None = None
    arranger_explanations: Tuple[ArrangerExplanationRow, ...] = field(
        default_factory=tuple
    )
    arranger_telemetry: Tuple[ArrangerTelemetryHint, ...] = field(
        default_factory=tuple
    )


__all__ = [
    "ARRANGER_STRATEGIES",
    "ARRANGER_STRATEGY_CURRENT",
    "ARRANGER_STRATEGY_STARRED_BEST",
    "DEFAULT_ARRANGER_STRATEGY",
    "MainViewModelState",
]
