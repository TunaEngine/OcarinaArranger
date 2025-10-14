"""Main window package exposing the Tkinter application window."""

from __future__ import annotations

import time as _time
from tkinter import messagebox as _messagebox
from typing import Any

time = _time
messagebox = _messagebox

__all__ = [
    "MainWindow",
    "messagebox",
    "prompt_for_instrument_choice",
    "prompt_for_note_name",
    "time",
]


def __getattr__(name: str) -> Any:
    if name == "MainWindow":
        from .window import MainWindow

        return MainWindow
    if name == "prompt_for_note_name":
        from ocarina_gui.note_selection import prompt_for_note_name

        return prompt_for_note_name
    if name == "prompt_for_instrument_choice":
        from ocarina_gui.instrument_selection import prompt_for_instrument_choice

        return prompt_for_instrument_choice
    raise AttributeError(f"module 'ui.main_window' has no attribute {name!r}")
