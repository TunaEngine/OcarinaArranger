"""Genetic programming arranger controls for convert settings."""

from __future__ import annotations

import tkinter as tk

from viewmodels.arranger_models import ArrangerGPSettings, gp_settings_warning


class ArrangerGPControlsMixin:
    """Manages GP arranger configuration values."""

    def _collect_arranger_gp_settings(self) -> ArrangerGPSettings:
        defaults = ArrangerGPSettings()

        def _safe_int(var: tk.Variable, fallback: int) -> int:
            try:
                return int(var.get())
            except (tk.TclError, ValueError, TypeError, AttributeError):
                return fallback

        def _safe_float(var: tk.Variable) -> float | None:
            try:
                value = var.get()
            except (tk.TclError, AttributeError):
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

        def _safe_rate(var: tk.Variable, fallback: float) -> float:
            value = _safe_float(var)
            if value is None:
                return fallback
            if value < 0.0:
                return 0.0
            if value > 1.0:
                return 1.0
            return value

        def _safe_weight(var: tk.Variable, fallback: float) -> float:
            value = _safe_float(var)
            if value is None:
                return fallback
            return value if value >= 0 else 0.0

        preference_var = getattr(self, "arranger_gp_apply_preference", None)
        if isinstance(preference_var, tk.Variable):
            try:
                preference_value = str(preference_var.get() or "").strip().lower()
            except (tk.TclError, AttributeError):
                preference_value = defaults.apply_program_preference
        else:
            preference_value = defaults.apply_program_preference

        return ArrangerGPSettings(
            generations=_safe_int(self.arranger_gp_generations, defaults.generations),
            population_size=_safe_int(self.arranger_gp_population, defaults.population_size),
            time_budget_seconds=_safe_float(self.arranger_gp_time_budget),
            archive_size=_safe_int(self.arranger_gp_archive_size, defaults.archive_size),
            random_program_count=_safe_int(
                self.arranger_gp_random_programs, defaults.random_program_count
            ),
            crossover_rate=_safe_rate(
                self.arranger_gp_crossover, defaults.crossover_rate
            ),
            mutation_rate=_safe_rate(self.arranger_gp_mutation, defaults.mutation_rate),
            log_best_programs=_safe_int(
                self.arranger_gp_log_best, defaults.log_best_programs
            ),
            random_seed=_safe_int(self.arranger_gp_random_seed, defaults.random_seed),
            playability_weight=_safe_weight(
                self.arranger_gp_playability_weight, defaults.playability_weight
            ),
            fidelity_weight=_safe_weight(
                self.arranger_gp_fidelity_weight, defaults.fidelity_weight
            ),
            tessitura_weight=_safe_weight(
                self.arranger_gp_tessitura_weight, defaults.tessitura_weight
            ),
            program_size_weight=_safe_weight(
                self.arranger_gp_program_size_weight, defaults.program_size_weight
            ),
            contour_weight=_safe_weight(
                self.arranger_gp_contour_weight, defaults.contour_weight
            ),
            lcs_weight=_safe_weight(self.arranger_gp_lcs_weight, defaults.lcs_weight),
            pitch_weight=_safe_weight(
                self.arranger_gp_pitch_weight, defaults.pitch_weight
            ),
            fidelity_priority_weight=_safe_weight(
                self.arranger_gp_fidelity_priority_weight,
                defaults.fidelity_priority_weight,
            ),
            range_clamp_penalty=_safe_weight(
                self.arranger_gp_range_clamp_penalty, defaults.range_clamp_penalty
            ),
            range_clamp_melody_bias=_safe_weight(
                self.arranger_gp_range_clamp_melody_bias,
                defaults.range_clamp_melody_bias,
            ),
            melody_shift_weight=_safe_weight(
                self.arranger_gp_melody_shift_weight, defaults.melody_shift_weight
            ),
            rhythm_simplify_weight=_safe_weight(
                self.arranger_gp_rhythm_simplify_weight,
                defaults.rhythm_simplify_weight,
            ),
            apply_program_preference=preference_value,
        )

    def _set_arranger_gp_warning(self, settings: ArrangerGPSettings) -> None:
        warning_var = getattr(self, "arranger_gp_warning", None)
        if warning_var is None:
            return
        warning_var.set(gp_settings_warning(settings))

    def _apply_arranger_gp_vars(self, settings: ArrangerGPSettings) -> None:
        normalized = settings if isinstance(settings, ArrangerGPSettings) else ArrangerGPSettings()
        normalized = normalized.normalized()
        self._suspend_arranger_gp_trace = True
        try:
            self.arranger_gp_generations.set(normalized.generations)
            self.arranger_gp_population.set(normalized.population_size)
            if normalized.time_budget_seconds is None:
                self.arranger_gp_time_budget.set("")
            else:
                display = (f"{normalized.time_budget_seconds:.1f}").rstrip("0").rstrip(".")
                self.arranger_gp_time_budget.set(display)
            self.arranger_gp_archive_size.set(normalized.archive_size)
            self.arranger_gp_random_programs.set(normalized.random_program_count)

            def _set_rate(var: tk.Variable, value: float) -> None:
                var.set((f"{value:.2f}").rstrip("0").rstrip("."))

            def _set_weight(var: tk.Variable, value: float) -> None:
                var.set((f"{value:.3f}").rstrip("0").rstrip("."))

            _set_rate(self.arranger_gp_crossover, normalized.crossover_rate)
            _set_rate(self.arranger_gp_mutation, normalized.mutation_rate)
            self.arranger_gp_log_best.set(normalized.log_best_programs)
            self.arranger_gp_random_seed.set(str(normalized.random_seed))
            _set_weight(self.arranger_gp_playability_weight, normalized.playability_weight)
            _set_weight(self.arranger_gp_fidelity_weight, normalized.fidelity_weight)
            _set_weight(self.arranger_gp_tessitura_weight, normalized.tessitura_weight)
            _set_weight(
                self.arranger_gp_program_size_weight, normalized.program_size_weight
            )
            _set_weight(self.arranger_gp_contour_weight, normalized.contour_weight)
            _set_weight(self.arranger_gp_lcs_weight, normalized.lcs_weight)
            _set_weight(self.arranger_gp_pitch_weight, normalized.pitch_weight)
            _set_weight(
                self.arranger_gp_fidelity_priority_weight,
                normalized.fidelity_priority_weight,
            )
            _set_weight(
                self.arranger_gp_range_clamp_penalty,
                normalized.range_clamp_penalty,
            )
            _set_weight(
                self.arranger_gp_range_clamp_melody_bias,
                normalized.range_clamp_melody_bias,
            )
            _set_weight(
                self.arranger_gp_melody_shift_weight,
                normalized.melody_shift_weight,
            )
            _set_weight(
                self.arranger_gp_rhythm_simplify_weight,
                normalized.rhythm_simplify_weight,
            )
            if hasattr(self, "arranger_gp_apply_preference"):
                self.arranger_gp_apply_preference.set(
                    normalized.apply_program_preference
                )
            self._set_arranger_gp_warning(normalized)
        finally:
            self._suspend_arranger_gp_trace = False

    def _on_arranger_gp_changed(self, _key: str) -> None:
        if self._suspend_arranger_gp_trace:
            return
        settings = self._collect_arranger_gp_settings()
        self._set_arranger_gp_warning(settings)
        self._viewmodel.update_settings(arranger_gp_settings=settings)

    def reset_arranger_gp_settings(self) -> None:
        defaults = ArrangerGPSettings()
        self._viewmodel.update_settings(arranger_gp_settings=defaults)
        self._apply_arranger_gp_vars(defaults)

    def export_arranger_gp_settings(self) -> None:
        settings = self._collect_arranger_gp_settings()
        result = self._viewmodel.export_gp_settings(settings)
        if result is None:
            return
        if result.is_err():
            message = f"GP preset export failed: {result.error}"
            if hasattr(self, "status"):
                try:
                    self.status.set(message)
                except Exception:  # pragma: no cover - Tk variable failures
                    pass
            return
        if hasattr(self, "status"):
            try:
                self.status.set(self._viewmodel.state.status_message)
            except Exception:  # pragma: no cover - Tk variable failures
                pass

    def import_arranger_gp_settings(self) -> None:
        result = self._viewmodel.import_gp_settings()
        if result is None:
            return
        if result.is_err():
            message = f"GP preset import failed: {result.error}"
            if hasattr(self, "status"):
                try:
                    self.status.set(message)
                except Exception:  # pragma: no cover - Tk variable failures
                    pass
            return
        imported = result.unwrap()
        self._apply_arranger_gp_vars(imported)
        if hasattr(self, "status"):
            try:
                self.status.set(self._viewmodel.state.status_message)
            except Exception:  # pragma: no cover - Tk variable failures
                pass

    def _sync_arranger_gp_from_state(
        self, settings: ArrangerGPSettings | None
    ) -> None:
        self._apply_arranger_gp_vars(settings or ArrangerGPSettings())


__all__ = ["ArrangerGPControlsMixin"]
