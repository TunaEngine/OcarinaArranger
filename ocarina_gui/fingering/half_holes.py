"""Helpers for instruments that support half-hole fingerings."""

from __future__ import annotations

from typing import Final

from .config import load_fingering_config
from .library import get_instrument, update_library_from_config

__all__ = ["instrument_allows_half_holes", "set_instrument_half_holes"]

# The stock six-hole ocarina supports half-holes by default.
_DEFAULT_HALF_HOLE_INSTRUMENT_IDS: Final[frozenset[str]] = frozenset({"alto_c_6"})


def instrument_allows_half_holes(instrument_id: str) -> bool:
    """Return ``True`` if the instrument supports half-hole fingerings."""

    key = str(instrument_id).strip()
    if not key:
        return False
    try:
        spec = get_instrument(key)
    except ValueError:
        return key in _DEFAULT_HALF_HOLE_INSTRUMENT_IDS
    return bool(getattr(spec, "allow_half_holes", key in _DEFAULT_HALF_HOLE_INSTRUMENT_IDS))


def _ensure_instrument_entry(
    config: dict[str, object], instrument_id: str, spec: object
) -> dict[str, object]:
    instruments = config.setdefault("instruments", [])
    if isinstance(instruments, dict):
        entry = instruments.get(instrument_id)
        if isinstance(entry, dict):
            return entry
        instruments = list(instruments.values())
        config["instruments"] = instruments
    if isinstance(instruments, list):
        for entry in instruments:
            if isinstance(entry, dict) and str(entry.get("id", "")) == instrument_id:
                return entry
    if spec is None:
        raise KeyError(instrument_id)
    entry = spec.to_dict()  # type: ignore[attr-defined]
    if isinstance(instruments, list):
        instruments.append(entry)
    else:
        config["instruments"] = [entry]
    return entry


def set_instrument_half_holes(instrument_id: str, enabled: bool) -> None:
    """Persist the half-hole support flag for an instrument to the configuration."""

    key = str(instrument_id).strip()
    if not key:
        return

    try:
        spec = get_instrument(key)
    except ValueError:
        return

    config = load_fingering_config()
    try:
        entry = _ensure_instrument_entry(config, key, spec)
    except KeyError:
        return
    current_value = getattr(spec, "allow_half_holes", None)
    previous = entry.get("allow_half_holes") if isinstance(entry, dict) else None
    new_value = bool(enabled)
    if previous is not None and bool(previous) == new_value and current_value == new_value:
        return
    entry["allow_half_holes"] = new_value
    update_library_from_config(config, current_instrument_id=key)
