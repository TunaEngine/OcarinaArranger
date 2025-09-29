"""Main window package exposing the Tkinter application window."""

import time as _time
from tkinter import messagebox as _messagebox

from ocarina_gui.note_selection import prompt_for_note_name

from .window import MainWindow

time = _time
messagebox = _messagebox

__all__ = ["MainWindow", "messagebox", "prompt_for_note_name", "time"]
