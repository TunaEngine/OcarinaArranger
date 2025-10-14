"""Public API for fingering instruments and views."""

from __future__ import annotations

from typing import Callable, List

from ocarina_gui.constants import midi_to_name, natural_of

from . import library as _library_module
from .config import (
    _CONFIG_ENV_VAR,
    _DEFAULT_CONFIG_FILENAME,
    _default_config_path,
    _instrument_specs_from_config,
    _load_config_from_path,
    _load_default_spec_map,
    _user_config_path,
    load_fingering_config,
    save_fingering_config,
    FingeringConfigPersistenceError,
)
from .grid import FingeringGridView, calculate_grid_columns
from .library import FingeringLibrary, update_instrument_spec as _update_instrument_spec
from .specs import (
    HoleSpec,
    InstrumentChoice,
    InstrumentSpec,
    OutlineSpec,
    StyleSpec,
    WindwaySpec,
    collect_instrument_note_names,
    preferred_note_window,
    parse_note_name_safe,
)
from .view import FingeringView

# Mirror the library module's state so tests can patch _LIBRARY directly on this module.
_LIBRARY = _library_module._LIBRARY


def _sync_library_to_module() -> None:
    _library_module._LIBRARY = _LIBRARY


def _sync_library_from_module() -> None:
    global _LIBRARY
    _LIBRARY = _library_module._LIBRARY


def get_available_instruments() -> List[InstrumentChoice]:
    _sync_library_to_module()
    return _library_module.get_available_instruments()


def get_current_instrument() -> InstrumentSpec:
    _sync_library_to_module()
    return _library_module.get_current_instrument()


def get_current_instrument_id() -> str:
    _sync_library_to_module()
    return _library_module.get_current_instrument_id()


def get_instrument(instrument_id: str) -> InstrumentSpec:
    _sync_library_to_module()
    return _library_module.get_instrument(instrument_id)


def set_active_instrument(instrument_id: str) -> None:
    _sync_library_to_module()
    _library_module.set_active_instrument(instrument_id)
    _sync_library_from_module()


def register_instrument_listener(
    listener: Callable[[InstrumentSpec], None]
) -> Callable[[], None]:
    _sync_library_to_module()
    return _library_module.register_instrument_listener(listener)


def update_library_from_config(
    config: dict[str, object],
    *,
    current_instrument_id: str | None = None,
) -> None:
    _sync_library_to_module()
    _library_module.update_library_from_config(
        config, current_instrument_id=current_instrument_id
    )
    _sync_library_from_module()


def update_instrument_spec(spec: InstrumentSpec) -> None:
    _sync_library_to_module()
    _update_instrument_spec(spec)
    _sync_library_from_module()


__all__ = [
    "_CONFIG_ENV_VAR",
    "_DEFAULT_CONFIG_FILENAME",
    "_LIBRARY",
    "_default_config_path",
    "_instrument_specs_from_config",
    "_load_config_from_path",
    "_load_default_spec_map",
    "_user_config_path",
    "FingeringGridView",
    "FingeringLibrary",
    "FingeringView",
    "HoleSpec",
    "InstrumentChoice",
    "InstrumentSpec",
    "OutlineSpec",
    "StyleSpec",
    "WindwaySpec",
    "calculate_grid_columns",
    "collect_instrument_note_names",
    "preferred_note_window",
    "get_available_instruments",
    "get_current_instrument",
    "get_current_instrument_id",
    "get_instrument",
    "load_fingering_config",
    "midi_to_name",
    "natural_of",
    "parse_note_name_safe",
    "register_instrument_listener",
    "save_fingering_config",
    "set_active_instrument",
    "update_instrument_spec",
    "update_library_from_config",
    "FingeringConfigPersistenceError",
]
