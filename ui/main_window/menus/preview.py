"""Preview refresh helpers for :class:`MenuActionsMixin`."""

from __future__ import annotations

from ._logger import logger


class PreviewMixin:
    def _mark_preview_stale(self) -> None:
        if not hasattr(self, "_preview_auto_rendered"):
            return
        self._preview_auto_rendered = False
        playback_map = getattr(self, "_preview_playback", {})
        if isinstance(playback_map, dict):
            for side, playback in playback_map.items():
                if playback is None:
                    continue
                try:
                    playback.stop()
                except Exception:
                    logger.debug(
                        "Failed to stop preview playback while refreshing project",
                        exc_info=True,
                    )
                try:
                    self._update_playback_visuals(side)
                except Exception:
                    logger.debug(
                        "Unable to refresh playback visuals while reloading project",
                        exc_info=True,
                    )
                try:
                    self._update_preview_apply_cancel_state(side)
                except Exception:
                    logger.debug(
                        "Unable to reset preview controls after project load",
                        exc_info=True,
                    )
