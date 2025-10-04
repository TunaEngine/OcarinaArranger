from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
import sys
from typing import Deque, Iterable, Union

import pytest

from ocarina_gui import themes
from ocarina_gui.pdf_export.types import PdfExportOptions
from ocarina_gui.preferences import Preferences
from ocarina_gui.preview import PreviewData
from ocarina_gui.fingering import InstrumentChoice
from ocarina_gui.scrolling import AutoScrollMode
from viewmodels.preview_playback_types import NullAudioRenderer
from ui.main_window import MainWindow
from ui.main_window.preview.utilities import PreviewUtilitiesMixin
from viewmodels.main_viewmodel import MainViewModel

from tests.e2e.fakes.file_dialog import FakeFileDialogAdapter
from tests.e2e.fakes.project_service import FakeProjectService
from tests.e2e.fakes.score_service import FakeConversionPlan, FakeScoreService
from tests.e2e.fakes.update_service import FakeUpdateBuilder, FakeUpdateService
from tests.e2e.support.messagebox import MessageboxRecorder


_SKIP_PREFERENCE_RECORDING_ATTR = "_e2e_skip_preference_recording"


@dataclass(slots=True)
class FakeInstrumentSpec:
    instrument_id: str
    name: str
    note_names: tuple[str, ...]
    preferred_range: tuple[str, str]
    note_map: dict[str, list[int]] = field(default_factory=dict)
    preferred_range_min: str = field(init=False)
    preferred_range_max: str = field(init=False)
    candidate_range_min: str = field(init=False)
    candidate_range_max: str = field(init=False)
    note_order: tuple[str, ...] = field(init=False)
    candidate_notes: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "preferred_range_min", self.preferred_range[0])
        object.__setattr__(self, "preferred_range_max", self.preferred_range[1])
        object.__setattr__(self, "candidate_range_min", self.note_names[0])
        object.__setattr__(self, "candidate_range_max", self.note_names[-1])
        object.__setattr__(self, "note_order", self.note_names)
        object.__setattr__(self, "candidate_notes", self.note_names)


class FakeFingeringView:
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN001 - signature compatibility
        self._hole_handler = None
        self._windway_handler = None
        self.displayed_fingerings: list[tuple[str, int]] = []

    def clear(self) -> None:
        self.displayed_fingerings.clear()

    def show_fingering(self, note_name: str, midi: int) -> None:
        self.displayed_fingerings.append((note_name, midi))

    def set_hole_click_handler(self, handler) -> None:  # noqa: ANN001 - tkinter protocol
        self._hole_handler = handler

    def set_windway_click_handler(self, handler) -> None:  # noqa: ANN001 - tkinter protocol
        self._windway_handler = handler


class FakeFingeringGridView:
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN001 - tkinter protocol
        self.notes: tuple[str, ...] = ()

    def set_notes(self, notes, *_args) -> None:  # noqa: ANN001 - tkinter protocol
        self.notes = tuple(notes)


class FakeFingeringLibrary:
    def __init__(self) -> None:
        alto_spec = FakeInstrumentSpec(
            instrument_id="alto_c_12",
            name="Alto C (12-hole)",
            note_names=("C4", "D4", "E4", "F4", "G4"),
            preferred_range=("C4", "G4"),
            note_map={
                "C4": [2, 2, 2, 2],
                "D4": [2, 2, 2, 0],
                "E4": [2, 2, 0, 0],
                "F4": [2, 0, 0, 0],
                "G4": [0, 0, 0, 0],
            },
        )
        tenor_spec = FakeInstrumentSpec(
            instrument_id="alto_c_6",
            name="Alto C (6-hole)",
            note_names=("C4", "D4", "E4", "F4", "G4"),
            preferred_range=("C4", "F4"),
            note_map={
                "C4": [2, 2, 2, 2],
                "D4": [2, 2, 2, 0],
                "E4": [2, 2, 0, 0],
                "F4": [2, 0, 0, 0],
                "G4": [0, 0, 0, 0],
            },
        )
        self._instruments: dict[str, FakeInstrumentSpec] = {
            alto_spec.instrument_id: alto_spec,
            tenor_spec.instrument_id: tenor_spec,
        }
        self._current_id = alto_spec.instrument_id
        self._listeners: list = []

    def get_available_instruments(self) -> list[InstrumentChoice]:
        return [
            InstrumentChoice(instrument_id=spec.instrument_id, name=spec.name)
            for spec in self._instruments.values()
        ]

    def get_instrument(self, instrument_id: str) -> FakeInstrumentSpec:
        if instrument_id not in self._instruments:
            raise ValueError(f"Unknown instrument: {instrument_id}")
        return self._instruments[instrument_id]

    def get_current_instrument_id(self) -> str:
        return self._current_id

    def set_active_instrument(self, instrument_id: str) -> None:
        spec = self.get_instrument(instrument_id)
        if instrument_id == self._current_id:
            return
        self._current_id = instrument_id
        for listener in list(self._listeners):
            listener(spec)

    def register_listener(self, listener) -> callable:  # noqa: ANN001 - interface compatibility
        self._listeners.append(listener)

        def _unsubscribe() -> None:
            try:
                self._listeners.remove(listener)
            except ValueError:
                pass

        return _unsubscribe

    def collect_note_names(self, instrument: FakeInstrumentSpec) -> list[str]:
        return list(instrument.note_names)

    def preferred_window(self, instrument: FakeInstrumentSpec) -> tuple[str, str]:
        return instrument.preferred_range


class ImmediateThread:
    def __init__(self, target=None, args=(), kwargs=None, **_unused) -> None:  # noqa: ANN001
        self._target = target or (lambda: None)
        self._args = args
        self._kwargs = kwargs or {}

    def start(self) -> None:
        self._target(*self._args, **self._kwargs)

    def join(self, timeout: float | None = None) -> None:  # noqa: D401 - compatibility no-op
        return None


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
    fingering_library: FakeFingeringLibrary
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
            self.queue_preview_result(_default_preview_data())

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
        try:
            if self.original_theme_id:
                try:
                    current_id = themes.get_current_theme_id()
                except Exception:
                    current_id = None
                if current_id and current_id != self.original_theme_id:
                    setattr(self.preferences, _SKIP_PREFERENCE_RECORDING_ATTR, True)
                    try:
                        themes.set_active_theme(self.original_theme_id)
                    except Exception:
                        pass
                    finally:
                        if hasattr(self.preferences, _SKIP_PREFERENCE_RECORDING_ATTR):
                            delattr(self.preferences, _SKIP_PREFERENCE_RECORDING_ATTR)
        finally:
            try:
                self.window.destroy()
            except Exception:
                pass


def _default_preview_data() -> PreviewData:
    return PreviewData(
        original_events=[(0, 480, 60, 1)],
        arranged_events=[(0, 480, 72, 1)],
        pulses_per_quarter=480,
        beats=4,
        beat_type=4,
        original_range=(60, 60),
        arranged_range=(72, 72),
        tempo_bpm=96,
    )


def create_e2e_harness(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> E2EHarness:
    dialogs = FakeFileDialogAdapter()
    score_service_double = FakeScoreService()
    conversion_plan = FakeConversionPlan(output_folder=tmp_path / "exports")
    score_service_double.set_conversion_plan(conversion_plan)
    # Preload preview results for auto-render plus follow-up actions
    score_service_double.set_preview_outcomes(
        _default_preview_data() for _ in range(6)
    )

    project_service = FakeProjectService()
    original_theme_id: str | None
    try:
        original_theme_id = themes.get_current_theme_id()
    except Exception:
        original_theme_id = None

    preferences = Preferences(
        auto_scroll_mode=AutoScrollMode.FLIP.value,
        preview_layout_mode="piano_staff",
        auto_update_enabled=False,
        update_channel="stable",
    )
    saved_preferences: list[Preferences] = []
    recorder = MessageboxRecorder()
    opened_paths: list[str] = []
    web_open_calls: list[str] = []
    update_failure_notices: Deque[tuple[str, str]] = deque()
    pdf_options_box = {"value": PdfExportOptions.with_defaults()}

    fingering_library = FakeFingeringLibrary()

    # Messagebox stubs
    from tkinter import messagebox as tk_messagebox

    monkeypatch.setattr(tk_messagebox, "showinfo", recorder.showinfo)
    monkeypatch.setattr(tk_messagebox, "showerror", recorder.showerror)
    monkeypatch.setattr(tk_messagebox, "askyesno", recorder.askyesno)
    monkeypatch.setattr(tk_messagebox, "askyesnocancel", recorder.askyesnocancel)

    # Headless menu support so tests can exercise menu wiring
    from tests.e2e.support.menu import HeadlessMenu

    monkeypatch.setattr("tkinter.Menu", HeadlessMenu)

    import tkinter as tk

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

    for target in [
        "ui.main_window.preview.commands.messagebox",
        "ui.main_window.preview.utilities.messagebox",
        "ui.main_window.menus.project_menu.messagebox",
        "ui.main_window.menus.update_menu.messagebox",
        "ui.main_window.fingering.setup.messagebox",
        "ui.main_window.fingering.events.messagebox",
    ]:
        monkeypatch.setattr(target, tk_messagebox)

    monkeypatch.setattr(
        PreviewUtilitiesMixin,
        "_open_path",
        lambda self, path: opened_paths.append(path),
    )

    # Preferences
    def _clone_preferences(source: object) -> Preferences:
        return Preferences(
            theme_id=getattr(source, "theme_id", None),
            log_verbosity=getattr(source, "log_verbosity", None),
            recent_projects=list(getattr(source, "recent_projects", []) or []),
            auto_scroll_mode=getattr(source, "auto_scroll_mode", None),
            preview_layout_mode=getattr(source, "preview_layout_mode", None),
            auto_update_enabled=getattr(source, "auto_update_enabled", None),
            update_channel=getattr(source, "update_channel", "stable"),
        )

    def save_preferences_stub(updated: object, *_args, **_kwargs) -> None:  # noqa: ANN001
        snapshot = _clone_preferences(updated)
        preferences.theme_id = snapshot.theme_id
        preferences.log_verbosity = snapshot.log_verbosity
        preferences.recent_projects = list(snapshot.recent_projects)
        preferences.auto_scroll_mode = snapshot.auto_scroll_mode
        preferences.preview_layout_mode = snapshot.preview_layout_mode
        preferences.auto_update_enabled = snapshot.auto_update_enabled
        preferences.update_channel = snapshot.update_channel
        if getattr(updated, _SKIP_PREFERENCE_RECORDING_ATTR, False):
            try:
                delattr(updated, _SKIP_PREFERENCE_RECORDING_ATTR)
            except AttributeError:
                pass
            return
        saved_preferences.append(snapshot)

    for target in [
        "ui.main_window.initialisation.load_preferences",
        "ocarina_gui.preferences.load_preferences",
        "ocarina_gui.themes.load_preferences",
    ]:
        monkeypatch.setattr(target, lambda *args, **kwargs: preferences)

    for target in [
        "ocarina_gui.preferences.save_preferences",
        "ui.main_window.menus.auto_scroll.save_preferences",
        "ui.main_window.menus.project_menu.save_preferences",
        "ui.main_window.menus.update_menu.save_preferences",
        "ui.main_window.preview.layout.save_preferences",
        "ocarina_gui.themes.save_preferences",
    ]:
        monkeypatch.setattr(target, save_preferences_stub)

    # Update service builder and failure notices
    default_update_service = FakeUpdateService(name="stable")
    update_builder = FakeUpdateBuilder(default_service=default_update_service)
    update_builder.register("stable", default_update_service)

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

    # Fingering library
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
        monkeypatch.setattr(target, FakeFingeringView)

    for target in [
        "ocarina_gui.fingering.FingeringGridView",
        "ui.main_window.initialisation.FingeringGridView",
        "ui.main_window.fingering.FingeringGridView",
    ]:
        monkeypatch.setattr(target, FakeFingeringGridView)

    # Logging and audio stubs
    monkeypatch.setattr(
        "ui.main_window.initialisation.ensure_app_logging",
        lambda: tmp_path / "ocarina.log",
    )
    monkeypatch.setattr(
        "ocarina_gui.audio.build_preview_audio_renderer",
        lambda: NullAudioRenderer(),
    )

    def _force_headless(self) -> bool:
        import tkinter as tk

        tk.Tk.__init__(self, useTk=False)
        return True

    monkeypatch.setattr(
        "ui.main_window.initialisation.MainWindowInitialisationMixin._initialise_tk_root",
        _force_headless,
    )

    # PDF export dialog
    monkeypatch.setattr(
        "ui.main_window.preview.commands.ask_pdf_export_options",
        lambda _self: pdf_options_box["value"],
    )

    # Web browser interception
    import webbrowser

    def fake_open(url: str, *args, **kwargs) -> bool:  # noqa: ANN001 - compatibility
        web_open_calls.append(url)
        return True

    monkeypatch.setattr(webbrowser, "open", fake_open)

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
