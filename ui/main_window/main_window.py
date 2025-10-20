from __future__ import annotations
import tkinter as tk

from adapters.file_dialog import FileDialogAdapter
from services.score_service import ScoreService

from ocarina_gui.preferences import (
    ARRANGER_MODES,
    DEFAULT_ARRANGER_MODE,
    Preferences,
)
from ocarina_gui.scrolling import normalize_auto_scroll_mode
from ocarina_gui.themes import get_current_theme
from shared.ttk import ttk
from viewmodels.main_viewmodel import MainViewModel

from ui.main_window.fingering import FingeringEditorMixin
from ui.main_window.initialisation import MainWindowInitialisationMixin
from ui.main_window.instrument_settings import InstrumentSettingsMixin
from ui.main_window.menus import MenuActionsMixin
from ui.main_window.linux_automation import LinuxAutomationMixin
from ui.main_window.preview import PreviewPlaybackMixin
from ui.main_window.runtime import MainWindowRuntimeMixin
from ui.main_window.state_sync import MainWindowStateSyncMixin

from .dependencies import resolve_viewmodel


if hasattr(ttk, "Window"):
    _TkBase = ttk.Window  # type: ignore[attr-defined]
else:
    _TkBase = tk.Tk


class MainWindow(
    MenuActionsMixin,
    FingeringEditorMixin,
    PreviewPlaybackMixin,
    InstrumentSettingsMixin,
    MainWindowStateSyncMixin,
    MainWindowRuntimeMixin,
    LinuxAutomationMixin,
    MainWindowInitialisationMixin,
    _TkBase,
):
    """Tk-based desktop application for arranging scores for Alto C ocarina."""

    def __init__(
        self,
        *,
        viewmodel: MainViewModel | None = None,
        dialogs: FileDialogAdapter | None = None,
        score_service: ScoreService | None = None,
    ) -> None:
        preferences = self._initialise_preferences()
        initial_auto_scroll_mode = normalize_auto_scroll_mode(
            getattr(preferences, "auto_scroll_mode", None)
        )
        current_theme = get_current_theme()

        self._headless = self._initialise_tk_root(current_theme.ttk_theme)

        self._viewmodel = resolve_viewmodel(viewmodel, dialogs, score_service)
        state = self._viewmodel.state

        selected_mode = DEFAULT_ARRANGER_MODE
        if isinstance(preferences, Preferences):
            stored_mode = getattr(preferences, "arranger_mode", None)
            if isinstance(stored_mode, str) and stored_mode in ARRANGER_MODES:
                selected_mode = stored_mode
        state.arranger_mode = selected_mode

        lenient_import = True
        if isinstance(preferences, Preferences):
            stored_lenient = getattr(preferences, "lenient_midi_import", None)
            if isinstance(stored_lenient, bool):
                lenient_import = stored_lenient
        state.lenient_midi_import = lenient_import

        if isinstance(preferences, Preferences):
            stored_instrument = getattr(preferences, "instrument_id", None)
            if isinstance(stored_instrument, str):
                normalized_instrument = stored_instrument.strip()
                if normalized_instrument:
                    state.instrument_id = normalized_instrument

        self._setup_instrument_attributes(state)
        self._create_convert_controls(state)
        self._setup_theme_support(preferences, current_theme)
        self._setup_auto_update_menu(preferences)
        self._setup_fingering_defaults()
        self._setup_preview_state(preferences, initial_auto_scroll_mode)
        self._setup_recent_projects(preferences)
        self._configure_main_window_shell()
        self._initialise_preview_references()

        self._build_ui()
        self._apply_preview_layout_mode()
        if self._headless:
            self._preview_tab_initialized.update({"original", "arranged"})
        else:
            self._apply_theme(get_current_theme())
            self._schedule_playback_loop()

        self._input_path_trace_id = self.input_path.trace_add(
            "write", self._on_input_path_changed
        )
        self._transpose_trace_id = self.transpose_offset.trace_add(
            "write", self._on_transpose_value_changed
        )

        self._setup_linux_automation()


__all__ = ["MainWindow"]
