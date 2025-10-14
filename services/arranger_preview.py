"""Services responsible for generating arranger preview summaries."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Sequence

from domain.arrangement.api import arrange
from domain.arrangement.config import FeatureFlags
from domain.arrangement.constraints import BreathSettings
from domain.arrangement.gp import arrange_v3_gp
from domain.arrangement.importers import note_events_from_phrase, phrase_from_note_events
from domain.arrangement.salvage import default_salvage_cascade
from ocarina_gui.fingering import get_available_instruments, get_instrument
from ocarina_gui.preview import PreviewData
from ocarina_tools.events import NoteEvent
from services.arranger_monophonic import ensure_monophonic

from viewmodels.arranger_models import (
    ArrangerBudgetSettings,
    ArrangerExplanationRow,
    ArrangerGPSettings,
    ArrangerInstrumentSummary,
    ArrangerResultSummary,
    ArrangerTelemetryHint,
)

from .arranger_preview_gp import (
    _gp_explanations,
    _gp_instrument_summary,
    _gp_result_summary,
    _gp_session_config,
    _gp_telemetry,
)
from .arranger_preview_utils import (
    DEFAULT_DIFFICULTY_THRESHOLD,
    _explanations_from,
    _first_program,
    _instrument_name_map,
    _instrument_range_for,
    _instrument_summary,
    _normalize_instrument_id,
    _result_summary,
    _telemetry_from,
    _to_salvage_budgets,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArrangerComputation:
    """Result bundle returned by :func:`compute_arranger_preview`."""

    summaries: tuple[ArrangerInstrumentSummary, ...]
    result_summary: ArrangerResultSummary | None
    strategy: str
    explanations: tuple[ArrangerExplanationRow, ...] = ()
    telemetry: tuple[ArrangerTelemetryHint, ...] = ()
    resolved_instrument_id: str | None = None
    resolved_starred_ids: tuple[str, ...] = ()
    arranged_events: tuple[NoteEvent, ...] | None = None


ProgressCallback = Callable[[float, str | None], None]


def _notify_progress(
    callback: ProgressCallback | None, percent: float, message: str | None = None
) -> None:
    if callback is None:
        return
    try:
        value = max(0.0, min(100.0, float(percent)))
    except (TypeError, ValueError):
        value = 0.0
    try:
        callback(value, message)
    except Exception:  # pragma: no cover - defensive safeguard
        logger.exception("Arranger progress callback failed")


def compute_arranger_preview(
    preview: PreviewData,
    *,
    arranger_mode: str,
    instrument_id: str,
    starred_instrument_ids: Sequence[str],
    strategy: str,
    dp_slack_enabled: bool,
    budgets: ArrangerBudgetSettings | None = None,
    gp_settings: ArrangerGPSettings | None = None,
    transpose_offset: int = 0,
    progress_callback: ProgressCallback | None = None,
) -> ArrangerComputation:
    """Return arranger summaries derived from ``preview`` for UI consumption."""

    strategy_normalized = (strategy or "current").strip().lower()
    mode = (arranger_mode or "classic").strip().lower()
    _notify_progress(progress_callback, 0.0, "Preparing arrangement…")
    logger.info(
        "Arranger preview requested: mode=%s strategy=%s instrument=%s dp_slack=%s",
        mode,
        strategy_normalized,
        instrument_id or "<none>",
        bool(dp_slack_enabled),
    )
    if mode not in {"best_effort", "gp"}:
        logger.info("Arranger preview using algorithm=classic (v1); returning baseline data")
        _notify_progress(progress_callback, 100.0, "Arrangement skipped for classic mode")
        return ArrangerComputation((), None, strategy=strategy_normalized)

    instrument_id = (instrument_id or "").strip()
    if not instrument_id or not preview.original_events:
        logger.debug(
            "Arranger preview missing instrument or events; cannot run arranger algorithm"
        )
        _notify_progress(progress_callback, 100.0, "Arrangement unavailable")
        return ArrangerComputation((), None, strategy=strategy_normalized)

    span = phrase_from_note_events(preview.original_events, preview.pulses_per_quarter)
    if not span.notes:
        logger.debug("Arranger preview span contained no notes; skipping arranger algorithm")
        _notify_progress(progress_callback, 100.0, "Arrangement unavailable")
        return ArrangerComputation((), None, strategy=strategy_normalized)

    try:
        manual_transpose = int(transpose_offset)
    except (TypeError, ValueError):
        manual_transpose = 0
    if manual_transpose:
        span = span.transpose(manual_transpose)

    try:
        choices = tuple(get_available_instruments())
    except Exception:
        choices = ()
    resolved_instrument_id = _normalize_instrument_id(instrument_id, choices)
    if resolved_instrument_id is None:
        logger.warning(
            "Arranger preview could not resolve instrument '%s'; skipping arranger algorithm",
            instrument_id,
        )
        _notify_progress(progress_callback, 100.0, "Instrument unavailable for arrangement")
        return ArrangerComputation((), None, strategy=strategy_normalized)

    starred_ids = tuple(
        candidate
        for candidate in (
            _normalize_instrument_id(value, choices)
            for value in starred_instrument_ids
            if value
        )
        if candidate is not None
    )

    if _instrument_range_for(resolved_instrument_id, resolver=get_instrument) is None:
        logger.warning(
            "Arranger preview missing range for instrument '%s'; skipping arranger algorithm",
            resolved_instrument_id,
        )
        _notify_progress(progress_callback, 100.0, "Instrument range unavailable")
        return ArrangerComputation((), None, strategy=strategy_normalized)

    for candidate in starred_ids:
        _instrument_range_for(candidate, resolver=get_instrument)

    name_map = _instrument_name_map(choices)

    if mode == "best_effort":
        budget_settings = (budgets or ArrangerBudgetSettings()).normalized()
        flags = FeatureFlags(dp_slack=bool(dp_slack_enabled))
        salvage_cascade = default_salvage_cascade(
            threshold=DEFAULT_DIFFICULTY_THRESHOLD,
            budgets=_to_salvage_budgets(budget_settings),
        )
        breath_settings = BreathSettings()

        try:
            strategy_result = arrange(
                span,
                instrument_id=resolved_instrument_id,
                starred_ids=starred_ids,
                strategy=strategy_normalized,
                flags=flags,
                salvage_cascade=salvage_cascade,
                tempo_bpm=float(preview.tempo_bpm) if preview.tempo_bpm else None,
                breath_settings=breath_settings,
                progress_callback=progress_callback,
            )
        except Exception:
            logger.exception("Arranger preview failed during best-effort arrange call")
            _notify_progress(progress_callback, 100.0, "Arrangement failed")
            return ArrangerComputation((), None, strategy=strategy_normalized)

        summaries = tuple(
            _instrument_summary(
                arrangement,
                name_map,
                strategy_result.chosen.instrument_id,
                transposition_offset=manual_transpose,
            )
            for arrangement in strategy_result.comparisons
        )

        chosen = strategy_result.chosen
        salvage = chosen.result.salvage
        logger.info(
            "Arranger preview using algorithm=best_effort (v2): instrument=%s strategy=%s dp_slack=%s salvage_success=%s steps=%d transposition=%+d",
            chosen.instrument_id,
            strategy_result.strategy,
            flags.dp_slack,
            bool(salvage and salvage.success),
            len(salvage.applied_steps) if salvage and salvage.applied_steps else 0,
            chosen.result.transposition,
        )
        result_summary = _result_summary(
            span,
            chosen,
            name_map,
            threshold=DEFAULT_DIFFICULTY_THRESHOLD,
            transposition_offset=manual_transpose,
        )

        program = (
            _first_program(preview.arranged_events)
            or _first_program(preview.original_events)
            or 0
        )
        arranged_events = note_events_from_phrase(chosen.result.span, program=program)
        arranged_events = ensure_monophonic(arranged_events)

        _notify_progress(progress_callback, 100.0, "Arrangement complete")
        return ArrangerComputation(
            summaries=summaries,
            result_summary=result_summary,
            strategy=strategy_result.strategy,
            explanations=_explanations_from(chosen),
            telemetry=_telemetry_from(chosen, budget_settings, DEFAULT_DIFFICULTY_THRESHOLD),
            resolved_instrument_id=resolved_instrument_id,
            resolved_starred_ids=tuple(dict.fromkeys(starred_ids)),
            arranged_events=arranged_events,
        )

    gp_config = _gp_session_config(gp_settings or ArrangerGPSettings())
    _notify_progress(progress_callback, 10.0, "Running GP arranger…")
    gp_total_generations = max(1, int(gp_config.generations or 0))

    gp_progress: Callable[[int, int], None] | None = None
    if progress_callback is not None:

        def _on_gp_generation(generation_index: int, total_generations: int) -> None:
            effective_total = total_generations or gp_total_generations
            if effective_total <= 0:
                return
            completed = min(generation_index + 1, effective_total)
            fraction = completed / effective_total
            percent = 10.0 + 89.0 * fraction
            message = f"Running GP generation {completed}/{effective_total}"
            _notify_progress(progress_callback, min(percent, 99.0), message)

        gp_progress = _on_gp_generation

    try:
        gp_result = arrange_v3_gp(
            span,
            instrument_id=resolved_instrument_id,
            starred_ids=starred_ids,
            config=gp_config,
            manual_transposition=manual_transpose,
            progress_callback=gp_progress,
        )
    except Exception:
        logger.exception("Arranger preview failed during GP arrange call")
        _notify_progress(progress_callback, 100.0, "Arrangement failed")
        return ArrangerComputation((), None, strategy=strategy_normalized)

    comparisons = tuple(
        _gp_instrument_summary(
            candidate,
            name_map,
            gp_result.chosen.instrument_id,
            transposition_offset=manual_transpose,
        )
        for candidate in gp_result.comparisons
    )

    result_summary = _gp_result_summary(
        span,
        gp_result.chosen,
        name_map,
        threshold=DEFAULT_DIFFICULTY_THRESHOLD,
        transposition_offset=manual_transpose,
    )

    chosen_strategy = getattr(gp_result, "strategy", strategy_normalized)
    program = (
        _first_program(preview.arranged_events)
        or _first_program(preview.original_events)
        or 0
    )
    if hasattr(gp_result.chosen, "arranged_events"):
        arranged_events = tuple(gp_result.chosen.arranged_events)
    else:
        arranged_events = note_events_from_phrase(gp_result.chosen.span, program=program)
        arranged_events = ensure_monophonic(arranged_events)

    _notify_progress(progress_callback, 100.0, "Arrangement complete")
    return ArrangerComputation(
        summaries=comparisons,
        result_summary=result_summary,
        strategy=chosen_strategy,
        explanations=_gp_explanations(gp_result.chosen),
        telemetry=_gp_telemetry(gp_result, gp_config),
        resolved_instrument_id=resolved_instrument_id,
        resolved_starred_ids=tuple(dict.fromkeys(starred_ids)),
        arranged_events=arranged_events,
    )


__all__ = [
    "ArrangerComputation",
    "compute_arranger_preview",
    "get_instrument",
]
