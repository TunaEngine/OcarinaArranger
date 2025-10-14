"""Genetic programming arranger controls for convert settings."""

from __future__ import annotations

import tkinter as tk

from viewmodels.arranger_models import ArrangerGPSettings


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
        )

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
        finally:
            self._suspend_arranger_gp_trace = False

    def _on_arranger_gp_changed(self, _key: str) -> None:
        if self._suspend_arranger_gp_trace:
            return
        settings = self._collect_arranger_gp_settings()
        self._viewmodel.update_settings(arranger_gp_settings=settings)

    def reset_arranger_gp_settings(self) -> None:
        defaults = ArrangerGPSettings()
        self._viewmodel.update_settings(arranger_gp_settings=defaults)
        self._apply_arranger_gp_vars(defaults)

    def _sync_arranger_gp_from_state(
        self, settings: ArrangerGPSettings | None
    ) -> None:
        self._apply_arranger_gp_vars(settings or ArrangerGPSettings())


__all__ = ["ArrangerGPControlsMixin"]
