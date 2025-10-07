from __future__ import annotations

import pytest
from pytest_bdd import then, when, parsers

from tests.helpers import require_ttkbootstrap

require_ttkbootstrap()

from tests.e2e.harness import E2EHarness


@when(parsers.parse("the user adjusts the arranged preview tempo to {tempo:d} bpm"))
def adjust_arranged_tempo(arranger_app: E2EHarness, tempo: int) -> None:
    window = arranger_app.window
    tempo_var = window._preview_tempo_vars["arranged"]
    tempo_var.set(float(tempo))
    window._on_preview_tempo_changed("arranged")
    window._apply_preview_settings("arranged")


@when(parsers.parse("the user enables looping from beat {start:g} to {end:g}"))
def enable_loop(arranger_app: E2EHarness, start: float, end: float) -> None:
    window = arranger_app.window
    loop_enabled = window._preview_loop_enabled_vars["arranged"]
    loop_start = window._preview_loop_start_vars["arranged"]
    loop_end = window._preview_loop_end_vars["arranged"]
    loop_enabled.set(True)
    window._on_preview_loop_enabled("arranged")
    loop_start.set(float(start))
    window._on_preview_loop_start_changed("arranged")
    loop_end.set(float(end))
    window._on_preview_loop_end_changed("arranged")
    window._apply_preview_settings("arranged")


@when(parsers.parse('the user switches auto scroll mode to "{mode}"'))
def switch_auto_scroll(arranger_app: E2EHarness, mode: str) -> None:
    arranger_app.window._apply_auto_scroll_mode(mode)


@when("the user enables the arranged metronome")
def enable_arranged_metronome(arranger_app: E2EHarness) -> None:
    window = arranger_app.window
    met_var = window._preview_metronome_vars["arranged"]
    met_var.set(True)
    window._on_preview_metronome_toggled("arranged")
    window._apply_preview_settings("arranged")


@when(parsers.parse('the user switches preview layout mode to "{mode}"'))
def switch_preview_layout(arranger_app: E2EHarness, mode: str) -> None:
    window = arranger_app.window
    window.preview_layout_mode.set(mode)
    window._on_preview_layout_mode_changed()


@then(parsers.parse("the arranged preview playback tempo is {tempo:d} bpm"))
def assert_tempo(arranger_app: E2EHarness, tempo: int) -> None:
    playback = arranger_app.window._preview_playback.get("arranged")
    assert playback is not None
    assert int(round(playback.state.tempo_bpm)) == tempo


@then(parsers.parse("the arranged preview loop spans beats {start:g} to {end:g}"))
def assert_loop(arranger_app: E2EHarness, start: float, end: float) -> None:
    snapshot = arranger_app.viewmodel.preview_settings().get("arranged")
    assert snapshot is not None
    assert snapshot.loop_enabled is True
    assert snapshot.loop_start_beat == pytest.approx(start)
    assert snapshot.loop_end_beat == pytest.approx(end)


@then(parsers.parse('the auto scroll preference is "{mode}"'))
def assert_auto_scroll(arranger_app: E2EHarness, mode: str) -> None:
    assert arranger_app.preferences.auto_scroll_mode == mode
    assert arranger_app.window._auto_scroll_mode_value == mode


@then("the arranged preview metronome is enabled")
def assert_metronome_enabled(arranger_app: E2EHarness) -> None:
    playback = arranger_app.window._preview_playback.get("arranged")
    assert playback is not None
    assert playback.state.metronome_enabled is True
    snapshot = arranger_app.viewmodel.preview_settings().get("arranged")
    assert snapshot is not None and snapshot.metronome_enabled is True


@then(parsers.parse('the preview layout preference is "{mode}"'))
def assert_preview_layout_preference(arranger_app: E2EHarness, mode: str) -> None:
    assert arranger_app.window.preview_layout_mode.get() == mode
    assert arranger_app.preferences.preview_layout_mode == mode
    assert arranger_app.saved_preferences, "Expected preferences to be persisted"
    assert arranger_app.saved_preferences[-1].preview_layout_mode == mode

