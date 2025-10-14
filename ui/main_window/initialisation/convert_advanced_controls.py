"""Advanced arranger settings helpers for convert controls."""

from __future__ import annotations

import tkinter as tk

from shared.ttk import ttk

from viewmodels.arranger_models import ArrangerBudgetSettings


class ArrangerAdvancedControlsMixin:
    """Manages advanced arranger preferences and budgets."""

    _arranger_advanced_frames: dict[str, ttk.Frame]

    def _register_arranger_advanced_frame(
        self, frame: ttk.Frame, *, mode: str
    ) -> None:
        if not hasattr(self, "_arranger_advanced_frames"):
            self._arranger_advanced_frames = {}
        self._arranger_advanced_frames[mode] = frame
        self._update_arranger_advanced_visibility()

    def _update_arranger_advanced_visibility(self) -> None:
        frames = getattr(self, "_arranger_advanced_frames", {})
        if not frames:
            return
        current_mode = (self.arranger_mode.get() or "").strip().lower()
        show = bool(self.arranger_show_advanced.get())
        for mode, frame in frames.items():
            if show and mode == current_mode:
                frame.grid()
            else:
                frame.grid_remove()

    def _on_arranger_show_advanced_changed(self, *_args: object) -> None:
        self._update_arranger_advanced_visibility()

    def _on_arranger_dp_slack_changed(self, *_args: object) -> None:
        if self._suspend_arranger_dp_trace:
            return
        try:
            enabled = bool(self.arranger_dp_slack.get())
        except (tk.TclError, AttributeError):
            enabled = False
        self._viewmodel.update_settings(arranger_dp_slack_enabled=enabled)

    def _collect_arranger_budget_values(self) -> ArrangerBudgetSettings:
        def _safe_get(var: tk.IntVar, fallback: int) -> int:
            try:
                return int(var.get())
            except (tk.TclError, ValueError, TypeError, AttributeError):
                return fallback

        return ArrangerBudgetSettings(
            max_octave_edits=_safe_get(self.arranger_budget_octave, 1),
            max_rhythm_edits=_safe_get(self.arranger_budget_rhythm, 1),
            max_substitutions=_safe_get(self.arranger_budget_substitution, 1),
            max_steps_per_span=_safe_get(self.arranger_budget_total, 3),
        )

    def _apply_arranger_budget_vars(self, budgets: ArrangerBudgetSettings) -> None:
        normalized = budgets if isinstance(budgets, ArrangerBudgetSettings) else ArrangerBudgetSettings()
        if not isinstance(budgets, ArrangerBudgetSettings):
            normalized = ArrangerBudgetSettings()
        normalized = normalized.normalized()
        self._suspend_arranger_budget_trace = True
        try:
            self.arranger_budget_octave.set(normalized.max_octave_edits)
            self.arranger_budget_rhythm.set(normalized.max_rhythm_edits)
            self.arranger_budget_substitution.set(normalized.max_substitutions)
            self.arranger_budget_total.set(normalized.max_steps_per_span)
        finally:
            self._suspend_arranger_budget_trace = False

    def _on_arranger_budget_changed(self, _key: str) -> None:
        if self._suspend_arranger_budget_trace:
            return
        budgets = self._collect_arranger_budget_values()
        self._viewmodel.update_settings(arranger_budgets=budgets)

    def reset_arranger_budgets(self) -> None:
        defaults = ArrangerBudgetSettings()
        self._viewmodel.update_settings(arranger_budgets=defaults)
        self._apply_arranger_budget_vars(defaults)

    def _sync_arranger_budgets_from_state(
        self, budgets: ArrangerBudgetSettings | None
    ) -> None:
        if budgets is None:
            budgets = ArrangerBudgetSettings()
        self._apply_arranger_budget_vars(budgets)


__all__ = ["ArrangerAdvancedControlsMixin"]
