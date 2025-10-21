"""Helpers for ranking GP programs for a specific instrument."""

from __future__ import annotations

import logging
import re
from dataclasses import replace
from typing import Sequence, Tuple

from domain.arrangement.config import GraceSettings
from domain.arrangement.logging_utils import (
    describe_difficulty,
    describe_instrument,
    describe_span,
)
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.range_guard import enforce_instrument_range
from domain.arrangement.soft_key import InstrumentRange

from .fitness import FitnessConfig
from .ops import GPPrimitive
from .program_utils import (
    auto_range_programs as _default_auto_range_programs,
    describe_program as _describe_program,
    program_candidates as _program_candidates,
)
from .strategy_alignment import _uniform_octave_shift
from .strategy_candidates import generate_candidate_programs
from .strategy_evaluation import (
    _evaluate_program_candidate as _default_evaluate_program_candidate,
)
from .strategy_scoring import (
    ScoringPenalties,
    SortKey,
    _difficulty_sort_key,
    _top_voice_notes,
)


logger = logging.getLogger(__name__)


def _resolve_evaluate_program_candidate():
    try:
        from domain.arrangement.gp import strategy as strategy_module
    except Exception:  # pragma: no cover - fallback when strategy not ready
        return _default_evaluate_program_candidate
    return getattr(
        strategy_module,
        "_evaluate_program_candidate",
        _default_evaluate_program_candidate,
    )


def _resolve_auto_range_factory():
    try:
        from domain.arrangement.gp import strategy as strategy_module
    except Exception:  # pragma: no cover - fallback when strategy not ready
        return _default_auto_range_programs
    return getattr(
        strategy_module,
        "_auto_range_programs",
        _default_auto_range_programs,
    )


def score_instrument(
    *,
    instrument_id: str,
    instrument: InstrumentRange,
    phrase: PhraseSpan,
    programs: Sequence[Sequence[GPPrimitive]],
    fitness_config: FitnessConfig | None,
    beats_per_measure: int,
    manual_transposition: int = 0,
    preferred_register_shift: int | None = None,
    penalties: ScoringPenalties | None = None,
    grace_settings: GraceSettings | None = None,
    baseline_top_voice: Sequence[PhraseNote] | None = None,
    expected_offset: int | None = None,
) -> tuple[
    "GPInstrumentCandidate",
    SortKey,
    tuple[tuple[GPPrimitive, ...], ...],
]:
    """Score candidate GP programs for ``instrument_id``.

    Returns the best candidate along with its sort key and the programs actually
    evaluated.  The implementation mirrors the previous inline version inside
    :mod:`domain.arrangement.gp.strategy` so behaviour remains unchanged while
    allowing the strategy module to stay within the size limit enforced by the
    tests.
    """

    from .strategy_types import GPInstrumentCandidate  # local import to avoid cycles

    penalties = penalties or ScoringPenalties()
    evaluate_candidate = _resolve_evaluate_program_candidate()
    allow_range_clamp = penalties.allow_range_clamp()
    baseline_notes: tuple[PhraseNote, ...] = (
        tuple(baseline_top_voice) if baseline_top_voice is not None else tuple()
    )

    auto_shift_hint = preferred_register_shift
    phrase_min = min((note.midi for note in phrase.notes), default=None)
    phrase_max = max((note.midi for note in phrase.notes), default=None)
    phrase_range = (
        (phrase_max - phrase_min)
        if (phrase_min is not None and phrase_max is not None)
        else 0
    )
    instrument_span = instrument.max_midi - instrument.min_midi
    family_bias_enabled = bool(re.search(r"_c_\d+$", instrument_id))
    phrase_exceeds_span = family_bias_enabled and phrase_range > instrument_span
    phrase_top_voice = _top_voice_notes(phrase) if phrase_exceeds_span else tuple()

    if auto_shift_hint is None and phrase_exceeds_span and phrase_min is not None:
        target_shift = instrument.min_midi - phrase_min
        if target_shift:
            candidate_shift = round(target_shift / 12) * 12
            if candidate_shift == 0:
                if abs(target_shift) >= 6:
                    candidate_shift = 12 if target_shift > 0 else -12
                else:
                    candidate_shift = 0
            auto_shift_hint = int(max(-36, min(36, candidate_shift)))

    auto_range_factory = _resolve_auto_range_factory()
    candidate_programs, auto_programs = generate_candidate_programs(
        programs,
        phrase=phrase,
        instrument=instrument,
        beats_per_measure=beats_per_measure,
        manual_transposition=manual_transposition,
        preferred_register_shift=auto_shift_hint,
        auto_range_factory=auto_range_factory,
    )
    if auto_programs:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "arrange_v3_gp:auto programs instrument_id=%s programs=%s",
                instrument_id,
                [_describe_program(program) for program in auto_programs],
            )
    elif manual_transposition and logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "arrange_v3_gp:auto programs skipped instrument_id=%s manual_transposition=%+d",
            instrument_id,
            manual_transposition,
        )

    program_spans = _program_candidates(programs=candidate_programs, phrase=phrase)
    candidates: list[GPInstrumentCandidate] = []
    fallback_candidates: list[GPInstrumentCandidate] = []
    identity_candidate: GPInstrumentCandidate | None = None
    identity_reference_span: PhraseSpan | None = None
    uniform_reference_spans: dict[
        int, tuple[PhraseSpan, tuple[PhraseNote, ...], tuple[int, ...]]
    ] = {}
    candidate_uniform_shifts: list[int | None] = []
    processed_programs: set[Tuple[GPPrimitive, ...]] = set()

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "arrange_v3_gp:score start instrument_id=%s instrument=%s programs=%d",
            instrument_id,
            describe_instrument(instrument),
            len(program_spans),
        )

    if phrase_exceeds_span:
        uniform_programs: list[Tuple[GPPrimitive, ...]] = []
        non_uniform_programs: list[Tuple[GPPrimitive, ...]] = []
        for program in candidate_programs:
            program_key = tuple(program)
            uniform_shift = _uniform_octave_shift(program_key, phrase)
            if uniform_shift not in (None, 0):
                uniform_programs.append(program_key)
            else:
                non_uniform_programs.append(program_key)
        ordered_programs = uniform_programs + non_uniform_programs
    else:
        ordered_programs = [tuple(program) for program in candidate_programs]

    for program in ordered_programs:
        program_key = tuple(program)
        if program_key in processed_programs:
            continue
        processed_programs.add(program_key)
        candidate_span = program_spans[program_key]
        uniform_shift = _uniform_octave_shift(program_key, phrase)
        reference = identity_reference_span
        uniform_reference_voice: tuple[PhraseNote, ...] | None = None
        uniform_reference_deltas: tuple[int, ...] | None = None
        if phrase_exceeds_span and uniform_shift not in (None, 0):
            stored = uniform_reference_spans.get(uniform_shift)
            if stored is None:
                if phrase_top_voice:
                    reference_notes: list[PhraseNote] = []
                    min_gap = None
                    if instrument.min_midi is not None and phrase_min is not None:
                        min_gap = instrument.min_midi - phrase_min
                    for original_note in phrase_top_voice:
                        if uniform_shift is not None and uniform_shift < 0:
                            target_midi = original_note.midi + uniform_shift
                        elif (
                            uniform_shift
                            and uniform_shift > 0
                            and min_gap is not None
                            and min_gap >= 6
                        ):
                            target_midi = original_note.midi + uniform_shift
                        else:
                            target_midi = original_note.midi
                        iteration = 0
                        while (
                            instrument.min_midi is not None
                            and target_midi < instrument.min_midi
                            and iteration < 8
                        ):
                            target_midi += 12
                            iteration += 1
                        iteration = 0
                        while (
                            instrument.max_midi is not None
                            and target_midi > instrument.max_midi
                            and iteration < 8
                        ):
                            target_midi -= 12
                            iteration += 1
                        if instrument.min_midi is not None:
                            target_midi = max(instrument.min_midi, target_midi)
                        if instrument.max_midi is not None:
                            target_midi = min(instrument.max_midi, target_midi)
                        reference_notes.append(original_note.with_midi(int(target_midi)))
                    reference_top_voice = tuple(reference_notes)
                    allowed_deltas = tuple(
                        reference_note.midi - original_note.midi
                        for reference_note, original_note in zip(
                            reference_top_voice, phrase_top_voice
                        )
                    )
                else:
                    reference_top_voice = tuple()
                    allowed_deltas = tuple()
                stored = (candidate_span, reference_top_voice, allowed_deltas)
                uniform_reference_spans[uniform_shift] = stored
            _, uniform_reference_voice, uniform_reference_deltas = stored
        elif phrase_exceeds_span and uniform_reference_spans:
            _, _, uniform_reference_deltas = next(iter(uniform_reference_spans.values()))
        candidate, range_event = evaluate_candidate(
            program_key,
            instrument_id=instrument_id,
            instrument=instrument,
            phrase=phrase,
            beats_per_measure=beats_per_measure,
            fitness_config=fitness_config,
            candidate_span=candidate_span,
            allow_range_clamp=allow_range_clamp,
            grace_settings=grace_settings,
            baseline_top_voice=baseline_notes if expected_offset is not None else None,
            expected_offset=expected_offset if baseline_notes else None,
            reference_span=reference,
            uniform_reference_top_voice=uniform_reference_voice,
            uniform_reference_deltas=(
                uniform_reference_deltas
                if (
                    phrase_exceeds_span
                    and (uniform_shift not in (None, 0) or uniform_reference_spans)
                )
                else None
            ),
        )
        if (
            phrase_exceeds_span
            and range_event is not None
            and uniform_reference_spans
            and phrase_top_voice
        ):
            top_candidate = _top_voice_notes(candidate.span)
            sample = min(len(phrase_top_voice), len(top_candidate))
            if sample:
                delta_values = [
                    top_candidate[index].midi - phrase_top_voice[index].midi
                    for index in range(sample)
                ]
                reference_deltas_options: list[tuple[int, ...]] = []
                if uniform_shift not in (None, 0):
                    stored = uniform_reference_spans.get(uniform_shift)
                    if stored is not None:
                        reference_deltas_options.append(stored[2])
                else:
                    reference_deltas_options.extend(
                        stored[2] for stored in uniform_reference_spans.values()
                    )
                if reference_deltas_options:
                    ratios: list[float] = []
                    for option in reference_deltas_options:
                        matches = 0
                        for index, delta in enumerate(delta_values):
                            try:
                                expected_delta = int(option[index])
                            except (IndexError, TypeError, ValueError):
                                expected_delta = None
                            if expected_delta is not None and delta == expected_delta:
                                matches += 1
                        ratios.append(1.0 - (matches / sample))
                    mismatch_ratio = min(ratios) if ratios else 0.0
                    if mismatch_ratio > 0:
                        adjusted_penalty = max(
                            candidate.melody_shift_penalty, mismatch_ratio * 12.0
                        )
                        if adjusted_penalty != candidate.melody_shift_penalty:
                            candidate = replace(
                                candidate,
                                melody_shift_penalty=round(adjusted_penalty, 12),
                            )
        if not program_key:
            identity_candidate = candidate
            identity_reference_span = candidate.span
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "arrange_v3_gp:score candidate instrument_id=%s program=%s %s fitness=%s melody_penalty=%.3f range_clamped=%s span=%s",
                instrument_id,
                _describe_program(program_key),
                describe_difficulty(candidate.difficulty),
                candidate.fitness.as_tuple(),
                candidate.melody_penalty,
                range_event.reason if range_event is not None else None,
                describe_span(candidate.span),
            )
        fallback_candidates.append(candidate)
        if not allow_range_clamp and range_event is not None:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "arrange_v3_gp:skip candidate instrument_id=%s reason=range-clamp-disabled program=%s",
                    instrument_id,
                    _describe_program(candidate.program),
                )
            continue
        candidates.append(candidate)
        candidate_uniform_shifts.append(uniform_shift if uniform_shift is not None else None)

    if not candidates:
        candidates = fallback_candidates
        if not candidate_uniform_shifts:
            candidate_uniform_shifts = [None] * len(candidates)
    if not candidates:  # pragma: no cover - defensive
        raise RuntimeError("Unable to score instrument without GP programs")

    fidelity_baseline = (
        identity_candidate.fitness.fidelity if identity_candidate is not None else None
    )
    fidelity_importance = (
        fitness_config.fidelity.weight if fitness_config is not None else 1.0
    )
    melody_baseline = (
        identity_candidate.melody_penalty if identity_candidate is not None else None
    )
    melody_importance = fidelity_importance

    keyed_candidates = []
    preferred_uniform_shift = (
        auto_shift_hint if (phrase_exceeds_span and auto_shift_hint) else None
    )
    for candidate, candidate_shift in zip(candidates, candidate_uniform_shifts):
        key = _difficulty_sort_key(
            candidate,
            baseline_fidelity=fidelity_baseline,
            fidelity_importance=fidelity_importance,
            baseline_melody=melody_baseline,
            melody_importance=melody_importance,
            penalties=penalties,
            grace_settings=grace_settings,
        )
        key_prefix = 1
        if (
            phrase_exceeds_span
            and auto_shift_hint is not None
            and auto_shift_hint != 0
            and candidate_shift == auto_shift_hint
        ):
            key_head = max(0, key[0] - 1)
            key_body = (key[1] - 100.0, *key[2:]) if len(key) > 1 else tuple()
            key = (key_head, *key_body)
            key_prefix = 0
        keyed_candidates.append(((key_prefix, *key), candidate))
    keyed_candidates.sort(key=lambda item: item[0])
    best_key, best_candidate = keyed_candidates[0]

    return best_candidate, best_key, tuple(candidate_programs)


__all__ = ["score_instrument"]

