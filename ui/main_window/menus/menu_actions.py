"""Aggregate :class:`MenuActionsMixin` definition."""

from __future__ import annotations

from .auto_scroll import AutoScrollMixin
from .instrument_layout import InstrumentLayoutMixin
from .lifecycle import LifecycleMixin
from .logging_menu import LoggingMenuMixin
from .menu_builder import MenuBuilderMixin
from .preview import PreviewMixin
from .project_menu import ProjectMenuMixin
from .support import SupportMenuMixin
from .theme import ThemeMenuMixin
from .update_menu import UpdateMenuMixin


class MenuActionsMixin(
    ThemeMenuMixin,
    LoggingMenuMixin,
    ProjectMenuMixin,
    AutoScrollMixin,
    PreviewMixin,
    InstrumentLayoutMixin,
    LifecycleMixin,
    MenuBuilderMixin,
    SupportMenuMixin,
    UpdateMenuMixin,
):
    """Menu, theme, and logging helpers shared by :class:`MainWindow`."""

    pass
