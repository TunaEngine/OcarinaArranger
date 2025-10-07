from __future__ import annotations

from bisect import bisect_right
import logging
import time
import tkinter as tk
from tkinter import messagebox
from typing import Dict, Optional, Sequence, Tuple

from ocarina_gui.fingering import FingeringView
from ocarina_gui.piano_roll import PianoRoll
from ocarina_gui.preview import PreviewData
from ocarina_gui.staff import StaffView
from ocarina_tools import NoteEvent
from services.project_service import PreviewPlaybackSnapshot
from viewmodels.preview_playback_viewmodel import LoopRegion

logger = logging.getLogger(__name__)


class PreviewRenderingMixin:
    """Render preview data into widgets and update fingering displays."""

    roll_orig: Optional[PianoRoll]
    roll_arr: Optional[PianoRoll]
    staff_orig: Optional[StaffView]
    staff_arr: Optional[StaffView]

    def _apply_preview_data(self, data: PreviewData) -> None:
        self._pending_preview_data = data

        preview_specs = {
            "original": (data.original_events, data.original_range),
            "arranged": (data.arranged_events, data.arranged_range),
        }

        for side, (events, _range) in preview_specs.items():
            normalized = self._set_preview_events(side, events)
            self._prepare_preview_playback(side, normalized, data)

        for side in preview_specs:
            self._preview_play_vars[side].set("Play")
            if side in getattr(self, "_preview_tab_initialized", set()):
                self._sync_preview_playback_controls(side)

        self._apply_preview_data_for_side("arranged", data)
        self._apply_preview_data_for_side("original", data)
        preview_settings = getattr(self._viewmodel.state, "preview_settings", {})
        for side, snapshot in preview_settings.items():
            if snapshot is None or not hasattr(snapshot, "tempo_bpm"):
                continue
            self._apply_preview_snapshot(side, snapshot)
        applied_offset = int(self._viewmodel.state.transpose_offset)
        self._transpose_applied_offset = applied_offset
        if self.transpose_offset.get() != applied_offset:
            self._suspend_transpose_update = True
            try:
                self.transpose_offset.set(applied_offset)
            finally:
                self._suspend_transpose_update = False
        self._update_transpose_apply_cancel_state()
        if not getattr(self, "_headless", False):
            if "original" in getattr(self, "_preview_tab_initialized", set()):
                self._update_playback_visuals("original")
            if "arranged" in getattr(self, "_preview_tab_initialized", set()):
                self._update_playback_visuals("arranged")

        self._resync_views()
        for side in preview_specs:
            if side in getattr(self, "_preview_tab_initialized", set()):
                self._set_preview_initial_loading(side, False)

    def _apply_preview_data_for_side(self, side: str, data: PreviewData) -> None:
        if side == "original":
            roll = self.roll_orig
            staff = self.staff_orig
            events = data.original_events
            minimum, maximum = data.original_range
        else:
            roll = self.roll_arr
            staff = self.staff_arr
            events = data.arranged_events
            minimum, maximum = data.arranged_range

        if roll is None or staff is None:
            self._set_preview_initial_loading(side, False)
            return

        roll.set_range(minimum, maximum)
        staff.LEFT_PAD = getattr(roll, "label_width", 70) + getattr(roll, "LEFT_PAD", 10)
        staff.render(events, data.pulses_per_quarter, data.beats, data.beat_type)
        roll.sync_x_with(staff.canvas)
        staff.sync_x_with(roll.canvas)
        roll.render(
            events,
            data.pulses_per_quarter,
            beats=int(getattr(data, "beats", 4) or 4),
            beat_unit=int(getattr(data, "beat_type", 4) or 4),
        )
        roll.set_cursor(0)
        if hasattr(staff, "set_cursor"):
            staff.set_cursor(0)
        if hasattr(staff, "set_secondary_cursor"):
            staff.set_secondary_cursor(None)
        applied = self._preview_applied_settings.setdefault(side, {})
        applied["tempo"] = float(getattr(data, "tempo_bpm", applied.get("tempo", 120.0)))
        applied.setdefault("metronome", False)
        applied.setdefault("loop_enabled", False)
        applied.setdefault("loop_start", 0.0)
        applied.setdefault("loop_end", 0.0)
        if hasattr(self, "_preview_settings_seeded"):
            self._preview_settings_seeded.add(side)
        self._set_preview_initial_loading(side, False)

    def _set_preview_events(
        self, side: str, events: Sequence[NoteEvent]
    ) -> tuple[NoteEvent, ...]:
        normalized = tuple(events)
        self._preview_events[side] = normalized
        self._preview_event_starts[side] = tuple(
            onset for onset, _duration, _midi, _program in normalized
        )
        self._preview_hover_midi[side] = None
        self._update_preview_fingering(side)
        return normalized

    def _prepare_preview_playback(
        self, side: str, events: tuple[NoteEvent, ...], data: PreviewData
    ) -> None:
        playback = self._preview_playback.get(side)
        if playback is None:
            return
        spec = (
            events,
            int(data.pulses_per_quarter),
            data.tempo_bpm,
            int(data.beats),
            int(data.beat_type),
        )
        tempo_value = spec[2]
        try:
            tempo_float = float(tempo_value)
        except (TypeError, ValueError):
            existing_playback = self._preview_playback.get(side)
            tempo_float = (
                float(existing_playback.state.tempo_bpm)
                if existing_playback is not None
                else 120.0
            )
        viewmodel_settings = getattr(self._viewmodel.state, "preview_settings", {})
        existing_snapshot = viewmodel_settings.get(side)
        default_snapshot = {
            "tempo": tempo_float,
            "metronome": False,
            "loop_enabled": False,
            "loop_start": 0.0,
            "loop_end": 0.0,
        }
        applied_snapshot = dict(default_snapshot)
        if isinstance(existing_snapshot, PreviewPlaybackSnapshot):
            applied_snapshot = {
                "tempo": float(existing_snapshot.tempo_bpm),
                "metronome": bool(existing_snapshot.metronome_enabled),
                "loop_enabled": bool(existing_snapshot.loop_enabled),
                "loop_start": float(existing_snapshot.loop_start_beat),
                "loop_end": float(existing_snapshot.loop_end_beat),
            }
            tempo_float = applied_snapshot["tempo"]
        self._preview_applied_settings[side] = dict(applied_snapshot)
        if hasattr(self, "_preview_settings_seeded"):
            self._preview_settings_seeded.add(side)
        should_seed_snapshot = True
        if existing_snapshot is not None:
            default_snapshot = PreviewPlaybackSnapshot()
            if (
                existing_snapshot.tempo_bpm != default_snapshot.tempo_bpm
                or existing_snapshot.metronome_enabled != default_snapshot.metronome_enabled
                or existing_snapshot.loop_enabled
                or existing_snapshot.loop_start_beat != default_snapshot.loop_start_beat
                or existing_snapshot.loop_end_beat != default_snapshot.loop_end_beat
            ):
                should_seed_snapshot = False
        if should_seed_snapshot:
            updated_settings = dict(viewmodel_settings)
            updated_settings[side] = PreviewPlaybackSnapshot(
                tempo_bpm=tempo_float,
                metronome_enabled=False,
                loop_enabled=False,
                loop_start_beat=0.0,
                loop_end_beat=0.0,
            )
            self._viewmodel.update_preview_settings(updated_settings)
        initialized = side in getattr(self, "_preview_tab_initialized", set())
        pending: Dict[
            str, Tuple[tuple[NoteEvent, ...], int, float | None, int, int]
        ] = getattr(
            self, "_pending_preview_playback", {}
        )
        if initialized:
            pending.pop(side, None)
            playback.load(
                events,
                spec[1],
                tempo_bpm=spec[2],
                beats_per_measure=spec[3],
                beat_unit=spec[4],
            )
            playback.set_tempo(applied_snapshot["tempo"])
            playback.state.tempo_bpm = applied_snapshot["tempo"]
            if isinstance(existing_snapshot, PreviewPlaybackSnapshot):
                self._apply_preview_snapshot(side, existing_snapshot)
            return

        pending[side] = spec
        playback.stop()
        playback.state.is_playing = False
        playback.state.is_loaded = False
        playback.state.position_tick = 0
        playback.state.duration_tick = 0
        playback.state.loop = LoopRegion(enabled=False, start_tick=0, end_tick=0)
        playback.state.last_error = None
        playback.state.is_rendering = False
        playback.state.render_progress = 0.0
        self._update_preview_render_progress(side)

    def _load_pending_preview_playback(self, side: str) -> None:
        pending: Dict[
            str, Tuple[tuple[NoteEvent, ...], int, float | None, int, int]
        ] = getattr(
            self, "_pending_preview_playback", {}
        )
        spec = pending.pop(side, None)
        if spec is None:
            return
        playback = self._preview_playback.get(side)
        if playback is None:
            return
        events, pulses_per_quarter, tempo_bpm, beats_per_measure, beat_unit = spec
        playback.load(
            events,
            pulses_per_quarter,
            tempo_bpm=tempo_bpm,
            beats_per_measure=beats_per_measure,
            beat_unit=beat_unit,
        )
        tempo_to_apply = playback.state.tempo_bpm
        if tempo_bpm is not None:
            try:
                tempo_to_apply = float(tempo_bpm)
            except (TypeError, ValueError):
                tempo_to_apply = playback.state.tempo_bpm
        playback.set_tempo(tempo_to_apply)
        playback.state.tempo_bpm = tempo_to_apply
        viewmodel_settings = getattr(self._viewmodel.state, "preview_settings", {})
        snapshot = viewmodel_settings.get(side)
        if isinstance(snapshot, PreviewPlaybackSnapshot):
            self._apply_preview_snapshot(side, snapshot)

    def _current_playback_midi(self, side: str) -> Optional[int]:
        events = self._preview_events.get(side, ())
        if not events:
            return None
        playback = self._preview_playback.get(side)
        if playback is None:
            return None
        tick = playback.state.position_tick
        starts = self._preview_event_starts.get(side, ())
        index = bisect_right(starts, tick) - 1
        while index >= 0:
            onset, duration, midi, _program = events[index]
            if tick < onset:
                index -= 1
                continue
            if tick < onset + duration:
                return midi
            index -= 1
        return None

    def _update_preview_fingering(self, side: str) -> None:
        view = self._side_fingering_for_side(side)
        if view is None:
            return
        hover_midi = self._preview_hover_midi.get(side)
        playback = self._preview_playback.get(side)
        is_playing = bool(playback and playback.state.is_playing)
        is_dragging = self._preview_cursor_dragging.get(side, False)
        if hover_midi is not None and not is_playing and not is_dragging:
            view.set_midi(hover_midi)
            return
        if playback is None:
            view.set_midi(None)
            return
        if not is_playing and not is_dragging:
            view.set_midi(None)
            return
        midi = self._current_playback_midi(side)
        if midi is not None:
            view.set_midi(midi)
        else:
            view.set_midi(None)

    def _on_preview_roll_hover(self, side: str, midi: Optional[int]) -> None:
        self._preview_hover_midi[side] = midi
        self._update_preview_fingering(side)

    def _on_preview_cursor_drag_state(self, side: str, dragging: bool) -> None:
        previous = self._preview_cursor_dragging.get(side, False)
        if previous == dragging:
            self._update_preview_fingering(side)
            return

        self._preview_cursor_dragging[side] = dragging
        playback = self._preview_playback.get(side)
        update_visuals = False

        if dragging:
            toggled = self._pause_preview_playback_for_cursor_seek(side)
            update_visuals = toggled
        else:
            resume = self._preview_resume_on_cursor_release.pop(side, False)
            if (
                resume
                and playback is not None
                and playback.state.is_loaded
                and not playback.state.is_playing
            ):
                restarted = playback.toggle_playback()
                if restarted:
                    self._playback_last_ts = time.perf_counter()
                else:
                    error = playback.state.last_error
                    if error:
                        try:
                            messagebox.showwarning("Audio unavailable", error)
                        except tk.TclError:
                            logger.debug(
                                "Unable to show audio warning after cursor drag resume",
                                exc_info=True,
                            )
                update_visuals = True

        self._update_preview_fingering(side)
        if update_visuals:
            self._update_playback_visuals(side)

    def _pause_preview_playback_for_cursor_seek(self, side: str) -> bool:
        playback = self._preview_playback.get(side)
        if (
            playback is None
            or not playback.state.is_loaded
            or not playback.state.is_playing
        ):
            return False

        if self._preview_resume_on_cursor_release.get(side):
            return False

        self._preview_resume_on_cursor_release[side] = True
        playback.toggle_playback()
        return True
