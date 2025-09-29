from __future__ import annotations

from ocarina_gui.constants import DEFAULT_MAX, DEFAULT_MIN


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
            applied_offset = int(state.transpose_offset)
            self._transpose_applied_offset = applied_offset
            self._suspend_transpose_update = True
            try:
                self.transpose_offset.set(applied_offset)
            finally:
                self._suspend_transpose_update = False
            instrument_id = state.instrument_id or ""
            if instrument_id and instrument_id != self._selected_instrument_id:
                self._on_library_instrument_changed(instrument_id, update_range=False)
            else:
                name = self._instrument_name_by_id.get(instrument_id, "")
                self.convert_instrument_var.set(name)
                self._selected_instrument_id = instrument_id
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


__all__ = ["MainWindowStateSyncMixin"]
