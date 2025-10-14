"""Public entry points for running the arranger pipeline."""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Iterable, Sequence, Tuple

from ocarina_tools import midi_to_name

from .config import (
    DEFAULT_FEATURE_FLAGS,
    FeatureFlags,
    get_instrument_range,
)
from .constraints import BreathSettings, SubholeConstraintSettings
from .difficulty import DifficultySummary, difficulty_score, summarize_difficulty
from .explanations import (
    ExplanationEvent,
    octave_shifted_notes,
    span_label_for_notes,
)
from .folding import FoldingResult, FoldingSettings, fold_octaves_with_slack
from .melody import MelodyIsolationAction, isolate_melody
from .phrase import PhraseNote, PhraseSpan
from .preprocessing import apply_breath_planning, apply_subhole_constraints
from .range_guard import enforce_instrument_range
from .salvage import SalvageCascade, SalvageResult
from .soft_key import InstrumentRange, soft_key_search


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


_OCTAVE_DOWN_ACTION = "OCTAVE_DOWN_LOCAL"


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


def _run_candidate_pipeline(
    span: PhraseSpan,
    instrument: InstrumentRange,
    *,
    flags: FeatureFlags,
    folding_settings: FoldingSettings | None,
    salvage_cascade: SalvageCascade | None,
    tempo_bpm: float | None = None,
    subhole_settings: SubholeConstraintSettings | None = None,
    breath_settings: BreathSettings | None = None,
) -> ArrangementResult:
    current_span = span
    folding_result: FoldingResult | None = None
    if flags.dp_slack:
        folding_result = fold_octaves_with_slack(
            span,
            instrument,
            settings=folding_settings,
        )
        current_span = folding_result.span

    preprocessing_events: list[ExplanationEvent] = []

    if tempo_bpm is not None and tempo_bpm > 0:
        if subhole_settings is not None:
            constrained_span, events = apply_subhole_constraints(
                current_span,
                instrument,
                tempo_bpm=tempo_bpm,
                subhole_settings=subhole_settings,
            )
            if events:
                preprocessing_events.extend(events)
                current_span = constrained_span

        if breath_settings is not None:
            planned_span, events = apply_breath_planning(
                current_span,
                instrument,
                tempo_bpm=tempo_bpm,
                settings=breath_settings,
            )
            if events:
                preprocessing_events.extend(events)
                current_span = planned_span

    salvage_result: SalvageResult | None = None
    if salvage_cascade is not None:
        def _difficulty(candidate: PhraseSpan) -> float:
            summary = summarize_difficulty(candidate, instrument)
            return difficulty_score(summary)

        salvage_result = salvage_cascade.run(current_span, _difficulty)
        salvage_result = _enrich_salvage_explanations(
            salvage_result,
            instrument,
            beats_per_measure=salvage_cascade.beats_per_measure,
        )
        current_span = salvage_result.span

    clamped_span, range_event, after_difficulty = enforce_instrument_range(
        current_span,
        instrument,
        beats_per_measure=salvage_cascade.beats_per_measure if salvage_cascade else 4,
    )
    if range_event is not None:
        current_span = clamped_span
        if salvage_result is not None:
            updated_steps = salvage_result.applied_steps + ("range-clamp",)
            updated_explanations = salvage_result.explanations + (range_event,)
            usage = dict(salvage_result.edits_used)
            usage["range-clamp"] = usage.get("range-clamp", 0) + 1
            usage["total"] = usage.get("total", 0) + 1
            salvage_result = replace(
                salvage_result,
                span=current_span,
                difficulty=after_difficulty
                if after_difficulty is not None
                else salvage_result.difficulty,
                applied_steps=updated_steps,
                explanations=updated_explanations,
                edits_used=MappingProxyType(usage),
            )
        else:
            preprocessing_events.append(range_event)

    return ArrangementResult(
        span=current_span,
        folding=folding_result,
        salvage=salvage_result,
        preprocessing=tuple(preprocessing_events),
    )


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
    candidates = _candidate_transpositions(base_span, instrument)
    best: tuple[tuple[float, float, float, float, int, int], ArrangementResult] | None = None

    for transposition in candidates:
        candidate_span = base_span.transpose(transposition)
        arranged = _run_candidate_pipeline(
            candidate_span,
            instrument,
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
        if salvage is not None:
            salvage_failure = 0 if salvage.success else 1
            usage_total = int(salvage.edits_used.get("total", len(salvage.applied_steps)))
            salvage_steps = usage_total
        if salvage is not None and salvage.applied_steps and salvage.success:
            penalized_score = difficulty_score(summary) + abs(transposition)
            ranking = (
                salvage_failure,
                abs(transposition),
                penalized_score,
                summary.hard_and_very_hard,
                summary.medium,
                summary.tessitura_distance,
                salvage_steps,
                transposition,
            )
        else:
            ranking = (
                salvage_failure,
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

    if best is None:
        return ArrangementResult(span=span, transposition=0)

    return best[1]


def _enrich_salvage_explanations(
    result: SalvageResult,
    instrument: InstrumentRange,
    *,
    beats_per_measure: int,
) -> SalvageResult:
    if not result.explanations:
        return result

    updated: list[ExplanationEvent] = []
    mutated = False
    for event in result.explanations:
        if event.action == _OCTAVE_DOWN_ACTION:
            enriched = _enrich_octave_down_event(
                event,
                instrument,
                beats_per_measure=beats_per_measure,
            )
            updated.append(enriched)
            mutated = mutated or enriched is not event
        else:
            updated.append(event)
    if not mutated:
        return result
    return replace(result, explanations=tuple(updated))


def _enrich_octave_down_event(
    event: ExplanationEvent,
    instrument: InstrumentRange,
    *,
    beats_per_measure: int,
) -> ExplanationEvent:
    shifted_notes = octave_shifted_notes(event.before, event.after)
    if not shifted_notes:
        return replace(
            event,
            reason="RANGE_EDGE",
            reason_code="range-edge",
            span=None,
        )

    lowest = min(note.midi for note in shifted_notes)
    highest = max(note.midi for note in shifted_notes)
    lowest_name = midi_to_name(lowest)
    highest_name = midi_to_name(highest)
    max_name = midi_to_name(instrument.max_midi)
    span_label = span_label_for_notes(
        shifted_notes,
        pulses_per_quarter=event.before.pulses_per_quarter,
        beats_per_measure=beats_per_measure,
    )
    pulses_per_beat = max(1, event.before.pulses_per_quarter)
    pulses_per_measure = pulses_per_beat * max(1, beats_per_measure)
    start_onset = min(note.onset for note in shifted_notes)
    bar_number = (start_onset // pulses_per_measure) + 1
    reason = f"RANGE_EDGE ({lowest_name}..{highest_name} > max {max_name})"
    return replace(
        event,
        bar=bar_number,
        reason=reason,
        reason_code="range-edge",
        span=span_label,
    )
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
