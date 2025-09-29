"""High level rendering façade for :class:`~ocarina_gui.staff.view.StaffView`."""

from __future__ import annotations

from typing import Tuple, TYPE_CHECKING

from .horizontal import HorizontalRenderer
from .note_painter import NotePainter
from .types import Event
from .wrapped import WrappedRenderer

if TYPE_CHECKING:  # pragma: no cover - only imported for typing
    from ..view import StaffView


class StaffRenderer:
    """Encapsulates drawing logic for :class:`StaffView`."""

    def __init__(self, view: "StaffView") -> None:
        self._view = view
        note_painter = NotePainter(view)
        self._horizontal = HorizontalRenderer(view, note_painter)
        self._wrapped = WrappedRenderer(view, note_painter)

    def render_horizontal(self, events: Tuple[Event, ...], beats: int, beat_type: int) -> None:
        self._horizontal.render(events, beats, beat_type)

    def render_wrapped(
        self,
        events: Tuple[Event, ...],
        pulses_per_quarter: int,
        beats: int,
        beat_type: int,
    ) -> None:
        self._wrapped.render(events, pulses_per_quarter, beats, beat_type)

    def redraw_visible_region(self, force: bool = False) -> None:
        self._horizontal.redraw_visible_region(force=force)
