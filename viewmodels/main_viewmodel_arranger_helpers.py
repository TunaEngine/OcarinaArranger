"""Helper functions used by :mod:`viewmodels.main_viewmodel`."""

from __future__ import annotations

from dataclasses import replace

from collections.abc import Callable

from ocarina_gui.preview import PreviewData

from services.arranger_preview import ArrangerComputation, compute_arranger_preview


__all__ = [
    "apply_arranger_results_from_preview",
    "preview_with_arranger_events",
]


def apply_arranger_results_from_preview(
    viewmodel: "MainViewModel",
    preview: PreviewData,
    *,
    progress_callback: Callable[[float, str | None], None] | None = None,
) -> ArrangerComputation:
    with viewmodel._state_lock:
        arranger_mode = viewmodel.state.arranger_mode
        instrument_id = viewmodel.state.instrument_id
        starred_instrument_ids = viewmodel.state.starred_instrument_ids
        strategy = viewmodel.state.arranger_strategy
        dp_slack_enabled = viewmodel.state.arranger_dp_slack_enabled
        budgets = viewmodel.state.arranger_budgets
        gp_settings = viewmodel.state.arranger_gp_settings
        transpose_offset = viewmodel.state.transpose_offset
        range_min = viewmodel.state.range_min
        range_max = viewmodel.state.range_max

    computation = compute_arranger_preview(
        preview,
        arranger_mode=arranger_mode,
        instrument_id=instrument_id,
        starred_instrument_ids=starred_instrument_ids,
        strategy=strategy,
        dp_slack_enabled=dp_slack_enabled,
        budgets=budgets,
        gp_settings=gp_settings,
        transpose_offset=transpose_offset,
        selected_instrument_range=(range_min, range_max),
        progress_callback=progress_callback,
    )

    winner_id = next(
        (summary.instrument_id for summary in computation.summaries if summary.is_winner),
        None,
    )

    with viewmodel._state_lock:
        prior_instrument = viewmodel.state.instrument_id
        instrument_changed = False
        if (
            computation.resolved_instrument_id
            and computation.resolved_instrument_id != prior_instrument
        ):
            viewmodel.state.instrument_id = computation.resolved_instrument_id
            instrument_changed = True
        elif (
            computation.resolved_instrument_id is None
            and winner_id
            and winner_id != prior_instrument
        ):
            viewmodel.state.instrument_id = winner_id
            instrument_changed = True

        if (
            computation.resolved_starred_ids
            and computation.resolved_starred_ids != viewmodel.state.starred_instrument_ids
        ):
            viewmodel.state.starred_instrument_ids = computation.resolved_starred_ids

        if instrument_changed and computation.resolved_instrument_range:
            range_min, range_max = computation.resolved_instrument_range
            if range_min:
                viewmodel.state.range_min = range_min
            if range_max:
                viewmodel.state.range_max = range_max

    viewmodel.update_arranger_summary(
        summaries=computation.summaries,
        strategy=computation.strategy,
    )
    viewmodel.update_arranger_results(
        summary=computation.result_summary,
        explanations=computation.explanations,
        telemetry=computation.telemetry,
    )

    return computation


def preview_with_arranger_events(
    preview: PreviewData, computation: ArrangerComputation | None
) -> PreviewData:
    if computation is None or computation.arranged_events is None:
        return preview

    arranged_events = computation.arranged_events
    arranged_range = preview.arranged_range
    if arranged_events:
        lowest = min(event.midi for event in arranged_events)
        highest = max(event.midi for event in arranged_events)
        arranged_range = (lowest, highest)

    return replace(
        preview,
        arranged_events=arranged_events,
        arranged_range=arranged_range,
    )


from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - avoids circular import at runtime
    from .main_viewmodel import MainViewModel
