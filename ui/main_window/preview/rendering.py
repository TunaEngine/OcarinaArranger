from __future__ import annotations

import logging
from typing import Optional, Sequence

from ocarina_gui.fingering import FingeringView
from ocarina_gui.piano_roll import PianoRoll
from ocarina_gui.preview import PreviewData
from ocarina_gui.staff import StaffView
from ocarina_tools import NoteEvent
from shared.tempo import first_tempo
from .rendering_playback import PreviewPlaybackSupportMixin

logger = logging.getLogger(__name__)


class PreviewRenderingMixin(PreviewPlaybackSupportMixin):
    """Render preview data into widgets and update fingering displays."""

    roll_orig: Optional[PianoRoll]
    roll_arr: Optional[PianoRoll]
    staff_orig: Optional[StaffView]
    staff_arr: Optional[StaffView]

    def _apply_preview_data(self, data: PreviewData) -> None:
        self._pending_preview_data = data

        target_instrument = getattr(self._viewmodel.state, "instrument_id", "")
        if target_instrument and target_instrument != getattr(
            self, "_selected_instrument_id", ""
        ):
            setter = getattr(self, "set_fingering_instrument", None)
            if callable(setter):
                try:
                    setter(target_instrument, update_range=False)
                except Exception:  # pragma: no cover - defensive safeguard
                    logger.exception(
                        "Failed to sync fingering instrument after arranger run",
                        extra={"instrument_id": target_instrument},
                    )

        for var, target in (
            (getattr(self, "range_min", None), getattr(self._viewmodel.state, "range_min", None)),
            (getattr(self, "range_max", None), getattr(self._viewmodel.state, "range_max", None)),
        ):
            if var is None or not target:
                continue
            try:
                current = var.get()
            except Exception:  # pragma: no cover - Tk variable access guard
                current = None
            if current != target:
                var.set(target)

        sides = (
            ("original", data.original_events, data.original_range),
            ("arranged", data.arranged_events, data.arranged_range),
        )
        initialized = getattr(self, "_preview_tab_initialized", set())

        for side, events, _ in sides:
            normalized = self._set_preview_events(side, events)
            self._prepare_preview_playback(side, normalized, data)
            self._preview_play_vars[side].set("Play")
            if side in initialized:
                self._sync_preview_playback_controls(side)

        for side, _, _ in sides:
            self._apply_preview_data_for_side(side, data)

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
            for side, *_ in sides:
                if side in initialized:
                    self._update_playback_visuals(side)

        self._resync_views()
        for side, *_ in sides:
            if side in initialized:
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
        tempo_changes = tuple(getattr(data, "tempo_changes", ()))
        applied = self._preview_applied_settings.setdefault(side, {})
        base_tempo = float(getattr(data, "tempo_bpm", applied.get("tempo", 120.0)))
        applied["tempo"] = base_tempo
        applied.setdefault("metronome", False)
        applied.setdefault("loop_enabled", False)
        applied.setdefault("loop_start", 0.0)
        applied.setdefault("loop_end", 0.0)
        tempo_maps = getattr(self, "_preview_tempo_maps", None)
        if isinstance(tempo_maps, dict):
            tempo_maps[side] = tempo_changes
        tempo_bases = getattr(self, "_preview_tempo_bases", None)
        if isinstance(tempo_bases, dict):
            tempo_bases[side] = first_tempo(tempo_changes, default=base_tempo)
        if hasattr(self, "_preview_settings_seeded"):
            self._preview_settings_seeded.add(side)
        self._set_preview_initial_loading(side, False)
        self._refresh_tempo_summary(side)

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
