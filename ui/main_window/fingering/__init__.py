from __future__ import annotations

from tkinter import ttk
from typing import Optional

from ocarina_gui.fingering import FingeringGridView, FingeringView

from .columns import FingeringColumnLayoutMixin
from .edit_mode import FingeringEditModeMixin
from .events import FingeringEventMixin
from .notes import FingeringNoteActionsMixin
from .setup import FingeringSetupMixin
from .style import FingeringStyleMixin
from .table import FingeringTableMixin


class FingeringEditorMixin(
    FingeringEditModeMixin,
    FingeringEventMixin,
    FingeringNoteActionsMixin,
    FingeringSetupMixin,
    FingeringStyleMixin,
    FingeringTableMixin,
    FingeringColumnLayoutMixin,
):
    """Helpers for managing fingering editor state within the main window."""

    fingering_table: Optional[ttk.Treeview]
    fingering_preview: Optional[FingeringView]
    fingering_grid: Optional[FingeringGridView]


__all__ = ["FingeringEditorMixin"]
