"""Concrete :class:`StaffView` widget composition."""

from __future__ import annotations

from .base import StaffViewBase
from .interaction import StaffViewInteractionMixin
from .scrolling import StaffViewScrollingMixin

__all__ = ["StaffView"]


class StaffView(StaffViewInteractionMixin, StaffViewScrollingMixin, StaffViewBase):
    """Treble staff canvas used in the preview tab."""

    pass
