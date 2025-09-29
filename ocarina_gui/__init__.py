from __future__ import annotations

"""Public package interface for the Ocarina GUI."""

from typing import TYPE_CHECKING, Any

from . import themes

# Backwards compatibility: expose exporter helpers at the package root so tests
# and legacy code can continue monkeypatching ocarina_gui.export_musicxml.
from ocarina_tools import export_mxl, export_musicxml

from .pdf_export import export_arranged_pdf

if TYPE_CHECKING:  # pragma: no cover - imported only for type checking
    from .app import App

__all__ = [
    "App",
    "export_musicxml",
    "export_mxl",
    "export_arranged_pdf",
    "themes",
]


def __getattr__(name: str) -> Any:
    """Provide lazy attribute access to avoid import-time cycles."""

    if name == "App":
        from .app import App

        return App
    raise AttributeError(f"module 'ocarina_gui' has no attribute {name!r}")
