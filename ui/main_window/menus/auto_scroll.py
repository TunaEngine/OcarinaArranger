"""Auto-scroll helpers for :class:`MenuActionsMixin`."""

from __future__ import annotations

import tkinter as tk

from ocarina_gui.preferences import Preferences, save_preferences
from ocarina_gui.scrolling import AutoScrollMode, normalize_auto_scroll_mode

from ._logger import logger


class AutoScrollMixin:
    _auto_scroll_mode_value: str
    _auto_scroll_mode_targets: list[object]
    _auto_scroll_mode: tk.Variable | None
    _preferences: Preferences | None

    def _register_auto_scroll_target(self, roll: object) -> None:
        targets = getattr(self, "_auto_scroll_mode_targets", None)
        if isinstance(targets, list) and roll not in targets:
            targets.append(roll)
        mode_value = getattr(self, "_auto_scroll_mode_value", AutoScrollMode.FLIP.value)
        setter = getattr(roll, "set_auto_scroll_mode", None)
        if callable(setter):
            try:
                setter(mode_value)
            except Exception:
                logger.debug("Failed to apply auto-scroll mode to piano roll", exc_info=True)

    def _apply_auto_scroll_mode(self, mode: object) -> None:
        normalized = normalize_auto_scroll_mode(mode)
        self._auto_scroll_mode_value = normalized.value
        var = getattr(self, "_auto_scroll_mode", None)
        if hasattr(self, "_suspend_auto_scroll_update"):
            suspend_flag = "_suspend_auto_scroll_update"
        else:
            suspend_flag = None
        if isinstance(var, tk.Variable):
            try:
                current_value = var.get()
            except Exception:
                current_value = None
            if current_value != normalized.value:
                if suspend_flag is not None:
                    setattr(self, suspend_flag, True)
                try:
                    var.set(normalized.value)
                finally:
                    if suspend_flag is not None:
                        setattr(self, suspend_flag, False)
        targets = getattr(self, "_auto_scroll_mode_targets", [])
        for roll in targets:
            setter = getattr(roll, "set_auto_scroll_mode", None)
            if callable(setter):
                try:
                    setter(normalized.value)
                except Exception:
                    logger.debug("Failed to update piano roll auto-scroll mode", exc_info=True)
        for attr in ("roll_orig", "roll_arr"):
            roll = getattr(self, attr, None)
            if roll is None:
                continue
            if isinstance(targets, list) and roll not in targets:
                targets.append(roll)
            setter = getattr(roll, "set_auto_scroll_mode", None)
            if callable(setter):
                try:
                    setter(normalized.value)
                except Exception:
                    logger.debug("Failed to update %s auto-scroll mode", attr, exc_info=True)
        if hasattr(self, "_preferences") and isinstance(self._preferences, Preferences):
            self._preferences.auto_scroll_mode = normalized.value
            try:
                save_preferences(self._preferences)
            except Exception:
                logger.debug("Failed to persist auto-scroll preference", exc_info=True)
