from __future__ import annotations

import logging

from ocarina_gui.preview import PreviewData
from ocarina_gui.preferences import PREVIEW_LAYOUT_MODES, save_preferences

logger = logging.getLogger(__name__)


class PreviewLayoutMixin:
    """Controls preview layout mode changes for the main window."""

    def _on_preview_layout_mode_changed(self, *_args: object) -> None:
        mode = self.preview_layout_mode.get()
        if mode not in PREVIEW_LAYOUT_MODES:
            return
        if getattr(self._preferences, "preview_layout_mode", None) != mode:
            self._preferences.preview_layout_mode = mode
            try:
                save_preferences(self._preferences)
            except Exception:
                logger.warning(
                    "Failed to persist preview layout preference", extra={"mode": mode}
                )
        try:
            self._apply_preview_layout_mode()
        except Exception:
            logger.exception(
                "Failed to apply preview layout mode", extra={"mode": mode}
            )

    def _apply_preview_layout_mode(self) -> None:
        mode = self.preview_layout_mode.get()
        data = getattr(self, "_pending_preview_data", None)
        for side in ("original", "arranged"):
            self._apply_preview_layout_mode_to_side(side, mode=mode, data=data)

    def _apply_preview_layout_mode_to_side(
        self,
        side: str,
        *,
        mode: str | None = None,
        data: PreviewData | None = None,
    ) -> None:
        active_mode = mode or self.preview_layout_mode.get()
        roll = self.roll_orig if side == "original" else self.roll_arr
        staff = self.staff_orig if side == "original" else self.staff_arr
        main = self._preview_main_frames.get(side)

        if roll is not None and hasattr(roll, "set_time_scroll_orientation"):
            try:
                roll.set_time_scroll_orientation("horizontal")
            except Exception:
                logger.debug("Failed to reset piano roll orientation", exc_info=True)
            if active_mode == "piano_vertical":
                try:
                    roll.set_time_scroll_orientation("vertical")
                except Exception:
                    logger.debug(
                        "Unable to set vertical piano roll orientation",
                        exc_info=True,
                        extra={"side": side},
                    )

        target_staff_layout = "wrapped" if active_mode == "staff" else "horizontal"
        if staff is not None and hasattr(staff, "set_layout_mode"):
            try:
                staff.set_layout_mode(target_staff_layout)
            except Exception:
                logger.debug(
                    "Failed to set staff layout mode",
                    exc_info=True,
                    extra={"mode": target_staff_layout, "side": side},
                )
            else:
                if target_staff_layout == "wrapped":
                    ensure_vbar = getattr(staff, "_ensure_vertical_bar_mapped", None)
                    if callable(ensure_vbar):
                        try:
                            ensure_vbar()
                        except Exception:
                            logger.debug(
                                "Unable to guarantee vertical scrollbar mapping",
                                exc_info=True,
                                extra={"side": side},
                            )

        if main is None:
            return

        if active_mode == "piano_staff":
            if roll is not None:
                roll.grid(row=0, column=0, sticky="nsew")
            if staff is not None:
                staff.grid(row=1, column=0, sticky="ew", pady=(6, 0))
            main.grid_rowconfigure(0, weight=1, minsize=0)
            main.grid_rowconfigure(1, weight=0)
        elif active_mode == "piano_vertical":
            if roll is not None and hasattr(roll, "grid"):
                try:
                    roll.grid(row=0, column=0, sticky="nsew")
                except Exception:
                    logger.debug(
                        "Unable to grid piano roll in vertical layout",
                        exc_info=True,
                        extra={"side": side},
                    )
            if staff is not None:
                staff.grid_remove()
            main.grid_rowconfigure(0, weight=1, minsize=0)
            main.grid_rowconfigure(1, weight=0, minsize=0)
        elif active_mode == "staff":
            if roll is not None:
                roll.grid_remove()
            if staff is not None:
                staff.grid(row=0, column=0, sticky="nsew")
                try:
                    staff.update_idletasks()
                except Exception:
                    pass
            main.grid_rowconfigure(0, weight=1, minsize=0)
            main.grid_rowconfigure(1, weight=0, minsize=0)

        if data is not None and hasattr(self, "_apply_preview_data_for_side"):
            try:
                self._apply_preview_data_for_side(side, data)
            except Exception:
                logger.debug(
                    "Failed to refresh preview after layout change",
                    exc_info=True,
                    extra={"side": side, "mode": active_mode},
                )


__all__ = ["PreviewLayoutMixin"]
