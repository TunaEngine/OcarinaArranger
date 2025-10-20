"""Debug logging helpers for the arranger v2 pipeline."""

from __future__ import annotations

import logging
from typing import Iterable, Sequence

from .difficulty import DifficultySummary
from .logging_utils import (
    describe_difficulty,
    describe_instrument,
    describe_melody_actions,
    describe_span,
)
from .phrase import PhraseSpan
from .salvage import SalvageResult
from .soft_key import InstrumentRange

if logging.getLogger(__name__).handlers:
    # Keep module import cheap; actual logging configuration happens elsewhere.
    _LOGGER = logging.getLogger(__name__)
else:  # pragma: no cover - defensive default
    _LOGGER = logging.getLogger(__name__)


def log_pipeline_start(
    logger: logging.Logger,
    *,
    instrument: InstrumentRange,
    span: PhraseSpan,
    flags: object,
    salvage_enabled: bool,
    tempo_bpm: float | None,
    subhole_settings: object | None,
    breath_settings: object | None,
    grace_settings: object | None,
) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return
    logger.debug(
        "arrange_span pipeline:start instrument=%s span=%s flags=%s salvage=%s tempo=%s subhole=%s breath=%s grace=%s",
        describe_instrument(instrument),
        describe_span(span),
        flags,
        salvage_enabled,
        tempo_bpm,
        subhole_settings,
        breath_settings,
        grace_settings,
    )


def log_pipeline_stage(
    logger: logging.Logger,
    *,
    stage: str,
    span: PhraseSpan,
    events: int | None = None,
    steps: int | None = None,
    cost: float | None = None,
    success: bool | None = None,
    reason: str | None = None,
) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return

    message = f"arrange_span pipeline:{stage} span=%s"
    args: list[object] = [describe_span(span)]

    if events is not None:
        message += " events=%d"
        args.append(events)
    if steps is not None:
        message += " steps=%d"
        args.append(steps)
    if cost is not None:
        message += " cost=%.3f"
        args.append(cost)
    if success is not None:
        message += " success=%s"
        args.append(success)
    if reason is not None:
        message += " reason=%s"
        args.append(reason)

    logger.debug(message, *args)


def log_pipeline_complete(
    logger: logging.Logger,
    *,
    span: PhraseSpan,
    preprocessing_count: int,
) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return
    logger.debug(
        "arrange_span pipeline:complete span=%s preprocessing=%d",
        describe_span(span),
        preprocessing_count,
    )


def log_candidate_start(
    logger: logging.Logger,
    *,
    transposition: int,
    span: PhraseSpan,
) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return
    logger.debug(
        "arrange_span:candidate start transposition=%+d span=%s",
        transposition,
        describe_span(span),
    )


def log_transpositions(logger: logging.Logger, *, candidates: Sequence[int]) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return
    logger.debug(
        "arrange_span:transpositions=%s",
        ", ".join(f"{value:+d}" for value in candidates) or "<none>",
    )


def log_candidate_result(
    logger: logging.Logger,
    *,
    transposition: int,
    difficulty: DifficultySummary,
    salvage: SalvageResult | None,
    ranking: Sequence[object],
    preprocessing_count: int,
) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return

    if salvage is None:
        salvage_state = "none"
    else:
        total = int(salvage.edits_used.get("total", len(salvage.applied_steps)))
        salvage_state = (
            f"{'success' if salvage.success else 'failed'} steps={len(salvage.applied_steps)} total_edits={total}"
        )

    logger.debug(
        "arrange_span:candidate done transposition=%+d %s %s ranking=%s preprocessing=%d",
        transposition,
        describe_difficulty(difficulty),
        salvage_state,
        ranking,
        preprocessing_count,
    )


def log_no_candidates(logger: logging.Logger) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return
    logger.debug("arrange_span:complete no-candidates; returning original span")


def log_selection(
    logger: logging.Logger,
    *,
    transposition: int,
    span: PhraseSpan,
    preprocessing: Sequence[object],
) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return
    logger.debug(
        "arrange_span:complete selected transposition=%+d span=%s preprocessing=%d",
        transposition,
        describe_span(span),
        len(preprocessing),
    )


def log_arrange_start(
    logger: logging.Logger,
    *,
    strategy: str,
    instrument_id: str,
    starred_ids: Iterable[str] | None,
    span: PhraseSpan,
) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return
    logger.debug(
        "arrange:start strategy=%s instrument_id=%s starred=%s span=%s",
        strategy,
        instrument_id,
        tuple(starred_ids or ()),
        describe_span(span),
    )


def log_instrument_result(
    logger: logging.Logger,
    *,
    instrument_id: str,
    result_span: PhraseSpan,
    transposition: int,
    difficulty: DifficultySummary,
) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return
    logger.debug(
        "arrange:instrument result instrument_id=%s transposition=%+d %s span=%s",
        instrument_id,
        transposition,
        describe_difficulty(difficulty),
        describe_span(result_span),
    )


def log_arrange_complete(
    logger: logging.Logger,
    *,
    strategy: str,
    ranked: Sequence[tuple[str, DifficultySummary]],
) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return
    logger.debug(
        "arrange:complete strategy=%s chosen=%s comparisons=%s",
        strategy,
        ranked[0][0] if ranked else None,
        [(instrument_id, describe_difficulty(summary)) for instrument_id, summary in ranked],
    )


def log_melody_actions(
    logger: logging.Logger,
    *,
    instrument: InstrumentRange,
    span: PhraseSpan,
    actions: Sequence[object],
) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return
    logger.debug(
        "arrange_span:start instrument=%s span=%s melody=%s",
        describe_instrument(instrument),
        describe_span(span),
        describe_melody_actions(actions),
    )


__all__ = [
    "log_arrange_complete",
    "log_arrange_start",
    "log_candidate_result",
    "log_candidate_start",
    "log_transpositions",
    "log_instrument_result",
    "log_melody_actions",
    "log_no_candidates",
    "log_pipeline_complete",
    "log_pipeline_stage",
    "log_pipeline_start",
    "log_selection",
]
