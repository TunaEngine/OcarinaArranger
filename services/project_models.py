"""Shared data structures used by the project persistence service."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ocarina_gui.conversion import ConversionResult
from ocarina_gui.pdf_export.types import PdfExportOptions
from ocarina_gui.settings import GraceTransformSettings, TransformSettings
from viewmodels.arranger_models import ArrangerBudgetSettings, ArrangerGPSettings


@dataclass(frozen=True)
class ProjectSnapshot:
    """Aggregate of state required to persist a project archive."""

    input_path: Path
    settings: TransformSettings
    pdf_options: PdfExportOptions | None
    pitch_list: list[str]
    pitch_entries: list[str]
    status_message: str
    conversion: ConversionResult | None
    preview_settings: dict[str, "PreviewPlaybackSnapshot"] = field(default_factory=dict)
    arranger_mode: str | None = None
    arranger_strategy: str | None = None
    starred_instrument_ids: tuple[str, ...] = field(default_factory=tuple)
    arranger_dp_slack_enabled: bool | None = None
    arranger_budgets: ArrangerBudgetSettings | None = None
    arranger_gp_settings: ArrangerGPSettings | None = None
    grace_settings: GraceTransformSettings = GraceTransformSettings()


@dataclass(frozen=True)
class LoadedProject:
    """Deserialized project data extracted from an archive."""

    archive_path: Path
    working_directory: Path
    input_path: Path
    settings: TransformSettings
    pdf_options: PdfExportOptions | None
    pitch_list: list[str]
    pitch_entries: list[str]
    status_message: str
    conversion: ConversionResult | None
    preview_settings: dict[str, "PreviewPlaybackSnapshot"]
    arranger_mode: str | None = None
    arranger_strategy: str | None = None
    starred_instrument_ids: tuple[str, ...] = field(default_factory=tuple)
    arranger_dp_slack_enabled: bool | None = None
    arranger_budgets: ArrangerBudgetSettings | None = None
    arranger_gp_settings: ArrangerGPSettings | None = None
    grace_settings: GraceTransformSettings = GraceTransformSettings()


@dataclass(frozen=True)
class PreviewPlaybackSnapshot:
    """Persisted playback adjustments for a preview pane."""

    tempo_bpm: float = 120.0
    metronome_enabled: bool = False
    loop_enabled: bool = False
    loop_start_beat: float = 0.0
    loop_end_beat: float = 0.0
    volume: float = 1.0


__all__ = [
    "LoadedProject",
    "PreviewPlaybackSnapshot",
    "ProjectSnapshot",
]
