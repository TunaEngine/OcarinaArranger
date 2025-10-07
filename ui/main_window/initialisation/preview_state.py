from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, Optional, Sequence

from shared.ttk import ttk

from ocarina_gui.audio import build_preview_audio_renderer
from ocarina_gui.fingering import FingeringGridView, FingeringView
from ocarina_gui.piano_roll import PianoRoll
from ocarina_gui.preview import Event, PreviewData
from ocarina_gui.preferences import PREVIEW_LAYOUT_MODES
from ocarina_gui.staff import StaffView
from viewmodels.preview_playback_viewmodel import PreviewPlaybackViewModel


class PreviewInitialisationMixin:
    """Initialise preview playback widgets, state, and bindings."""

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
        self._preview_play_buttons: Dict[str, object] = {}
        self._preview_play_icons: Dict[str, Dict[str, object]] = {}
        self._preview_position_vars = {
            "original": tk.StringVar(master=self, value="0:00.000"),
            "arranged": tk.StringVar(master=self, value="0:00.000"),
        }
        self._preview_duration_vars = {
            "original": tk.StringVar(master=self, value="0:00.000"),
            "arranged": tk.StringVar(master=self, value="0:00.000"),
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
        self._preview_linked_apply_buttons: dict[str, list[ttk.Button]] = {}
        self._preview_linked_cancel_buttons: dict[str, list[ttk.Button]] = {}
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
        self._transpose_spinboxes: list[ttk.Spinbox] = []
        self._transpose_apply_button: object | None = None
        self._transpose_cancel_button: object | None = None
        self._transpose_applied_offset = int(self.transpose_offset.get())
        self._suspend_state_sync = False


__all__ = ["PreviewInitialisationMixin"]
