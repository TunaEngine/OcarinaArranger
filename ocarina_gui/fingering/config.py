"""Configuration helpers for fingering instruments."""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from ocarina_tools.pitch import midi_to_name as pitch_midi_to_name

from .specs import InstrumentSpec, parse_note_name_safe

logger = logging.getLogger(__name__)

_CONFIG_ENV_VAR = "OCARINA_GUI_FINGERING_CONFIG_PATH"
_DEFAULT_CONFIG_FILENAME = "fingering_config.json"

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
]


def _user_config_path() -> Path:
    override = os.environ.get(_CONFIG_ENV_VAR, "").strip()
    if override:
        return Path(override)
    return Path.home() / ".ocarina_arranger" / _DEFAULT_CONFIG_FILENAME


def _default_config_path() -> Path:
    return Path(__file__).resolve().parent / "config" / _DEFAULT_CONFIG_FILENAME


def _load_config_from_path(path: Path) -> dict[str, object] | None:
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
        return None


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
                combined = list(dict.fromkeys(existing_candidates + list(fallback_candidates)))
                if len(combined) > len(existing_candidates):
                    logger.debug(
                        "Extending candidate notes from fallback",
                        extra={
                            "instrument_id": instrument_id,
                            "existing_candidates": existing_candidates,
                            "fallback_candidates": list(fallback_candidates),
                            "combined_count": len(combined),
                        },
                    )
                data["candidate_notes"] = combined
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

            combined_min = current_min
            combined_max = current_max
            if fallback_min is not None and (combined_min is None or fallback_min < combined_min):
                combined_min = fallback_min
            if fallback_max is not None and (combined_max is None or fallback_max > combined_max):
                combined_max = fallback_max

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
    data = _load_config_from_path(override_path)
    if data is not None:
        return data

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
