from __future__ import annotations

from types import SimpleNamespace

import pytest

from ocarina_gui.preferences import Preferences
from ui.main_window import MainWindow


class _StubVar:
    def __init__(self) -> None:
        self._value = ""
        self._traces: list[tuple[object, ...]] = []

    def trace_add(self, *args: object) -> str:
        token = f"trace-{len(self._traces)}"
        self._traces.append(args)
        return token

    def set(self, value: str) -> None:
        self._value = value

    def get(self) -> str:
        return self._value


@pytest.mark.gui
def test_startup_honors_instrument_preference(monkeypatch: pytest.MonkeyPatch) -> None:
    preferred = Preferences(instrument_id="test_alt")

    def fake_initialise_preferences(self: MainWindow) -> Preferences:
        self._preferences = preferred
        return preferred

    monkeypatch.setattr(MainWindow, "_initialise_preferences", fake_initialise_preferences)
    monkeypatch.setattr(
        "ui.main_window.main_window.get_current_theme",
        lambda: SimpleNamespace(ttk_theme="test-theme"),
    )
    monkeypatch.setattr(
        "ui.main_window.main_window.normalize_auto_scroll_mode",
        lambda _mode: SimpleNamespace(value="continuous"),
    )

    state = SimpleNamespace(arranger_mode=None, lenient_midi_import=None, instrument_id="")
    viewmodel = SimpleNamespace(state=state)

    def fake_initialise_tk_root(self: MainWindow, _theme: str | None) -> bool:
        return True

    monkeypatch.setattr(MainWindow, "_initialise_tk_root", fake_initialise_tk_root)

    def fake_create_convert_controls(self: MainWindow, _state: object) -> None:
        self.input_path = _StubVar()
        self.transpose_offset = _StubVar()

    monkeypatch.setattr(MainWindow, "_create_convert_controls", fake_create_convert_controls)

    def fake_setup_preview_state(self: MainWindow, _preferences: object, _auto_scroll: object) -> None:
        self._preview_tab_initialized = set()

    monkeypatch.setattr(MainWindow, "_setup_preview_state", fake_setup_preview_state)

    monkeypatch.setattr(MainWindow, "_setup_theme_support", lambda self, *args, **kwargs: None)
    monkeypatch.setattr(MainWindow, "_setup_auto_update_menu", lambda self, *args, **kwargs: None)
    monkeypatch.setattr(MainWindow, "_setup_fingering_defaults", lambda self: None)
    monkeypatch.setattr(MainWindow, "_setup_recent_projects", lambda self, *args, **kwargs: None)
    monkeypatch.setattr(MainWindow, "_configure_main_window_shell", lambda self: None)
    monkeypatch.setattr(MainWindow, "_initialise_preview_references", lambda self: None)
    monkeypatch.setattr(MainWindow, "_build_ui", lambda self: None)
    monkeypatch.setattr(MainWindow, "_apply_preview_layout_mode", lambda self: None)
    monkeypatch.setattr(MainWindow, "_schedule_playback_loop", lambda self: None)
    monkeypatch.setattr(MainWindow, "_setup_linux_automation", lambda self: None)

    captured: dict[str, object] = {}

    def fake_setup_instrument_attributes(self: MainWindow, main_state: object) -> None:
        captured["instrument_id"] = getattr(main_state, "instrument_id", None)

    monkeypatch.setattr(MainWindow, "_setup_instrument_attributes", fake_setup_instrument_attributes)

    app = MainWindow(viewmodel=viewmodel)

    assert captured.get("instrument_id") == "test_alt"
    assert state.instrument_id == "test_alt"

    # Prevent pytest from flagging the unused variable.
    assert app is not None
