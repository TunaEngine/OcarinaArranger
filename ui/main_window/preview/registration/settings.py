from __future__ import annotations

import tkinter as tk

from services.project_service import PreviewPlaybackSnapshot
from shared.tempo import align_duration_to_measure
from viewmodels.preview_playback_viewmodel import LoopRegion

from .settings_helpers import (
    apply_preview_settings,
    apply_preview_snapshot,
    record_snapshot_track_end,
    resolve_track_end_tick,
    snapshot_track_end_store,
)


class PreviewSettingsMixin:
    """Apply, cancel, and synchronize preview playback settings."""

    # ------------------------------------------------------------------
    # Snapshot bookkeeping helpers
    # ------------------------------------------------------------------
    def _snapshot_track_end_store(self) -> dict[str, int]:
        return snapshot_track_end_store(self)

    def _record_snapshot_track_end(self, side: str, track_end_tick: int) -> None:
        record_snapshot_track_end(self, side, track_end_tick)

    @staticmethod
    def _resolve_track_end_tick(playback: "PreviewPlaybackViewModel") -> int:
        return resolve_track_end_tick(playback)

    def _set_preview_controls_enabled(self, side: str, enabled: bool) -> None:
        state_flags = ["!disabled"] if enabled else ["disabled"]
        widgets = (
            self._preview_tempo_controls.get(side),
            self._preview_metronome_controls.get(side),
        )
        loop_widgets = self._preview_loop_controls.get(side, ())
        volume_widgets = self._preview_volume_controls.get(side, ())

        def _apply_widget_state(widget: object, flags: list[str]) -> None:
            try:
                widget.state(tuple(flags))  # type: ignore[attr-defined]
            except Exception:
                pass
            if any(flag == "!disabled" for flag in flags):
                for action in (
                    lambda: widget.state(("!disabled",)),
                    lambda: widget.configure(state="normal"),
                    lambda: widget.__setitem__("state", "normal"),
                ):
                    try:
                        action()  # type: ignore[misc]
                    except Exception:
                        pass
            elif any(flag == "disabled" for flag in flags):
                for action in (
                    lambda: widget.state(("disabled",)),
                    lambda: widget.configure(state="disabled"),
                    lambda: widget.__setitem__("state", "disabled"),
                ):
                    try:
                        action()  # type: ignore[misc]
                    except Exception:
                        pass

        for widget in (*widgets, *loop_widgets):
            if widget is None:
                continue
            _apply_widget_state(widget, state_flags)
        playback = getattr(self, "_preview_playback", {}).get(side)
        if playback is not None:
            volume_enabled = playback.state.is_loaded and not playback.state.is_rendering
            volume_state = ["!disabled"] if volume_enabled else ["disabled"]
        else:
            volume_state = state_flags
        for widget in volume_widgets:
            if widget is None:
                continue
            _apply_widget_state(widget, volume_state)
        if not enabled:
            self._cancel_loop_range_selection(side)

    def _apply_preview_settings(self, side: str) -> None:
        apply_preview_settings(self, side)

    def _cancel_preview_settings(self, side: str) -> None:
        applied = self._preview_applied_settings.get(side)
        if not applied:
            return
        tempo_var = self._preview_tempo_vars.get(side)
        met_var = self._preview_metronome_vars.get(side)
        loop_enabled_var = self._preview_loop_enabled_vars.get(side)
        loop_start_var = self._preview_loop_start_vars.get(side)
        loop_end_var = self._preview_loop_end_vars.get(side)
        volume_value = float(applied.get("volume", 100.0))
        self._set_volume_controls_value(side, volume_value)
        if tempo_var is not None:
            self._suspend_tempo_update.add(side)
            try:
                tempo_value = float(applied["tempo"])
                tempo_var.set(tempo_value)
                if hasattr(self, "_refresh_tempo_summary"):
                    try:
                        self._refresh_tempo_summary(side, tempo_value=tempo_value)
                    except Exception:
                        pass
            except (tk.TclError, ValueError):
                pass
            finally:
                self._suspend_tempo_update.discard(side)
        if met_var is not None:
            self._suspend_metronome_update.add(side)
            try:
                met_var.set(bool(applied["metronome"]))
            except tk.TclError:
                pass
            finally:
                self._suspend_metronome_update.discard(side)
        if loop_enabled_var is not None and loop_start_var is not None and loop_end_var is not None:
            self._suspend_loop_update.add(side)
            try:
                loop_enabled_var.set(bool(applied["loop_enabled"]))
                loop_start_var.set(float(applied["loop_start"]))
                loop_end_var.set(float(applied["loop_end"]))
            except (tk.TclError, ValueError):
                pass
            finally:
                self._suspend_loop_update.discard(side)
        playback = self._preview_playback.get(side)
        if playback is not None:
            playback.set_volume(volume_value / 100.0)
            self._update_mute_button_state(side)
        self._update_preview_apply_cancel_state(side)
        self._update_loop_marker_visuals(side)

    def _apply_preview_snapshot(
        self, side: str, snapshot: PreviewPlaybackSnapshot
    ) -> None:
        apply_preview_snapshot(self, side, snapshot)

    def _update_preview_apply_cancel_state(
        self,
        side: str,
        *,
        tempo: float | None = None,
        metronome: bool | None = None,
        loop_enabled: bool | None = None,
        loop_start: float | None = None,
        loop_end: float | None = None,
        valid: bool = True,
        volume: float | None = None,
    ) -> None:
        apply_button = self._preview_apply_buttons.get(side)
        cancel_button = self._preview_cancel_buttons.get(side)
        if apply_button is None or cancel_button is None:
            return
        all_apply = self._preview_linked_apply_buttons.get(side) or [apply_button]
        all_cancel = self._preview_linked_cancel_buttons.get(side) or [cancel_button]

        def set_state(buttons, state):
            for button in buttons:
                try:
                    button.state(state)
                except tk.TclError:
                    continue

        playback = self._preview_playback.get(side)
        applied = self._preview_applied_settings.get(side)
        if playback is None or applied is None:
            return
        if not valid:
            set_state(all_apply, ["disabled"])
            set_state(all_cancel, ["disabled"])
            return
        tempo_value = tempo
        if tempo_value is None:
            var = self._preview_tempo_vars.get(side)
            if var is not None:
                try:
                    tempo_value = float(var.get())
                except (tk.TclError, ValueError):
                    set_state(all_apply, ["disabled"])
                    set_state(all_cancel, ["disabled"])
                    return
        met_value = metronome
        if met_value is None:
            var_bool = self._preview_metronome_vars.get(side)
            if var_bool is not None:
                try:
                    met_value = self._coerce_tk_bool(var_bool.get())
                except (tk.TclError, TypeError, ValueError):
                    met_value = bool(applied["metronome"])
            else:
                met_value = bool(applied["metronome"])
        else:
            try:
                met_value = self._coerce_tk_bool(met_value)
            except (TypeError, ValueError):
                met_value = bool(applied["metronome"])
        loop_enabled_value = loop_enabled
        if loop_enabled_value is None:
            var_loop = self._preview_loop_enabled_vars.get(side)
            if var_loop is not None:
                try:
                    loop_enabled_value = self._coerce_tk_bool(var_loop.get())
                except (tk.TclError, TypeError, ValueError):
                    loop_enabled_value = bool(applied["loop_enabled"])
            else:
                loop_enabled_value = bool(applied["loop_enabled"])
        else:
            try:
                loop_enabled_value = self._coerce_tk_bool(loop_enabled_value)
            except (TypeError, ValueError):
                loop_enabled_value = bool(applied["loop_enabled"])
        loop_start_value = loop_start
        if loop_start_value is None:
            start_var = self._preview_loop_start_vars.get(side)
            if start_var is not None:
                try:
                    loop_start_value = float(start_var.get())
                except (tk.TclError, ValueError):
                    set_state(all_apply, ["disabled"])
                    set_state(all_cancel, ["disabled"])
                    return
        loop_end_value = loop_end
        if loop_end_value is None:
            end_var = self._preview_loop_end_vars.get(side)
            if end_var is not None:
                try:
                    loop_end_value = float(end_var.get())
                except (tk.TclError, ValueError):
                    set_state(all_apply, ["disabled"])
                    set_state(all_cancel, ["disabled"])
                    return
        volume_value = volume
        if volume_value is None:
            volume_var = self._preview_volume_vars.get(side)
            if volume_var is not None:
                try:
                    volume_value = float(volume_var.get())
                except (tk.TclError, ValueError):
                    volume_value = float(applied.get("volume", 100.0))
            else:
                volume_value = float(applied.get("volume", 100.0))
        else:
            try:
                volume_value = float(volume_value)
            except (TypeError, ValueError):
                volume_value = float(applied.get("volume", 100.0))
        if volume_value is not None:
            volume_value = max(0.0, min(100.0, volume_value))
        if (
            loop_start_value is not None
            and loop_end_value is not None
            and loop_end_value < loop_start_value
        ):
            set_state(all_apply, ["disabled"])
            set_state(all_cancel, ["disabled"])
            return
        changed = False
        if tempo_value is not None and abs(tempo_value - applied["tempo"]) > 1e-6:
            changed = True
        if met_value is not None and bool(met_value) != bool(applied["metronome"]):
            changed = True
        if bool(loop_enabled_value) != bool(applied["loop_enabled"]):
            changed = True
        if loop_start_value is not None and abs(loop_start_value - applied["loop_start"]) > 1e-6:
            changed = True
        if loop_end_value is not None and abs(loop_end_value - applied["loop_end"]) > 1e-6:
            changed = True
        if volume_value is not None and abs(volume_value - applied.get("volume", 100.0)) > 1e-6:
            changed = True
        if playback.state.is_rendering or playback.state.is_playing:
            set_state(all_apply, ["disabled"])
            set_state(all_cancel, ["disabled"])
        elif changed:
            set_state(all_apply, ["!disabled"])
            set_state(all_cancel, ["!disabled"])
        else:
            set_state(all_apply, ["disabled"])
            set_state(all_cancel, ["disabled"])

        self._update_transpose_apply_cancel_state()
