from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from typing import Callable

import pytest

from ocarina_gui.fingering import InstrumentSpec, get_instrument
from ocarina_gui.fingering.grid import FingeringGridView


class _RecordingView(tk.Canvas):
    def __init__(self, master: tk.Misc, *, scale: float) -> None:
        super().__init__(master, width=10, height=10, highlightthickness=0)
        self.scale = scale
        self.calls: list[tuple[str, int | None]] = []

    def show_fingering(self, note: str, midi: int | None) -> None:
        self.calls.append((note, midi))


@pytest.mark.gui
def test_grid_updates_only_changed_note(monkeypatch: pytest.MonkeyPatch) -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    root.withdraw()

    instrument = get_instrument("alto_c_6")
    state = {"spec": instrument}
    listeners: list[Callable[[InstrumentSpec], None]] = []

    def fake_register(listener: Callable[[InstrumentSpec], None]) -> Callable[[], None]:
        listeners.append(listener)

        def _unsubscribe() -> None:
            try:
                listeners.remove(listener)
            except ValueError:  # pragma: no cover - defensive cleanup
                pass

        return _unsubscribe

    monkeypatch.setattr(
        "ocarina_gui.fingering.grid.get_current_instrument", lambda: state["spec"]
    )
    monkeypatch.setattr(
        "ocarina_gui.fingering.grid.register_instrument_listener", fake_register
    )

    try:
        grid = FingeringGridView(
            root,
            view_factory=lambda parent, scale: _RecordingView(parent, scale=scale),
        )
        root.update_idletasks()

        # Clear the initial render calls recorded during construction.
        for view in grid._tiles.values():  # type: ignore[attr-defined]
            view.calls.clear()  # type: ignore[attr-defined]

        assert grid._note_order, "Grid should contain fingering tiles"
        target_note = next(
            (note for note in grid._note_order if note in instrument.note_map),
            None,
        )
        if target_note is None:
            pytest.skip("Instrument does not define mapped fingerings")

        modified_map = {
            note: list(pattern) for note, pattern in instrument.note_map.items()
        }
        pattern = modified_map[target_note]
        if pattern:
            pattern[0] = 0 if pattern[0] >= 2 else 2
            modified_map[target_note] = pattern

        state["spec"] = replace(instrument, note_map=modified_map)
        for listener in list(listeners):
            listener(state["spec"])

        updated_notes = {
            note
            for note, view in grid._tiles.items()  # type: ignore[attr-defined]
            if view.calls  # type: ignore[attr-defined]
        }
        assert updated_notes == {target_note}
    finally:
        root.destroy()
