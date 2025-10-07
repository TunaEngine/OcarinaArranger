from __future__ import annotations

from tkinter import messagebox

from .base import FingeringEventBaseMixin, logger
from .heading import FingeringHeadingEventsMixin
from .preview import FingeringPreviewEventsMixin
from .table import FingeringTableEventsMixin


class FingeringEventMixin(
    FingeringTableEventsMixin,
    FingeringPreviewEventsMixin,
    FingeringHeadingEventsMixin,
    FingeringEventBaseMixin,
):
    """Event handlers for fingering editor interactions."""


__all__ = [
    "FingeringEventMixin",
    "FingeringEventBaseMixin",
    "logger",
    "messagebox",
]
