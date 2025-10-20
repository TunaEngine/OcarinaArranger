from __future__ import annotations

from types import SimpleNamespace

import pytest

from ocarina_gui.preferences import Preferences
from ui.main_window.fingering.setup import FingeringSetupMixin
from ui.main_window.instrument_settings import InstrumentSettingsMixin


class _StubWindow(InstrumentSettingsMixin, FingeringSetupMixin):
    def __init__(self) -> None:
        self._headless = True
        self._instrument_name_by_id = {}
        self._instrument_id_by_name = {}
        self._instrument_display_names = []
        self._range_note_options = []
        self._convert_instrument_combo = None
        self._range_min_combo = None
        self._range_max_combo = None
        self._suspend_instrument_updates = False
        self._selected_instrument_id = ""
        self._viewmodel = SimpleNamespace(
            state=SimpleNamespace(instrument_id="", range_min="A4", range_max="B4")
        )
        self.refresh_calls: list[str] = []
        self._preferences: Preferences | None = None

    # InstrumentSettingsMixin expects these helpers to exist.
    def _apply_half_note_default(self, instrument_id: str) -> None:  # pragma: no cover - stub
        self.refresh_calls.append(f"half:{instrument_id}")

    def _refresh_fingering_instrument_choices(self, instrument_id: str) -> None:
        self.refresh_calls.append(f"fingering:{instrument_id}")

    def _populate_fingering_table(self) -> None:  # pragma: no cover - stub
        self.refresh_calls.append("populate")

    def _on_fingering_table_select(self) -> None:  # pragma: no cover - stub
        self.refresh_calls.append("select")

    @property
    def preferences(self) -> Preferences | None:
        return self._preferences


def test_refresh_after_layout_save_updates_convert_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, bool]] = []

    instrument_sequence = iter(["old", "new"])

    def fake_get_current_instrument_id() -> str:
        return next(instrument_sequence)

    monkeypatch.setattr(
        "ui.main_window.fingering.setup.get_current_instrument_id",
        fake_get_current_instrument_id,
    )
    monkeypatch.setattr(
        "ui.main_window.fingering.setup.set_active_instrument",
        lambda instrument_id: None,
    )

    window = _StubWindow()
    window._on_library_instrument_changed = lambda instrument_id, update_range: calls.append(
        (instrument_id, update_range)
    )

    window._refresh_fingering_after_layout_save("new")

    assert calls == [("new", True)]


def test_library_instrument_change_persists_preferences(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _StubWindow()
    window._preferences = Preferences()
    window._on_convert_setting_changed = lambda: None
    window.convert_instrument_var = SimpleNamespace(set=lambda _value: None)

    class _DummyVar:
        def __init__(self, value: str) -> None:
            self._value = value

        def set(self, value: str) -> None:
            self._value = value

        def get(self) -> str:
            return self._value

    window.range_min = _DummyVar("A4")
    window.range_max = _DummyVar("B4")

    instrument_id = "test_instrument"
    choices = [SimpleNamespace(instrument_id=instrument_id, name="Test instrument")]

    monkeypatch.setattr(
        "ui.main_window.instrument_settings.get_available_instruments",
        lambda: choices,
    )
    monkeypatch.setattr(
        "ui.main_window.instrument_settings.get_instrument", lambda _identifier: object()
    )
    monkeypatch.setattr(
        "ui.main_window.instrument_settings.collect_instrument_note_names",
        lambda _spec: ["A4", "B4"],
    )

    saved_ids: list[str] = []

    monkeypatch.setattr(
        "ui.main_window.instrument_settings.save_preferences",
        lambda prefs: saved_ids.append(prefs.instrument_id or ""),
    )

    window._on_library_instrument_changed(instrument_id, update_range=False)

    assert window._viewmodel.state.instrument_id == instrument_id
    assert window.preferences is not None
    assert window.preferences.instrument_id == instrument_id
    assert saved_ids == [instrument_id]

