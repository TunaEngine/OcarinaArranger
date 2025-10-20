"""Helper utilities for serialising arranger GP settings in project manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from viewmodels.arranger_models import ArrangerGPSettings


PRESET_FILE_TYPE = "ocarina_gp_settings"
PRESET_VERSION = 1


class GPSettingsPresetError(Exception):
    """Raised when an imported GP preset cannot be parsed."""


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_rate(value: Any, fallback: float) -> float:
    numeric = _safe_float(value)
    if numeric is None:
        return fallback
    if numeric < 0.0:
        return 0.0
    if numeric > 1.0:
        return 1.0
    return numeric


def _safe_weight(value: Any, fallback: float) -> float:
    numeric = _safe_float(value)
    if numeric is None or numeric < 0.0:
        return fallback
    return numeric


def serialize_gp_settings(gp: ArrangerGPSettings) -> dict[str, object]:
    """Convert ``ArrangerGPSettings`` into a manifest-friendly dictionary."""

    return {
        "generations": int(gp.generations),
        "population_size": int(gp.population_size),
        "time_budget_seconds": gp.time_budget_seconds,
        "archive_size": int(gp.archive_size),
        "random_program_count": int(gp.random_program_count),
        "crossover_rate": float(gp.crossover_rate),
        "mutation_rate": float(gp.mutation_rate),
        "log_best_programs": int(gp.log_best_programs),
        "random_seed": int(gp.random_seed),
        "playability_weight": float(gp.playability_weight),
        "fidelity_weight": float(gp.fidelity_weight),
        "tessitura_weight": float(gp.tessitura_weight),
        "program_size_weight": float(gp.program_size_weight),
        "contour_weight": float(gp.contour_weight),
        "lcs_weight": float(gp.lcs_weight),
        "pitch_weight": float(gp.pitch_weight),
        "fidelity_priority_weight": float(gp.fidelity_priority_weight),
        "range_clamp_penalty": float(gp.range_clamp_penalty),
        "range_clamp_melody_bias": float(gp.range_clamp_melody_bias),
        "melody_shift_weight": float(gp.melody_shift_weight),
        "rhythm_simplify_weight": float(gp.rhythm_simplify_weight),
        "apply_program_preference": gp.apply_program_preference,
    }


def deserialize_gp_settings(
    raw_gp: Mapping[str, Any], defaults: ArrangerGPSettings
) -> ArrangerGPSettings:
    """Normalise persisted GP arranger settings back into the dataclass."""

    time_budget_raw = raw_gp.get("time_budget_seconds")
    time_budget = _safe_float(time_budget_raw)

    preference_raw = raw_gp.get(
        "apply_program_preference", defaults.apply_program_preference
    )
    preference = str(preference_raw or "").strip().lower() or defaults.apply_program_preference

    return ArrangerGPSettings(
        generations=_safe_int(raw_gp.get("generations"), defaults.generations),
        population_size=_safe_int(
            raw_gp.get("population_size"), defaults.population_size
        ),
        time_budget_seconds=time_budget,
        archive_size=_safe_int(raw_gp.get("archive_size"), defaults.archive_size),
        random_program_count=_safe_int(
            raw_gp.get("random_program_count"), defaults.random_program_count
        ),
        crossover_rate=_safe_rate(
            raw_gp.get("crossover_rate"), defaults.crossover_rate
        ),
        mutation_rate=_safe_rate(raw_gp.get("mutation_rate"), defaults.mutation_rate),
        log_best_programs=_safe_int(
            raw_gp.get("log_best_programs"), defaults.log_best_programs
        ),
        random_seed=_safe_int(raw_gp.get("random_seed"), defaults.random_seed),
        playability_weight=_safe_weight(
            raw_gp.get("playability_weight"), defaults.playability_weight
        ),
        fidelity_weight=_safe_weight(
            raw_gp.get("fidelity_weight"), defaults.fidelity_weight
        ),
        tessitura_weight=_safe_weight(
            raw_gp.get("tessitura_weight"), defaults.tessitura_weight
        ),
        program_size_weight=_safe_weight(
            raw_gp.get("program_size_weight"), defaults.program_size_weight
        ),
        contour_weight=_safe_weight(
            raw_gp.get("contour_weight"), defaults.contour_weight
        ),
        lcs_weight=_safe_weight(raw_gp.get("lcs_weight"), defaults.lcs_weight),
        pitch_weight=_safe_weight(raw_gp.get("pitch_weight"), defaults.pitch_weight),
        fidelity_priority_weight=_safe_weight(
            raw_gp.get("fidelity_priority_weight"), defaults.fidelity_priority_weight
        ),
        range_clamp_penalty=_safe_weight(
            raw_gp.get("range_clamp_penalty"), defaults.range_clamp_penalty
        ),
        range_clamp_melody_bias=_safe_weight(
            raw_gp.get("range_clamp_melody_bias"), defaults.range_clamp_melody_bias
        ),
        melody_shift_weight=_safe_weight(
            raw_gp.get("melody_shift_weight"), defaults.melody_shift_weight
        ),
        rhythm_simplify_weight=_safe_weight(
            raw_gp.get("rhythm_simplify_weight"), defaults.rhythm_simplify_weight
        ),
        apply_program_preference=preference,
    ).normalized()


def build_gp_preset_payload(settings: ArrangerGPSettings) -> dict[str, object]:
    """Create a serialisable payload containing GP settings metadata."""

    return {
        "type": PRESET_FILE_TYPE,
        "version": PRESET_VERSION,
        "settings": serialize_gp_settings(settings),
    }


def export_gp_preset(
    settings: ArrangerGPSettings, destination: Path
) -> Path:
    """Write the GP settings preset to ``destination`` and return the path."""

    payload = build_gp_preset_payload(settings)
    destination = Path(destination)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination


def import_gp_preset(
    source: Path, defaults: ArrangerGPSettings
) -> ArrangerGPSettings:
    """Parse GP settings from ``source`` using ``defaults`` as fallbacks."""

    try:
        raw_text = Path(source).read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - depends on filesystem errors
        raise GPSettingsPresetError(str(exc)) from exc
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise GPSettingsPresetError("Preset file is not valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise GPSettingsPresetError("Preset file must contain a JSON object")

    preset_type = str(payload.get("type", "")).strip().lower()
    if preset_type and preset_type != PRESET_FILE_TYPE:
        raise GPSettingsPresetError("Preset file type is not recognised")

    version = payload.get("version", PRESET_VERSION)
    try:
        version_number = int(version)
    except (TypeError, ValueError):
        raise GPSettingsPresetError("Preset version is invalid") from None
    if version_number != PRESET_VERSION:
        raise GPSettingsPresetError(
            f"Unsupported preset version {version_number}"
        )

    settings_payload = payload.get("settings")
    if not isinstance(settings_payload, Mapping):
        raise GPSettingsPresetError("Preset is missing the settings payload")

    return deserialize_gp_settings(settings_payload, defaults)


__all__ = [
    "GPSettingsPresetError",
    "PRESET_FILE_TYPE",
    "PRESET_VERSION",
    "build_gp_preset_payload",
    "deserialize_gp_settings",
    "export_gp_preset",
    "import_gp_preset",
    "serialize_gp_settings",
]
