from __future__ import annotations

import tkinter as tk

from services.project_service import PreviewPlaybackSnapshot
from shared.tempo import align_duration_to_measure
from viewmodels.preview_playback_viewmodel import LoopRegion, PreviewPlaybackViewModel


def snapshot_track_end_store(host: object) -> dict[str, int]:
    store = getattr(host, "_preview_snapshot_track_end", None)
    if not isinstance(store, dict):
        store = {}
        setattr(host, "_preview_snapshot_track_end", store)
    return store


def record_snapshot_track_end(host: object, side: str, track_end_tick: int) -> None:
    store = snapshot_track_end_store(host)
    store[side] = max(0, int(track_end_tick))


def resolve_track_end_tick(playback: PreviewPlaybackViewModel) -> int:
    track_end_tick = getattr(playback.state, "track_end_tick", 0)
    if track_end_tick <= 0:
        track_end_tick = align_duration_to_measure(
            playback.state.duration_tick,
            playback.state.pulses_per_quarter,
            playback.state.beats_per_measure,
            playback.state.beat_unit,
        )
    return max(0, int(track_end_tick))


def apply_preview_settings(host: object, side: str) -> None:
    playback = getattr(host, "_preview_playback", {}).get(side)
    if playback is None:
        return
    tempo_var = getattr(host, "_preview_tempo_vars", {}).get(side)
    met_var = getattr(host, "_preview_metronome_vars", {}).get(side)
    loop_enabled_var = getattr(host, "_preview_loop_enabled_vars", {}).get(side)
    loop_start_var = getattr(host, "_preview_loop_start_vars", {}).get(side)
    loop_end_var = getattr(host, "_preview_loop_end_vars", {}).get(side)
    volume_var = getattr(host, "_preview_volume_vars", {}).get(side)
    if (
        tempo_var is None
        or met_var is None
        or loop_enabled_var is None
        or loop_start_var is None
        or loop_end_var is None
    ):
        return
    try:
        tempo = float(tempo_var.get())
    except (tk.TclError, ValueError):
        return
    try:
        met_enabled = host._coerce_tk_bool(met_var.get())  # type: ignore[attr-defined]
    except (tk.TclError, TypeError, ValueError):
        met_enabled = host._coerce_tk_bool(  # type: ignore[attr-defined]
            playback.state.metronome_enabled,
            default=bool(playback.state.metronome_enabled),
        )
    try:
        loop_enabled = host._coerce_tk_bool(loop_enabled_var.get())  # type: ignore[attr-defined]
    except (tk.TclError, TypeError, ValueError):
        loop_enabled = host._coerce_tk_bool(  # type: ignore[attr-defined]
            playback.state.loop.enabled,
            default=bool(playback.state.loop.enabled),
        )
    try:
        loop_start = float(loop_start_var.get())
        loop_end = float(loop_end_var.get())
    except (tk.TclError, ValueError):
        host._update_preview_apply_cancel_state(side, valid=False)  # type: ignore[attr-defined]
        return
    applied = getattr(host, "_preview_applied_settings", {}).get(side, {})
    try:
        applied_start = float(applied.get("loop_start", loop_start))
    except (TypeError, ValueError):
        applied_start = loop_start
    try:
        applied_end = float(applied.get("loop_end", loop_end))
    except (TypeError, ValueError):
        applied_end = loop_end
    has_range = loop_end > loop_start
    range_changed = (
        abs(loop_start - applied_start) > 1e-6
        or abs(loop_end - applied_end) > 1e-6
    )
    if has_range and range_changed and not loop_enabled:
        loop_enabled = True
    if loop_end < loop_start:
        host._update_preview_apply_cancel_state(side, valid=False)  # type: ignore[attr-defined]
        return

    default_volume_percent: float | None
    applied_volume = applied.get("volume") if isinstance(applied, dict) else None
    if isinstance(applied_volume, (int, float)):
        default_volume_percent = float(applied_volume)
    else:
        state_volume = getattr(getattr(playback, "state", None), "volume", None)
        if isinstance(state_volume, (int, float)):
            default_volume_percent = float(state_volume) * 100.0
        else:
            default_volume_percent = 100.0

    if volume_var is not None:
        try:
            volume_percent = float(volume_var.get())
        except (tk.TclError, ValueError):
            volume_percent = default_volume_percent
    else:
        volume_percent = default_volume_percent

    volume_percent = max(0.0, min(100.0, volume_percent))

    playback.set_tempo(tempo)
    playback.set_metronome(met_enabled)
    pulses_per_quarter = max(1, playback.state.pulses_per_quarter)
    track_end_tick = resolve_track_end_tick(playback)
    track_end_beats = track_end_tick / pulses_per_quarter if track_end_tick > 0 else 0.0
    requested_start_tick = max(0, int(round(loop_start * pulses_per_quarter)))
    requested_end_tick = max(requested_start_tick, int(round(loop_end * pulses_per_quarter)))
    requested_start_beats = requested_start_tick / pulses_per_quarter
    requested_end_beats = requested_end_tick / pulses_per_quarter
    normalized_start_tick = max(0, min(requested_start_tick, track_end_tick))
    normalized_end_tick = max(normalized_start_tick, min(requested_end_tick, track_end_tick))
    if has_range and loop_enabled:
        visible_loop = True
        region = LoopRegion(
            enabled=True,
            start_tick=requested_start_tick,
            end_tick=requested_end_tick,
        )
        snapshot_loop_start = requested_start_beats
        snapshot_loop_end = requested_end_beats
    else:
        visible_loop = False
        region = LoopRegion(
            enabled=False,
            start_tick=0,
            end_tick=track_end_tick,
        )
        normalized_start_tick = 0
        normalized_end_tick = track_end_tick
        snapshot_loop_start = 0.0
        snapshot_loop_end = track_end_beats
        requested_start_tick = normalized_start_tick
        requested_end_tick = normalized_end_tick
    playback.set_loop(region)
    if hasattr(playback, "set_volume"):
        playback.set_volume(volume_percent / 100.0)

    applied_snapshot = {
        "tempo": float(tempo),
        "metronome": bool(met_enabled),
        "loop_enabled": bool(visible_loop),
        "loop_start": float(snapshot_loop_start),
        "loop_end": float(snapshot_loop_end),
        "volume": float(volume_percent),
    }
    getattr(host, "_preview_applied_settings")[side] = applied_snapshot
    if hasattr(host, "_preview_settings_seeded"):
        host._preview_settings_seeded.add(side)  # type: ignore[attr-defined]

    settings = dict(getattr(host._viewmodel.state, "preview_settings", {}))  # type: ignore[attr-defined]
    settings[side] = PreviewPlaybackSnapshot(
        tempo_bpm=float(tempo),
        metronome_enabled=bool(met_enabled),
        loop_enabled=bool(visible_loop),
        loop_start_beat=float(loop_start),
        loop_end_beat=float(loop_end),
        volume=volume_percent / 100.0,
    )
    host._viewmodel.update_preview_settings(settings)  # type: ignore[attr-defined]
    record_snapshot_track_end(host, side, track_end_tick)
    host._sync_preview_playback_controls(side)  # type: ignore[attr-defined]
    host._update_preview_render_progress(side)  # type: ignore[attr-defined]


def apply_preview_snapshot(
    host: object, side: str, snapshot: PreviewPlaybackSnapshot
) -> None:
    playback = getattr(host, "_preview_playback", {}).get(side)
    tempo = float(snapshot.tempo_bpm)

    viewmodel_settings = getattr(host._viewmodel.state, "preview_settings", {})
    current_snapshot = viewmodel_settings.get(side)
    active_snapshot = snapshot
    if (
        isinstance(current_snapshot, PreviewPlaybackSnapshot)
        and current_snapshot != snapshot
        and bool(current_snapshot.loop_enabled)
        and not bool(snapshot.loop_enabled)
    ):
        active_snapshot = current_snapshot

    pulses_per_quarter: int | None = None
    track_end_tick: int | None = None
    track_end_beats: float | None = None
    if playback is not None and playback.state.is_loaded:
        pulses_per_quarter = max(1, playback.state.pulses_per_quarter)
        track_end_tick = resolve_track_end_tick(playback)
        if track_end_tick > 0 and pulses_per_quarter:
            track_end_beats = track_end_tick / pulses_per_quarter

    loop_start = max(0.0, float(active_snapshot.loop_start_beat))
    loop_end = max(loop_start, float(active_snapshot.loop_end_beat))
    loop_enabled = bool(active_snapshot.loop_enabled) and loop_end > loop_start

    recorded_end = None
    if track_end_tick is not None:
        store = snapshot_track_end_store(host)
        recorded_end = store.get(side)

    if track_end_beats is not None:
        if recorded_end and recorded_end > 0 and recorded_end != track_end_tick:
            # Track length changed; reset to full-length selection and disable loop
            loop_start = 0.0
            loop_end = track_end_beats
            loop_enabled = False
        else:
            loop_start = min(loop_start, track_end_beats)
            loop_end = min(loop_end, track_end_beats)
            if not loop_enabled:
                loop_start = 0.0
                loop_end = track_end_beats

    # Fallback pulses when playback is not yet loaded
    pulses_for_ticks = pulses_per_quarter or (
        max(1, getattr(getattr(playback, "state", None), "pulses_per_quarter", 1))
        if playback is not None
        else 1
    )

    start_tick = int(round(loop_start * pulses_for_ticks))
    end_tick = int(round(loop_end * pulses_for_ticks))
    end_tick = max(start_tick, end_tick)
    visible_loop = loop_enabled and end_tick > start_tick

    if not visible_loop:
        display_start = 0.0
        display_end = track_end_beats if track_end_beats is not None else loop_end
        region = LoopRegion(
            enabled=False,
            start_tick=0,
            end_tick=track_end_tick or end_tick,
        )
    else:
        display_start = loop_start
        display_end = loop_end
        region = LoopRegion(
            enabled=True,
            start_tick=start_tick,
            end_tick=end_tick,
        )

    desired_snapshot = (
        current_snapshot if isinstance(current_snapshot, PreviewPlaybackSnapshot) else None
    )
    if (
        desired_snapshot is not None
        and bool(desired_snapshot.loop_enabled)
        and pulses_per_quarter is not None
        and track_end_tick is not None
        and (recorded_end is None or recorded_end == track_end_tick)
    ):
        desired_start = max(0.0, float(desired_snapshot.loop_start_beat))
        desired_end = max(desired_start, float(desired_snapshot.loop_end_beat))
        desired_start = min(desired_start, track_end_beats or desired_start)
        desired_end = min(desired_end, track_end_beats or desired_end)
        desired_start_tick = int(round(desired_start * pulses_per_quarter))
        desired_end_tick = int(round(desired_end * pulses_per_quarter))
        desired_end_tick = max(desired_start_tick, desired_end_tick)
        if desired_end_tick > desired_start_tick:
            display_start = desired_start
            display_end = desired_end
            region = LoopRegion(
                enabled=True,
                start_tick=desired_start_tick,
                end_tick=desired_end_tick,
            )
            loop_enabled = True
            visible_loop = True

    if playback is not None:
        playback.set_tempo(tempo)
        playback.set_metronome(bool(snapshot.metronome_enabled))
        playback.set_volume(float(snapshot.volume))
        if playback.state.is_loaded and track_end_tick is not None:
            # Ensure loop ticks respect the resolved track end
            start_tick = int(round(display_start * pulses_for_ticks))
            end_tick = int(round(display_end * pulses_for_ticks))
            end_tick = max(start_tick, min(end_tick, track_end_tick))
            if not loop_enabled:
                region = LoopRegion(
                    enabled=False,
                    start_tick=0,
                    end_tick=track_end_tick,
                )
            else:
                region = LoopRegion(
                    enabled=True,
                    start_tick=start_tick,
                    end_tick=end_tick,
                )
        playback.set_loop(region)

    applied = {
        "tempo": tempo,
        "metronome": bool(snapshot.metronome_enabled),
        "loop_enabled": loop_enabled,
        "loop_start": display_start,
        "loop_end": display_end,
        "volume": float(snapshot.volume) * 100.0,
    }
    getattr(host, "_preview_applied_settings")[side] = applied
    if hasattr(host, "_preview_settings_seeded"):
        host._preview_settings_seeded.add(side)  # type: ignore[attr-defined]

    normalized_snapshot = PreviewPlaybackSnapshot(
        tempo_bpm=tempo,
        metronome_enabled=bool(snapshot.metronome_enabled),
        loop_enabled=loop_enabled,
        loop_start_beat=display_start,
        loop_end_beat=display_end,
        volume=float(snapshot.volume),
    )
    settings = dict(getattr(host._viewmodel.state, "preview_settings", {}))  # type: ignore[attr-defined]
    existing_snapshot = settings.get(side)
    should_update_snapshot = True
    if existing_snapshot is not None and existing_snapshot is not snapshot:
        should_update_snapshot = False
    if existing_snapshot is None:
        should_update_snapshot = True
    if (
        should_update_snapshot
        and existing_snapshot != normalized_snapshot
    ):
        settings[side] = normalized_snapshot
        host._viewmodel.update_preview_settings(settings)  # type: ignore[attr-defined]

    if track_end_tick and track_end_tick > 0:
        record_snapshot_track_end(host, side, track_end_tick)
    else:
        store = snapshot_track_end_store(host)
        store.pop(side, None)

    tempo_var = getattr(host, "_preview_tempo_vars", {}).get(side)
    if tempo_var is not None:
        host._suspend_tempo_update.add(side)  # type: ignore[attr-defined]
        try:
            tempo_var.set(tempo)
            if hasattr(host, "_refresh_tempo_summary"):
                try:
                    host._refresh_tempo_summary(side, tempo_value=tempo)  # type: ignore[attr-defined]
                except Exception:
                    pass
        except (tk.TclError, ValueError):
            pass
        finally:
            host._suspend_tempo_update.discard(side)  # type: ignore[attr-defined]

    met_var = getattr(host, "_preview_metronome_vars", {}).get(side)
    if met_var is not None:
        host._suspend_metronome_update.add(side)  # type: ignore[attr-defined]
        try:
            met_var.set(bool(snapshot.metronome_enabled))
        except tk.TclError:
            pass
        finally:
            host._suspend_metronome_update.discard(side)  # type: ignore[attr-defined]

    loop_enabled_var = getattr(host, "_preview_loop_enabled_vars", {}).get(side)
    loop_start_var = getattr(host, "_preview_loop_start_vars", {}).get(side)
    loop_end_var = getattr(host, "_preview_loop_end_vars", {}).get(side)
    if (
        loop_enabled_var is not None
        and loop_start_var is not None
        and loop_end_var is not None
    ):
        host._suspend_loop_update.add(side)  # type: ignore[attr-defined]
        try:
            loop_enabled_var.set(loop_enabled)
            loop_start_var.set(display_start)
            loop_end_var.set(display_end)
        except (tk.TclError, ValueError):
            pass
        finally:
            host._suspend_loop_update.discard(side)  # type: ignore[attr-defined]

    if playback is not None and playback.state.is_loaded and track_end_tick is not None:
        force_flags = getattr(host, "_force_autoscroll_once", None)
        if isinstance(force_flags, dict):
            force_flags[side] = True
        host._update_playback_visuals(side)  # type: ignore[attr-defined]

    host._set_volume_controls_value(side, applied["volume"])  # type: ignore[attr-defined]
    host._update_mute_button_state(side)  # type: ignore[attr-defined]
    host._update_preview_apply_cancel_state(side)  # type: ignore[attr-defined]
    host._update_loop_marker_visuals(side)  # type: ignore[attr-defined]
