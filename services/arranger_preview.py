"""Helpers for computing arranger best-effort results from preview data."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from domain.arrangement.api import arrange, summarize_difficulty
from domain.arrangement.config import FeatureFlags, register_instrument_range
from domain.arrangement.constraints import BreathSettings
from domain.arrangement.importers import note_events_from_phrase, phrase_from_note_events
from domain.arrangement.salvage import SalvageBudgets, default_salvage_cascade
from domain.arrangement.soft_key import InstrumentRange
from ocarina_gui.fingering import get_available_instruments, get_instrument
from ocarina_gui.preview import PreviewData
from ocarina_tools.events import NoteEvent
from ocarina_tools.pitch import parse_note_name
from services.arranger_monophonic import ensure_monophonic

from viewmodels.arranger_models import (
    ArrangerBudgetSettings,
    ArrangerEditBreakdown,
    ArrangerExplanationRow,
    ArrangerInstrumentSummary,
    ArrangerResultSummary,
    ArrangerTelemetryHint,
)


_DEFAULT_DIFFICULTY_THRESHOLD = 0.65
_DEFAULT_INSTRUMENT_MIN = 60
_DEFAULT_INSTRUMENT_MAX = 84


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


def compute_arranger_preview(
    preview: PreviewData,
    *,
    arranger_mode: str,
    instrument_id: str,
    starred_instrument_ids: Sequence[str],
    strategy: str,
    dp_slack_enabled: bool,
    budgets: ArrangerBudgetSettings | None = None,
) -> ArrangerComputation:
    """Return arranger summaries derived from ``preview`` for UI consumption."""

    strategy_normalized = (strategy or "current").strip().lower()
    mode = (arranger_mode or "classic").strip().lower()
    logger.info(
        "Arranger preview requested: mode=%s strategy=%s instrument=%s dp_slack=%s",
        mode,
        strategy_normalized,
        instrument_id or "<none>",
        bool(dp_slack_enabled),
    )
    if mode != "best_effort":
        logger.info("Arranger preview using algorithm=classic (v1); returning baseline data")
        return ArrangerComputation((), None, strategy=strategy_normalized)

    instrument_id = (instrument_id or "").strip()
    if not instrument_id or not preview.original_events:
        logger.debug(
            "Arranger preview missing instrument or events; cannot run best-effort algorithm"
        )
        return ArrangerComputation((), None, strategy=strategy_normalized)

    span = phrase_from_note_events(preview.original_events, preview.pulses_per_quarter)
    if not span.notes:
        logger.debug("Arranger preview span contained no notes; skipping best-effort algorithm")
        return ArrangerComputation((), None, strategy=strategy_normalized)

    try:
        choices = tuple(get_available_instruments())
    except Exception:
        choices = ()
    resolved_instrument_id = _normalize_instrument_id(instrument_id, choices)
    if resolved_instrument_id is None:
        logger.warning(
            "Arranger preview could not resolve instrument '%s'; skipping best-effort algorithm",
            instrument_id,
        )
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

    if _instrument_range_for(resolved_instrument_id) is None:
        logger.warning(
            "Arranger preview missing range for instrument '%s'; skipping best-effort algorithm",
            resolved_instrument_id,
        )
        return ArrangerComputation((), None, strategy=strategy_normalized)

    for candidate in starred_ids:
        _instrument_range_for(candidate)

    budget_settings = (budgets or ArrangerBudgetSettings()).normalized()
    flags = FeatureFlags(dp_slack=bool(dp_slack_enabled))
    salvage_cascade = default_salvage_cascade(
        threshold=_DEFAULT_DIFFICULTY_THRESHOLD,
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
        )
    except Exception:
        logger.exception("Arranger preview failed during best-effort arrange call")
        return ArrangerComputation((), None, strategy=strategy_normalized)

    name_map = _instrument_name_map(choices)
    summaries = tuple(
        _instrument_summary(arrangement, name_map, strategy_result.chosen.instrument_id)
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
        threshold=_DEFAULT_DIFFICULTY_THRESHOLD,
    )

    program = (
        _first_program(preview.arranged_events)
        or _first_program(preview.original_events)
        or 0
    )
    arranged_events = note_events_from_phrase(chosen.result.span, program=program)
    arranged_events = ensure_monophonic(arranged_events)

    return ArrangerComputation(
        summaries=summaries,
        result_summary=result_summary,
        strategy=strategy_result.strategy,
        explanations=_explanations_from(chosen),
        telemetry=_telemetry_from(chosen, budget_settings, _DEFAULT_DIFFICULTY_THRESHOLD),
        resolved_instrument_id=resolved_instrument_id,
        resolved_starred_ids=tuple(dict.fromkeys(starred_ids)),
        arranged_events=arranged_events,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _instrument_summary(
    arrangement,
    name_map: dict[str, str],
    chosen_id: str,
) -> ArrangerInstrumentSummary:
    easy, medium, hard, very_hard, tessitura, _ = _normalize_difficulty(arrangement.difficulty)
    return ArrangerInstrumentSummary(
        instrument_id=arrangement.instrument_id,
        instrument_name=name_map.get(arrangement.instrument_id, arrangement.instrument_id),
        easy=easy,
        medium=medium,
        hard=hard,
        very_hard=very_hard,
        tessitura=tessitura,
        transposition=arrangement.result.transposition,
        is_winner=arrangement.instrument_id == chosen_id,
    )


def _result_summary(
    span,
    arrangement,
    name_map: dict[str, str],
    *,
    threshold: float,
) -> ArrangerResultSummary:
    easy, medium, hard, very_hard, tessitura, _ = _normalize_difficulty(arrangement.difficulty)
    starting_summary = summarize_difficulty(span, arrangement.instrument)
    start_score = _difficulty_score(starting_summary)
    final_score = _difficulty_score(arrangement.difficulty)
    salvage = arrangement.result.salvage
    return ArrangerResultSummary(
        instrument_id=arrangement.instrument_id,
        instrument_name=name_map.get(arrangement.instrument_id, arrangement.instrument_id),
        transposition=arrangement.result.transposition,
        easy=easy,
        medium=medium,
        hard=hard,
        very_hard=very_hard,
        tessitura=tessitura,
        starting_difficulty=start_score,
        final_difficulty=final_score,
        difficulty_threshold=threshold,
        met_threshold=final_score <= threshold,
        difficulty_delta=start_score - final_score,
        applied_steps=tuple(salvage.applied_steps) if salvage else tuple(),
        edits=_edit_breakdown(salvage.edits_used) if salvage else ArrangerEditBreakdown(),
    )


def _instrument_name_map(choices: Iterable) -> dict[str, str]:
    return {choice.instrument_id: choice.name for choice in choices}


def _first_program(events: Sequence[NoteEvent] | Iterable[NoteEvent]) -> int | None:
    for event in events:
        return event.program
    return None


def _instrument_range_for(instrument_id: str) -> InstrumentRange | None:
    instrument_id = instrument_id.strip()
    if not instrument_id:
        return None
    try:
        spec = get_instrument(instrument_id)
    except Exception:
        return None
    instrument_range = _instrument_range_from_spec(spec)
    register_instrument_range(instrument_id, instrument_range)
    return instrument_range


def _instrument_range_from_spec(spec) -> InstrumentRange:
    def _parse(note: str, fallback: int | None = None) -> int | None:
        if note:
            try:
                return parse_note_name(note)
            except ValueError:
                return fallback
        return fallback

    min_midi = _parse(spec.candidate_range_min, _DEFAULT_INSTRUMENT_MIN)
    max_midi = _parse(spec.candidate_range_max, _DEFAULT_INSTRUMENT_MAX)
    pref_min = _parse(spec.preferred_range_min, min_midi)
    pref_max = _parse(spec.preferred_range_max, max_midi)

    if min_midi is None or max_midi is None:
        min_midi = _DEFAULT_INSTRUMENT_MIN
        max_midi = _DEFAULT_INSTRUMENT_MAX
    if min_midi > max_midi:
        min_midi, max_midi = max_midi, min_midi

    if pref_min is None:
        pref_min = min_midi
    if pref_max is None:
        pref_max = max_midi
    if pref_min > pref_max:
        pref_min, pref_max = pref_max, pref_min

    center = (pref_min + pref_max) / 2.0 if pref_min is not None and pref_max is not None else None
    return InstrumentRange(min_midi=min_midi, max_midi=max_midi, comfort_center=center)


def _normalize_difficulty(difficulty) -> tuple[float, float, float, float, float, float]:
    total = difficulty.easy + difficulty.medium + difficulty.hard + difficulty.very_hard
    if total <= 0:
        return 0.0, 0.0, 0.0, 0.0, difficulty.tessitura_distance, 0.0
    return (
        difficulty.easy / total,
        difficulty.medium / total,
        difficulty.hard / total,
        difficulty.very_hard / total,
        difficulty.tessitura_distance,
        total,
    )


def _difficulty_score(difficulty) -> float:
    total = difficulty.easy + difficulty.medium + difficulty.hard + difficulty.very_hard
    if total <= 0:
        return 0.0
    return (difficulty.hard + difficulty.very_hard) / total


def _edit_breakdown(usage: Mapping[str, int]) -> ArrangerEditBreakdown:
    return ArrangerEditBreakdown(
        total=int(usage.get("total", 0)),
        octave=int(usage.get("octave", 0)),
        rhythm=int(usage.get("rhythm", 0)),
        substitution=int(usage.get("substitution", 0)),
    )


def _explanations_from(arrangement) -> tuple[ArrangerExplanationRow, ...]:
    salvage = arrangement.result.salvage
    if salvage is None:
        return ()
    rows = []
    for event in salvage.explanations:
        rows.append(
            ArrangerExplanationRow(
                bar=event.bar,
                action=event.action,
                reason=event.reason,
                reason_code=event.reason_code,
                difficulty_delta=event.difficulty_delta,
                before_note_count=len(event.before.notes),
                after_note_count=len(event.after.notes),
                span_id=event.span_id,
                span=event.span,
                key_id=event.key_id,
            )
        )
    return tuple(rows)


def _telemetry_from(
    arrangement,
    budgets: ArrangerBudgetSettings,
    threshold: float,
) -> tuple[ArrangerTelemetryHint, ...]:
    salvage = arrangement.result.salvage
    if salvage is None:
        return (
            ArrangerTelemetryHint(
                category="Salvage",
                message="Salvage cascade disabled; showing baseline difficulty only.",
            ),
        )

    hints: list[ArrangerTelemetryHint] = []
    if salvage.applied_steps:
        joined = ", ".join(salvage.applied_steps)
        hints.append(
            ArrangerTelemetryHint(
                category="Salvage",
                message=f"Applied {len(salvage.applied_steps)} step(s): {joined}.",
            )
        )
    else:
        hints.append(
            ArrangerTelemetryHint(
                category="Salvage",
                message="No salvage edits applied; heuristics or budgets kept the span unchanged.",
            )
        )

    if salvage.success:
        hints.append(
            ArrangerTelemetryHint(
                category="Difficulty",
                message=(
                    f"Difficulty reduced from {salvage.starting_difficulty:.2f} "
                    f"to {salvage.difficulty:.2f} (threshold {threshold:.2f})."
                ),
            )
        )
    else:
        hints.append(
            ArrangerTelemetryHint(
                category="Difficulty",
                message=(
                    f"Difficulty remains {salvage.difficulty:.2f} "
                    f"above threshold {threshold:.2f}; span marked not recommended."
                ),
            )
        )

    usage = salvage.edits_used
    normalized = budgets.normalized()
    budgets_message = "; ".join(
        [
            f"Octave {int(usage.get('octave', 0))}/{normalized.max_octave_edits}",
            f"Rhythm {int(usage.get('rhythm', 0))}/{normalized.max_rhythm_edits}",
            f"Substitution {int(usage.get('substitution', 0))}/{normalized.max_substitutions}",
            f"Total {int(usage.get('total', 0))}/{normalized.max_steps_per_span}",
        ]
    )
    hints.append(
        ArrangerTelemetryHint(
            category="Budgets",
            message=budgets_message,
        )
    )
    return tuple(hints)


def _to_salvage_budgets(settings: ArrangerBudgetSettings) -> SalvageBudgets:
    normalized = settings.normalized()
    return SalvageBudgets(
        max_octave_edits=normalized.max_octave_edits,
        max_rhythm_edits=normalized.max_rhythm_edits,
        max_substitutions=normalized.max_substitutions,
        max_steps_per_span=normalized.max_steps_per_span,
    )


def _normalize_instrument_id(
    instrument_id: str,
    choices: Sequence,
) -> str | None:
    instrument_id = instrument_id.strip()
    if not instrument_id:
        return None

    by_id = {choice.instrument_id: choice.instrument_id for choice in choices}
    if instrument_id in by_id:
        return instrument_id

    lower = instrument_id.lower()
    by_name = {choice.name.lower(): choice.instrument_id for choice in choices}
    if lower in by_name:
        return by_name[lower]

    prefix_matches = [
        choice.instrument_id
        for choice in choices
        if choice.instrument_id.startswith(instrument_id)
    ]
    if prefix_matches:
        return prefix_matches[0]

    if "_" in instrument_id:
        base = instrument_id.rsplit("_", 1)[0]
        base_matches = [
            choice.instrument_id
            for choice in choices
            if choice.instrument_id.startswith(base)
        ]
        if base_matches:
            return base_matches[0]

    return None


__all__ = [
    "ArrangerComputation",
    "compute_arranger_preview",
]
