from __future__ import annotations

from shared.tempo import align_duration_to_measure

from viewmodels.preview_playback_viewmodel import LoopRegion

from ._preview_playback_helpers import _build_viewmodel, _make_events


def test_loop_region_wraps_when_enabled() -> None:
    viewmodel, renderer = _build_viewmodel()
    events = _make_events((0, 480, 60))
    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)
    viewmodel.set_loop(LoopRegion(enabled=True, start_tick=120, end_tick=240))
    assert renderer.loop_updates[-1].enabled

    viewmodel.seek_to(220)
    viewmodel.toggle_playback()
    # 0.5 seconds correspond to 120 ticks at 120bpm with ppq=120
    viewmodel.advance(0.5)

    assert 120 <= viewmodel.state.position_tick <= 240
    assert viewmodel.state.is_playing


def test_loop_allows_aligned_track_end() -> None:
    viewmodel, renderer = _build_viewmodel()
    events = _make_events((0, 1500, 60))

    viewmodel.load(events, pulses_per_quarter=480, beats_per_measure=4, beat_unit=4)

    aligned_end = align_duration_to_measure(1500, 480, 4, 4)
    assert viewmodel.state.track_end_tick == aligned_end

    renderer.loop_updates.clear()

    viewmodel.set_loop(LoopRegion(enabled=True, start_tick=0, end_tick=aligned_end))

    assert viewmodel.state.loop.enabled
    assert viewmodel.state.loop.end_tick == aligned_end
    assert renderer.loop_updates[-1].end_tick == aligned_end


def test_disabling_loop_resets_region_to_full_duration() -> None:
    viewmodel, renderer = _build_viewmodel()
    events = _make_events((0, 480, 60), (480, 240, 62))

    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)
    viewmodel.set_loop(LoopRegion(enabled=True, start_tick=120, end_tick=360))

    renderer.loop_updates.clear()

    viewmodel.set_loop(LoopRegion(enabled=False, start_tick=240, end_tick=300))

    assert not viewmodel.state.loop.enabled
    assert viewmodel.state.loop.start_tick == 240
    assert viewmodel.state.loop.end_tick == 300
    assert not renderer.loop_updates[-1].enabled
    assert renderer.loop_updates[-1].start_tick == 0
    assert renderer.loop_updates[-1].end_tick == viewmodel.state.track_end_tick


def test_load_resets_audio_loop_region() -> None:
    viewmodel, renderer = _build_viewmodel()
    events = _make_events((0, 360, 60))

    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=4, beat_unit=4)
    viewmodel.set_loop(LoopRegion(enabled=True, start_tick=120, end_tick=240))
    renderer.loop_updates.clear()

    viewmodel.load(events, pulses_per_quarter=120, beats_per_measure=3, beat_unit=8)

    assert renderer.loop_updates
    reset_region = renderer.loop_updates[-1]
    assert not reset_region.enabled
    assert reset_region.start_tick == 0
    assert reset_region.end_tick == viewmodel.state.track_end_tick
