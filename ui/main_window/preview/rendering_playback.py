"""Playback helpers extracted from :mod:`ui.main_window.preview.rendering`."""

from __future__ import annotations

from bisect import bisect_right
import logging
import time
import tkinter as tk
from tkinter import messagebox
from typing import Dict, Optional, Tuple

from ocarina_gui.piano_roll import PianoRoll
from ocarina_gui.preview import PreviewData
from ocarina_gui.staff import StaffView
from ocarina_tools import NoteEvent
from services.project_service import PreviewPlaybackSnapshot
from shared.tempo import TempoChange, first_tempo, scaled_tempo_marker_pairs
from viewmodels.preview_playback_viewmodel import LoopRegion


logger = logging.getLogger(__name__)


class PreviewPlaybackSupportMixin:
    """Tempo and playback synchronisation helpers."""

    def _refresh_tempo_summary(
        self, side: str, tempo_value: float | None = None
    ) -> None:
        tempo_maps = getattr(self, "_preview_tempo_maps", {})
        tempo_changes = tempo_maps.get(side, ()) if isinstance(tempo_maps, dict) else ()
        if not tempo_changes:
            marker_store = getattr(self, "_preview_tempo_marker_pairs", None)
            if isinstance(marker_store, dict):
                marker_store[side] = ()
            self._update_tempo_marker_widgets(side)
            return
        tempo_bases = getattr(self, "_preview_tempo_bases", {})
        base = tempo_bases.get(side, 120.0) if isinstance(tempo_bases, dict) else 120.0
        target = tempo_value
        if target is None:
            tempo_vars = getattr(self, "_preview_tempo_vars", {})
            tempo_var = tempo_vars.get(side) if isinstance(tempo_vars, dict) else None
            if tempo_var is not None:
                try:
                    target = float(tempo_var.get())
                except (tk.TclError, TypeError, ValueError):
                    target = None
        if target is None:
            target = base
        marker_pairs = scaled_tempo_marker_pairs(tempo_changes, target)
        marker_store = getattr(self, "_preview_tempo_marker_pairs", None)
        if isinstance(marker_store, dict):
            marker_store[side] = marker_pairs
        self._update_tempo_marker_widgets(side)

    def _update_tempo_marker_widgets(self, side: str) -> None:
        marker_store = getattr(self, "_preview_tempo_marker_pairs", {})
        markers = ()
        if isinstance(marker_store, dict):
            markers = marker_store.get(side, ())

        roll: Optional[PianoRoll]
        staff: Optional[StaffView]
        if side == "original":
            roll = self.roll_orig
            staff = self.staff_orig
        else:
            roll = self.roll_arr
            staff = self.staff_arr

        if roll is not None and hasattr(roll, "set_tempo_markers"):
            try:
                roll.set_tempo_markers(markers)
            except Exception:
                logger.exception("Failed to update piano roll tempo markers")
        if staff is not None and hasattr(staff, "set_tempo_markers"):
            try:
                staff.set_tempo_markers(markers)
            except Exception:
                logger.exception("Failed to update staff tempo markers")

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
            tuple(getattr(data, "tempo_changes", ())),
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
        memory_store = getattr(self, "_preview_volume_memory", None)
        memory_volume: float | None = None
        if isinstance(memory_store, dict):
            raw_memory = memory_store.get(side)
            if isinstance(raw_memory, (int, float)):
                memory_volume = float(raw_memory)

        if memory_volume is not None:
            current_volume = max(0.0, min(100.0, memory_volume))
        else:
            base_volume = (
                float(getattr(playback.state, "volume", 1.0)) * 100.0
                if playback is not None
                else 100.0
            )
            current_volume = max(0.0, min(100.0, base_volume))

        if isinstance(memory_store, dict) and current_volume > 0.0:
            memory_store[side] = current_volume
        default_snapshot = {
            "tempo": tempo_float,
            "metronome": False,
            "loop_enabled": False,
            "loop_start": 0.0,
            "loop_end": 0.0,
            "volume": current_volume,
        }
        applied_snapshot = dict(default_snapshot)
        if isinstance(existing_snapshot, PreviewPlaybackSnapshot):
            applied_snapshot = {
                "tempo": float(existing_snapshot.tempo_bpm),
                "metronome": bool(existing_snapshot.metronome_enabled),
                "loop_enabled": bool(existing_snapshot.loop_enabled),
                "loop_start": float(existing_snapshot.loop_start_beat),
                "loop_end": float(existing_snapshot.loop_end_beat),
                "volume": float(existing_snapshot.volume) * 100.0,
            }
            tempo_float = applied_snapshot["tempo"]
        self._preview_applied_settings[side] = dict(applied_snapshot)
        if hasattr(self, "_preview_settings_seeded"):
            self._preview_settings_seeded.add(side)
        default_snapshot = PreviewPlaybackSnapshot()
        seeded_snapshot: PreviewPlaybackSnapshot | None = None
        needs_seed = not isinstance(
            existing_snapshot, PreviewPlaybackSnapshot
        ) or existing_snapshot == default_snapshot
        if needs_seed:
            seeded_snapshot = PreviewPlaybackSnapshot(
                tempo_bpm=tempo_float,
                metronome_enabled=False,
                loop_enabled=False,
                loop_start_beat=0.0,
                loop_end_beat=0.0,
                volume=current_volume / 100.0,
            )
            updated_settings = dict(viewmodel_settings)
            updated_settings[side] = seeded_snapshot
            self._viewmodel.update_preview_settings(updated_settings)
        initialized = side in getattr(self, "_preview_tab_initialized", set())
        pending: Dict[
            str,
            Tuple[
                tuple[NoteEvent, ...],
                int,
                float | None,
                int,
                int,
                tuple[TempoChange, ...],
            ],
        ] = getattr(
            self, "_pending_preview_playback", {}
        )
        if initialized:
            pending.pop(side, None)
            playback.load(
                events,
                spec[1],
                tempo_bpm=spec[2],
                tempo_changes=spec[5],
                beats_per_measure=spec[3],
                beat_unit=spec[4],
            )
            playback.set_tempo(applied_snapshot["tempo"])
            playback.state.tempo_bpm = applied_snapshot["tempo"]
            snapshot_to_apply: PreviewPlaybackSnapshot | None
            snapshot_to_apply = (
                existing_snapshot
                if isinstance(existing_snapshot, PreviewPlaybackSnapshot)
                else seeded_snapshot
            )

            if snapshot_to_apply is not None:
                self._apply_preview_snapshot(side, snapshot_to_apply)
            else:
                target_volume_percent = float(applied_snapshot["volume"])
                playback.set_volume(
                    max(0.0, min(1.0, target_volume_percent / 100.0))
                )
                self._set_volume_controls_value(side, target_volume_percent)
                self._update_mute_button_state(side)
                self._update_preview_apply_cancel_state(side, volume=target_volume_percent)
                refresh_summary = getattr(self, "_refresh_tempo_summary", None)
                if callable(refresh_summary):
                    try:
                        refresh_summary(side, tempo_value=applied_snapshot["tempo"])
                    except Exception:
                        pass
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
            str,
            Tuple[
                tuple[NoteEvent, ...],
                int,
                float | None,
                int,
                int,
                tuple[TempoChange, ...],
            ],
        ] = getattr(
            self, "_pending_preview_playback", {}
        )
        spec = pending.pop(side, None)
        if spec is None:
            return
        playback = self._preview_playback.get(side)
        if playback is None:
            return
        (
            events,
            pulses_per_quarter,
            tempo_bpm,
            beats_per_measure,
            beat_unit,
            tempo_changes,
        ) = spec
        playback.load(
            events,
            pulses_per_quarter,
            tempo_bpm=tempo_bpm,
            tempo_changes=tempo_changes,
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
        else:
            self._refresh_tempo_summary(side, tempo_value=tempo_to_apply)

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


__all__ = ["PreviewPlaybackSupportMixin"]
