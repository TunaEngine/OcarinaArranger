from __future__ import annotations

from pathlib import Path
from typing import Callable

from tests.helpers import require_ttkbootstrap

require_ttkbootstrap()

from pytest_bdd import given, parsers, then, when

from services.project_service import ProjectPersistenceError

from tests.e2e.harness import E2EHarness
from tests.e2e.support.menu import invoke_menu_path, list_menu_entries, set_menu_command


@when("the user saves the project")
def save_project(arranger_app: E2EHarness) -> None:
    invoke_menu_path(arranger_app.window, "File", "Save Project...")


@when("the user loads the project")
def load_project(arranger_app: E2EHarness) -> None:
    invoke_menu_path(arranger_app.window, "File", "Open Project...")


@when("the user loads the most recent project from the File menu")
def load_recent_project(arranger_app: E2EHarness) -> None:
    recent_labels = list_menu_entries(arranger_app.window, "File", "Open Recent")
    if not recent_labels:
        raise AssertionError("Recent projects menu was empty")
    for label in recent_labels:
        if label:
            invoke_menu_path(arranger_app.window, "File", "Open Recent", label)
            return
    raise AssertionError("No selectable recent projects were present")


@when("the user exits the application from the File menu")
def exit_via_menu(arranger_app: E2EHarness) -> None:
    window = arranger_app.window
    window._destroyed_via_menu = False
    previous_command: Callable[[], None] | None = None

    def _tracking_destroy() -> None:
        window._destroyed_via_menu = True
        if callable(previous_command):
            previous_command()

    previous_command = set_menu_command(window, "File", "Exit", command=_tracking_destroy)
    try:
        invoke_menu_path(window, "File", "Exit")
    finally:
        set_menu_command(window, "File", "Exit", command=previous_command)


@when(parsers.parse('the project service will fail to save with "{message}"'))
def project_save_failure(arranger_app: E2EHarness, message: str) -> None:
    arranger_app.project_service.queue_save_result(ProjectPersistenceError(message))


@given(parsers.parse('loading the project will fail with "{message}"'))
def project_load_failure(arranger_app: E2EHarness, message: str) -> None:
    arranger_app.project_service.queue_load_result(ProjectPersistenceError(message))


@then(parsers.parse('the project service saved to "{filename}"'))
def project_saved_to(arranger_app: E2EHarness, tmp_path: Path, filename: str) -> None:
    expected = tmp_path / filename
    assert arranger_app.project_service.save_calls, "Project save was not attempted"
    assert arranger_app.project_service.save_calls[-1].destination == expected


@then("no project saves were attempted")
def no_project_saves(arranger_app: E2EHarness) -> None:
    assert not arranger_app.project_service.save_calls


@then(parsers.parse('the project service loaded from "{filename}"'))
def project_loaded_from(arranger_app: E2EHarness, tmp_path: Path, filename: str) -> None:
    expected = tmp_path / filename
    assert arranger_app.project_service.load_calls, "Project load was not attempted"
    assert arranger_app.project_service.load_calls[-1].path == expected


@then("no project loads were attempted")
def no_project_loads(arranger_app: E2EHarness) -> None:
    assert not arranger_app.project_service.load_calls


@then(parsers.parse('the recent projects list contains "{filename}"'))
def recent_projects_contains(arranger_app: E2EHarness, tmp_path: Path, filename: str) -> None:
    expected = (tmp_path / filename).resolve()
    recorded = {Path(entry).resolve() for entry in arranger_app.preferences.recent_projects}
    assert expected in recorded


@then("the last project load failed")
def last_project_load_failed(arranger_app: E2EHarness) -> None:
    assert arranger_app.window.status.get() == "Project load failed."


@then("the last project save failed")
def last_project_save_failed(arranger_app: E2EHarness) -> None:
    assert arranger_app.window.status.get() == "Project save failed."


@then("the main window destruction sequence ran")
def window_destroyed(arranger_app: E2EHarness) -> None:
    window = arranger_app.window
    assert getattr(window, "_destroyed_via_menu", False)
    assert getattr(window, "_theme_unsubscribe", None) is None

