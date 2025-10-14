"""Configuration helpers for fingering instruments."""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

from ocarina_tools.pitch import midi_to_name as pitch_midi_to_name

from .specs import InstrumentSpec, parse_note_name_safe

logger = logging.getLogger(__name__)

_CONFIG_ENV_VAR = "OCARINA_GUI_FINGERING_CONFIG_PATH"
_DEFAULT_CONFIG_FILENAME = "fingering_config.json"

class FingeringConfigPersistenceError(RuntimeError):
    """Raised when the fingering configuration cannot be persisted."""


__all__ = [
    "_CONFIG_ENV_VAR",
    "_DEFAULT_CONFIG_FILENAME",
    "_default_config_path",
    "_instrument_specs_from_config",
    "_load_config_from_path",
    "_load_default_spec_map",
    "_user_config_path",
    "load_fingering_config",
    "save_fingering_config",
    "FingeringConfigPersistenceError",
]


def _user_config_path() -> Path:
    override = os.environ.get(_CONFIG_ENV_VAR, "").strip()
    if override:
        return Path(override)
    return Path.home() / ".ocarina_arranger" / _DEFAULT_CONFIG_FILENAME


def _default_config_path() -> Path:
    return Path(__file__).resolve().parent / "config" / _DEFAULT_CONFIG_FILENAME


def _load_config_from_path(
    path: Path,
    *,
    invalid_handler: Callable[[Path], None] | None = None,
) -> dict[str, object] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning("Failed to read fingering config from %s: %s", path, exc)
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Invalid fingering config at %s: %s", path, exc)
        if invalid_handler is not None:
            invalid_handler(path)
        return None


def _next_backup_path(path: Path) -> Path:
    candidate = path.with_name(path.name + ".bk")
    if not candidate.exists():
        return candidate

    index = 1
    while True:
        candidate = path.with_name(f"{path.name}.bk{index}")
        if not candidate.exists():
            return candidate
        index += 1


def _reset_invalid_user_config(path: Path) -> None:
    backup_path = _next_backup_path(path)
    try:
        path.replace(backup_path)
    except OSError as exc:
        logger.warning(
            "Failed to back up invalid fingering config from %s to %s: %s",
            path,
            backup_path,
            exc,
        )
    else:
        logger.warning(
            "Moved invalid fingering config to backup %s",
            backup_path,
        )

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({}, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to recreate fingering config at %s: %s", path, exc)


@lru_cache(maxsize=1)
def _load_default_spec_map() -> dict[str, InstrumentSpec]:
    """Return the default instrument specifications keyed by identifier."""

    config = _load_config_from_path(_default_config_path())
    if not config:
        return {}

    instruments: dict[str, InstrumentSpec] = {}
    for entry in config.get("instruments", []):
        try:
            spec = InstrumentSpec.from_dict(entry)
        except Exception:  # pragma: no cover - defensive against bad defaults
            continue
        instruments[spec.instrument_id] = spec
    return instruments


def _instrument_specs_from_config(
    config: dict[str, object],
    *,
    fallback_specs: Mapping[str, InstrumentSpec] | Iterable[InstrumentSpec] | None = None,
) -> list[InstrumentSpec]:
    """Build instrument specs, hydrating missing candidate ranges from fallbacks."""

    fallback_map: dict[str, InstrumentSpec] = {}
    if fallback_specs:
        if isinstance(fallback_specs, Mapping):
            fallback_map = dict(fallback_specs)
        else:
            fallback_map = {spec.instrument_id: spec for spec in fallback_specs}

    instruments: list[InstrumentSpec] = []
    for entry in config.get("instruments", []):
        data = dict(entry)
        instrument_id = str(data.get("id", ""))
        fallback = fallback_map.get(instrument_id)
        fallback_candidates: Sequence[str] = ()
        if fallback and fallback.candidate_notes:
            fallback_candidates = tuple(str(note) for note in fallback.candidate_notes)

        if fallback_candidates:
            existing_candidates = [str(note) for note in data.get("candidate_notes", [])]
            if existing_candidates:
                data["candidate_notes"] = list(dict.fromkeys(existing_candidates))
            else:
                logger.debug(
                    "Restoring candidate notes from fallback",
                    extra={
                        "instrument_id": instrument_id,
                        "fallback_candidates": list(fallback_candidates),
                    },
                )
                data["candidate_notes"] = list(fallback_candidates)

        if fallback:
            fallback_min_name = getattr(fallback, "candidate_range_min", "")
            fallback_max_name = getattr(fallback, "candidate_range_max", "")
            fallback_min = parse_note_name_safe(fallback_min_name)
            fallback_max = parse_note_name_safe(fallback_max_name)

            range_data = data.get("candidate_range") or {}
            current_min_name = str(range_data.get("min", "")).strip()
            current_max_name = str(range_data.get("max", "")).strip()
            current_min = parse_note_name_safe(current_min_name) if current_min_name else None
            current_max = parse_note_name_safe(current_max_name) if current_max_name else None

            combined_min = current_min if current_min is not None else fallback_min
            combined_max = current_max if current_max is not None else fallback_max

            if combined_min is not None and combined_max is not None:
                data["candidate_range"] = {
                    "min": pitch_midi_to_name(combined_min, flats=False),
                    "max": pitch_midi_to_name(combined_max, flats=False),
                }

        instruments.append(InstrumentSpec.from_dict(data))

    return instruments


def load_fingering_config() -> dict[str, object]:
    """Load the fingering configuration, preferring the user override if present."""

    override_path = _user_config_path()
    data = _load_config_from_path(
        override_path,
        invalid_handler=_reset_invalid_user_config,
    )
    if data:
        return data
    if data == {}:
        logger.warning(
            "User fingering config at %s is empty; falling back to defaults.",
            override_path,
        )
    if data is not None:
        fallback = _load_config_from_path(_default_config_path())
        if fallback is not None:
            return fallback

    default_path = _default_config_path()
    try:
        raw = default_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:  # pragma: no cover - configuration must exist in source tree
        raise RuntimeError(
            "Fingering configuration file not found. Ensure fingering_config.json is available."
        ) from exc
    except OSError as exc:  # pragma: no cover - unexpected filesystem failure
        raise RuntimeError(f"Could not read fingering configuration: {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - invalid configuration
        raise RuntimeError(f"Invalid fingering configuration: {exc}") from exc


def save_fingering_config(config: dict[str, object]) -> None:
    """Persist the fingering configuration to the user override path."""

    path = _user_config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem failures are environment-specific
        logger.warning("Failed to write fingering config to %s: %s", path, exc)
        message = (
            f"Could not save fingering configuration at {path}. "
            "Free up some disk space and try again."
        )
        raise FingeringConfigPersistenceError(message) from exc
