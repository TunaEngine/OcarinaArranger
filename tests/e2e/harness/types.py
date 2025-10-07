from __future__ import annotations

from dataclasses import dataclass
from typing import Deque, Iterable, Union

from ocarina_gui.pdf_export.types import PdfExportOptions
from ocarina_gui.preferences import Preferences
from ocarina_gui.preview import PreviewData
from ui.main_window import MainWindow
from viewmodels.main_viewmodel import MainViewModel

from tests.e2e.fakes.file_dialog import FakeFileDialogAdapter
from tests.e2e.fakes.project_service import FakeProjectService
from tests.e2e.fakes.score_service import FakeScoreService
from tests.e2e.fakes.update_service import FakeUpdateBuilder, FakeUpdateService
from tests.e2e.support.messagebox import MessageboxRecorder

from .preview import default_preview_data


@dataclass(slots=True)
class E2EHarness:
    window: MainWindow
    viewmodel: MainViewModel
    dialogs: FakeFileDialogAdapter
    score_service: FakeScoreService
    project_service: FakeProjectService
    update_builder: FakeUpdateBuilder
    messagebox: MessageboxRecorder
    opened_paths: list[str]
    preferences: Preferences
    saved_preferences: list[Preferences]
    web_open_calls: list[str]
    fingering_library: object
    update_failure_notices: Deque[tuple[str, str]]
    _pdf_options_box: dict[str, PdfExportOptions]
    original_theme_id: str | None = None
    last_preview_result: object | None = None
    last_conversion_result: object | None = None

    def queue_open_path(self, path: str | None) -> None:
        self.dialogs.queue_open_path(path)

    def queue_save_path(self, path: str | None) -> None:
        self.dialogs.queue_save_path(path)

    def queue_open_project_path(self, path: str | None) -> None:
        self.dialogs.queue_open_project_path(path)

    def queue_save_project_path(self, path: str | None) -> None:
        self.dialogs.queue_save_project_path(path)

    def queue_preview_result(self, preview: PreviewData) -> None:
        self.score_service.queue_preview_result(preview)

    def set_preview_outcomes(
        self, outcomes: Iterable[Union[PreviewData, Exception]]
    ) -> None:
        self.score_service.set_preview_outcomes(list(outcomes))

    def ensure_preview_successes(self, count: int) -> None:
        missing = max(0, count - self.score_service.pending_preview_outcomes())
        for _ in range(missing):
            self.queue_preview_result(default_preview_data())

    def queue_preview_error(self, error: Exception) -> None:
        self.score_service.queue_preview_error(error)

    def queue_conversion_error(self, error: Exception) -> None:
        self.score_service.queue_conversion_error(error)

    def queue_conversion_result(self, result) -> None:  # noqa: ANN001 - conversion protocol
        self.score_service.queue_conversion_result(result)

    def update_service(self, channel: str = "stable") -> FakeUpdateService:
        if channel in self.update_builder.services:
            return self.update_builder.services[channel]
        if channel == "stable" and self.update_builder.default_service is not None:
            return self.update_builder.default_service
        service = FakeUpdateService(name=channel)
        self.update_builder.register(channel, service)
        return service

    def queue_update_failure_notice(self, reason: str, advice: str = "") -> None:
        self.update_failure_notices.append((reason, advice))

    @property
    def pdf_options(self) -> PdfExportOptions:
        return self._pdf_options_box["value"]

    def set_pdf_options(self, options: PdfExportOptions) -> None:
        self._pdf_options_box["value"] = options

    def destroy(self) -> None:
        from ocarina_gui import themes

        from .preferences import clear_unrecorded_flag, mark_preferences_unrecorded

        try:
            if self.original_theme_id:
                try:
                    current_id = themes.get_current_theme_id()
                except Exception:
                    current_id = None
                if current_id and current_id != self.original_theme_id:
                    mark_preferences_unrecorded(self.preferences)
                    try:
                        themes.set_active_theme(self.original_theme_id)
                    except Exception:
                        pass
                    finally:
                        clear_unrecorded_flag(self.preferences)
        finally:
            try:
                self.window.destroy()
            except Exception:
                pass


__all__ = ["E2EHarness"]
