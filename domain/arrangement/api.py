"""Public entry points for running the arranger pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Iterable, Sequence, Tuple

from .config import (
    DEFAULT_FEATURE_FLAGS,
    FeatureFlags,
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

# Backwards-compatible alias for legacy imports in downstream tests.
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
    top_k: int = _KEY_SEARCH_TOP_K,
) -> tuple[int, ...]:
    fits = soft_key_search(span, instrument, top_k=top_k)
    ordered: list[int] = []
    for fit in fits:
        if fit.transposition not in ordered:
            ordered.append(fit.transposition)
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
) -> ArrangementResult:
    """Arrange ``span`` for ``instrument`` respecting feature flags.

    The arranger first evaluates the top soft-key transpositions (including the
    baseline) and runs the DP + salvage pipeline for each candidate. The final
    result reflects the transposed span with the lowest post-salvage difficulty.
    When ``flags.dp_slack`` is disabled the octave-folding step is skipped, but
    transposition and salvage may still adjust the phrase.
    """

    active_flags = flags or DEFAULT_FEATURE_FLAGS
    melody_result = isolate_melody(span)
    base_span = melody_result.span
    log_melody_actions(
        logger,
        instrument=instrument,
        span=base_span,
        actions=melody_result.actions,
    )
    candidates = _candidate_transpositions(base_span, instrument)
    log_transpositions(logger, candidates=candidates)
    best: tuple[tuple[int | float, ...], ArrangementResult] | None = None

    for transposition in candidates:
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
        )
        arranged = replace(
            arranged,
            transposition=transposition,
            preprocessing=melody_result.events + arranged.preprocessing,
            melody_actions=melody_result.actions,
        )
        summary = summarize_difficulty(arranged.span, instrument)
        salvage = arranged.salvage
        salvage_failure = 0
        salvage_steps = 0
        range_clamp_penalty = 0
        if any(event.action == "range-clamp" for event in arranged.preprocessing):
            range_clamp_penalty = 1
        if salvage is not None:
            salvage_failure = 0 if salvage.success else 1
            usage_total = int(salvage.edits_used.get("total", len(salvage.applied_steps)))
            salvage_steps = usage_total
            if "range-clamp" in salvage.applied_steps:
                range_clamp_penalty = 1
        if salvage is not None and salvage.applied_steps and salvage.success:
            penalized_score = difficulty_score(summary) + abs(transposition)
            ranking = (
                salvage_failure,
                range_clamp_penalty,
                salvage_steps,
                summary.hard_and_very_hard,
                summary.medium,
                summary.tessitura_distance,
                penalized_score,
                abs(transposition),
                transposition,
            )
        else:
            ranking = (
                salvage_failure,
                range_clamp_penalty,
                salvage_steps,
                difficulty_score(summary),
                summary.hard_and_very_hard,
                summary.medium,
                summary.tessitura_distance,
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

    if best is None:
        log_no_candidates(logger)
        return ArrangementResult(span=span, transposition=0)

    chosen = best[1]
    log_selection(
        logger,
        transposition=chosen.transposition,
        span=chosen.span,
        preprocessing=chosen.preprocessing,
    )
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
    )
    summary = summarize_difficulty(result.span, instrument)
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
) -> ArrangementStrategyResult:
    """Arrange ``span`` using the requested instrument selection strategy."""

    strategy_normalized = strategy or "current"
    if strategy_normalized not in {"current", "starred-best"}:
        raise ValueError(f"Unsupported strategy: {strategy}")

    active_flags = flags or DEFAULT_FEATURE_FLAGS
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
        )
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
        )

    candidate_ids = [instrument_id]
    for starred in starred_list:
        if starred not in candidate_ids:
            candidate_ids.append(starred)

    comparisons = tuple(
        _arrange_for_instrument(
            span,
            candidate_id,
            flags=active_flags,
            folding_settings=folding_settings,
            salvage_cascade=salvage_cascade,
            tempo_bpm=tempo_bpm,
            subhole_settings=subhole_settings,
            breath_settings=breath_settings,
        )
        for candidate_id in candidate_ids
    )

    ranked = tuple(
        sorted(
            comparisons,
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
