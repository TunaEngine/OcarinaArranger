"""Program evaluation helpers for the GP arrangement strategy."""

from __future__ import annotations

import logging
from typing import Sequence, Tuple

from domain.arrangement.config import GraceSettings
from domain.arrangement.difficulty import summarize_difficulty
from domain.arrangement.explanations import ExplanationEvent
from domain.arrangement.melody import isolate_melody as _isolate_melody
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.range_guard import enforce_instrument_range
from domain.arrangement.soft_key import InstrumentRange

from .explain import explain_program
from .fitness import FitnessConfig, compute_fitness, melody_pitch_penalty
from .ops import GPPrimitive, GlobalTranspose
from .program_utils import (
    apply_program as _apply_program,
    describe_program as _describe_program,
    span_within_instrument_range as _span_within_instrument_range,
)
from .strategy_alignment import (
    _align_top_voice_to_baseline,
    _align_uniform_octave_span,
    _uniform_octave_shift,
)
from .strategy_scoring import _melody_shift_penalty, _top_voice_notes
from .strategy_types import GPInstrumentCandidate

logger = logging.getLogger(__name__)

# Re-export the melody isolation helper so existing tests can monkeypatch via this module.
isolate_melody = _isolate_melody


def _evaluate_program_candidate(
    program: Tuple[GPPrimitive, ...],
    *,
    instrument_id: str,
    instrument: InstrumentRange,
    phrase: PhraseSpan,
    beats_per_measure: int,
    fitness_config: FitnessConfig | None,
    candidate_span: PhraseSpan | None = None,
    allow_range_clamp: bool = True,
    grace_settings: GraceSettings | None = None,
    baseline_top_voice: Sequence[PhraseNote] | None = None,
    expected_offset: int | None = None,
    reference_span: PhraseSpan | None = None,
    uniform_reference_top_voice: Sequence[PhraseNote] | None = None,
    uniform_reference_deltas: Sequence[int] | None = None,
) -> tuple[GPInstrumentCandidate, ExplanationEvent | None]:
    if candidate_span is None:
        candidate_span = phrase if not program else _apply_program(program, phrase)
    reference_span = reference_span or phrase
    range_event: ExplanationEvent | None = None
    clamp_disabled_out_of_range = False
    uniform_shift = _uniform_octave_shift(program, phrase)
    prefer_octave_top_voice = uniform_shift is not None
    penalty_shift = uniform_shift
    if penalty_shift is None and len(program) == 1 and isinstance(program[0], GlobalTranspose):
        semitones = getattr(program[0], "semitones", 0)
        try:
            raw_shift = int(semitones)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            raw_shift = 0
        if raw_shift != 0:
            candidate_shift = round(raw_shift / 12) * 12
            if candidate_shift == 0:
                candidate_shift = 12 if raw_shift > 0 else -12
            penalty_shift = candidate_shift
    if not _span_within_instrument_range(candidate_span, instrument):
        if not allow_range_clamp:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "arrange_v3_gp:range clamp disabled instrument_id=%s program=%s",
                    instrument_id,
                    _describe_program(program),
                )
            clamp_disabled_out_of_range = True
        else:
            candidate_span, range_event, _ = enforce_instrument_range(
                candidate_span,
                instrument,
                beats_per_measure=beats_per_measure,
                prefer_octave_top_voice=prefer_octave_top_voice,
            )
            if range_event is not None and uniform_shift is not None:
                candidate_span = _align_uniform_octave_span(
                    candidate_span,
                    reference_span=reference_span,
                    instrument=instrument,
                    uniform_shift=uniform_shift,
                )

    if baseline_top_voice and expected_offset is not None:
        candidate_span = _align_top_voice_to_baseline(
            candidate_span,
            baseline_top_voice=baseline_top_voice,
            instrument=instrument,
            expected_offset=expected_offset,
        )
    if uniform_reference_top_voice:
        candidate_span = _align_top_voice_to_baseline(
            candidate_span,
            baseline_top_voice=uniform_reference_top_voice,
            instrument=instrument,
            expected_offset=0,
        )

    difficulty = summarize_difficulty(
        candidate_span, instrument, grace_settings=grace_settings
    )
    fitness = compute_fitness(
        original=phrase,
        candidate=candidate_span,
        instrument=instrument,
        program=program,
        difficulty=difficulty,
        config=fitness_config,
        grace_settings=grace_settings,
    )
    melody_penalty = melody_pitch_penalty(
        phrase,
        candidate_span,
        beats_per_measure=beats_per_measure,
    )
    shift_penalty = _melody_shift_penalty(
        phrase,
        candidate_span,
        beats_per_measure=beats_per_measure,
    )
    if range_event is not None and (
        penalty_shift is not None or uniform_reference_deltas is not None
    ):
        top_original = _top_voice_notes(phrase)
        top_candidate = _top_voice_notes(candidate_span)
        sample = min(len(top_original), len(top_candidate))
        if sample:
            delta_values = [
                top_candidate[index].midi - top_original[index].midi
                for index in range(sample)
            ]
            expected_shift: int | None = None
            if penalty_shift is not None:
                try:
                    expected_shift = int(penalty_shift)
                except (TypeError, ValueError):  # pragma: no cover - defensive
                    expected_shift = None

            reference_matches = 0
            if uniform_reference_deltas:
                for index, delta in enumerate(delta_values):
                    try:
                        expected_delta = int(uniform_reference_deltas[index])
                    except (IndexError, TypeError, ValueError):
                        expected_delta = None
                    if expected_delta is not None and delta == expected_delta:
                        reference_matches += 1

            if expected_shift is not None and all(
                delta == expected_shift for delta in delta_values
            ):
                shift_penalty = 0.0
            elif (
                uniform_reference_deltas is not None
                and reference_matches == sample
                and expected_shift is None
            ):
                shift_penalty = 0.0
            else:
                uniform_matches = 0
                if expected_shift is not None:
                    uniform_matches = sum(
                        1 for delta in delta_values if delta == expected_shift
                    )
                ratios: list[float] = []
                if uniform_reference_deltas is not None:
                    ratios.append(1.0 - (reference_matches / sample))
                if expected_shift is not None:
                    ratios.append(1.0 - (uniform_matches / sample))
                mismatch_ratio = min(ratios) if ratios else 0.0
                if mismatch_ratio > 0:
                    shift_penalty = max(shift_penalty, mismatch_ratio * 12.0)
    shift_penalty = round(shift_penalty, 12)
    explanations = explain_program(
        program,
        phrase,
        instrument,
        beats_per_measure=beats_per_measure,
        grace_settings=grace_settings,
    )
    disabled_event: ExplanationEvent | None = None
    if range_event is not None:
        explanations = explanations + (range_event,)
    elif clamp_disabled_out_of_range:
        disabled_event = ExplanationEvent.from_step(
            action="range-warning",
            reason="Range clamp disabled; candidate exceeds instrument range",
            reason_code="range-clamp-disabled",
            before=candidate_span,
            after=candidate_span,
            difficulty_before=difficulty.hard_and_very_hard,
            difficulty_after=difficulty.hard_and_very_hard,
            beats_per_measure=beats_per_measure,
        )
        explanations = explanations + (disabled_event,)
        range_event = disabled_event

    candidate = GPInstrumentCandidate(
        instrument_id=instrument_id,
        instrument=instrument,
        program=program,
        span=candidate_span,
        difficulty=difficulty,
        fitness=fitness,
        melody_penalty=round(melody_penalty, 12),
        melody_shift_penalty=shift_penalty,
        explanations=explanations,
    )
    return candidate, range_event


__all__ = [
    "isolate_melody",
    "_evaluate_program_candidate",
]
