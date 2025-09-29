from __future__ import annotations

import importlib
from typing import Optional

from adapters.file_dialog import FileDialogAdapter, TkFileDialogAdapter
from services.score_service import ScoreService
from viewmodels.main_viewmodel import MainViewModel

from ocarina_gui.preview import build_preview_data
from ocarina_tools import export_midi_poly, load_score


def build_default_score_service() -> ScoreService:
    """Construct the default :class:`ScoreService` used by the main window."""

    conversion_module = importlib.import_module("ocarina_gui.conversion")
    gui_pkg = importlib.import_module("ocarina_gui")
    return ScoreService(
        load_score=load_score,
        build_preview_data=build_preview_data,
        convert_score=conversion_module.convert_score,
        export_musicxml=gui_pkg.export_musicxml,
        export_mxl=gui_pkg.export_mxl,
        export_midi=export_midi_poly,
        export_pdf=gui_pkg.export_arranged_pdf,
    )


def resolve_viewmodel(
    viewmodel: Optional[MainViewModel],
    dialogs: Optional[FileDialogAdapter],
    score_service: Optional[ScoreService],
) -> MainViewModel:
    """Return a fully initialised :class:`MainViewModel` for the window.

    Parameters
    ----------
    viewmodel:
        An existing view-model instance.  When provided it is returned as-is.
    dialogs:
        Adapter used for file dialogs.  Defaults to :class:`TkFileDialogAdapter`.
    score_service:
        Service used for score conversion/export.  Defaults to
        :func:`build_default_score_service`.
    """

    if viewmodel is not None:
        return viewmodel

    if dialogs is None:
        dialogs = TkFileDialogAdapter()

    if score_service is None:
        score_service = build_default_score_service()

    return MainViewModel(dialogs=dialogs, score_service=score_service)


__all__ = ["build_default_score_service", "resolve_viewmodel"]
