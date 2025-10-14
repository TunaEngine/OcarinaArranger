"""Support routines for the arranger v2 candidate pipeline."""

from __future__ import annotations

import logging
from dataclasses import replace
from types import MappingProxyType

from ocarina_tools import midi_to_name

from .api_logging import log_pipeline_complete, log_pipeline_stage, log_pipeline_start
from .config import FeatureFlags
from .constraints import BreathSettings, SubholeConstraintSettings
from .difficulty import difficulty_score, summarize_difficulty
from .explanations import ExplanationEvent, octave_shifted_notes, span_label_for_notes
from .folding import FoldingResult, FoldingSettings, fold_octaves_with_slack
from .phrase import PhraseSpan
from .preprocessing import apply_breath_planning, apply_subhole_constraints
from .range_guard import enforce_instrument_range
from .salvage import SalvageCascade, SalvageResult
from .soft_key import InstrumentRange

def run_candidate_pipeline(
    span: PhraseSpan,
    instrument: InstrumentRange,
    *,
    logger: logging.Logger,
    flags: FeatureFlags,
    folding_settings: FoldingSettings | None,
    salvage_cascade: SalvageCascade | None,
    tempo_bpm: float | None = None,
    subhole_settings: SubholeConstraintSettings | None = None,
    breath_settings: BreathSettings | None = None,
) -> "ArrangementResult":
    """Run preprocessing, salvage, and range enforcement for a candidate span."""

    current_span = span
    folding_result: FoldingResult | None = None
    log_pipeline_start(
        logger,
        instrument=instrument,
        span=span,
        flags=flags,
        salvage_enabled=bool(salvage_cascade),
        tempo_bpm=tempo_bpm,
        subhole_settings=subhole_settings,
        breath_settings=breath_settings,
    )
    if flags.dp_slack:
        folding_result = fold_octaves_with_slack(
            span,
            instrument,
            settings=folding_settings,
        )
        current_span = folding_result.span
        if folding_result is not None:
            log_pipeline_stage(
                logger,
                stage="dp_slack",
                span=current_span,
                steps=len(folding_result.steps),
                cost=folding_result.total_cost,
            )

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
                log_pipeline_stage(
                    logger,
                    stage="subhole",
                    span=current_span,
                    events=len(events),
                )

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
                log_pipeline_stage(
                    logger,
                    stage="breath",
                    span=current_span,
                    events=len(events),
                )

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
        log_pipeline_stage(
            logger,
            stage="salvage",
            span=current_span,
            success=salvage_result.success,
            steps=len(salvage_result.applied_steps),
        )

    clamped_span, range_event, after_difficulty = enforce_instrument_range(
        current_span,
        instrument,
        beats_per_measure=salvage_cascade.beats_per_measure if salvage_cascade else 4,
    )
    if range_event is not None:
        current_span = clamped_span
        log_pipeline_stage(
            logger,
            stage="range-clamp",
            span=current_span,
            reason=range_event.reason,
        )
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

    log_pipeline_complete(
        logger,
        span=current_span,
        preprocessing_count=len(preprocessing_events),
    )
    from .api import ArrangementResult  # Local import to avoid cycle

    return ArrangementResult(
        span=current_span,
        folding=folding_result,
        salvage=salvage_result,
        preprocessing=tuple(preprocessing_events),
    )


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
        if event.action == "OCTAVE_DOWN_LOCAL":
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


__all__ = ["run_candidate_pipeline"]
