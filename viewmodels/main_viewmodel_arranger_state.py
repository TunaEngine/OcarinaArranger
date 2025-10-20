"""Mix-in containing arranger-related state update helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Optional

from viewmodels.arranger_models import (
    ArrangerBudgetSettings,
    ArrangerExplanationRow,
    ArrangerInstrumentSummary,
    ArrangerResultSummary,
    ArrangerTelemetryHint,
)

from .main_viewmodel_state import ARRANGER_STRATEGIES

_ARRANGER_RESULT_UNSET = object()


class MainViewModelArrangerStateMixin:
    """Shared helpers for manipulating arranger state on the view-model."""

    def update_arranger_summary(
        self,
        *,
        summaries: Optional[
            list[ArrangerInstrumentSummary] | tuple[ArrangerInstrumentSummary, ...]
        ] = None,
        strategy: Optional[str] = None,
    ) -> None:
        """Refresh arranger v2 summary data exposed to the UI."""

        with self._state_lock:  # type: ignore[attr-defined]
            if strategy is not None and strategy in ARRANGER_STRATEGIES:
                self.state.arranger_strategy = strategy  # type: ignore[attr-defined]
            if summaries is not None:
                self.state.arranger_strategy_summary = tuple(summaries)  # type: ignore[attr-defined]

    def update_arranger_results(
        self,
        *,
        summary: ArrangerResultSummary | None | object = _ARRANGER_RESULT_UNSET,
        explanations: Optional[Iterable[ArrangerExplanationRow]] = None,
        telemetry: Optional[Iterable[ArrangerTelemetryHint]] = None,
    ) -> None:
        """Refresh arranger v2 outcome details used by the results panel."""

        with self._state_lock:  # type: ignore[attr-defined]
            if summary is not _ARRANGER_RESULT_UNSET:
                self.state.arranger_result_summary = summary  # type: ignore[attr-defined,assignment]
            if explanations is not None:
                self.state.arranger_explanations = tuple(explanations)  # type: ignore[attr-defined]
            if telemetry is not None:
                self.state.arranger_telemetry = tuple(telemetry)  # type: ignore[attr-defined]

    def reset_arranger_budgets(self) -> None:
        """Restore arranger salvage budgets to default values."""

        with self._state_lock:  # type: ignore[attr-defined]
            self.state.arranger_budgets = ArrangerBudgetSettings()  # type: ignore[attr-defined]


__all__ = ["MainViewModelArrangerStateMixin"]

