"""Utilities for normalising arranger-related view-model settings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .arranger_models import ArrangerBudgetSettings, ArrangerGPSettings


def normalize_arranger_budgets(
    arranger_budgets: ArrangerBudgetSettings | Mapping[str, Any] | tuple[int, int, int, int]
) -> ArrangerBudgetSettings:
    """Coerce various representations of arranger budgets into the dataclass form."""

    if isinstance(arranger_budgets, ArrangerBudgetSettings):
        budgets = arranger_budgets
    elif isinstance(arranger_budgets, Mapping):
        budgets = ArrangerBudgetSettings(
            max_octave_edits=int(arranger_budgets.get("max_octave_edits", 1)),
            max_rhythm_edits=int(arranger_budgets.get("max_rhythm_edits", 1)),
            max_substitutions=int(arranger_budgets.get("max_substitutions", 1)),
            max_steps_per_span=int(arranger_budgets.get("max_steps_per_span", 3)),
        )
    elif isinstance(arranger_budgets, tuple) and len(arranger_budgets) == 4:
        budgets = ArrangerBudgetSettings(
            max_octave_edits=int(arranger_budgets[0]),
            max_rhythm_edits=int(arranger_budgets[1]),
            max_substitutions=int(arranger_budgets[2]),
            max_steps_per_span=int(arranger_budgets[3]),
        )
    else:
        budgets = ArrangerBudgetSettings()
    return budgets.normalized()


def normalize_arranger_gp_settings(
    arranger_gp_settings: ArrangerGPSettings | Mapping[str, Any] | tuple[int, int, Any],
    base: ArrangerGPSettings,
) -> ArrangerGPSettings:
    """Coerce GP settings into a normalised ``ArrangerGPSettings`` instance."""

    if isinstance(arranger_gp_settings, ArrangerGPSettings):
        gp_settings = arranger_gp_settings
    elif isinstance(arranger_gp_settings, Mapping):

        def _get_int(key: str, fallback: int) -> int:
            value = arranger_gp_settings.get(key, fallback)
            try:
                return int(value)
            except (TypeError, ValueError):
                return fallback

        def _get_float(key: str, fallback: float) -> float:
            value = arranger_gp_settings.get(key, fallback)
            if value is None:
                return fallback
            try:
                return float(value)
            except (TypeError, ValueError):
                return fallback

        time_budget_value = arranger_gp_settings.get("time_budget_seconds")
        try:
            time_budget_seconds = (
                float(time_budget_value) if time_budget_value not in (None, "") else None
            )
        except (TypeError, ValueError):
            time_budget_seconds = None

        gp_settings = ArrangerGPSettings(
            generations=_get_int("generations", base.generations),
            population_size=_get_int("population_size", base.population_size),
            time_budget_seconds=time_budget_seconds,
            archive_size=_get_int("archive_size", base.archive_size),
            random_program_count=_get_int("random_program_count", base.random_program_count),
            crossover_rate=_get_float("crossover_rate", base.crossover_rate),
            mutation_rate=_get_float("mutation_rate", base.mutation_rate),
            log_best_programs=_get_int("log_best_programs", base.log_best_programs),
            random_seed=_get_int("random_seed", base.random_seed),
            playability_weight=_get_float("playability_weight", base.playability_weight),
            fidelity_weight=_get_float("fidelity_weight", base.fidelity_weight),
            tessitura_weight=_get_float("tessitura_weight", base.tessitura_weight),
            program_size_weight=_get_float("program_size_weight", base.program_size_weight),
            contour_weight=_get_float("contour_weight", base.contour_weight),
            lcs_weight=_get_float("lcs_weight", base.lcs_weight),
            pitch_weight=_get_float("pitch_weight", base.pitch_weight),
        )
    elif isinstance(arranger_gp_settings, tuple) and len(arranger_gp_settings) == 3:
        gp_settings = ArrangerGPSettings(
            generations=int(arranger_gp_settings[0]),
            population_size=int(arranger_gp_settings[1]),
            time_budget_seconds=arranger_gp_settings[2],
        )
    else:
        gp_settings = ArrangerGPSettings()
    return gp_settings.normalized()

