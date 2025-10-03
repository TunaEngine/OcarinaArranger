from __future__ import annotations

from types import SimpleNamespace

import pytest

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
        self._viewmodel = SimpleNamespace(state=SimpleNamespace(instrument_id=""))
        self.refresh_calls: list[str] = []

    # InstrumentSettingsMixin expects these helpers to exist.
    def _apply_half_note_default(self, instrument_id: str) -> None:  # pragma: no cover - stub
        self.refresh_calls.append(f"half:{instrument_id}")

    def _refresh_fingering_instrument_choices(self, instrument_id: str) -> None:
        self.refresh_calls.append(f"fingering:{instrument_id}")

    def _populate_fingering_table(self) -> None:  # pragma: no cover - stub
        self.refresh_calls.append("populate")

    def _on_fingering_table_select(self) -> None:  # pragma: no cover - stub
        self.refresh_calls.append("select")


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

