from __future__ import annotations

import tkinter as tk

import pytest

from ocarina_gui.preview import PreviewData


@pytest.mark.gui
def test_volume_button_switches_icons_when_muted(gui_app) -> None:
    gui_app._ensure_preview_tab_initialized("arranged")
    gui_app.update()

    button = gui_app._preview_volume_buttons["arranged"]
    icon_map = gui_app._preview_volume_icons["arranged"]

    normal_icon = tk.PhotoImage(master=gui_app, width=1, height=1)
    muted_icon = tk.PhotoImage(master=gui_app, width=1, height=1)
    icon_map["normal"] = normal_icon
    icon_map["muted"] = muted_icon

    gui_app._preview_volume_vars["arranged"].set(0.0)
    gui_app.update_idletasks()
    gui_app._update_mute_button_state("arranged")

    assert _image_name(button) == str(muted_icon)
    assert button.instate(["pressed"])

    gui_app._preview_volume_vars["arranged"].set(50.0)
    gui_app.update_idletasks()
    gui_app._update_mute_button_state("arranged")

    assert _image_name(button) == str(normal_icon)
    assert not button.instate(["pressed"])


@pytest.mark.gui
def test_volume_button_uses_text_fallback_without_icons(gui_app) -> None:
    gui_app._ensure_preview_tab_initialized("arranged")
    gui_app.update_idletasks()

    button = gui_app._preview_volume_buttons["arranged"]
    icon_map = gui_app._preview_volume_icons["arranged"]
    icon_map["normal"] = None
    icon_map["muted"] = None

    gui_app._preview_volume_vars["arranged"].set(0.0)
    gui_app.update_idletasks()
    gui_app._update_mute_button_state("arranged")

    assert _image_name(button) == ""
    assert button.cget("text") == "🔇"

    gui_app._preview_volume_vars["arranged"].set(75.0)
    gui_app.update_idletasks()
    gui_app._update_mute_button_state("arranged")

    assert _image_name(button) == ""
    assert button.cget("text") == "🔈"


@pytest.mark.gui
def test_volume_button_toggle_updates_slider(gui_app) -> None:
    gui_app._ensure_preview_tab_initialized("arranged")
    gui_app.update_idletasks()

    button = gui_app._preview_volume_buttons["arranged"]
    icon_map = gui_app._preview_volume_icons["arranged"]
    icon_map["normal"] = None
    icon_map["muted"] = None

    volume_var = gui_app._preview_volume_vars["arranged"]
    original_id = id(volume_var)
    volume_var.set(65.0)
    gui_app.update_idletasks()

    gui_app._toggle_preview_mute("arranged")
    gui_app.update()

    assert gui_app._preview_playback["arranged"].state.volume == pytest.approx(0.0)
    assert volume_var.get() == pytest.approx(0.0)
    assert gui_app._preview_volume_vars["arranged"].get() == pytest.approx(0.0)
    assert id(gui_app._preview_volume_vars["arranged"]) == original_id
    assert button.cget("text") == "🔇"

    gui_app._toggle_preview_mute("arranged")
    gui_app.update()

    assert volume_var.get() == pytest.approx(65.0)
    assert gui_app._preview_playback["arranged"].state.volume == pytest.approx(0.65)
    assert button.cget("text") == "🔈"


@pytest.mark.gui
def test_volume_survives_input_change(gui_app) -> None:
    gui_app._ensure_preview_tab_initialized("arranged")
    gui_app.update_idletasks()

    volume_var = gui_app._preview_volume_vars["arranged"]
    playback = gui_app._preview_playback["arranged"]

    volume_var.set(42.0)
    playback.state.volume = 0.42
    gui_app._preview_volume_memory["arranged"] = 42.0
    gui_app.update_idletasks()

    gui_app.input_path.set("")
    gui_app._on_input_path_changed()

    assert volume_var.get() == pytest.approx(42.0)
    assert playback.state.volume == pytest.approx(0.42)
    assert gui_app._preview_volume_memory["arranged"] == pytest.approx(42.0)


@pytest.mark.gui
def test_prepare_preview_uses_volume_memory(gui_app) -> None:
    gui_app._ensure_preview_tab_initialized("arranged")
    gui_app.update_idletasks()

    gui_app._viewmodel.update_preview_settings({})
    playback = gui_app._preview_playback["arranged"]
    playback.state.volume = 1.0

    gui_app._preview_volume_memory["arranged"] = 37.0

    preview = PreviewData(
        original_events=(),
        arranged_events=(),
        pulses_per_quarter=480,
        beats=4,
        beat_type=4,
        original_range=(60, 72),
        arranged_range=(60, 72),
        tempo_bpm=120,
        tempo_changes=(),
    )

    gui_app._prepare_preview_playback("arranged", (), preview)
    gui_app.update_idletasks()

    snapshot = gui_app._viewmodel.state.preview_settings["arranged"]
    assert snapshot.volume == pytest.approx(0.37)
    assert gui_app._preview_applied_settings["arranged"]["volume"] == pytest.approx(
        37.0
    )
    assert gui_app._preview_volume_vars["arranged"].get() == pytest.approx(37.0)
    assert gui_app._preview_volume_memory["arranged"] == pytest.approx(37.0)
    assert playback.state.volume == pytest.approx(0.37)


@pytest.mark.gui
def test_volume_button_mute_uses_playback_volume_when_slider_stale(gui_app) -> None:
    gui_app._ensure_preview_tab_initialized("arranged")
    gui_app.update_idletasks()

    playback = gui_app._preview_playback["arranged"]
    playback.state.is_loaded = True
    playback.state.is_rendering = False
    playback.state.volume = 0.6

    button = gui_app._preview_volume_buttons["arranged"]
    volume_var = gui_app._preview_volume_vars["arranged"]
    slider = gui_app._preview_volume_controls["arranged"][1]

    gui_app._preview_volume_memory["arranged"] = 0.0
    volume_var.set(0.0)
    slider.set(0.0)
    gui_app.update_idletasks()

    playback.state.volume = 0.6
    gui_app._test_audio_renderers["arranged"].volume = 0.6

    gui_app._toggle_preview_mute("arranged")
    gui_app.update_idletasks()

    assert volume_var.get() == pytest.approx(0.0, abs=1e-6)
    assert slider.get() == pytest.approx(0.0, abs=1e-6)
    assert playback.state.volume == pytest.approx(0.0, abs=1e-6)
    assert gui_app._preview_volume_memory["arranged"] == pytest.approx(60.0, abs=1e-6)


@pytest.mark.gui
def test_volume_button_mute_uses_slider_when_audio_muted(gui_app) -> None:
    gui_app._ensure_preview_tab_initialized("arranged")
    gui_app.update_idletasks()

    playback = gui_app._preview_playback["arranged"]
    playback.state.is_loaded = True
    playback.state.is_rendering = False

    volume_var = gui_app._preview_volume_vars["arranged"]
    slider = gui_app._preview_volume_controls["arranged"][1]
    button = gui_app._preview_volume_buttons["arranged"]

    gui_app._preview_volume_memory["arranged"] = 0.0

    starting_volume = 72.0
    volume_var.set(starting_volume)
    slider.set(starting_volume)
    gui_app.update_idletasks()

    playback.state.volume = 0.0
    gui_app._test_audio_renderers["arranged"].volume = 0.0

    gui_app._toggle_preview_mute("arranged")
    gui_app.update()

    assert volume_var.get() == pytest.approx(0.0, abs=1e-6)
    assert slider.get() == pytest.approx(0.0, abs=1e-6)
    assert playback.state.volume == pytest.approx(0.0, abs=1e-6)
    assert gui_app._preview_volume_memory["arranged"] == pytest.approx(
        starting_volume, abs=1e-6
    )
    assert button.instate(["pressed"])

    gui_app._toggle_preview_mute("arranged")
    gui_app.update()

    assert volume_var.get() == pytest.approx(starting_volume, abs=1e-6)
    assert slider.get() == pytest.approx(starting_volume, abs=1e-6)
    assert playback.state.volume == pytest.approx(starting_volume / 100.0, abs=1e-6)
    assert button.instate(["!pressed"])


@pytest.mark.gui
def test_volume_controls_active_during_playback(gui_app) -> None:
    gui_app._ensure_preview_tab_initialized("arranged")
    gui_app.update_idletasks()

    playback = gui_app._preview_playback["arranged"]
    playback.state.is_loaded = True
    playback.state.is_rendering = False
    playback.state.is_playing = True

    gui_app._set_preview_controls_enabled("arranged", False)

    button = gui_app._preview_volume_buttons["arranged"]
    slider = gui_app._preview_volume_controls["arranged"][1]

    assert button.instate(["!disabled"])
    assert slider.instate(["!disabled"])

    volume_var = gui_app._preview_volume_vars["arranged"]
    volume_var.set(55.0)
    gui_app.update_idletasks()

    button.invoke()
    gui_app.update()

    assert volume_var.get() == pytest.approx(0.0)
    assert playback.state.volume == pytest.approx(0.0)
    assert button.instate(["pressed"])

    button.invoke()
    gui_app.update()

    assert volume_var.get() == pytest.approx(55.0)
    assert playback.state.volume == pytest.approx(0.55)
    assert button.instate(["!pressed"])


@pytest.mark.gui
def test_volume_button_mouse_click_toggles(gui_app) -> None:
    gui_app._ensure_preview_tab_initialized("arranged")
    gui_app.update_idletasks()

    playback = gui_app._preview_playback["arranged"]
    playback.state.is_loaded = True
    playback.state.is_rendering = False

    button = gui_app._preview_volume_buttons["arranged"]
    slider = gui_app._preview_volume_controls["arranged"][1]
    volume_var = gui_app._preview_volume_vars["arranged"]

    starting_volume = 64.0
    volume_var.set(starting_volume)
    slider.set(starting_volume)
    gui_app.update_idletasks()

    button.update_idletasks()
    width = max(1, button.winfo_width())
    height = max(1, button.winfo_height())

    button.event_generate("<Enter>", x=width // 2, y=height // 2)
    button.event_generate("<ButtonPress-1>", x=width // 2, y=height // 2)
    gui_app.update()
    button.event_generate("<ButtonRelease-1>", x=width // 2, y=height // 2)
    gui_app.update()

    assert volume_var.get() == pytest.approx(0.0, abs=1e-6)
    assert slider.get() == pytest.approx(0.0, abs=1e-6)
    assert playback.state.volume == pytest.approx(0.0, abs=1e-6)
    assert gui_app._preview_volume_memory["arranged"] == pytest.approx(
        starting_volume, abs=1e-6
    )
    assert button.instate(["pressed"])

    button.event_generate("<ButtonPress-1>", x=width // 2, y=height // 2)
    gui_app.update()
    button.event_generate("<ButtonRelease-1>", x=width // 2, y=height // 2)
    gui_app.update()

    assert volume_var.get() == pytest.approx(starting_volume, abs=1e-6)
    assert slider.get() == pytest.approx(starting_volume, abs=1e-6)
    assert playback.state.volume == pytest.approx(
        starting_volume / 100.0, abs=1e-6
    )
    assert button.instate(["!pressed"])


@pytest.mark.gui
def test_volume_slider_click_pauses_and_resumes(gui_app) -> None:
    gui_app._ensure_preview_tab_initialized("arranged")
    gui_app.update_idletasks()

    playback = gui_app._preview_playback["arranged"]
    playback.state.is_loaded = True
    playback.state.is_rendering = False
    playback.state.duration_tick = 480

    gui_app._on_preview_play_toggle("arranged")
    gui_app.update()

    assert playback.state.is_playing

    slider = gui_app._preview_volume_controls["arranged"][1]
    gui_app.update_idletasks()
    width = max(1, slider.winfo_width())
    height = max(1, slider.winfo_height())

    slider.event_generate("<ButtonPress-1>", x=width // 4, y=height // 2)
    gui_app.update()

    assert not playback.state.is_playing
    assert gui_app._preview_volume_vars["arranged"].get() == pytest.approx(25.0, abs=5.0)

    slider.event_generate("<B1-Motion>", x=width, y=height // 2)
    gui_app.update()
    assert gui_app._preview_volume_vars["arranged"].get() == pytest.approx(100.0, abs=1.5)

    slider.event_generate("<ButtonRelease-1>", x=width, y=height // 2)
    gui_app.update()

    assert playback.state.is_playing
    assert gui_app._preview_volume_vars["arranged"].get() == pytest.approx(100.0, abs=1.5)


@pytest.mark.gui
def test_volume_button_mutes_after_slider_interaction(gui_app) -> None:
    gui_app._ensure_preview_tab_initialized("arranged")
    gui_app.update_idletasks()

    playback = gui_app._preview_playback["arranged"]
    playback.state.is_loaded = True
    playback.state.is_rendering = False

    button = gui_app._preview_volume_buttons["arranged"]
    slider = gui_app._preview_volume_controls["arranged"][1]

    slider.update_idletasks()
    width = max(1, slider.winfo_width())
    height = max(1, slider.winfo_height())

    slider.event_generate("<ButtonPress-1>", x=width // 2, y=height // 2)
    gui_app.update()
    slider.event_generate("<ButtonRelease-1>", x=width // 2, y=height // 2)
    gui_app.update()

    starting_volume = gui_app._preview_volume_vars["arranged"].get()
    assert starting_volume > 1.0

    button.invoke()
    gui_app.update()

    assert gui_app._preview_volume_vars["arranged"].get() == pytest.approx(0.0, abs=1e-6)
    assert slider.get() == pytest.approx(0.0, abs=1e-6)
    assert playback.state.volume == pytest.approx(0.0, abs=1e-6)
    assert button.instate(["pressed"])

    button.invoke()
    gui_app.update()

    assert gui_app._preview_volume_vars["arranged"].get() == pytest.approx(starting_volume, abs=1.5)
    assert slider.get() == pytest.approx(starting_volume, abs=1.5)
    assert playback.state.volume == pytest.approx(starting_volume / 100.0, abs=1e-6)
    assert button.instate(["!pressed"])


def _image_name(widget) -> str:
    value = widget.cget("image")
    if isinstance(value, tuple):
        return value[0] if value else ""
    return value
