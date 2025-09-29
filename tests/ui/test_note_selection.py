import tkinter as tk

import pytest

from ocarina_gui.note_selection import prompt_for_note_name


@pytest.mark.gui
def test_prompt_for_note_name_creates_dialog_without_geometry_conflict(monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    root.withdraw()

    def _close_immediately(self, window=None):  # pragma: no cover - Tk internals
        self.update_idletasks()
        self.destroy()

    monkeypatch.setattr(
        "ocarina_gui.note_selection._NoteSelectionDialog.wait_window", _close_immediately
    )

    try:
        result = prompt_for_note_name(root, ("C4", "D4"), disabled=("C4",))
        assert result is None
    finally:
        root.update_idletasks()
        root.destroy()
