"""Instrument layout editor helpers."""

from __future__ import annotations

from typing import Dict

from ocarina_gui.layout_editor import InstrumentLayoutEditor

from ._logger import logger


class InstrumentLayoutMixin:
    _layout_editor_window: InstrumentLayoutEditor | None
    _headless: bool
    status: object

    def open_instrument_layout_editor(self) -> None:
        logger.info("Instrument layout editor requested (headless=%s)", self._headless)
        if self._headless:
            try:
                self.status.set("Layout editor requires a graphical display.")
            except Exception:
                pass
            logger.warning("Instrument layout editor unavailable in headless mode")
            return
        window = self._layout_editor_window
        if window is not None and window.winfo_exists():
            logger.info("Instrument layout editor already open; focusing existing window")
            window.lift()
            window.focus_set()
            return

        def _on_close() -> None:
            self._layout_editor_window = None
            logger.info("Instrument layout editor closed")

        def _on_config_saved(_config: Dict[str, object], current_id: str) -> None:
            logger.info("Instrument layout configuration saved", extra={"instrument_id": current_id})
            self._refresh_fingering_after_layout_save(current_id)

        self._layout_editor_window = InstrumentLayoutEditor(
            self,
            on_close=_on_close,
            on_config_saved=_on_config_saved,
        )
        logger.info("Instrument layout editor window created")
