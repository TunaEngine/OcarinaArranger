from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Deque

from tests.helpers import require_ttkbootstrap

require_ttkbootstrap()

import pytest

from ocarina_gui import themes
from ocarina_gui.pdf_export.types import PdfExportOptions
from tests.e2e.fakes.file_dialog import FakeFileDialogAdapter
from tests.e2e.fakes.project_service import FakeProjectService
from tests.e2e.fakes.score_service import FakeConversionPlan, FakeScoreService
from tests.e2e.fakes.update_service import FakeUpdateBuilder, FakeUpdateService
from tests.e2e.support.messagebox import MessageboxRecorder
from ui.main_window import MainWindow
from viewmodels.main_viewmodel import MainViewModel

from .fakes import FakeFingeringLibrary
from .patches import (
    ensure_headless_tk,
    install_audio_stub,
    install_fingering_stubs,
    install_headless_main_window,
    install_logging_stub,
    install_menu_stub,
    install_messagebox_stubs,
    install_pdf_export_stub,
    install_preference_loaders,
    install_preference_savers,
    install_preview_open_stub,
    install_update_services,
    install_webbrowser_stub,
)
from .preferences import build_preferences, create_save_preferences_stub
from .preview import default_preview_data
from .types import E2EHarness


def _prepare_score_service(tmp_path: Path) -> FakeScoreService:
    score_service = FakeScoreService()
    conversion_plan = FakeConversionPlan(output_folder=tmp_path / "exports")
    score_service.set_conversion_plan(conversion_plan)
    score_service.set_preview_outcomes(default_preview_data() for _ in range(6))
    return score_service


def _capture_original_theme() -> str | None:
    try:
        return themes.get_current_theme_id()
    except Exception:
        return None


def create_e2e_harness(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> E2EHarness:
    dialogs = FakeFileDialogAdapter()
    score_service_double = _prepare_score_service(tmp_path)
    project_service = FakeProjectService()
    original_theme_id = _capture_original_theme()

    preferences = build_preferences()
    saved_preferences: list = []
    recorder = MessageboxRecorder()
    opened_paths: list[str] = []
    web_open_calls: list[str] = []
    update_failure_notices: Deque[tuple[str, str]] = deque()
    pdf_options_box = {"value": PdfExportOptions.with_defaults()}
    fingering_library = FakeFingeringLibrary()

    install_messagebox_stubs(monkeypatch, recorder)
    install_menu_stub(monkeypatch)
    ensure_headless_tk(monkeypatch)
    install_preview_open_stub(monkeypatch, opened_paths)

    install_preference_loaders(monkeypatch, preferences)
    save_preferences_stub = create_save_preferences_stub(preferences, saved_preferences)
    install_preference_savers(monkeypatch, save_preferences_stub)

    default_update_service = FakeUpdateService(name="stable")
    update_builder = FakeUpdateBuilder(default_service=default_update_service)
    install_update_services(monkeypatch, update_builder, update_failure_notices)

    install_fingering_stubs(monkeypatch, fingering_library)
    install_logging_stub(monkeypatch, tmp_path)
    install_audio_stub(monkeypatch)
    install_headless_main_window(monkeypatch)
    install_pdf_export_stub(monkeypatch, pdf_options_box)
    install_webbrowser_stub(monkeypatch, web_open_calls)

    viewmodel = MainViewModel(
        dialogs=dialogs,
        score_service=score_service_double.as_service(),
        project_service=project_service,
    )
    window = MainWindow(viewmodel=viewmodel)
    window._build_menus()
    window.withdraw()
    window.update_idletasks()
    window._cancel_playback_loop()

    return E2EHarness(
        window=window,
        viewmodel=viewmodel,
        dialogs=dialogs,
        score_service=score_service_double,
        project_service=project_service,
        update_builder=update_builder,
        messagebox=recorder,
        opened_paths=opened_paths,
        preferences=preferences,
        saved_preferences=saved_preferences,
        web_open_calls=web_open_calls,
        fingering_library=fingering_library,
        update_failure_notices=update_failure_notices,
        _pdf_options_box=pdf_options_box,
        original_theme_id=original_theme_id,
    )
