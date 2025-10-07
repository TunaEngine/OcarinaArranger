from __future__ import annotations

from ocarina_gui.headless import build_headless_ui
from ocarina_gui.ui_builders import build_ui


class UIBuildMixin:
    """Bridge to the UI builder implementations."""

    def _build_ui(self) -> None:
        if self._headless:
            build_headless_ui(self)
        else:
            build_ui(self)


__all__ = ["UIBuildMixin"]
