"""Library management for fingering instruments."""

from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Mapping, Sequence

from .config import (
    _instrument_specs_from_config,
    _load_default_spec_map,
    load_fingering_config,
    save_fingering_config,
)
from .specs import InstrumentChoice, InstrumentSpec


__all__ = [
    "FingeringLibrary",
    "_LIBRARY",
    "get_available_instruments",
    "get_current_instrument",
    "get_current_instrument_id",
    "get_instrument",
    "set_active_instrument",
    "update_instrument_spec",
    "update_library_from_config",
    "register_instrument_listener",
]


class FingeringLibrary:
    """Manages available fingering instruments and observers."""

    def __init__(self, instruments: Sequence[InstrumentSpec]) -> None:
        if not instruments:
            raise ValueError("At least one instrument specification is required.")
        self._instruments: Dict[str, InstrumentSpec] = {
            instrument.instrument_id: instrument for instrument in instruments
        }
        self._order: List[str] = [instrument.instrument_id for instrument in instruments]
        self._current_id: str = self._order[0]
        self._listeners: List[Callable[[InstrumentSpec], None]] = []

    # ------------------------------------------------------------------
    # Access helpers
    # ------------------------------------------------------------------
    def get(self, instrument_id: str) -> InstrumentSpec:
        try:
            return self._instruments[instrument_id]
        except KeyError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Unknown fingering instrument: {instrument_id}") from exc

    def current(self) -> InstrumentSpec:
        return self._instruments[self._current_id]

    def current_id(self) -> str:
        return self._current_id

    def choices(self) -> List[InstrumentChoice]:
        return [
            InstrumentChoice(
                instrument_id=instrument_id,
                name=self._instruments[instrument_id].name,
            )
            for instrument_id in self._order
        ]

    def replace(self, instruments: Sequence[InstrumentSpec], current_id: str | None) -> None:
        if not instruments:
            raise ValueError("At least one instrument specification is required.")

        self._instruments = {instrument.instrument_id: instrument for instrument in instruments}
        self._order = [instrument.instrument_id for instrument in instruments]

        if current_id and current_id in self._instruments:
            self._current_id = current_id
        elif self._current_id not in self._instruments:
            self._current_id = instruments[0].instrument_id

        instrument = self._instruments[self._current_id]
        for listener in list(self._listeners):
            listener(instrument)

    def update_instrument(self, spec: InstrumentSpec) -> None:
        instrument_id = spec.instrument_id
        if instrument_id not in self._instruments:
            raise ValueError(f"Unknown fingering instrument: {instrument_id}")

        self._instruments[instrument_id] = spec

        try:
            index = self._order.index(instrument_id)
        except ValueError:
            self._order.append(instrument_id)
        else:
            self._order[index] = instrument_id

        if instrument_id == self._current_id:
            for listener in list(self._listeners):
                listener(spec)

    # ------------------------------------------------------------------
    # Observer management
    # ------------------------------------------------------------------
    def register(self, listener: Callable[[InstrumentSpec], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def _unsubscribe() -> None:
            try:
                self._listeners.remove(listener)
            except ValueError:  # pragma: no cover - already removed
                pass

        return _unsubscribe

    def set_current(self, instrument_id: str) -> None:
        if instrument_id == self._current_id:
            return
        if instrument_id not in self._instruments:
            raise ValueError(f"Unknown fingering instrument: {instrument_id}")
        self._current_id = instrument_id
        instrument = self._instruments[instrument_id]
        for listener in list(self._listeners):
            listener(instrument)


# ----------------------------------------------------------------------
# Module-level helpers
# ----------------------------------------------------------------------

def _load_library() -> FingeringLibrary:
    config = load_fingering_config()
    default_specs = _load_default_spec_map()
    instruments = _instrument_specs_from_config(
        config,
        fallback_specs=default_specs,
    )
    if not instruments:
        raise RuntimeError("Fingering configuration must define at least one instrument.")
    return FingeringLibrary(instruments)


_LIBRARY = _load_library()


def update_library_from_config(
    config: dict[str, object],
    *,
    current_instrument_id: str | None = None,
) -> None:
    global _LIBRARY

    fallback: Mapping[str, InstrumentSpec] | Iterable[InstrumentSpec]
    if _LIBRARY is not None:
        fallback = _LIBRARY._instruments  # type: ignore[attr-defined]
    else:
        fallback = _load_default_spec_map()

    instruments = _instrument_specs_from_config(
        config,
        fallback_specs=fallback,
    )
    if not instruments:
        raise ValueError("Fingering configuration must define at least one instrument.")

    if _LIBRARY is None:
        _LIBRARY = FingeringLibrary(instruments)
        if current_instrument_id and current_instrument_id in {
            inst.instrument_id for inst in instruments
        }:
            _LIBRARY.set_current(current_instrument_id)
        return

    preferred_id = current_instrument_id or _LIBRARY.current_id()
    _LIBRARY.replace(instruments, preferred_id)

    save_fingering_config(config)


def update_instrument_spec(spec: InstrumentSpec) -> None:
    """Replace a single instrument specification without persisting to disk."""

    _LIBRARY.update_instrument(spec)


def get_available_instruments() -> List[InstrumentChoice]:
    """Return available instruments for selection widgets."""

    return _LIBRARY.choices()


def get_current_instrument() -> InstrumentSpec:
    """Return the currently active fingering instrument."""

    return _LIBRARY.current()


def get_current_instrument_id() -> str:
    """Return the identifier of the currently active instrument."""

    return _LIBRARY.current_id()


def get_instrument(instrument_id: str) -> InstrumentSpec:
    """Lookup an instrument by identifier."""

    return _LIBRARY.get(instrument_id)


def set_active_instrument(instrument_id: str) -> None:
    """Activate the instrument with the given identifier."""

    _LIBRARY.set_current(instrument_id)


def register_instrument_listener(
    listener: Callable[[InstrumentSpec], None]
) -> Callable[[], None]:
    """Subscribe to instrument change notifications."""

    return _LIBRARY.register(listener)
