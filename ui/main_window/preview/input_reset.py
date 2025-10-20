from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


class PreviewInputResetMixin:
    """Helpers for resetting preview state when the source input changes."""

    def _on_input_path_changed(self, *_args: object) -> None:
        if getattr(self, "_suspend_state_sync", False):
            return
        self._preview_auto_rendered = False
        self._pending_preview_data = None
        for side, playback in self._preview_playback.items():
            try:
                playback.stop()
            except Exception:
                logger.debug("Failed to stop preview playback on input change", exc_info=True)
            try:
                previous_volume = float(playback.state.volume)
            except Exception:
                previous_volume = 1.0
            try:
                playback.reset_adjustments()
            except Exception:
                logger.debug("Failed to reset preview playback state", exc_info=True)
            try:
                playback.set_volume(previous_volume)
                self._set_volume_controls_value(side, previous_volume * 100.0)
                self._preview_volume_memory[side] = previous_volume * 100.0
                self._update_mute_button_state(side)
            except Exception:
                logger.debug("Failed to restore preview volume after input change", exc_info=True)
            try:
                self._preview_applied_settings.pop(side, None)
                if hasattr(self, "_preview_settings_seeded"):
                    self._preview_settings_seeded.discard(side)
            except Exception:
                pass
            self._sync_preview_playback_controls(side)
            self._update_playback_visuals(side)
            self._update_preview_apply_cancel_state(side)
        try:
            self._viewmodel.update_preview_settings({})
        except Exception:
            logger.debug("Unable to clear stored preview settings", exc_info=True)
        path = self.input_path.get().strip()
        refresh_title = getattr(self, "_refresh_window_title", None)
        if callable(refresh_title):
            refresh_title()
        if hasattr(self, "_update_reimport_button_state"):
            self._update_reimport_button_state()
        if not path or not os.path.exists(path):
            return
        target_tab = self._preview_frame_for_side("arranged")
        self._select_preview_tab("arranged")
        self._auto_render_preview(target_tab)


__all__ = ["PreviewInputResetMixin"]
