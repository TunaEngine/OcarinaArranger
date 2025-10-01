from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from ocarina_gui.preferences import Preferences
from services.update import ReleaseInfo


@dataclass
class _FakeUpdateService:
    release: ReleaseInfo | None
    installs: list[ReleaseInfo]

    def get_available_release(self) -> ReleaseInfo | None:
        return self.release

    def download_and_install(self, release: ReleaseInfo) -> None:
        self.installs.append(release)


class _ImmediateThread:
    def __init__(self, *, target, args=(), kwargs=None, **unused):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self) -> None:
        self._target(*self._args, **self._kwargs)


def _install_thread_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ui.main_window.menus.update_menu.threading.Thread",
        lambda *a, **k: _ImmediateThread(*a, **k),
    )


def test_setup_auto_update_menu_reports_previous_failure(
    gui_app, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    install_root = tmp_path / "OcarinaArranger_1.1.1"
    install_root.mkdir()
    marker_path = install_root.parent / f"{install_root.name}.update_failed.json"
    payload = {
        "reason": "Cannot move item because the item is in use.",
        "advice": "Close File Explorer and try again.",
    }
    marker_path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setenv("OCARINA_UPDATE_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(sys, "platform", "win32", raising=False)

    errors: list[tuple[str, str]] = []

    def _record_error(title: str, message: str, parent=None):  # type: ignore[override]
        errors.append((title, message))

    monkeypatch.setattr(
        "ui.main_window.menus.update_menu.messagebox.showerror",
        _record_error,
    )

    preferences = gui_app._preferences if isinstance(getattr(gui_app, "_preferences", None), Preferences) else Preferences()

    gui_app._setup_auto_update_menu(preferences)

    assert errors
    title, message = errors[-1]
    assert "update" in title.lower()
    assert payload["reason"] in message
    assert payload["advice"] in message
    assert not marker_path.exists()

    gui_app._setup_auto_update_menu(preferences)
    assert len(errors) == 1


def test_auto_update_toggle_updates_preferences(gui_app, monkeypatch):
    saved_states: list[bool] = []

    def fake_save(preferences, path=None):  # type: ignore[unused-argument]
        saved_states.append(bool(preferences.auto_update_enabled))

    monkeypatch.setattr(
        "ui.main_window.menus.update_menu.save_preferences",
        fake_save,
    )

    var = getattr(gui_app, "_auto_update_enabled_var", None)
    assert var is not None
    assert bool(var.get()) is False
    assert gui_app.auto_update_enabled is False

    var.set(True)
    gui_app._on_auto_update_toggled()

    assert gui_app.auto_update_enabled is True
    assert gui_app._preferences.auto_update_enabled is True
    assert saved_states[-1] is True

    var.set(False)
    gui_app._on_auto_update_toggled()

    assert gui_app.auto_update_enabled is False
    assert gui_app._preferences.auto_update_enabled is False
    assert saved_states[-1] is False


def test_manual_update_check_prompts_before_install(gui_app, monkeypatch):
    _install_thread_stub(monkeypatch)
    monkeypatch.setattr(sys, "platform", "win32", raising=False)

    release = ReleaseInfo(
        version="9.9.9",
        asset_name="OcarinaArranger-windows.zip",
        release_notes="Bug fixes and polish.",
    )
    installs: list[ReleaseInfo] = []
    service = _FakeUpdateService(release, installs)

    monkeypatch.setattr(
        "ui.main_window.menus.update_menu.build_update_service",
        lambda installer=None: service,
    )

    prompts: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "ui.main_window.menus.update_menu.messagebox.askyesno",
        lambda title, message, parent=None: prompts.append((title, message)) or False,
    )

    infos: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "ui.main_window.menus.update_menu.messagebox.showinfo",
        lambda title, message, parent=None: infos.append((title, message)),
    )

    gui_app._check_for_updates_command()

    assert prompts
    _, prompt_message = prompts[-1]
    assert "release notes" in prompt_message.lower()
    assert "bug fixes" in prompt_message.lower()
    assert installs == []
    assert infos == []
    assert getattr(gui_app, "_update_check_in_progress", False) is False


def test_manual_update_check_installs_when_confirmed(gui_app, monkeypatch):
    _install_thread_stub(monkeypatch)
    monkeypatch.setattr(sys, "platform", "win32", raising=False)

    release = ReleaseInfo(
        version="2.1.0",
        asset_name="OcarinaArranger-windows.zip",
        release_notes="First line\nSecond line",
    )
    installs: list[ReleaseInfo] = []
    service = _FakeUpdateService(release, installs)

    monkeypatch.setattr(
        "ui.main_window.menus.update_menu.build_update_service",
        lambda installer=None: service,
    )

    prompts: list[tuple[str, str]] = []

    def _accept(*args, **kwargs):
        prompts.append((args[0], args[1]))
        return True

    monkeypatch.setattr(
        "ui.main_window.menus.update_menu.messagebox.askyesno",
        _accept,
    )

    infos: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "ui.main_window.menus.update_menu.messagebox.showinfo",
        lambda title, message, parent=None: infos.append((title, message)),
    )

    gui_app._check_for_updates_command()

    assert installs == [release]
    assert prompts
    _, prompt_message = prompts[-1]
    assert "release notes" in prompt_message.lower()
    assert "first line" in prompt_message.lower()
    assert any("Downloading" in message for _, message in infos)


def test_manual_update_check_reports_latest_when_no_release(gui_app, monkeypatch):
    _install_thread_stub(monkeypatch)
    monkeypatch.setattr(sys, "platform", "win32", raising=False)

    installs: list[ReleaseInfo] = []
    service = _FakeUpdateService(None, installs)

    monkeypatch.setattr(
        "ui.main_window.menus.update_menu.build_update_service",
        lambda installer=None: service,
    )

    infos: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "ui.main_window.menus.update_menu.messagebox.showinfo",
        lambda title, message, parent=None: infos.append((title, message)),
    )

    gui_app._check_for_updates_command()

    assert installs == []
    assert infos
    title, message = infos[-1]
    assert "latest" in message.lower()


def test_release_notes_prompt_truncation(gui_app):
    notes = "\n".join(f"Line {index}" for index in range(40))
    release = ReleaseInfo(
        version="3.0.0",
        asset_name="OcarinaArranger-windows.zip",
        release_notes=notes,
    )

    message = gui_app._build_update_prompt_message(release)

    assert "Release notes" in message
    assert "Line 0" in message
    assert "Line 39" not in message
    assert message.strip().endswith("…")


def test_manual_update_check_shows_info_on_non_windows(gui_app, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux", raising=False)

    infos: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "ui.main_window.menus.update_menu.messagebox.showinfo",
        lambda title, message, parent=None: infos.append((title, message)),
    )

    gui_app._check_for_updates_command()

    assert infos
    title, message = infos[-1]
    assert "windows" in message.lower()


def test_start_automatic_update_check_skips_when_disabled(gui_app, monkeypatch):
    var = getattr(gui_app, "_auto_update_enabled_var", None)
    if var is not None:
        var.set(False)

    invoked: list[None] = []

    def _fail(*args, **kwargs):  # pragma: no cover - defensive guard
        invoked.append(None)
        return None

    monkeypatch.setattr(
        "ui.main_window.menus.update_menu.build_update_service",
        _fail,
    )

    gui_app.start_automatic_update_check()

    assert invoked == []


def test_start_automatic_update_check_prompts(gui_app, monkeypatch):
    _install_thread_stub(monkeypatch)
    monkeypatch.setattr(sys, "platform", "win32", raising=False)

    var = getattr(gui_app, "_auto_update_enabled_var", None)
    if var is not None:
        var.set(True)

    release = ReleaseInfo(
        version="4.0.0",
        asset_name="OcarinaArranger-windows.zip",
        release_notes="Latest improvements",
    )
    installs: list[ReleaseInfo] = []
    service = _FakeUpdateService(release, installs)

    monkeypatch.setattr(
        "ui.main_window.menus.update_menu.build_update_service",
        lambda installer=None: service,
    )

    prompts: list[str] = []
    monkeypatch.setattr(
        "ui.main_window.menus.update_menu.messagebox.askyesno",
        lambda *args, **kwargs: prompts.append(args[1]) or False,
    )

    gui_app.start_automatic_update_check()

    assert prompts
    assert "latest improvements" in prompts[-1].lower()
    assert installs == []
    assert getattr(gui_app, "_update_check_in_progress", False) is False
