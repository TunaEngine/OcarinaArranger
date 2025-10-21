from __future__ import annotations
import logging
import tkinter as tk
from typing import Dict

from shared.ttk import ttk

from ocarina_gui.constants import DEFAULT_MAX, DEFAULT_MIN
from ocarina_gui.preferences import (
    ARRANGER_MODES,
    DEFAULT_ARRANGER_MODE,
    Preferences,
    save_preferences,
)
from viewmodels.main_viewmodel import (
    ARRANGER_STRATEGIES,
    ARRANGER_STRATEGY_CURRENT,
    ARRANGER_STRATEGY_STARRED_BEST,
    DEFAULT_ARRANGER_STRATEGY,
)
from viewmodels.arranger_models import (
    ArrangerBudgetSettings,
    ArrangerGPSettings,
    gp_settings_warning,
)

from .arranger_results import ArrangerResultsMixin
from .convert_advanced_controls import ArrangerAdvancedControlsMixin
from .convert_gp_controls import ArrangerGPControlsMixin
from .convert_grace_controls import ArrangerGraceControlsMixin
from .convert_subhole_controls import ArrangerSubholeControlsMixin
from .convert_starred_controls import ArrangerStarredControlsMixin
from .convert_summary_controls import ArrangerSummaryControlsMixin


logger = logging.getLogger(__name__)


class ConvertControlsMixin(
    ArrangerGraceControlsMixin,
    ArrangerSubholeControlsMixin,
    ArrangerResultsMixin,
    ArrangerStarredControlsMixin,
    ArrangerSummaryControlsMixin,
    ArrangerAdvancedControlsMixin,
    ArrangerGPControlsMixin,
):
    """Initialise conversion-related Tk variables and helpers."""

    def _create_convert_controls(self, state) -> None:
        self.input_path = tk.StringVar(master=self, value=state.input_path)
        self.prefer_mode = tk.StringVar(master=self, value=state.prefer_mode)
        self.prefer_flats = tk.BooleanVar(master=self, value=state.prefer_flats)
        self.collapse_chords = tk.BooleanVar(master=self, value=state.collapse_chords)
        self.favor_lower = tk.BooleanVar(master=self, value=state.favor_lower)
        self.lenient_midi_import = tk.BooleanVar(
            master=self, value=bool(getattr(state, "lenient_midi_import", True))
        )
        self.transpose_offset = tk.IntVar(master=self, value=state.transpose_offset)
        self.convert_instrument_var = tk.StringVar(
            master=self,
            value=self._instrument_name_by_id.get(self._selected_instrument_id, ""),
        )
        self.range_min = tk.StringVar(master=self, value=state.range_min or DEFAULT_MIN)
        self.range_max = tk.StringVar(master=self, value=state.range_max or DEFAULT_MAX)
        mode_value = state.arranger_mode or DEFAULT_ARRANGER_MODE
        if mode_value not in ARRANGER_MODES:
            mode_value = DEFAULT_ARRANGER_MODE
        self.arranger_mode = tk.StringVar(master=self, value=mode_value)
        strategy_value = state.arranger_strategy or DEFAULT_ARRANGER_STRATEGY
        if strategy_value not in ARRANGER_STRATEGIES:
            strategy_value = DEFAULT_ARRANGER_STRATEGY
        self.arranger_strategy = tk.StringVar(master=self, value=strategy_value)
        self._suppress_arranger_strategy_trace = False
        dp_enabled = bool(getattr(state, "arranger_dp_slack_enabled", True))
        self.arranger_dp_slack = tk.BooleanVar(master=self, value=dp_enabled)
        budgets_state = getattr(state, "arranger_budgets", ArrangerBudgetSettings())
        if not isinstance(budgets_state, ArrangerBudgetSettings):
            budgets_state = ArrangerBudgetSettings()
        budgets_state = budgets_state.normalized()
        self.arranger_budget_octave = tk.IntVar(
            master=self, value=budgets_state.max_octave_edits
        )
        self.arranger_budget_rhythm = tk.IntVar(
            master=self, value=budgets_state.max_rhythm_edits
        )
        self.arranger_budget_substitution = tk.IntVar(
            master=self, value=budgets_state.max_substitutions
        )
        self.arranger_budget_total = tk.IntVar(
            master=self, value=budgets_state.max_steps_per_span
        )
        self._arranger_budget_vars: dict[str, tk.IntVar] = {
            "max_octave_edits": self.arranger_budget_octave,
            "max_rhythm_edits": self.arranger_budget_rhythm,
            "max_substitutions": self.arranger_budget_substitution,
            "max_steps_per_span": self.arranger_budget_total,
        }
        self._suspend_arranger_budget_trace = False
        self._suspend_arranger_dp_trace = False
        self.arranger_show_advanced = tk.BooleanVar(master=self, value=False)
        self._arranger_advanced_frames: dict[str, ttk.Frame] = {}
        self._suspend_starred_updates = False
        self._starred_instrument_vars: dict[str, tk.BooleanVar] = {}
        self._starred_var_traces: dict[str, str] = {}
        self._starred_checkbox_widgets: dict[str, ttk.Checkbutton] = {}
        self._starred_instrument_container: ttk.Frame | None = None
        self._arranger_summary_container: ttk.Frame | None = None
        self._arranger_summary_body: ttk.Frame | None = None
        self._arranger_summary_placeholder: ttk.Label | None = None
        self.midi_import_notice = tk.StringVar(master=self, value="")
        self._midi_notice_frame: ttk.Frame | None = None
        self._midi_notice_button: ttk.Button | None = None
        self._suspend_lenient_midi_trace = False
        gp_state = getattr(state, "arranger_gp_settings", ArrangerGPSettings())
        if not isinstance(gp_state, ArrangerGPSettings):
            gp_state = ArrangerGPSettings()
        gp_state = gp_state.normalized()
        self.arranger_gp_generations = tk.IntVar(
            master=self, value=gp_state.generations
        )
        self.arranger_gp_population = tk.IntVar(
            master=self, value=gp_state.population_size
        )
        if gp_state.time_budget_seconds is None:
            gp_budget_text = ""
        else:
            gp_budget_text = (f"{gp_state.time_budget_seconds:.1f}").rstrip("0").rstrip(".")

        def _format_float(value: float, precision: int = 3) -> str:
            display = f"{value:.{precision}f}".rstrip("0").rstrip(".")
            return display or "0"

        self.arranger_gp_time_budget = tk.StringVar(
            master=self, value=gp_budget_text
        )
        self.arranger_gp_archive_size = tk.IntVar(
            master=self, value=gp_state.archive_size
        )
        self.arranger_gp_random_programs = tk.IntVar(
            master=self, value=gp_state.random_program_count
        )
        self.arranger_gp_crossover = tk.StringVar(
            master=self, value=_format_float(gp_state.crossover_rate, precision=2)
        )
        self.arranger_gp_mutation = tk.StringVar(
            master=self, value=_format_float(gp_state.mutation_rate, precision=2)
        )
        self.arranger_gp_log_best = tk.IntVar(
            master=self, value=gp_state.log_best_programs
        )
        self.arranger_gp_random_seed = tk.StringVar(
            master=self, value=str(gp_state.random_seed)
        )
        self.arranger_gp_playability_weight = tk.StringVar(
            master=self, value=_format_float(gp_state.playability_weight)
        )
        self.arranger_gp_fidelity_weight = tk.StringVar(
            master=self, value=_format_float(gp_state.fidelity_weight)
        )
        self.arranger_gp_tessitura_weight = tk.StringVar(
            master=self, value=_format_float(gp_state.tessitura_weight)
        )
        self.arranger_gp_program_size_weight = tk.StringVar(
            master=self, value=_format_float(gp_state.program_size_weight)
        )
        self.arranger_gp_contour_weight = tk.StringVar(
            master=self, value=_format_float(gp_state.contour_weight)
        )
        self.arranger_gp_lcs_weight = tk.StringVar(
            master=self, value=_format_float(gp_state.lcs_weight)
        )
        self.arranger_gp_pitch_weight = tk.StringVar(
            master=self, value=_format_float(gp_state.pitch_weight)
        )
        self.arranger_gp_fidelity_priority_weight = tk.StringVar(
            master=self, value=_format_float(gp_state.fidelity_priority_weight)
        )
        self.arranger_gp_range_clamp_penalty = tk.StringVar(
            master=self, value=_format_float(gp_state.range_clamp_penalty)
        )
        self.arranger_gp_range_clamp_melody_bias = tk.StringVar(
            master=self, value=_format_float(gp_state.range_clamp_melody_bias)
        )
        self.arranger_gp_melody_shift_weight = tk.StringVar(
            master=self, value=_format_float(gp_state.melody_shift_weight)
        )
        self.arranger_gp_rhythm_simplify_weight = tk.StringVar(
            master=self, value=_format_float(gp_state.rhythm_simplify_weight)
        )
        self.arranger_gp_apply_preference = tk.StringVar(
            master=self, value=gp_state.apply_program_preference
        )
        self.arranger_gp_warning = tk.StringVar(
            master=self, value=gp_settings_warning(gp_state)
        )
        self._arranger_gp_vars: dict[str, tk.Variable] = {
            "generations": self.arranger_gp_generations,
            "population_size": self.arranger_gp_population,
            "time_budget_seconds": self.arranger_gp_time_budget,
            "archive_size": self.arranger_gp_archive_size,
            "random_program_count": self.arranger_gp_random_programs,
            "crossover_rate": self.arranger_gp_crossover,
            "mutation_rate": self.arranger_gp_mutation,
            "log_best_programs": self.arranger_gp_log_best,
            "random_seed": self.arranger_gp_random_seed,
            "playability_weight": self.arranger_gp_playability_weight,
            "fidelity_weight": self.arranger_gp_fidelity_weight,
            "tessitura_weight": self.arranger_gp_tessitura_weight,
            "program_size_weight": self.arranger_gp_program_size_weight,
            "contour_weight": self.arranger_gp_contour_weight,
            "lcs_weight": self.arranger_gp_lcs_weight,
            "pitch_weight": self.arranger_gp_pitch_weight,
            "fidelity_priority_weight": self.arranger_gp_fidelity_priority_weight,
            "range_clamp_penalty": self.arranger_gp_range_clamp_penalty,
            "range_clamp_melody_bias": self.arranger_gp_range_clamp_melody_bias,
            "melody_shift_weight": self.arranger_gp_melody_shift_weight,
            "rhythm_simplify_weight": self.arranger_gp_rhythm_simplify_weight,
            "apply_program_preference": self.arranger_gp_apply_preference,
        }
        self._suspend_arranger_gp_trace = False
        self._initialize_grace_controls(state)
        self._initialize_subhole_controls(state)
        self._initialise_arranger_results(state)
        self.status = tk.StringVar(master=self, value=state.status_message)
        self._reimport_button: ttk.Button | None = None
        self._last_imported_path: str | None = None
        self._last_import_settings: Dict[str, object] = {}
        self._convert_setting_traces: list[tuple[tk.Variable, str]] = []
        self._suppress_arranger_mode_trace = False
        self._register_convert_setting_var(self.prefer_mode)
        self._register_convert_setting_var(self.prefer_flats)
        self._register_convert_setting_var(self.collapse_chords)
        self._register_convert_setting_var(self.favor_lower)
        self._register_convert_setting_var(self.lenient_midi_import)
        self._register_convert_setting_var(self.range_min)
        self._register_convert_setting_var(self.range_max)
        self._register_convert_setting_var(self.convert_instrument_var)
        self._register_convert_setting_var(self.transpose_offset)
        self._register_convert_setting_var(self.arranger_mode)
        self._register_convert_setting_var(self.arranger_strategy)
        self._register_convert_setting_var(self.arranger_dp_slack)
        for var in self._arranger_budget_vars.values():
            self._register_convert_setting_var(var)
        for var in self._arranger_gp_vars.values():
            self._register_convert_setting_var(var)
        self._register_grace_setting_vars()
        self._register_subhole_setting_vars()
        self.arranger_mode.trace_add("write", self._on_arranger_mode_changed)
        self.arranger_strategy.trace_add("write", self._on_arranger_strategy_changed)
        self.lenient_midi_import.trace_add(
            "write", self._on_lenient_midi_import_changed
        )
        self.arranger_dp_slack.trace_add(
            "write", self._on_arranger_dp_slack_changed
        )
        for key, var in self._arranger_budget_vars.items():
            var.trace_add(
                "write",
                lambda *_args, budget_key=key: self._on_arranger_budget_changed(
                    budget_key
                ),
            )
        for key, var in self._arranger_gp_vars.items():
            var.trace_add(
                "write",
                lambda *_args, gp_key=key: self._on_arranger_gp_changed(gp_key),
            )
        self._register_grace_traces()
        self._register_subhole_traces()
        self.arranger_show_advanced.trace_add(
            "write", self._on_arranger_show_advanced_changed
        )
        self.arranger_explanation_filter.trace_add(
            "write", self._on_arranger_explanation_filter_changed
        )
        if self._selected_instrument_id:
            self._on_library_instrument_changed(
                self._selected_instrument_id, update_range=False
            )

    @staticmethod
    def _format_decimal(value: object, precision: int = 3) -> str:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = 0.0
        text = f"{numeric:.{precision}f}".rstrip("0").rstrip(".")
        return text or "0"

    def _on_arranger_mode_changed(self, *_args: object) -> None:
        if self._suppress_arranger_mode_trace:
            return
        raw_value = (self.arranger_mode.get() or "").strip().lower()
        if raw_value in {"v2", "best_effort"}:
            normalized = "best_effort"
        elif raw_value in {"v1", "classic"}:
            normalized = "classic"
        elif raw_value in ARRANGER_MODES:
            normalized = raw_value
        else:
            normalized = DEFAULT_ARRANGER_MODE
        if raw_value != normalized:
            self._suppress_arranger_mode_trace = True
            try:
                self.arranger_mode.set(normalized)
            finally:
                self._suppress_arranger_mode_trace = False
            return

        self._viewmodel.update_settings(arranger_mode=normalized)

        preferences = self.preferences
        if isinstance(preferences, Preferences) and preferences.arranger_mode != normalized:
            preferences.arranger_mode = normalized
            try:
                save_preferences(preferences)
            except Exception:
                logger.warning(
                    "Failed to persist arranger mode preference", extra={"mode": normalized}
                )

        refresh = getattr(self, "_update_arranger_mode_layout", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                logger.exception(
                    "Failed to refresh arranger mode layout", extra={"mode": normalized}
                )
        advanced_refresh = getattr(self, "_update_arranger_advanced_visibility", None)
        if callable(advanced_refresh):
            try:
                advanced_refresh()
            except Exception:
                logger.debug("Advanced arranger visibility update failed", exc_info=True)

    def _on_lenient_midi_import_changed(self, *_args: object) -> None:
        if self._suspend_lenient_midi_trace:
            return
        try:
            enabled = bool(self.lenient_midi_import.get())
        except Exception:
            enabled = True
        self._viewmodel.update_settings(lenient_midi_import=enabled)
        preferences = self.preferences
        if (
            isinstance(preferences, Preferences)
            and preferences.lenient_midi_import != enabled
        ):
            preferences.lenient_midi_import = enabled
            try:
                save_preferences(preferences)
            except Exception:
                logger.warning(
                    "Failed to persist MIDI import mode preference",
                    extra={"lenient": enabled},
                )
        if not enabled and hasattr(self, "_update_midi_import_notice"):
            try:
                self._update_midi_import_notice(None)
            except Exception:
                logger.exception(
                    "Failed to hide MIDI import notice after disabling lenient mode"
                )

    def _on_arranger_strategy_changed(self, *_args: object) -> None:
        if self._suppress_arranger_strategy_trace:
            return
        raw_value = (self.arranger_strategy.get() or "").strip().lower()
        if raw_value in {"current", ARRANGER_STRATEGY_CURRENT}:
            normalized = ARRANGER_STRATEGY_CURRENT
        elif raw_value in {"starred", "starred-best"}:
            normalized = ARRANGER_STRATEGY_STARRED_BEST
        elif raw_value in ARRANGER_STRATEGIES:
            normalized = raw_value
        else:
            normalized = DEFAULT_ARRANGER_STRATEGY
        if raw_value != normalized:
            self._suppress_arranger_strategy_trace = True
            try:
                self.arranger_strategy.set(normalized)
            finally:
                self._suppress_arranger_strategy_trace = False
            return

        self._viewmodel.update_settings(arranger_strategy=normalized)



__all__ = ["ConvertControlsMixin"]
