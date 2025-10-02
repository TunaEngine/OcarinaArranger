from __future__ import annotations

from ui.main_window.fingering.edit_mode import FingeringEditModeMixin


class _FakeTkString:
    def __init__(self, value: str):
        self.value = value

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<string object: {self.value!r}>"

    def __str__(self) -> str:
        return self.value


class _FakeCombobox:
    def __init__(self) -> None:
        self._state = _FakeTkString("readonly")

    def __setitem__(self, key: str, value: str) -> None:
        if key != "state":  # pragma: no cover - defensive
            raise KeyError(key)
        self._state = _FakeTkString(value)

    def configure(self, **kwargs: str) -> None:
        state = kwargs.get("state")
        if state is None:  # pragma: no cover - defensive
            return
        self._state = _FakeTkString(state)

    def state(self, values: list[str]) -> None:
        if not values:  # pragma: no cover - defensive
            return
        value = values[-1]
        if value.startswith("!"):
            value = "readonly"
        self._state = _FakeTkString(value)

    def cget(self, option: str) -> object:
        if option != "state":  # pragma: no cover - defensive
            raise KeyError(option)
        return self._state


class _DummyApp(FingeringEditModeMixin):
    def __init__(self) -> None:
        self._headless = False
        self.fingering_selector = None
        self._convert_instrument_combo = None

    def _selected_fingering_note(self) -> None:  # pragma: no cover - mixin contract
        return None


def test_set_instrument_switching_enabled_normalises_state_strings() -> None:
    app = _DummyApp()
    combo = _FakeCombobox()
    app.fingering_selector = combo

    app._set_instrument_switching_enabled(False)

    assert combo.cget("state") == "disabled"

    app._set_instrument_switching_enabled(True)

    assert combo.cget("state") == "readonly"
