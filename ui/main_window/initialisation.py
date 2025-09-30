from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional, Sequence

from adapters.file_dialog import FileDialogAdapter
from services.score_service import ScoreService

from ocarina_gui.audio import build_preview_audio_renderer
from ocarina_gui.constants import APP_TITLE, DEFAULT_MAX, DEFAULT_MIN
from ocarina_gui.headless import build_headless_ui
from ocarina_gui.piano_roll import PianoRoll
from ocarina_gui.preview import Event, PreviewData
from ocarina_gui.preferences import PREVIEW_LAYOUT_MODES, load_preferences
from ocarina_gui.staff import StaffView
from ocarina_gui.themes import ThemeSpec, get_available_themes, get_current_theme, register_theme_listener
from ocarina_gui.fingering import FingeringGridView, FingeringView
from ocarina_gui.ui_builders import build_ui
from shared.logging_config import ensure_app_logging, get_file_log_verbosity
from ui.logging_preferences import LOG_VERBOSITY_CHOICES
from viewmodels.instrument_layout_editor_viewmodel import InstrumentLayoutEditorViewModel
from viewmodels.main_viewmodel import MainViewModel, MainViewModelState
from viewmodels.preview_playback_viewmodel import PreviewPlaybackViewModel

from ui.main_window.tk_support import collect_tk_variables_from_attrs, release_tracked_tk_variables

logger = logging.getLogger(__name__)


class MainWindowInitialisationMixin:
    """Helper methods for initialising :class:`ui.main_window.MainWindow`."""

    def _initialise_preferences(self) -> object:
        self._log_path = ensure_app_logging()
        preferences = load_preferences()
        self._preferences = preferences
        return preferences

    def _initialise_tk_root(self) -> bool:
        try:
            super().__init__()
        except tk.TclError:
            super().__init__(useTk=False)
            return True
        return False

    def _setup_instrument_attributes(self, state: MainViewModelState) -> None:
        self._instrument_name_by_id: Dict[str, str] = {}
        self._instrument_id_by_name: Dict[str, str] = {}
        self._instrument_display_names: List[str] = []
        self._range_note_options: list[str] = []
        self._convert_instrument_combo: Optional[ttk.Combobox] = None
        self._range_min_combo: Optional[ttk.Combobox] = None
        self._range_max_combo: Optional[ttk.Combobox] = None
        self._suspend_instrument_updates = False
        self._selected_instrument_id = ""
        self._initialize_instrument_state(state)

    def _create_convert_controls(self, state: MainViewModelState) -> None:
        self.input_path = tk.StringVar(master=self, value=state.input_path)
        self.prefer_mode = tk.StringVar(master=self, value=state.prefer_mode)
        self.prefer_flats = tk.BooleanVar(master=self, value=state.prefer_flats)
        self.collapse_chords = tk.BooleanVar(master=self, value=state.collapse_chords)
        self.favor_lower = tk.BooleanVar(master=self, value=state.favor_lower)
        self.transpose_offset = tk.IntVar(master=self, value=state.transpose_offset)
        self.convert_instrument_var = tk.StringVar(
            master=self,
            value=self._instrument_name_by_id.get(self._selected_instrument_id, ""),
        )
        self.range_min = tk.StringVar(master=self, value=state.range_min or DEFAULT_MIN)
        self.range_max = tk.StringVar(master=self, value=state.range_max or DEFAULT_MAX)
        self.status = tk.StringVar(master=self, value=state.status_message)
        self._reimport_button: ttk.Button | None = None
        self._last_imported_path: str | None = None
        self._last_import_settings: dict[str, object] = {}
        self._convert_setting_traces: list[tuple[tk.Variable, str]] = []
        self._register_convert_setting_var(self.prefer_mode)
        self._register_convert_setting_var(self.prefer_flats)
        self._register_convert_setting_var(self.collapse_chords)
        self._register_convert_setting_var(self.favor_lower)
        self._register_convert_setting_var(self.range_min)
        self._register_convert_setting_var(self.range_max)
        self._register_convert_setting_var(self.convert_instrument_var)
        self._register_convert_setting_var(self.transpose_offset)
        if self._selected_instrument_id:
            self._on_library_instrument_changed(
                self._selected_instrument_id, update_range=False
            )

    def _setup_theme_support(self, preferences: object) -> None:
        current_theme = get_current_theme()
        self.theme_id = tk.StringVar(master=self, value=current_theme.theme_id)
        self.theme_name = tk.StringVar(master=self, value=current_theme.name)
        self._theme_choices = get_available_themes()
        self._log_verbosity = tk.StringVar(master=self, value=get_file_log_verbosity().value)
        self._log_verbosity_choices = LOG_VERBOSITY_CHOICES
        self._restore_log_verbosity_preference(preferences)
        self.pitch_list: List[str] = list(self._viewmodel.state.pitch_list)
        self._style: ttk.Style | None = None
        self._theme_unsubscribe: Callable[[], None] | None = register_theme_listener(
            self._apply_theme
        )
        self._theme: ThemeSpec | None = None
        self._theme_actions: Dict[str, Callable[[], None]] = {}
        self._log_menu_actions: Dict[str, Callable[[], None]] = {}
        self._applied_style_maps: Dict[str, List[str]] = {}

    def _setup_fingering_defaults(self) -> None:
        self._fingering_table_style: str | None = None
        self._fingering_heading_lines: int = 1
        self._fingering_heading_font_name: str | None = None
        self._fingering_heading_base_padding: tuple[int, int, int, int] | None = None
        self._fingering_edit_mode: bool = False
        self._fingering_edit_vm: InstrumentLayoutEditorViewModel | None = None
        self._fingering_edit_backup: Dict[str, object] | None = None
        self._fingering_edit_button: Optional[ttk.Button] = None
        self._fingering_cancel_button: Optional[ttk.Button] = None
        self._fingering_cancel_pad: tuple[int, int] | None = None
        self._fingering_edit_controls: Optional[ttk.Frame] = None
        self._fingering_ignore_next_select: bool = False
        self._fingering_last_selected_note: Optional[str] = None
        self._fingering_click_guard_note: Optional[str] = None
        self._fingering_column_hole_index: Dict[str, int] = {}
        self._fingering_display_columns_override: list[str] | None = None
        self._fingering_display_columns: tuple[str, ...] = ()
        self._fingering_column_drag_source: str | None = None
        self._fingering_drop_indicator: tk.Widget | None = None
        self._fingering_drop_indicator_color: str | None = None

    def _setup_preview_state(self, preferences: object, auto_scroll_mode) -> None:
        layout_pref = getattr(preferences, "preview_layout_mode", None)
        if layout_pref not in PREVIEW_LAYOUT_MODES:
            layout_pref = "piano_staff"
        self._preview_layout_value_to_label = {
            "piano_staff": "Piano roll and Staff",
            "piano_vertical": "Only Piano roll - vertical scroll",
            "staff": "Only Staff",
        }
        self._preview_layout_label_to_value = {
            label: value for value, label in self._preview_layout_value_to_label.items()
        }
        self.preview_layout_mode = tk.StringVar(master=self, value=layout_pref)
        self._preview_layout_trace = self.preview_layout_mode.trace_add(
            "write", self._on_preview_layout_mode_changed
        )
        self._preview_main_frames: Dict[str, ttk.Frame] = {}
        self._preview_side_panels: Dict[str, ttk.Frame] = {}
        self._preview_roll_widgets: Dict[str, PianoRoll] = {}
        self._preview_staff_widgets: Dict[str, StaffView] = {}

        def _make_playback_vm() -> PreviewPlaybackViewModel:
            audio = None if self._headless else build_preview_audio_renderer()
            return PreviewPlaybackViewModel(audio_renderer=audio)

        self._preview_playback = {
            "original": _make_playback_vm(),
            "arranged": _make_playback_vm(),
        }
        self._preview_play_vars = {
            "original": tk.StringVar(master=self, value="Play"),
            "arranged": tk.StringVar(master=self, value="Play"),
        }
        self._preview_tempo_vars = {
            "original": tk.DoubleVar(
                master=self, value=self._preview_playback["original"].state.tempo_bpm
            ),
            "arranged": tk.DoubleVar(
                master=self, value=self._preview_playback["arranged"].state.tempo_bpm
            ),
        }
        self._preview_metronome_vars = {
            "original": tk.BooleanVar(
                master=self, value=self._preview_playback["original"].state.metronome_enabled
            ),
            "arranged": tk.BooleanVar(
                master=self, value=self._preview_playback["arranged"].state.metronome_enabled
            ),
        }
        self._auto_scroll_mode_targets: list[object] = []
        self._auto_scroll_mode_value = auto_scroll_mode.value
        self._auto_scroll_mode = tk.StringVar(master=self, value=self._auto_scroll_mode_value)
        self._suspend_auto_scroll_update = False
        self._auto_scroll_mode.trace_add("write", self._on_auto_scroll_mode_changed)
        self._preview_loop_enabled_vars = {
            "original": tk.BooleanVar(
                master=self, value=self._preview_playback["original"].state.loop.enabled
            ),
            "arranged": tk.BooleanVar(
                master=self, value=self._preview_playback["arranged"].state.loop.enabled
            ),
        }
        self._preview_loop_start_vars = {
            "original": tk.DoubleVar(master=self, value=0.0),
            "arranged": tk.DoubleVar(master=self, value=0.0),
        }
        self._preview_loop_end_vars = {
            "original": tk.DoubleVar(master=self, value=0.0),
            "arranged": tk.DoubleVar(master=self, value=0.0),
        }
        self._preview_render_progress_vars = {
            "original": tk.DoubleVar(master=self, value=0.0),
            "arranged": tk.DoubleVar(master=self, value=0.0),
        }
        self._preview_render_progress_labels = {
            "original": tk.StringVar(master=self, value=""),
            "arranged": tk.StringVar(master=self, value=""),
        }
        self._preview_tempo_controls: dict[str, object] = {}
        self._preview_metronome_controls: dict[str, object] = {}
        self._preview_loop_controls: dict[str, tuple[object, ...]] = {}
        self._preview_loop_range_buttons: dict[str, object] = {}
        self._force_autoscroll_once: dict[str, bool] = {"original": False, "arranged": False}
        self._suspend_tempo_update: set[str] = set()
        self._suspend_metronome_update: set[str] = set()
        self._suspend_loop_update: set[str] = set()
        self._tempo_trace_tokens: dict[str, str] = {}
        self._metronome_trace_tokens: dict[str, str] = {}
        self._loop_enabled_trace_tokens: dict[str, str] = {}
        self._loop_start_trace_tokens: dict[str, str] = {}
        self._loop_end_trace_tokens: dict[str, str] = {}
        self._loop_range_first_tick: dict[str, int | None] = {
            "original": None,
            "arranged": None,
        }
        self._loop_range_active: set[str] = set()
        self._preview_apply_buttons: dict[str, ttk.Button] = {}
        self._preview_cancel_buttons: dict[str, ttk.Button] = {}
        self._preview_progress_frames: dict[str, ttk.Frame] = {}
        self._preview_progress_places: dict[str, dict[str, float]] = {}
        self._preview_progress_messages: dict[str, str] = {}
        self._preview_tab_builders: Dict[str, Callable[[], None]] = {}
        self._preview_tab_initialized: set[str] = set()
        self._pending_preview_playback: dict[
            str, tuple[tuple[Event, ...], int, float | None, int, int]
        ] = {}
        self._preview_frames_by_side: Dict[str, ttk.Frame] = {}
        self._preview_sides_by_frame: dict[tk.Widget, str] = {}
        self._pending_preview_data: PreviewData | None = None
        self._input_path_trace_id: str | None = None
        self._preview_applied_settings: dict[str, dict[str, object]] = {}
        self._preview_settings_seeded: set[str] = set()
        self._preview_events: dict[str, tuple[Event, ...]] = {
            "original": (),
            "arranged": (),
        }
        self._preview_event_starts: dict[str, tuple[int, ...]] = {
            "original": (),
            "arranged": (),
        }
        self._preview_hover_midi: dict[str, Optional[int]] = {
            "original": None,
            "arranged": None,
        }
        self._preview_cursor_dragging: dict[str, bool] = {
            "original": False,
            "arranged": False,
        }
        self._preview_initial_loading: set[str] = set()
        self._suppress_preview_error_dialogs = False
        self._bind_preview_render_observers()
        for side, playback in self._preview_playback.items():
            pulses_per_quarter = max(1, playback.state.pulses_per_quarter)
            loop_start = playback.state.loop.start_tick / pulses_per_quarter
            loop_end = playback.state.loop.end_tick / pulses_per_quarter
            self._preview_applied_settings[side] = {
                "tempo": playback.state.tempo_bpm,
                "metronome": playback.state.metronome_enabled,
                "loop_enabled": playback.state.loop.enabled,
                "loop_start": loop_start,
                "loop_end": loop_end,
            }
        for side in ("original", "arranged"):
            tempo_var = self._preview_tempo_vars[side]
            self._tempo_trace_tokens[side] = tempo_var.trace_add(
                "write", lambda *_args, s=side: self._on_preview_tempo_changed(s)
            )
            met_var = self._preview_metronome_vars[side]
            self._metronome_trace_tokens[side] = met_var.trace_add(
                "write", lambda *_args, s=side: self._on_preview_metronome_toggled(s)
            )
            loop_enabled_var = self._preview_loop_enabled_vars[side]
            self._loop_enabled_trace_tokens[side] = loop_enabled_var.trace_add(
                "write", lambda *_args, s=side: self._on_preview_loop_enabled(s)
            )
            loop_start_var = self._preview_loop_start_vars[side]
            self._loop_start_trace_tokens[side] = loop_start_var.trace_add(
                "write", lambda *_args, s=side: self._on_preview_loop_start_changed(s)
            )
            loop_end_var = self._preview_loop_end_vars[side]
            self._loop_end_trace_tokens[side] = loop_end_var.trace_add(
                "write", lambda *_args, s=side: self._on_preview_loop_end_changed(s)
            )
        self._playback_last_ts: float | None = None
        self._playback_job: str | None = None

    def _setup_recent_projects(self, preferences: object) -> None:
        self._recent_projects: list[str] = list(getattr(preferences, "recent_projects", []))
        self._recent_projects_menu: tk.Menu | None = None

    def _configure_main_window_shell(self) -> None:
        if not self._headless:
            self.title(APP_TITLE)
            self.geometry("860x560")
            self.resizable(True, True)
            self._style = ttk.Style(self)
            self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._build_theme_actions()
        if not self._headless:
            self._build_menus()
        self._apply_auto_scroll_mode(self._auto_scroll_mode_value)
        logger.info(
            "Main window initialised (headless=%s, log_path=%s, log_verbosity=%s)",
            self._headless,
            self._log_path,
            self._log_verbosity.get(),
        )

    def _initialise_preview_references(self) -> None:
        self.roll_orig: Optional[PianoRoll] = None
        self.roll_arr: Optional[PianoRoll] = None
        self.staff_orig: Optional[StaffView] = None
        self.staff_arr: Optional[StaffView] = None
        self.side_fing_orig: Optional[FingeringView] = None
        self.side_fing_arr: Optional[FingeringView] = None
        self.fingering_table: Optional[ttk.Treeview] = None
        self.fingering_preview: Optional[FingeringView] = None
        self.fingering_grid: Optional[FingeringGridView] = None
        self.fingering_selector: Optional[ttk.Combobox] = None
        self.fingering_instrument_var: Optional[tk.StringVar] = None
        self._fingering_note_to_midi: Dict[str, Optional[int]] = {}
        self._layout_editor_window: Optional[object] = None
        self._notebook: Optional[ttk.Notebook] = None
        self._preview_tab_frames: Sequence[ttk.Frame] = ()
        self._preview_auto_rendered = False
        self._transpose_trace_id: str | None = None
        self._suspend_transpose_update = False
        self._transpose_spinboxes: List[ttk.Spinbox] = []
        self._transpose_apply_button: object | None = None
        self._transpose_cancel_button: object | None = None
        self._transpose_applied_offset = int(self.transpose_offset.get())
        self._suspend_state_sync = False

    @staticmethod
    def _build_viewmodel(
        dialogs: FileDialogAdapter, score_service: ScoreService
    ) -> MainViewModel:
        return MainViewModel(dialogs=dialogs, score_service=score_service)

    def _build_ui(self) -> None:
        if self._headless:
            build_headless_ui(self)
        else:
            build_ui(self)

    def _tk_variables(self) -> tuple[tk.Variable, ...]:
        """Return all Tk variables currently referenced by the window."""

        return collect_tk_variables_from_attrs(self)

    def _release_tk_variables(self, interpreter: object | None = None) -> None:
        release_tracked_tk_variables(self, interpreter, log=logger)


__all__ = ["MainWindowInitialisationMixin"]
