"""Aggregate mixin export for main-window initialisation helpers."""

from __future__ import annotations

from .resources import MAIN_WINDOW_RESOURCE_PACKAGE, get_main_window_resource

_IMPORT_ERROR: Exception | None = None

try:
    from .convert_controls import ConvertControlsMixin as _ConvertControlsMixin
    from .fingering import FingeringInitialisationMixin as _FingeringInitialisationMixin
    from .instrument import InstrumentInitialisationMixin as _InstrumentInitialisationMixin
    from .preferences import PreferencesMixin as _PreferencesMixin
    from .preview_state import PreviewInitialisationMixin as _PreviewInitialisationMixin
    from .theme_setup import ThemeInitialisationMixin as _ThemeInitialisationMixin
    from .tk_root import TkRootMixin as _TkRootMixin
    from .tk_variables import TkVariableTrackingMixin as _TkVariableTrackingMixin
    from .ui_builder import UIBuildMixin as _UIBuildMixin
    from .viewmodel_factory import ViewModelFactoryMixin as _ViewModelFactoryMixin
except (ModuleNotFoundError, AttributeError) as exc:  # pragma: no cover - lean test envs
    _IMPORT_ERROR = exc
    _ConvertControlsMixin = None
    _FingeringInitialisationMixin = None
    _InstrumentInitialisationMixin = None
    _PreferencesMixin = None
    _PreviewInitialisationMixin = None
    _ThemeInitialisationMixin = None
    _TkRootMixin = None
    _TkVariableTrackingMixin = None
    _UIBuildMixin = None
    _ViewModelFactoryMixin = None
else:
    _IMPORT_ERROR = None


if _IMPORT_ERROR is None:

    class MainWindowInitialisationMixin(
        _PreferencesMixin,  # type: ignore[misc]
        _TkRootMixin,  # type: ignore[misc]
        _InstrumentInitialisationMixin,  # type: ignore[misc]
        _ConvertControlsMixin,  # type: ignore[misc]
        _ThemeInitialisationMixin,  # type: ignore[misc]
        _FingeringInitialisationMixin,  # type: ignore[misc]
        _PreviewInitialisationMixin,  # type: ignore[misc]
        _ViewModelFactoryMixin,  # type: ignore[misc]
        _UIBuildMixin,  # type: ignore[misc]
        _TkVariableTrackingMixin,  # type: ignore[misc]
    ):
        """Aggregate mixin used by :class:`ui.main_window.main_window.MainWindow`."""

else:  # pragma: no cover - exercised only when ttkbootstrap is unavailable

    class MainWindowInitialisationMixin:  # type: ignore[too-few-public-methods]
        """Placeholder raising the import error when initialisation is attempted."""

        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise _IMPORT_ERROR  # type: ignore[misc]


__all__ = [
    "MainWindowInitialisationMixin",
    "MAIN_WINDOW_RESOURCE_PACKAGE",
    "get_main_window_resource",
    "_get_main_window_resource",
]

# Backwards compatibility with legacy imports in tests expecting the old helper
_get_main_window_resource = get_main_window_resource
