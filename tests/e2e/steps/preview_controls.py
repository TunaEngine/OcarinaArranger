from __future__ import annotations

import logging
from typing import Any

import pytest
from pytest_bdd import parsers, then, when

from tests.helpers import require_ttkbootstrap

require_ttkbootstrap()

from tests.e2e.harness import E2EHarness
from shared.tk_style import get_ttk_style
from ocarina_gui import themes


logger = logging.getLogger(__name__)


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return "None" if value is None else str(value)


def _preview_volume_snapshot(arranger_app: E2EHarness) -> dict[str, Any]:
    window = arranger_app.window
    var = window._preview_volume_vars.get("arranged")
    try:
        slider_value: float | None = float(var.get()) if var is not None else None
    except Exception:  # pragma: no cover - defensive diagnostic path
        slider_value = None

    playback = window._preview_playback.get("arranged")
    if playback is not None:
        playback_volume = getattr(playback.state, "volume", None)
        is_loaded = getattr(playback.state, "is_loaded", None)
        is_playing = getattr(playback.state, "is_playing", None)
    else:
        playback_volume = None
        is_loaded = None
        is_playing = None

    button = window._preview_volume_buttons.get("arranged")
    if button is None:
        button_state: str | None = None
    else:
        try:
            button_state = "pressed" if button.instate(["pressed"]) else "released"
        except Exception:  # pragma: no cover - defensive diagnostic path
            button_state = "error"

    memory = getattr(window, "_preview_volume_memory", {})
    remembered = memory.get("arranged") if isinstance(memory, dict) else None

    resume_flags = getattr(window, "_resume_volume_on_release", {})
    resume_on_release = (
        resume_flags.get("arranged") if isinstance(resume_flags, dict) else None
    )

    active_adjustments = getattr(window, "_active_volume_adjustment", set())
    is_adjusting = (
        "arranged" in active_adjustments if isinstance(active_adjustments, set) else None
    )

    return {
        "slider": slider_value,
        "playback_volume": playback_volume,
        "playback_loaded": is_loaded,
        "playback_playing": is_playing,
        "button_state": button_state,
        "remembered": remembered,
        "resume_on_release": resume_on_release,
        "is_adjusting": is_adjusting,
    }


def _log_preview_volume_state(arranger_app: E2EHarness, label: str) -> None:
    snapshot = _preview_volume_snapshot(arranger_app)
    formatted = " ".join(
        f"{key}={_format_value(value)}" for key, value in snapshot.items()
    )
    message = f"[preview-volume] {label}: {formatted}"
    logger.info(message)
    print(message)


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


@when(parsers.parse("the user sets the arranged preview volume to {percent:g} percent"))
def set_arranged_preview_volume(arranger_app: E2EHarness, percent: float) -> None:
    _log_preview_volume_state(arranger_app, "before slider set")
    window = arranger_app.window
    window._ensure_preview_tab_initialized("arranged")
    volume_var = window._preview_volume_vars["arranged"]
    volume_var.set(float(percent))
    window._on_preview_volume_changed("arranged")
    window.update_idletasks()
    _log_preview_volume_state(arranger_app, "after slider set")


@when("the user clicks the arranged preview volume button")
def click_arranged_preview_volume_button(arranger_app: E2EHarness) -> None:
    _log_preview_volume_state(arranger_app, "before button click")
    window = arranger_app.window
    window._ensure_preview_tab_initialized("arranged")
    button = window._preview_volume_buttons.get("arranged")
    if button is not None:
        button.invoke()
    else:
        window._toggle_preview_mute("arranged")
    window.update_idletasks()
    _log_preview_volume_state(arranger_app, "after button click")


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


@then(parsers.parse("the arranged preview volume slider reads {percent:g} percent"))
def assert_arranged_volume_slider(arranger_app: E2EHarness, percent: float) -> None:
    _log_preview_volume_state(arranger_app, f"assert slider target={percent}")
    window = arranger_app.window
    volume_var = window._preview_volume_vars["arranged"]
    assert volume_var.get() == pytest.approx(percent, abs=0.25)
    controls = window._preview_volume_controls.get("arranged")
    if controls:
        slider = controls[-1]
        get = getattr(slider, "get", None)
        if callable(get):
            assert get() == pytest.approx(percent, abs=0.25)


@then(parsers.parse("the arranged preview playback volume is {value:g}"))
def assert_arranged_playback_volume(arranger_app: E2EHarness, value: float) -> None:
    _log_preview_volume_state(arranger_app, f"assert playback volume target={value}")
    playback = arranger_app.window._preview_playback.get("arranged")
    assert playback is not None
    assert playback.state.volume == pytest.approx(value, abs=1e-6)


@then("the arranged preview volume slider uses the light theme high contrast colors")
def assert_volume_slider_high_contrast(arranger_app: E2EHarness) -> None:
    window = arranger_app.window
    window._ensure_preview_tab_initialized("arranged")
    controls = window._preview_volume_controls.get("arranged")
    assert controls, "Preview volume controls were not initialised"

    theme = themes.get_theme("light")
    slider_spec = theme.styles.get("info.Horizontal.TScale", {})
    trough_spec = (slider_spec.get("troughcolor") or "").lower()
    border_spec = (slider_spec.get("bordercolor") or "").lower()
    background_spec = (slider_spec.get("background") or "").lower()
    light_spec = (slider_spec.get("lightcolor") or "").lower()
    dark_spec = (slider_spec.get("darkcolor") or "").lower()
    trough_element = theme.styles.get("Horizontal.Scale.trough", {})
    trough_background_spec = (trough_element.get("background") or "").lower()
    trough_fill_spec = (trough_element.get("troughcolor") or "").lower()
    assert trough_spec == "#ced4da"
    assert border_spec == "#ced4da"
    assert background_spec == "#e9ecef"
    assert light_spec == "#f8f9fa"
    assert dark_spec == "#ced4da"
    assert trough_background_spec == "#495057"
    assert trough_fill_spec == "#495057"

    if getattr(window, "_headless", False):
        return

    slider = controls[-1]
    style = getattr(window, "_style", None) or get_ttk_style(window)
    cget = getattr(slider, "cget", None)
    if callable(cget):
        style_name = str(cget("style") or "")
    else:
        style_name = ""
    if not style_name:
        style_name = "info.Horizontal.TScale"

    trough = (style.lookup(style_name, "troughcolor") or "").lower()
    border = (style.lookup(style_name, "bordercolor") or "").lower()
    background = (style.lookup(style_name, "background") or "").lower()
    light = (style.lookup(style_name, "lightcolor") or "").lower()
    dark = (style.lookup(style_name, "darkcolor") or "").lower()
    trough_background = (
        style.lookup("Horizontal.Scale.trough", "background") or ""
    ).lower()
    trough_fill = (
        style.lookup("Horizontal.Scale.trough", "troughcolor") or ""
    ).lower()

    assert trough == "#ced4da"
    assert border == "#ced4da"
    assert background == "#e9ecef"
    assert light == "#f8f9fa"
    assert dark == "#ced4da"
    assert trough_background == "#495057"
    assert trough_fill == "#495057"


@then("the arranged preview mute button is pressed")
def assert_arranged_mute_button_pressed(arranger_app: E2EHarness) -> None:
    _log_preview_volume_state(arranger_app, "assert mute pressed")
    window = arranger_app.window
    button = window._preview_volume_buttons.get("arranged")
    if button is not None:
        assert button.instate(["pressed"])
    else:
        assert abs(window._preview_volume_vars["arranged"].get()) <= 1e-6


@then("the arranged preview mute button is released")
def assert_arranged_mute_button_released(arranger_app: E2EHarness) -> None:
    _log_preview_volume_state(arranger_app, "assert mute released")
    window = arranger_app.window
    button = window._preview_volume_buttons.get("arranged")
    if button is not None:
        assert button.instate(["!pressed"])
    else:
        assert window._preview_volume_vars["arranged"].get() > 1e-6


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

