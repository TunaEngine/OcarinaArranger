from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Optional

from adapters.file_dialog import FileDialogAdapter
from ocarina_gui.settings import (
    GraceTransformSettings,
    SubholeTransformSettings,
    TransformSettings,
)
from ocarina_tools.midi_import.models import MidiImportReport
from ocarina_tools.parts import MusicXmlPartInfo
from services.project_service import ProjectService
from services.score_service import ScoreService
from shared.melody_part import select_melody_candidate

from .main_viewmodel_arranger_settings import (
    normalize_arranger_budgets,
    normalize_arranger_gp_settings,
    normalize_grace_settings,
    normalize_subhole_settings,
)
from .main_viewmodel_part_selection import (
    normalize_available_parts,
    normalize_selected_part_ids,
)
from .main_viewmodel_preview_state import capture_preview_state
from .main_viewmodel_state import (
    ARRANGER_STRATEGIES,
    DEFAULT_ARRANGER_STRATEGY,
    MainViewModelState,
)

logger = logging.getLogger(__name__)


class MainViewModelSettingsMixin:
    """Shared settings and part-selection behaviors for the main view-model."""

    state: MainViewModelState
    _dialogs: FileDialogAdapter
    _score_service: ScoreService
    _project_service: ProjectService

    def update_settings(
        self,
        *,
        input_path: Optional[str] = None,
        prefer_mode: Optional[str] = None,
        prefer_flats: Optional[bool] = None,
        collapse_chords: Optional[bool] = None,
        favor_lower: Optional[bool] = None,
        range_min: Optional[str] = None,
        range_max: Optional[str] = None,
        transpose_offset: Optional[int] = None,
        instrument_id: Optional[str] = None,
        available_parts: Optional[Iterable[MusicXmlPartInfo | Mapping[str, Any]]] = None,
        selected_part_ids: Optional[tuple[str, ...] | list[str]] = None,
        arranger_mode: Optional[str] = None,
        arranger_strategy: Optional[str] = None,
        starred_instrument_ids: Optional[tuple[str, ...] | list[str]] = None,
        arranger_dp_slack_enabled: Optional[bool] = None,
        arranger_budgets: Optional[
            tuple[int, int, int, int]
            | Mapping[str, int]
        ] = None,
        arranger_gp_settings: Optional[
            Mapping[str, object]
        ] = None,
        subhole_settings: Optional[SubholeTransformSettings | Mapping[str, Any]] = None,
        grace_settings: Optional[GraceTransformSettings | Mapping[str, Any]] = None,
        lenient_midi_import: Optional[bool] = None,
    ) -> None:
        with self._state_lock:
            if input_path is not None:
                normalized_path = input_path
                if normalized_path != self.state.input_path:
                    if (
                        self._last_successful_input_snapshot is not None
                        and self._last_successful_input_snapshot.input_path
                        == self.state.input_path
                    ):
                        self._last_successful_input_snapshot = capture_preview_state(
                            self.state, self._pitch_entries
                        )
                    self.state.preview_settings = {}
                    self.state.available_parts = ()
                    self.state.selected_part_ids = ()
                    self.state.arranger_strategy_summary = ()
                    self.state.arranger_result_summary = None
                    self.state.arranger_explanations = ()
                    self.state.arranger_telemetry = ()
                    self.state.pitch_list = []
                    self._pitch_entries = []
                    self._pending_input_confirmation = bool(normalized_path)
                    self.state.midi_import_report = None
                    self.state.midi_import_error = None
                self.state.input_path = normalized_path
            if prefer_mode is not None:
                self.state.prefer_mode = prefer_mode
            if prefer_flats is not None:
                self.state.prefer_flats = prefer_flats
            if collapse_chords is not None:
                self.state.collapse_chords = collapse_chords
            if favor_lower is not None:
                self.state.favor_lower = favor_lower
            if range_min is not None:
                self.state.range_min = range_min
            if range_max is not None:
                self.state.range_max = range_max
            if transpose_offset is not None:
                self.state.transpose_offset = transpose_offset
            if instrument_id is not None:
                self.state.instrument_id = instrument_id
            if available_parts is not None:
                normalized_parts = normalize_available_parts(available_parts)
                self.state.available_parts = normalized_parts
                if self.state.selected_part_ids:
                    filtered = normalize_selected_part_ids(
                        self.state.selected_part_ids,
                        (part.part_id for part in normalized_parts),
                    )
                    if filtered != self.state.selected_part_ids:
                        self.state.selected_part_ids = filtered
            if selected_part_ids is not None:
                allowed_part_ids = (
                    (part.part_id for part in self.state.available_parts)
                    if self.state.available_parts
                    else None
                )
                self.state.selected_part_ids = normalize_selected_part_ids(
                    selected_part_ids,
                    allowed_part_ids,
                )
            if arranger_mode is not None:
                self.state.arranger_mode = arranger_mode
            if arranger_strategy is not None:
                normalized_strategy = (
                    arranger_strategy
                    if arranger_strategy in ARRANGER_STRATEGIES
                    else DEFAULT_ARRANGER_STRATEGY
                )
                self.state.arranger_strategy = normalized_strategy
            if starred_instrument_ids is not None:
                ordered: list[str] = []
                seen = set()
                for identifier in starred_instrument_ids:
                    if not isinstance(identifier, str):
                        continue
                    if identifier in seen:
                        continue
                    seen.add(identifier)
                    ordered.append(identifier)
                self.state.starred_instrument_ids = tuple(ordered)
            if arranger_dp_slack_enabled is not None:
                self.state.arranger_dp_slack_enabled = bool(arranger_dp_slack_enabled)
            if arranger_budgets is not None:
                self.state.arranger_budgets = normalize_arranger_budgets(arranger_budgets)
            if arranger_gp_settings is not None:
                self.state.arranger_gp_settings = normalize_arranger_gp_settings(
                    arranger_gp_settings,
                    self.state.arranger_gp_settings,
                )
            if grace_settings is not None:
                base_grace = getattr(self.state, "grace_settings", None)
                self.state.grace_settings = normalize_grace_settings(
                    grace_settings,
                    base_grace,
                )
            if subhole_settings is not None:
                base_subhole = getattr(self.state, "subhole_settings", None)
                self.state.subhole_settings = normalize_subhole_settings(
                    subhole_settings,
                    base_subhole,
                )
            if lenient_midi_import is not None:
                self.state.lenient_midi_import = bool(lenient_midi_import)

    def settings(self) -> TransformSettings:
        with self._state_lock:
            return TransformSettings(
                prefer_mode=self.state.prefer_mode,
                range_min=self.state.range_min,
                range_max=self.state.range_max,
                prefer_flats=self.state.prefer_flats,
                collapse_chords=self.state.collapse_chords,
                favor_lower=self.state.favor_lower,
                transpose_offset=self.state.transpose_offset,
                instrument_id=self.state.instrument_id,
                selected_part_ids=self.state.selected_part_ids,
                grace_settings=self.state.grace_settings,
                subhole_settings=self.state.subhole_settings,
                lenient_midi_import=self.state.lenient_midi_import,
            )

    def _midi_import_mode(self) -> str:
        with self._state_lock:
            enabled = bool(getattr(self.state, "lenient_midi_import", True))
        return "auto" if enabled else "strict"

    def update_midi_import_report(self, report: MidiImportReport | None) -> None:
        with self._state_lock:
            self.state.midi_import_report = report

    def update_midi_import_error(self, message: str | None) -> None:
        with self._state_lock:
            self.state.midi_import_error = message

    def load_part_metadata(self) -> tuple[MusicXmlPartInfo, ...]:
        with self._state_lock:
            path = self.state.input_path.strip()
        if not path:
            logger.debug("Skipping part metadata load: no input path set")
            self.update_settings(available_parts=())
            self.update_midi_import_report(None)
            return ()
        parts: tuple[MusicXmlPartInfo, ...] = ()
        midi_mode = self._midi_import_mode()
        try:
            loaded = self._score_service.load_part_metadata(path, midi_mode=midi_mode)
        except Exception as exc:
            logger.exception("Failed to load part metadata", extra={"path": path})
            self.update_midi_import_report(getattr(self._score_service, "last_midi_report", None))
            self.update_midi_import_error(str(exc) or exc.__class__.__name__)
        else:
            parts = tuple(loaded)
            self.update_midi_import_report(getattr(self._score_service, "last_midi_report", None))
            self.update_midi_import_error(None)
        self.update_settings(available_parts=parts)
        with self._state_lock:
            if self.state.available_parts and not self.state.selected_part_ids:
                melody_part_id = select_melody_candidate(self.state.available_parts)
                default_id = melody_part_id or self.state.available_parts[0].part_id
                self.update_settings(selected_part_ids=(default_id,))
            return self.state.available_parts

    def apply_part_selection(self, part_ids: Sequence[str]) -> tuple[str, ...]:
        with self._state_lock:
            allowed = (part.part_id for part in self.state.available_parts)
        normalized = normalize_selected_part_ids(part_ids, allowed)
        self.update_settings(selected_part_ids=normalized)
        confirmed_selection = bool(normalized) or bool(part_ids)
        with self._state_lock:
            if (
                confirmed_selection
                and self.state.midi_import_error is None
            ):
                self._pending_input_confirmation = False
            return self.state.selected_part_ids

    def ask_select_parts(
        self,
        parts: Sequence[MusicXmlPartInfo],
        preselected: Sequence[str],
    ) -> tuple[str, ...] | None:
        chooser = getattr(self._dialogs, "ask_select_parts", None)
        if chooser is None:
            logger.debug("No part selection dialog available; using defaults")
            return tuple(preselected)
        try:
            result = chooser(parts, preselected)
        except Exception:
            logger.exception("Part selection dialog failed")
            return None
        if result is None:
            return None
        return tuple(result)
