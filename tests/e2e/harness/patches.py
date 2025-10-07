from __future__ import annotations

from typing import Callable, Deque

from tests.helpers import require_ttkbootstrap

require_ttkbootstrap()

import pytest

from ocarina_gui.pdf_export.types import PdfExportOptions
from ocarina_gui.preferences import Preferences
from tests.e2e.support.messagebox import MessageboxRecorder

from .fakes import (
    FakeFingeringGridView,
    FakeFingeringLibrary,
    FakeFingeringView,
    ImmediateThread,
)


def install_messagebox_stubs(monkeypatch, recorder: MessageboxRecorder) -> None:
    from tkinter import messagebox as tk_messagebox

    monkeypatch.setattr(tk_messagebox, "showinfo", recorder.showinfo)
    monkeypatch.setattr(tk_messagebox, "showerror", recorder.showerror)
    monkeypatch.setattr(tk_messagebox, "askyesno", recorder.askyesno)
    monkeypatch.setattr(tk_messagebox, "askyesnocancel", recorder.askyesnocancel)

    targets = [
        "ui.main_window.preview.commands.messagebox",
        "ui.main_window.preview.utilities.messagebox",
        "ui.main_window.menus.project_menu.messagebox",
        "ui.main_window.menus.update_menu.messagebox",
        "ui.main_window.fingering.setup.messagebox",
        "ui.main_window.fingering.events.messagebox",
    ]
    for target in targets:
        monkeypatch.setattr(target, tk_messagebox)


def install_menu_stub(monkeypatch) -> None:
    from tests.e2e.support.menu import HeadlessMenu

    monkeypatch.setattr("tkinter.Menu", HeadlessMenu)


def ensure_headless_tk(monkeypatch) -> None:
    import tkinter as tk

    try:
        sentinel = tk.Tk(useTk=False)
    except tk.TclError as exc:
        pytest.skip(f"Tkinter headless interpreter unavailable: {exc}")
    else:
        try:
            sentinel.destroy()
        except Exception:
            pass

    def _configure_stub(self, cnf=None, **kw):  # noqa: ANN001 - Tk compatible signature
        options = {}
        if cnf:
            options.update(cnf)
        options.update(kw)
        menu = options.pop("menu", None)
        if menu is not None:
            setattr(self, "_test_menubar", menu)
        return options

    monkeypatch.setattr(tk.Misc, "configure", _configure_stub)
    monkeypatch.setattr(tk.Misc, "config", _configure_stub)


def install_preview_open_stub(monkeypatch, opened_paths: list[str]) -> None:
    from ui.main_window.preview.utilities import PreviewUtilitiesMixin

    monkeypatch.setattr(
        PreviewUtilitiesMixin,
        "_open_path",
        lambda self, path: opened_paths.append(path),
    )


def install_preference_loaders(monkeypatch, preferences: Preferences) -> None:
    for target in [
        "ui.main_window.initialisation.load_preferences",
        "ocarina_gui.preferences.load_preferences",
        "ocarina_gui.themes.load_preferences",
    ]:
        monkeypatch.setattr(target, lambda *args, **kwargs: preferences)


def install_preference_savers(monkeypatch, save_stub: Callable[[object], None]) -> None:
    for target in [
        "ocarina_gui.preferences.save_preferences",
        "ui.main_window.menus.auto_scroll.save_preferences",
        "ui.main_window.menus.project_menu.save_preferences",
        "ui.main_window.menus.update_menu.save_preferences",
        "ui.main_window.preview.layout.save_preferences",
        "ocarina_gui.themes.save_preferences",
    ]:
        monkeypatch.setattr(target, save_stub)


def install_update_services(
    monkeypatch,
    update_builder,
    update_failure_notices: Deque[tuple[str, str]],
) -> None:
    default_service = update_builder.default_service
    if default_service is not None:
        update_builder.register("stable", default_service)

    monkeypatch.setattr(
        "services.update.builder.build_update_service",
        update_builder.build,
    )
    monkeypatch.setattr(
        "ui.main_window.menus.update_menu.build_update_service",
        update_builder.build,
    )

    def consume_notice() -> tuple[str, str] | None:
        if update_failure_notices:
            return update_failure_notices.popleft()
        return None

    monkeypatch.setattr(
        "services.update.recovery.consume_update_failure_notice",
        consume_notice,
    )
    monkeypatch.setattr(
        "ui.main_window.menus.update_menu.consume_update_failure_notice",
        consume_notice,
    )

    monkeypatch.setattr(
        "ui.main_window.menus.update_menu.threading.Thread",
        ImmediateThread,
    )
    monkeypatch.setattr(
        "ui.main_window.menus.update_menu.sys.platform",
        "win32",
    )


def install_fingering_stubs(
    monkeypatch,
    fingering_library: FakeFingeringLibrary,
    fingering_view_cls: type[FakeFingeringView] = FakeFingeringView,
    fingering_grid_cls: type[FakeFingeringGridView] = FakeFingeringGridView,
) -> None:
    monkeypatch.setattr(
        "ocarina_gui.fingering.get_available_instruments",
        fingering_library.get_available_instruments,
    )
    monkeypatch.setattr(
        "ocarina_gui.fingering.get_current_instrument_id",
        fingering_library.get_current_instrument_id,
    )
    monkeypatch.setattr(
        "ocarina_gui.fingering.get_instrument",
        fingering_library.get_instrument,
    )
    monkeypatch.setattr(
        "ocarina_gui.fingering.set_active_instrument",
        fingering_library.set_active_instrument,
    )
    monkeypatch.setattr(
        "ocarina_gui.fingering.collect_instrument_note_names",
        fingering_library.collect_note_names,
    )
    monkeypatch.setattr(
        "ocarina_gui.fingering.preferred_note_window",
        fingering_library.preferred_window,
    )
    monkeypatch.setattr(
        "ocarina_gui.fingering.register_instrument_listener",
        fingering_library.register_listener,
    )
    monkeypatch.setattr(
        "ui.main_window.instrument_settings.get_available_instruments",
        fingering_library.get_available_instruments,
    )
    monkeypatch.setattr(
        "ui.main_window.instrument_settings.get_current_instrument_id",
        fingering_library.get_current_instrument_id,
    )
    monkeypatch.setattr(
        "ui.main_window.instrument_settings.get_instrument",
        fingering_library.get_instrument,
    )
    monkeypatch.setattr(
        "ui.main_window.instrument_settings.collect_instrument_note_names",
        fingering_library.collect_note_names,
    )
    monkeypatch.setattr(
        "ui.main_window.instrument_settings.preferred_note_window",
        fingering_library.preferred_window,
    )
    monkeypatch.setattr(
        "ui.main_window.fingering.setup.get_available_instruments",
        fingering_library.get_available_instruments,
    )
    monkeypatch.setattr(
        "ui.main_window.fingering.setup.get_current_instrument_id",
        fingering_library.get_current_instrument_id,
    )
    monkeypatch.setattr(
        "ui.main_window.fingering.setup.set_active_instrument",
        fingering_library.set_active_instrument,
    )
    monkeypatch.setattr("ocarina_gui.fingering.load_fingering_config", lambda: {})
    monkeypatch.setattr("ocarina_gui.fingering.save_fingering_config", lambda config: None)

    for target in [
        "ocarina_gui.fingering.FingeringView",
        "ui.main_window.initialisation.FingeringView",
        "ui.main_window.fingering.FingeringView",
        "ui.main_window.preview.playback.FingeringView",
        "ui.main_window.preview.rendering.FingeringView",
    ]:
        monkeypatch.setattr(target, fingering_view_cls)

    for target in [
        "ocarina_gui.fingering.FingeringGridView",
        "ui.main_window.initialisation.FingeringGridView",
        "ui.main_window.fingering.FingeringGridView",
    ]:
        monkeypatch.setattr(target, fingering_grid_cls)


def install_logging_stub(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "ui.main_window.initialisation.ensure_app_logging",
        lambda: tmp_path / "ocarina.log",
    )


def install_audio_stub(monkeypatch) -> None:
    from viewmodels.preview_playback_types import NullAudioRenderer

    monkeypatch.setattr(
        "ocarina_gui.audio.build_preview_audio_renderer",
        lambda: NullAudioRenderer(),
    )


def install_headless_main_window(monkeypatch) -> None:
    def _force_headless(self, themename: str | None = None) -> bool:  # noqa: ARG001
        import tkinter as tk

        tk.Tk.__init__(self, useTk=False)
        return True

    monkeypatch.setattr(
        "ui.main_window.initialisation.MainWindowInitialisationMixin._initialise_tk_root",
        _force_headless,
    )


def install_pdf_export_stub(
    monkeypatch,
    pdf_options_box: dict[str, PdfExportOptions],
) -> None:
    monkeypatch.setattr(
        "ui.main_window.preview.commands.ask_pdf_export_options",
        lambda _self: pdf_options_box["value"],
    )


def install_webbrowser_stub(monkeypatch, web_open_calls: list[str]) -> None:
    import webbrowser

    def fake_open(url: str, *args, **kwargs) -> bool:  # noqa: ANN001 - compatibility
        web_open_calls.append(url)
        return True

    monkeypatch.setattr(webbrowser, "open", fake_open)


__all__ = [
    "install_messagebox_stubs",
    "install_menu_stub",
    "ensure_headless_tk",
    "install_preview_open_stub",
    "install_preference_loaders",
    "install_preference_savers",
    "install_update_services",
    "install_fingering_stubs",
    "install_logging_stub",
    "install_audio_stub",
    "install_headless_main_window",
    "install_pdf_export_stub",
    "install_webbrowser_stub",
]
