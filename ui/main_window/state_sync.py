from __future__ import annotations

from ocarina_gui.constants import DEFAULT_MAX, DEFAULT_MIN
from ocarina_gui.preferences import DEFAULT_ARRANGER_MODE
from viewmodels.arranger_models import ArrangerBudgetSettings, ArrangerGPSettings
from viewmodels.main_viewmodel import DEFAULT_ARRANGER_STRATEGY


class MainWindowStateSyncMixin:
    """Synchronise controls from the :class:`viewmodels.main_viewmodel.MainViewModel`."""

    def _sync_controls_from_state(self) -> None:
        state = self._viewmodel.state
        self._suspend_state_sync = True
        try:
            self.input_path.set(state.input_path)
            self.prefer_mode.set(state.prefer_mode)
            self.prefer_flats.set(bool(state.prefer_flats))
            self.collapse_chords.set(bool(state.collapse_chords))
            self.favor_lower.set(bool(state.favor_lower))
            self.range_min.set(state.range_min or DEFAULT_MIN)
            self.range_max.set(state.range_max or DEFAULT_MAX)
            self._suppress_arranger_mode_trace = True
            try:
                self.arranger_mode.set(state.arranger_mode or DEFAULT_ARRANGER_MODE)
            finally:
                self._suppress_arranger_mode_trace = False
            if hasattr(self, "arranger_strategy"):
                self._suppress_arranger_strategy_trace = True
                try:
                    self.arranger_strategy.set(
                        getattr(state, "arranger_strategy", DEFAULT_ARRANGER_STRATEGY)
                        or DEFAULT_ARRANGER_STRATEGY
                    )
                finally:
                    self._suppress_arranger_strategy_trace = False
            if hasattr(self, "arranger_dp_slack"):
                self._suspend_arranger_dp_trace = True
                try:
                    self.arranger_dp_slack.set(
                        bool(getattr(state, "arranger_dp_slack_enabled", False))
                    )
                finally:
                    self._suspend_arranger_dp_trace = False
            applied_offset = int(state.transpose_offset)
            self._transpose_applied_offset = applied_offset
            self._suspend_transpose_update = True
            try:
                self.transpose_offset.set(applied_offset)
            finally:
                self._suspend_transpose_update = False
            instrument_id = state.instrument_id or ""
            if instrument_id and instrument_id != self._selected_instrument_id:
                set_fingering = getattr(self, "set_fingering_instrument", None)
                if callable(set_fingering):
                    set_fingering(instrument_id, update_range=False)
                else:
                    handler = getattr(self, "_on_library_instrument_changed", None)
                    if callable(handler):
                        handler(instrument_id, update_range=False)
            else:
                name = self._instrument_name_by_id.get(instrument_id, "")
                self.convert_instrument_var.set(name)
                self._selected_instrument_id = instrument_id
            if hasattr(self, "_sync_starred_instruments_from_state"):
                try:
                    self._sync_starred_instruments_from_state(
                        getattr(state, "starred_instrument_ids", ())
                    )
                except Exception:
                    pass
            if hasattr(self, "_sync_arranger_budgets_from_state"):
                try:
                    budgets = getattr(state, "arranger_budgets", ArrangerBudgetSettings())
                    self._sync_arranger_budgets_from_state(budgets)
                except Exception:
                    pass
            if hasattr(self, "_sync_arranger_gp_from_state"):
                try:
                    gp_settings = getattr(state, "arranger_gp_settings", ArrangerGPSettings())
                    self._sync_arranger_gp_from_state(gp_settings)
                except Exception:
                    pass
            if hasattr(self, "_sync_grace_settings_from_state"):
                try:
                    grace_settings = getattr(state, "grace_settings", None)
                    self._sync_grace_settings_from_state(grace_settings)
                except Exception:
                    pass
        finally:
            self._suspend_state_sync = False
        self.status.set(state.status_message)
        self.pitch_list = list(state.pitch_list)
        self._record_preview_import()
        preview_settings = getattr(state, "preview_settings", {})
        for side, snapshot in preview_settings.items():
            if snapshot is None:
                continue
            if not hasattr(snapshot, "tempo_bpm"):
                continue
            self._apply_preview_snapshot(side, snapshot)
        if hasattr(self, "_render_arranger_summary"):
            try:
                self._render_arranger_summary()
            except Exception:
                pass
        if hasattr(self, "_refresh_arranger_results_from_state"):
            try:
                self._refresh_arranger_results_from_state()
            except Exception:
                pass
        refresh = getattr(self, "_update_arranger_mode_layout", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass
        advanced_refresh = getattr(self, "_update_arranger_advanced_visibility", None)
        if callable(advanced_refresh):
            try:
                advanced_refresh()
            except Exception:
                pass


__all__ = ["MainWindowStateSyncMixin"]
