"""Services responsible for generating arranger preview summaries."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Sequence

from domain.arrangement.api import arrange
from domain.arrangement.config import DEFAULT_GRACE_SETTINGS, FeatureFlags, GraceSettings
from domain.arrangement.constraints import BreathSettings, SubholeConstraintSettings
from domain.arrangement.gp import arrange_v3_gp
from domain.arrangement.soft_key import InstrumentRange
from domain.arrangement.importers import note_events_from_phrase, phrase_from_note_events
from domain.arrangement.salvage import default_salvage_cascade
from ocarina_gui.fingering import (
    get_available_instruments,
    get_instrument,
    preferred_note_window,
)
from ocarina_gui.preview import PreviewData
from ocarina_tools.events import NoteEvent
from ocarina_tools.pitch import midi_to_name as pitch_midi_to_name
from services.arranger_monophonic import ensure_monophonic

from viewmodels.arranger_models import (
    ArrangerBudgetSettings,
    ArrangerExplanationRow,
    ArrangerGPSettings,
    ArrangerInstrumentSummary,
    ArrangerResultSummary,
    ArrangerTelemetryHint,
    GP_APPLY_RANKED,
    GP_APPLY_SESSION_WINNER,
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
    _auto_register_shift,
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


def _preferred_range_names(
    instrument_id: str,
    fallback: InstrumentRange | None = None,
) -> tuple[str, str] | None:
    """Return preferred range note names for ``instrument_id`` if available."""

    try:
        spec = get_instrument(instrument_id)
    except Exception:
        spec = None

    if spec is not None:
        try:
            preferred_min, preferred_max = preferred_note_window(spec)
        except Exception:
            candidate_min = getattr(spec, "candidate_range_min", "").strip()
            candidate_max = getattr(spec, "candidate_range_max", "").strip()
            if candidate_min and candidate_max:
                return candidate_min, candidate_max
        else:
            if preferred_min and preferred_max:
                return preferred_min, preferred_max

    if fallback is not None:
        try:
            low = pitch_midi_to_name(int(fallback.min_midi), flats=False)
            high = pitch_midi_to_name(int(fallback.max_midi), flats=False)
        except Exception:
            return None
        return low, high

    return None


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
    resolved_instrument_range: tuple[str, str] | None = None


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
    selected_instrument_range: tuple[str | None, str | None] | None = None,
    progress_callback: ProgressCallback | None = None,
    grace_settings: GraceSettings | None = None,
    subhole_settings: SubholeConstraintSettings | None = None,
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
    total_transposition = manual_transpose

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

    if strategy_normalized == "starred-best":
        starred_ids_for_strategy = starred_ids
    else:
        starred_ids_for_strategy: tuple[str, ...] = ()

    override_range: tuple[str | None, str | None] | None = None
    if selected_instrument_range is not None:
        override_range = (
            (selected_instrument_range[0] or "").strip() or None,
            (selected_instrument_range[1] or "").strip() or None,
        )

    resolved_range = _instrument_range_for(
        resolved_instrument_id,
        resolver=get_instrument,
        preferred_override=override_range,
    )
    if resolved_range is None:
        logger.warning(
            "Arranger preview missing range for instrument '%s'; skipping arranger algorithm",
            resolved_instrument_id,
        )
        _notify_progress(progress_callback, 100.0, "Instrument range unavailable")
        return ArrangerComputation((), None, strategy=strategy_normalized)

    auto_register_shift = 0
    seed_transposition = manual_transpose
    if mode == "gp":
        auto_register_shift = _auto_register_shift(span, resolved_range)
        seed_transposition += auto_register_shift

    for candidate in starred_ids_for_strategy:
        if candidate == resolved_instrument_id:
            # Ensure the selected instrument remains registered with the override range
            # when it also appears in the starred list.
            _instrument_range_for(
                candidate,
                resolver=get_instrument,
                preferred_override=override_range,
            )
            continue
        _instrument_range_for(
            candidate,
            resolver=get_instrument,
            preferred_override=None,
        )

    name_map = _instrument_name_map(choices)

    active_grace = grace_settings or DEFAULT_GRACE_SETTINGS
    active_subhole = subhole_settings

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
                starred_ids=starred_ids_for_strategy,
                strategy=strategy_normalized,
                flags=flags,
                salvage_cascade=salvage_cascade,
                tempo_bpm=float(preview.tempo_bpm) if preview.tempo_bpm else None,
                breath_settings=breath_settings,
                grace_settings=active_grace,
                subhole_settings=active_subhole,
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
                transposition_offset=total_transposition,
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
            chosen.result.transposition + total_transposition,
        )
        result_summary = _result_summary(
            span,
            chosen,
            name_map,
            threshold=DEFAULT_DIFFICULTY_THRESHOLD,
            transposition_offset=total_transposition,
            grace_settings=active_grace,
        )

        program = (
            _first_program(preview.arranged_events)
            or _first_program(preview.original_events)
            or 0
        )
        arranged_events = note_events_from_phrase(chosen.result.span, program=program)
        arranged_events = ensure_monophonic(arranged_events)

        resolved_state_instrument = resolved_instrument_id
        resolved_state_range: tuple[str, str] | None = None
        if strategy_normalized == "starred-best":
            resolved_state_instrument = chosen.instrument_id
            if resolved_state_instrument != resolved_instrument_id:
                resolved_state_range = _preferred_range_names(
                    resolved_state_instrument,
                    fallback=chosen.instrument,
                )

        _notify_progress(progress_callback, 100.0, "Arrangement complete")
        return ArrangerComputation(
            summaries=summaries,
            result_summary=result_summary,
            strategy=strategy_result.strategy,
            explanations=_explanations_from(chosen),
            telemetry=_telemetry_from(chosen, budget_settings, DEFAULT_DIFFICULTY_THRESHOLD),
            resolved_instrument_id=resolved_state_instrument,
            resolved_starred_ids=tuple(dict.fromkeys(starred_ids)),
            arranged_events=arranged_events,
            resolved_instrument_range=resolved_state_range,
        )

    gp_settings_normalized = (gp_settings or ArrangerGPSettings()).normalized()
    apply_preference = gp_settings_normalized.apply_program_preference
    if strategy_normalized == "starred-best":
        apply_preference = GP_APPLY_RANKED
    gp_config = _gp_session_config(gp_settings_normalized)
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
            starred_ids=starred_ids_for_strategy,
            config=gp_config,
            manual_transposition=manual_transpose,
            transposition=seed_transposition,
            preferred_register_shift=auto_register_shift,
            grace_settings=active_grace,
            progress_callback=gp_progress,
        )
    except Exception:
        logger.exception("Arranger preview failed during GP arrange call")
        _notify_progress(progress_callback, 100.0, "Arrangement failed")
        return ArrangerComputation((), None, strategy=strategy_normalized)

    chosen_candidate = gp_result.chosen
    applied_candidate = chosen_candidate
    if (
        apply_preference == GP_APPLY_SESSION_WINNER
        and getattr(gp_result, "winner_candidate", None) is not None
    ):
        applied_candidate = gp_result.winner_candidate

    winner_id = chosen_candidate.instrument_id

    summary_rows: list[ArrangerInstrumentSummary] = []
    for candidate in gp_result.comparisons:
        source = (
            applied_candidate
            if candidate.instrument_id == applied_candidate.instrument_id
            and apply_preference == GP_APPLY_SESSION_WINNER
            else candidate
        )
        summary_rows.append(
            _gp_instrument_summary(
                source,
                name_map,
                winner_id,
                transposition_offset=total_transposition,
            )
        )
    comparisons = tuple(summary_rows)

    result_summary = _gp_result_summary(
        span,
        applied_candidate,
        name_map,
        threshold=DEFAULT_DIFFICULTY_THRESHOLD,
        transposition_offset=total_transposition,
        grace_settings=active_grace,
    )

    chosen_strategy = getattr(gp_result, "strategy", strategy_normalized)
    program = (
        _first_program(preview.arranged_events)
        or _first_program(preview.original_events)
        or 0
    )
    if hasattr(applied_candidate, "arranged_events"):
        arranged_events = tuple(applied_candidate.arranged_events)
    else:
        arranged_events = note_events_from_phrase(applied_candidate.span, program=program)
        arranged_events = ensure_monophonic(arranged_events)

    resolved_state_instrument = resolved_instrument_id
    resolved_state_range: tuple[str, str] | None = None
    if strategy_normalized == "starred-best":
        resolved_state_instrument = chosen_candidate.instrument_id
        if resolved_state_instrument != resolved_instrument_id:
            resolved_state_range = _preferred_range_names(
                resolved_state_instrument,
                fallback=chosen_candidate.instrument,
            )

    _notify_progress(progress_callback, 100.0, "Arrangement complete")
    return ArrangerComputation(
        summaries=comparisons,
        result_summary=result_summary,
        strategy=chosen_strategy,
        explanations=_gp_explanations(applied_candidate),
        telemetry=_gp_telemetry(gp_result, gp_config),
        resolved_instrument_id=resolved_state_instrument,
        resolved_starred_ids=tuple(dict.fromkeys(starred_ids)),
        arranged_events=arranged_events,
        resolved_instrument_range=resolved_state_range,
    )


__all__ = [
    "ArrangerComputation",
    "compute_arranger_preview",
    "get_instrument",
]
