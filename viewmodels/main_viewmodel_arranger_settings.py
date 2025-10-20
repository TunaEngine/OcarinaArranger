"""Utilities for normalising arranger-related view-model settings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ocarina_gui.settings import GraceTransformSettings

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

        raw_preference = arranger_gp_settings.get(
            "apply_program_preference", base.apply_program_preference
        )
        if isinstance(raw_preference, str):
            preference_value = raw_preference.strip().lower()
        else:
            preference_value = base.apply_program_preference

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
            fidelity_priority_weight=_get_float(
                "fidelity_priority_weight", base.fidelity_priority_weight
            ),
            range_clamp_penalty=_get_float(
                "range_clamp_penalty", base.range_clamp_penalty
            ),
            range_clamp_melody_bias=_get_float(
                "range_clamp_melody_bias", base.range_clamp_melody_bias
            ),
            melody_shift_weight=_get_float(
                "melody_shift_weight", base.melody_shift_weight
            ),
            rhythm_simplify_weight=_get_float(
                "rhythm_simplify_weight", base.rhythm_simplify_weight
            ),
            apply_program_preference=preference_value,
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


def normalize_grace_settings(
    grace_settings: GraceTransformSettings | Mapping[str, Any] | None,
    base: GraceTransformSettings | None,
) -> GraceTransformSettings:
    """Coerce grace settings into a normalized ``GraceTransformSettings``."""

    if isinstance(grace_settings, GraceTransformSettings):
        candidate = grace_settings
    elif isinstance(grace_settings, Mapping):

        def _get_float(key: str, fallback: float) -> float:
            value = grace_settings.get(key, fallback)
            if value is None:
                return fallback
            try:
                return float(value)
            except (TypeError, ValueError):
                return fallback

        def _get_int(key: str, fallback: int) -> int:
            value = grace_settings.get(key, fallback)
            try:
                return int(value)
            except (TypeError, ValueError):
                return fallback

        def _get_bool(key: str, fallback: bool) -> bool:
            value = grace_settings.get(key, fallback)
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                try:
                    return bool(int(value))
                except (TypeError, ValueError):
                    return fallback
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"1", "true", "t", "yes", "on"}:
                    return True
                if normalized in {"0", "false", "f", "no", "off", ""}:
                    return False
            return fallback

        policy_value = grace_settings.get("policy", base.policy if base else "tempo-weighted")
        if isinstance(policy_value, str):
            policy = policy_value.strip()
        else:
            policy = str(policy_value)

        fractions_value = grace_settings.get("fractions")
        if isinstance(fractions_value, (list, tuple)):
            fractions_list: list[float] = []
            for raw_value in fractions_value:
                try:
                    fractions_list.append(float(raw_value))
                except (TypeError, ValueError):
                    continue
            fractions = tuple(fractions_list)
        else:
            fractions = base.fractions if base else GraceTransformSettings().fractions

        candidate = GraceTransformSettings(
            policy=policy,
            fractions=fractions,
            max_chain=_get_int("max_chain", base.max_chain if base else 3),
            anchor_min_fraction=_get_float(
                "anchor_min_fraction", base.anchor_min_fraction if base else 0.25
            ),
            fold_out_of_range=_get_bool(
                "fold_out_of_range", base.fold_out_of_range if base else True
            ),
            drop_out_of_range=_get_bool(
                "drop_out_of_range", base.drop_out_of_range if base else True
            ),
            slow_tempo_bpm=_get_float(
                "slow_tempo_bpm", base.slow_tempo_bpm if base else 60.0
            ),
            fast_tempo_bpm=_get_float(
                "fast_tempo_bpm", base.fast_tempo_bpm if base else 132.0
            ),
            grace_bonus=_get_float("grace_bonus", base.grace_bonus if base else 0.25),
        )
    else:
        candidate = base or GraceTransformSettings()
    return candidate.normalized()

