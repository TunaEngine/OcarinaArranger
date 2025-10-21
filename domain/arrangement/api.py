"""Public entry points for running the arranger pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Callable, Iterable, Sequence, Tuple

from .config import (
    DEFAULT_FEATURE_FLAGS,
    DEFAULT_GRACE_SETTINGS,
    FeatureFlags,
    GraceSettings,
    get_instrument_range,
)
from .constraints import BreathSettings, SubholeConstraintSettings
from .difficulty import DifficultySummary, difficulty_score, summarize_difficulty
from .explanations import ExplanationEvent
from .folding import FoldingResult, FoldingSettings
from .melody import MelodyIsolationAction, isolate_melody
from .phrase import PhraseNote, PhraseSpan
from .range_guard import enforce_instrument_range
from .salvage import SalvageCascade, SalvageResult
from .soft_key import InstrumentRange, soft_key_search
from .v2_pipeline import run_candidate_pipeline
from .api_logging import (
    log_arrange_complete,
    log_arrange_start,
    log_candidate_result,
    log_candidate_start,
    log_instrument_result,
    log_melody_actions,
    log_no_candidates,
    log_pipeline_complete,
    log_pipeline_stage,
    log_pipeline_start,
    log_selection,
    log_transpositions,
)


logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str | None], None]


def _noop_progress(_percent: float, _message: str | None = None) -> None:
    return None


def _prepare_progress(callback: ProgressCallback | None) -> ProgressCallback:
    if callback is None:
        return _noop_progress
    failed = False

    def reporter(percent: float, message: str | None = None) -> None:
        nonlocal failed
        if failed:
            return
        try:
            value = max(0.0, min(100.0, float(percent)))
        except (TypeError, ValueError):
            value = 0.0
        try:
            callback(value, message)
        except Exception:
            failed = True
            logger.exception("Arranger progress callback failed")

    return reporter


def _scaled_progress(
    callback: ProgressCallback,
    start: float,
    end: float,
    *,
    prefix: str | None = None,
) -> ProgressCallback:
    span = max(0.0, end - start)

    def reporter(percent: float, message: str | None = None) -> None:
        try:
            inner = max(0.0, min(100.0, float(percent)))
        except (TypeError, ValueError):
            inner = 0.0
        scaled = start + (span * inner / 100.0 if span else 0.0)
        text = message
        if prefix:
            text = f"{prefix}: {message}" if message else f"{prefix}: {inner:.0f}%"
        callback(scaled, text)

    return reporter

_run_candidate_pipeline = run_candidate_pipeline


@dataclass(frozen=True)
class ArrangementResult:
    """Outcome of arranging a single span."""

    span: PhraseSpan
    folding: FoldingResult | None = None
    salvage: SalvageResult | None = None
    transposition: int = 0
    preprocessing: Tuple[ExplanationEvent, ...] = ()
    melody_actions: Tuple[MelodyIsolationAction, ...] = ()


def _difficulty_score(summary: DifficultySummary) -> float:
    """Backwards-compatible wrapper for the moved difficulty helper."""

    return difficulty_score(summary)


@dataclass(frozen=True)
class InstrumentArrangement:
    """Arrangement outcome tied to a specific instrument identifier."""

    instrument_id: str
    instrument: InstrumentRange
    result: ArrangementResult
    difficulty: DifficultySummary


@dataclass(frozen=True)
class ArrangementStrategyResult:
    """Return value for ``arrange`` covering comparisons across instruments."""

    strategy: str
    chosen: InstrumentArrangement
    comparisons: Tuple[InstrumentArrangement, ...]


_KEY_SEARCH_TOP_K = 4


def _candidate_transpositions(
    span: PhraseSpan,
    instrument: InstrumentRange,
    *,
    grace_settings: GraceSettings,
    top_k: int = _KEY_SEARCH_TOP_K,
) -> tuple[int, ...]:
    fits = soft_key_search(span, instrument, top_k=top_k)
    ordered: list[int] = []
    for fit in fits:
        if fit.transposition not in ordered:
            ordered.append(fit.transposition)

    difficulty_ranked: list[tuple[float, float, int, int]] = []
    for transposition in range(-10, 11):
        candidate_span = span.transpose(transposition)
        summary = summarize_difficulty(
            candidate_span,
            instrument,
            grace_settings=grace_settings,
        )
        score = difficulty_score(summary, grace_settings=grace_settings)
        difficulty_ranked.append(
            (
                score,
                summary.fast_windway_switch_exposure,
                abs(transposition),
                transposition,
            )
        )

    difficulty_ranked.sort()
    for _, _, _, candidate in difficulty_ranked[:top_k]:
        if candidate not in ordered:
            ordered.append(candidate)

    if 0 not in ordered:
        ordered.append(0)

    return tuple(ordered)


def arrange_span(
    span: PhraseSpan,
    *,
    instrument: InstrumentRange,
    flags: FeatureFlags | None = None,
    folding_settings: FoldingSettings | None = None,
    salvage_cascade: SalvageCascade | None = None,
    tempo_bpm: float | None = None,
    subhole_settings: SubholeConstraintSettings | None = None,
    breath_settings: BreathSettings | None = None,
    grace_settings: GraceSettings | None = None,
    progress_callback: ProgressCallback | None = None,
) -> ArrangementResult:
    """Arrange ``span`` for ``instrument`` respecting feature flags."""

    active_flags = flags or DEFAULT_FEATURE_FLAGS
    melody_result = isolate_melody(span)
    base_span = melody_result.span
    log_melody_actions(
        logger,
        instrument=instrument,
        span=base_span,
        actions=melody_result.actions,
    )
    grace_config = grace_settings or DEFAULT_GRACE_SETTINGS
    candidates = _candidate_transpositions(
        base_span,
        instrument,
        grace_settings=grace_config,
    )
    log_transpositions(logger, candidates=candidates)
    best: tuple[tuple[int | float, ...], ArrangementResult] | None = None
    report = progress_callback or _noop_progress
    total_candidates = max(len(candidates), 1)
    report(0.0, "Selecting candidate transpositions")

    for index, transposition in enumerate(candidates, start=1):
        start_percent = ((index - 1) / total_candidates) * 100.0
        report(start_percent, f"Testing transposition {transposition:+d}")
        candidate_span = base_span.transpose(transposition)
        log_candidate_start(
            logger,
            transposition=transposition,
            span=candidate_span,
        )
        arranged = run_candidate_pipeline(
            candidate_span,
            instrument,
            logger=logger,
            flags=active_flags,
            folding_settings=folding_settings,
            salvage_cascade=salvage_cascade,
            tempo_bpm=tempo_bpm,
            subhole_settings=subhole_settings,
            breath_settings=breath_settings,
            grace_settings=grace_config,
        )
        arranged = replace(
            arranged,
            transposition=transposition,
            preprocessing=melody_result.events + arranged.preprocessing,
            melody_actions=melody_result.actions,
        )
        summary = summarize_difficulty(
            arranged.span,
            instrument,
            grace_settings=grace_config,
        )
        try:
            fast_switch_penalty = summary.fast_windway_switch_exposure * max(
                0.0, float(getattr(grace_config, "fast_windway_switch_weight", 0.0))
            )
        except (TypeError, ValueError, AttributeError):
            fast_switch_penalty = 0.0
        salvage = arranged.salvage
        range_clamp_penalty = int(
            any(event.action == "range-clamp" for event in arranged.preprocessing)
            or (salvage is not None and "range-clamp" in salvage.applied_steps)
        )
        salvage_failure = 0 if salvage is None or salvage.success else 1
        salvage_steps = (
            int(salvage.edits_used.get("total", len(salvage.applied_steps)))
            if salvage is not None
            else 0
        )
        base_score = difficulty_score(summary, grace_settings=grace_config)
        if salvage is not None and salvage.applied_steps and salvage.success:
            difficulty_components = (
                summary.hard_and_very_hard,
                summary.medium,
                summary.tessitura_distance,
                base_score + abs(transposition),
            )
        else:
            difficulty_components = (
                base_score,
                summary.hard_and_very_hard,
                summary.medium,
                summary.tessitura_distance,
            )
        ranking = (
            salvage_failure,
            fast_switch_penalty,
            range_clamp_penalty,
            salvage_steps,
            *difficulty_components,
            abs(transposition),
            transposition,
        )
        if best is None or ranking < best[0]:
            best = (ranking, arranged)
        log_candidate_result(
            logger,
            transposition=transposition,
            difficulty=summary,
            salvage=salvage,
            ranking=ranking,
            preprocessing_count=len(arranged.preprocessing),
        )
        end_percent = (index / total_candidates) * 100.0
        report(end_percent, f"Completed transposition {transposition:+d}")

    if best is None:
        log_no_candidates(logger)
        report(100.0, "No viable transpositions")
        return ArrangementResult(span=span, transposition=0)

    chosen = best[1]
    log_selection(
        logger,
        transposition=chosen.transposition,
        span=chosen.span,
        preprocessing=chosen.preprocessing,
    )
    report(100.0, "Selected best transposition")
    return best[1]


def _arrange_for_instrument(
    span: PhraseSpan,
    instrument_id: str,
    *,
    flags: FeatureFlags,
    folding_settings: FoldingSettings | None,
    salvage_cascade: SalvageCascade | None,
    tempo_bpm: float | None = None,
    subhole_settings: SubholeConstraintSettings | None = None,
    breath_settings: BreathSettings | None = None,
    grace_settings: GraceSettings | None = None,
    progress_callback: ProgressCallback | None = None,
) -> InstrumentArrangement:
    instrument = get_instrument_range(instrument_id)
    result = arrange_span(
        span,
        instrument=instrument,
        flags=flags,
        folding_settings=folding_settings,
        salvage_cascade=salvage_cascade,
        tempo_bpm=tempo_bpm,
        subhole_settings=subhole_settings,
        breath_settings=breath_settings,
        grace_settings=grace_settings,
        progress_callback=progress_callback,
    )
    active_grace = grace_settings or DEFAULT_GRACE_SETTINGS
    summary = summarize_difficulty(result.span, instrument, grace_settings=active_grace)
    log_instrument_result(
        logger,
        instrument_id=instrument_id,
        result_span=result.span,
        transposition=result.transposition,
        difficulty=summary,
    )
    return InstrumentArrangement(
        instrument_id=instrument_id,
        instrument=instrument,
        result=result,
        difficulty=summary,
    )


def arrange(
    span: PhraseSpan,
    *,
    instrument_id: str,
    starred_ids: Iterable[str] | None = None,
    strategy: str = "current",
    flags: FeatureFlags | None = None,
    folding_settings: FoldingSettings | None = None,
    salvage_cascade: SalvageCascade | None = None,
    tempo_bpm: float | None = None,
    subhole_settings: SubholeConstraintSettings | None = None,
    breath_settings: BreathSettings | None = None,
    grace_settings: GraceSettings | None = None,
    progress_callback: ProgressCallback | None = None,
) -> ArrangementStrategyResult:
    """Arrange ``span`` using the requested instrument selection strategy."""

    strategy_normalized = strategy or "current"
    if strategy_normalized not in {"current", "starred-best"}:
        raise ValueError(f"Unsupported strategy: {strategy}")

    active_flags = flags or DEFAULT_FEATURE_FLAGS
    grace_config = grace_settings or DEFAULT_GRACE_SETTINGS
    report = _prepare_progress(progress_callback)
    label = instrument_id or "instrument"
    report(0.0, f"Arranging {label}")
    log_arrange_start(
        logger,
        strategy=strategy_normalized,
        instrument_id=instrument_id,
        starred_ids=starred_ids,
        span=span,
    )

    if strategy_normalized == "current":
        arrangement = _arrange_for_instrument(
            span,
            instrument_id,
            flags=active_flags,
            folding_settings=folding_settings,
            salvage_cascade=salvage_cascade,
            tempo_bpm=tempo_bpm,
            subhole_settings=subhole_settings,
            breath_settings=breath_settings,
            grace_settings=grace_config,
            progress_callback=_scaled_progress(
                report,
                0.0,
                100.0,
                prefix=instrument_id or "current",
            ),
        )
        report(100.0, f"Arranged {instrument_id or 'current instrument'}")
        return ArrangementStrategyResult(
            strategy=strategy_normalized,
            chosen=arrangement,
            comparisons=(arrangement,),
        )

    starred_list: Sequence[str] = tuple(starred_ids or ())
    if not starred_list:
        # No starred instruments available; fall back to current strategy.
        return arrange(
            span,
            instrument_id=instrument_id,
            strategy="current",
            flags=active_flags,
            folding_settings=folding_settings,
            salvage_cascade=salvage_cascade,
            tempo_bpm=tempo_bpm,
            subhole_settings=subhole_settings,
            breath_settings=breath_settings,
            grace_settings=grace_config,
            progress_callback=progress_callback,
        )

    candidate_ids: list[str] = []
    if instrument_id in starred_list:
        candidate_ids.append(instrument_id)
    for starred in starred_list:
        if starred not in candidate_ids:
            candidate_ids.append(starred)

    total_candidates = len(candidate_ids) or 1
    comparisons: list[InstrumentArrangement] = []
    for index, candidate_id in enumerate(candidate_ids):
        start = (index / total_candidates) * 100.0
        end = ((index + 1) / total_candidates) * 100.0
        prefix = candidate_id or f"candidate-{index+1}"
        report(start, f"Arranging {prefix}")
        comparison = _arrange_for_instrument(
            span,
            candidate_id,
            flags=active_flags,
            folding_settings=folding_settings,
            salvage_cascade=salvage_cascade,
            tempo_bpm=tempo_bpm,
            subhole_settings=subhole_settings,
            breath_settings=breath_settings,
            grace_settings=grace_config,
            progress_callback=_scaled_progress(report, start, end, prefix=prefix),
        )
        comparisons.append(comparison)
        report(end, f"Evaluated {prefix}")
    comparisons_tuple = tuple(comparisons)

    ranked = tuple(
        sorted(
            comparisons_tuple,
            key=lambda item: (
                item.difficulty.hard_and_very_hard,
                item.difficulty.medium,
                item.difficulty.tessitura_distance,
            ),
        )
    )
    ranked_pairs = tuple((item.instrument_id, item.difficulty) for item in ranked)
    log_arrange_complete(
        logger,
        strategy=strategy_normalized,
        ranked=ranked_pairs,
    )
    report(100.0, f"Selected {ranked[0].instrument_id}")
    return ArrangementStrategyResult(
        strategy=strategy_normalized,
        chosen=ranked[0],
        comparisons=ranked,
    )


__all__ = [
    "ArrangementResult",
    "ArrangementStrategyResult",
    "DifficultySummary",
    "InstrumentArrangement",
    "arrange",
    "arrange_span",
    "_difficulty_score",
    "summarize_difficulty",
]
