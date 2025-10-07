from __future__ import annotations

from adapters.file_dialog import FileDialogAdapter
from services.score_service import ScoreService

from viewmodels.main_viewmodel import MainViewModel


class ViewModelFactoryMixin:
    """Factory helper for building the main view-model."""

    @staticmethod
    def _build_viewmodel(
        dialogs: FileDialogAdapter, score_service: ScoreService
    ) -> MainViewModel:
        return MainViewModel(dialogs=dialogs, score_service=score_service)


__all__ = ["ViewModelFactoryMixin"]
