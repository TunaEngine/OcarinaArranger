from __future__ import annotations

from typing import Any, Protocol

from ocarina_gui.preferences import DEFAULT_ARRANGER_MODE
from ocarina_gui.settings import (
    GraceTransformSettings,
    SubholeTransformSettings,
)
from viewmodels.arranger_models import ArrangerGPSettings, gp_settings_warning


class SupportsGet(Protocol):
    def get(self) -> Any:  # pragma: no cover - protocol definition
        ...


def _safe_int(var: SupportsGet, fallback: int) -> int:
    try:
        return int(var.get())
    except Exception:
        return fallback


def _safe_float(var: SupportsGet) -> float | None:
    try:
        value = var.get()
    except Exception:
        return None
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _safe_rate(var: SupportsGet, fallback: float) -> float:
    value = _safe_float(var)
    if value is None:
        return fallback
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _safe_weight(var: SupportsGet, fallback: float) -> float:
    value = _safe_float(var)
    if value is None or value < 0:
        return fallback
    return value


def _safe_choice(var: SupportsGet | str | None, fallback: str) -> str:
    try:
        if hasattr(var, "get"):
            text = str(var.get() or "").strip().lower()
        else:
            text = str(var or "").strip().lower()
    except Exception:
        return fallback
    return text or fallback


def _gp_snapshot(owner: Any, defaults: ArrangerGPSettings) -> dict[str, object]:
    if not hasattr(owner, "arranger_gp_generations"):
        return {
            "generations": defaults.generations,
            "population_size": defaults.population_size,
            "time_budget_seconds": defaults.time_budget_seconds,
            "archive_size": defaults.archive_size,
            "random_program_count": defaults.random_program_count,
            "crossover_rate": defaults.crossover_rate,
            "mutation_rate": defaults.mutation_rate,
            "log_best_programs": defaults.log_best_programs,
            "random_seed": defaults.random_seed,
            "playability_weight": defaults.playability_weight,
            "fidelity_weight": defaults.fidelity_weight,
            "tessitura_weight": defaults.tessitura_weight,
            "program_size_weight": defaults.program_size_weight,
            "contour_weight": defaults.contour_weight,
            "lcs_weight": defaults.lcs_weight,
            "pitch_weight": defaults.pitch_weight,
            "fidelity_priority_weight": defaults.fidelity_priority_weight,
            "range_clamp_penalty": defaults.range_clamp_penalty,
            "range_clamp_melody_bias": defaults.range_clamp_melody_bias,
            "melody_shift_weight": defaults.melody_shift_weight,
            "rhythm_simplify_weight": defaults.rhythm_simplify_weight,
            "apply_program_preference": defaults.apply_program_preference,
        }

    snapshot = {
        "generations": _safe_int(owner.arranger_gp_generations, defaults.generations),
        "population_size": _safe_int(
            owner.arranger_gp_population, defaults.population_size
        ),
        "time_budget_seconds": _safe_float(owner.arranger_gp_time_budget),
        "archive_size": _safe_int(owner.arranger_gp_archive_size, defaults.archive_size),
        "random_program_count": _safe_int(
            owner.arranger_gp_random_programs, defaults.random_program_count
        ),
        "crossover_rate": _safe_rate(owner.arranger_gp_crossover, defaults.crossover_rate),
        "mutation_rate": _safe_rate(owner.arranger_gp_mutation, defaults.mutation_rate),
        "log_best_programs": _safe_int(
            owner.arranger_gp_log_best, defaults.log_best_programs
        ),
        "random_seed": _safe_int(owner.arranger_gp_random_seed, defaults.random_seed),
        "playability_weight": _safe_weight(
            owner.arranger_gp_playability_weight, defaults.playability_weight
        ),
        "fidelity_weight": _safe_weight(
            owner.arranger_gp_fidelity_weight, defaults.fidelity_weight
        ),
        "tessitura_weight": _safe_weight(
            owner.arranger_gp_tessitura_weight, defaults.tessitura_weight
        ),
        "program_size_weight": _safe_weight(
            owner.arranger_gp_program_size_weight, defaults.program_size_weight
        ),
        "contour_weight": _safe_weight(
            owner.arranger_gp_contour_weight, defaults.contour_weight
        ),
        "lcs_weight": _safe_weight(owner.arranger_gp_lcs_weight, defaults.lcs_weight),
        "pitch_weight": _safe_weight(owner.arranger_gp_pitch_weight, defaults.pitch_weight),
        "fidelity_priority_weight": _safe_weight(
            owner.arranger_gp_fidelity_priority_weight,
            defaults.fidelity_priority_weight,
        ),
        "range_clamp_penalty": _safe_weight(
            owner.arranger_gp_range_clamp_penalty, defaults.range_clamp_penalty
        ),
        "range_clamp_melody_bias": _safe_weight(
            owner.arranger_gp_range_clamp_melody_bias,
            defaults.range_clamp_melody_bias,
        ),
        "melody_shift_weight": _safe_weight(
            owner.arranger_gp_melody_shift_weight, defaults.melody_shift_weight
        ),
        "rhythm_simplify_weight": _safe_weight(
            getattr(owner, "arranger_gp_rhythm_simplify_weight", defaults.rhythm_simplify_weight),
            defaults.rhythm_simplify_weight,
        ),
        "apply_program_preference": _safe_choice(
            getattr(owner, "arranger_gp_apply_preference", defaults.apply_program_preference),
            defaults.apply_program_preference,
        ),
    }
    try:
        settings = ArrangerGPSettings(**snapshot)
    except TypeError:
        settings = ArrangerGPSettings()
    warning_var = getattr(owner, "arranger_gp_warning", None)
    if warning_var is not None:
        try:
            warning_var.set(gp_settings_warning(settings))
        except Exception:
            pass
    return snapshot


def _grace_snapshot(owner: Any, defaults: GraceTransformSettings) -> dict[str, object]:
    if not hasattr(owner, "_collect_grace_settings"):
        settings = defaults
    else:
        try:
            settings = owner._collect_grace_settings().normalized()
        except Exception:
            settings = defaults
    return {
        "policy": settings.policy,
        "fractions": list(settings.fractions),
        "max_chain": settings.max_chain,
        "anchor_min_fraction": settings.anchor_min_fraction,
        "fold_out_of_range": settings.fold_out_of_range,
        "drop_out_of_range": settings.drop_out_of_range,
        "slow_tempo_bpm": settings.slow_tempo_bpm,
        "fast_tempo_bpm": settings.fast_tempo_bpm,
        "grace_bonus": settings.grace_bonus,
        "fast_windway_switch_weight": settings.fast_windway_switch_weight,
    }


def _subhole_snapshot(owner: Any, defaults: SubholeTransformSettings) -> dict[str, object]:
    if not hasattr(owner, "_collect_subhole_settings"):
        settings = defaults
    else:
        try:
            settings = owner._collect_subhole_settings().normalized()
        except Exception:
            settings = defaults
    return {
        "max_changes_per_second": settings.max_changes_per_second,
        "max_subhole_changes_per_second": settings.max_subhole_changes_per_second,
        "pair_limits": [list(entry) for entry in settings.pair_limits],
    }


def build_convert_snapshot(owner: Any) -> dict[str, object]:
    gp_defaults = ArrangerGPSettings()
    grace_defaults = GraceTransformSettings().normalized()
    subhole_defaults = SubholeTransformSettings().normalized()

    snapshot: dict[str, object] = {
        "prefer_mode": owner.prefer_mode.get(),
        "prefer_flats": bool(owner.prefer_flats.get()),
        "collapse_chords": bool(owner.collapse_chords.get()),
        "favor_lower": bool(owner.favor_lower.get()),
        "range_min": owner.range_min.get(),
        "range_max": owner.range_max.get(),
        "instrument_id": getattr(owner, "_selected_instrument_id", ""),
    }

    transpose_var = getattr(owner, "transpose_offset", None)
    if hasattr(transpose_var, "get"):
        try:
            snapshot["transpose_offset"] = int(transpose_var.get())
        except Exception:
            snapshot["transpose_offset"] = getattr(owner, "_transpose_applied_offset", 0)
    else:
        snapshot["transpose_offset"] = getattr(owner, "_transpose_applied_offset", 0)

    arranger_mode_var = getattr(owner, "arranger_mode", None)
    snapshot["arranger_mode"] = (
        arranger_mode_var.get() if hasattr(arranger_mode_var, "get") else DEFAULT_ARRANGER_MODE
    )

    if hasattr(owner, "arranger_dp_slack"):
        snapshot["arranger_dp_slack"] = bool(owner.arranger_dp_slack.get())
    else:
        snapshot["arranger_dp_slack"] = False

    if hasattr(owner, "arranger_budget_octave"):
        snapshot["arranger_budgets"] = (
            _safe_int(owner.arranger_budget_octave, 1),
            _safe_int(owner.arranger_budget_rhythm, 1),
            _safe_int(owner.arranger_budget_substitution, 1),
            _safe_int(owner.arranger_budget_total, 3),
        )
    else:
        snapshot["arranger_budgets"] = (1, 1, 1, 3)

    snapshot["arranger_gp_settings"] = _gp_snapshot(owner, gp_defaults)
    snapshot["grace_settings"] = _grace_snapshot(owner, grace_defaults)
    snapshot["subhole_settings"] = _subhole_snapshot(owner, subhole_defaults)

    lenient_var = getattr(owner, "lenient_midi_import", None)
    snapshot["lenient_midi_import"] = bool(lenient_var.get()) if hasattr(lenient_var, "get") else True

    return snapshot
