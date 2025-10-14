"""High-level orchestration helpers for GP-backed arrangement strategies."""

from __future__ import annotations

import logging
from typing import Callable, Iterable, Mapping, Sequence, Tuple, TYPE_CHECKING

from domain.arrangement.config import get_instrument_range
from domain.arrangement.difficulty import DifficultySummary, summarize_difficulty
from domain.arrangement.explanations import ExplanationEvent
from domain.arrangement.melody import isolate_melody as _isolate_melody
from domain.arrangement.phrase import PhraseSpan
from domain.arrangement.range_guard import enforce_instrument_range
from domain.arrangement.soft_key import InstrumentRange
from domain.arrangement.logging_utils import (
    describe_difficulty,
    describe_instrument,
    describe_span,
)

from .fitness import FitnessConfig, FitnessVector, compute_fitness, melody_pitch_penalty
from .explain import explain_program
from .ops import GPPrimitive
from .session import GPSessionConfig, GPSessionResult, run_gp_session
from .session_logging import serialize_individual
from .program_utils import (
    apply_program as _apply_program,
    auto_range_programs as _auto_range_programs,
    describe_program as _describe_program,
    program_candidates as _program_candidates,
    span_within_instrument_range as _span_within_instrument_range,
)
from .strategy_scoring import (
    _difficulty_sort_key,
    _melody_shift_penalty,
    _summarize_individual,
)
from .strategy_types import GPArrangementStrategyResult, GPInstrumentCandidate


if TYPE_CHECKING:
    from domain.arrangement.api import ArrangementStrategyResult


logger = logging.getLogger(__name__)
# Re-export the melody isolation helper so existing tests can monkeypatch via this module.
isolate_melody = _isolate_melody


def _score_instrument(
    *,
    instrument_id: str,
    instrument: InstrumentRange,
    phrase: PhraseSpan,
    programs: Sequence[Sequence[GPPrimitive]],
    fitness_config: FitnessConfig | None,
    beats_per_measure: int,
    manual_transposition: int = 0,
) -> tuple[
    GPInstrumentCandidate,
    tuple[int, float, float, float, float, float, float, float, float, float, float],
    tuple[tuple[GPPrimitive, ...], ...],
]:
    program_keys = {tuple(program) for program in programs}
    candidate_programs: list[tuple[GPPrimitive, ...]] = [tuple(program) for program in programs]

    auto_programs: tuple[tuple[GPPrimitive, ...], ...] = ()
    if manual_transposition == 0:
        auto_programs = _auto_range_programs(
            phrase, instrument, beats_per_measure=beats_per_measure
        )
        if auto_programs and logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "arrange_v3_gp:auto programs instrument_id=%s programs=%s",
                instrument_id,
                [_describe_program(program) for program in auto_programs],
            )
    elif logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "arrange_v3_gp:auto programs skipped instrument_id=%s manual_transposition=%+d",
            instrument_id,
            manual_transposition,
        )

    for extra_program in auto_programs:
        if extra_program not in program_keys:
            candidate_programs.append(extra_program)
            program_keys.add(extra_program)

    program_spans = _program_candidates(programs=candidate_programs, phrase=phrase)
    candidates: list[GPInstrumentCandidate] = []
    identity_candidate: GPInstrumentCandidate | None = None

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "arrange_v3_gp:score start instrument_id=%s instrument=%s programs=%d",
            instrument_id,
            describe_instrument(instrument),
            len(program_spans),
        )

    for program, candidate_span in program_spans.items():
        adjusted_span = candidate_span
        range_event = None
        if not _span_within_instrument_range(candidate_span, instrument):
            adjusted_span, range_event, _ = enforce_instrument_range(
                candidate_span,
                instrument,
                beats_per_measure=beats_per_measure,
            )
        difficulty = summarize_difficulty(adjusted_span, instrument)
        fitness = compute_fitness(
            original=phrase,
            candidate=adjusted_span,
            instrument=instrument,
            program=program,
            difficulty=difficulty,
            config=fitness_config,
        )
        melody_penalty = melody_pitch_penalty(
            phrase,
            adjusted_span,
            beats_per_measure=beats_per_measure,
        )
        shift_penalty = _melody_shift_penalty(
            phrase,
            adjusted_span,
            beats_per_measure=beats_per_measure,
        )
        explanations = explain_program(
            program,
            phrase,
            instrument,
            beats_per_measure=beats_per_measure,
        )
        if range_event is not None:
            explanations = explanations + (range_event,)
        candidate = GPInstrumentCandidate(
            instrument_id=instrument_id,
            instrument=instrument,
            program=program,
            span=adjusted_span,
            difficulty=difficulty,
            fitness=fitness,
            melody_penalty=round(melody_penalty, 12),
            melody_shift_penalty=shift_penalty,
            explanations=explanations,
        )
        if not program:
            identity_candidate = candidate
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "arrange_v3_gp:score candidate instrument_id=%s program=%s %s fitness=%s melody_penalty=%.3f range_clamped=%s span=%s",
                instrument_id,
                _describe_program(program),
                describe_difficulty(difficulty),
                fitness.as_tuple(),
                melody_penalty,
                range_event.reason if range_event is not None else None,
                describe_span(adjusted_span),
            )
        candidates.append(candidate)

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

    keyed_candidates = [
        (
            _difficulty_sort_key(
                candidate,
                baseline_fidelity=fidelity_baseline,
                fidelity_importance=fidelity_importance,
                baseline_melody=melody_baseline,
                melody_importance=melody_importance,
            ),
            candidate,
        )
        for candidate in candidates
    ]
    keyed_candidates.sort(key=lambda item: item[0])
    best_key, best_candidate = keyed_candidates[0]

    return best_candidate, best_key, tuple(candidate_programs)


def arrange_v3_gp(
    phrase: PhraseSpan,
    *,
    instrument_id: str,
    config: GPSessionConfig,
    starred_ids: Iterable[str] | None = None,
    salvage_events: Sequence[ExplanationEvent] | None = None,
    transposition: int = 0,
    manual_transposition: int | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> GPArrangementStrategyResult:
    """Run a GP session for ``instrument_id`` and rank starred instruments.

    The return value surfaces the winning candidate, the ordered comparison list,
    the serialized Pareto archive, termination metadata, and any best-effort
    fallback computed via the arranger v2 pipeline when the GP loop exits early.
    """

    manual_offset = manual_transposition or 0

    base_instrument = get_instrument_range(instrument_id)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "arrange_v3_gp:start instrument_id=%s instrument=%s starred=%s transposition=%+d manual_transposition=%+d span=%s config=%s",
            instrument_id,
            describe_instrument(base_instrument),
            tuple(starred_ids or ()),
            transposition,
            manual_offset,
            describe_span(phrase),
            config,
        )
    session = run_gp_session(
        phrase,
        base_instrument,
        config=config,
        salvage_events=salvage_events,
        transposition=transposition,
        progress_callback=progress_callback,
    )

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "arrange_v3_gp:session complete reason=%s generations=%d elapsed=%.3fs winner_program=%s winner_fitness=%s",
            session.termination_reason,
            session.generations,
            session.elapsed_seconds,
            _describe_program(session.winner.program),
            session.winner.fitness.as_tuple(),
        )
        for generation in session.log.generations:
            best_programs = ", ".join(
                _summarize_individual(summary) for summary in generation.best_programs
            )
            archive_size = len(generation.archive)
            logger.debug(
                "arrange_v3_gp:generation index=%d best=[%s] archive=%d",
                generation.index,
                best_programs or "",
                archive_size,
            )
        if session.log.final_best is not None:
            logger.debug(
                "arrange_v3_gp:final best=%s",
                _summarize_individual(session.log.final_best),
            )

    winner_program = tuple(session.winner.program)
    programs: list[Tuple[GPPrimitive, ...]] = [tuple()]
    if winner_program and winner_program not in programs:
        programs.append(winner_program)
    elif not winner_program:
        # Winner already represents the identity transformation; keep the list stable.
        pass
    beats_per_measure = config.constraints.beats_per_measure if config.constraints else 4

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "arrange_v3_gp:programs=%s",
            [_describe_program(program) for program in programs],
        )

    tracked_programs: list[Tuple[GPPrimitive, ...]] = list(programs)
    archive_summary = tuple(serialize_individual(individual) for individual in session.archive)

    candidate_ids = [instrument_id]
    for starred in tuple(starred_ids or ()):  # preserve declaration order
        if starred not in candidate_ids:
            candidate_ids.append(starred)

    candidates: list[GPInstrumentCandidate] = []
    candidate_keys: dict[
        str,
        tuple[int, float, float, float, float, float, float, float, float, float, float],
    ] = {}
    for candidate_id in candidate_ids:
        instrument = get_instrument_range(candidate_id)
        candidate, sort_key, used_programs = _score_instrument(
            instrument_id=candidate_id,
            instrument=instrument,
            phrase=phrase,
            programs=tuple(programs),
            fitness_config=config.fitness_config,
            beats_per_measure=beats_per_measure,
            manual_transposition=manual_offset,
        )
        candidates.append(candidate)
        candidate_keys[candidate.instrument_id] = sort_key
        for program in used_programs:
            if program not in programs:
                programs.append(program)
            if program not in tracked_programs:
                tracked_programs.append(program)

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "arrange_v3_gp:scored candidates=%s",
            [
                (
                    candidate.instrument_id,
                    _describe_program(candidate.program),
                    describe_difficulty(candidate.difficulty),
                    f"melody={candidate.melody_penalty:.3f}",
                    f"key={candidate_keys[candidate.instrument_id]}",
                )
                for candidate in candidates
            ],
        )

    ranked = tuple(
        sorted(
            candidates,
            key=lambda candidate: candidate_keys[candidate.instrument_id],
        )
    )

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "arrange_v3_gp:ranked order=%s",
            [candidate.instrument_id for candidate in ranked],
        )

    fallback_result: "ArrangementStrategyResult | None" = None
    if session.termination_reason != "generation_limit":
        from domain.arrangement.api import arrange

        fallback_result = arrange(
            phrase,
            instrument_id=instrument_id,
            starred_ids=starred_ids,
            strategy="starred-best",
        )
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("arrange_v3_gp:fallback computed strategy=starred-best")

    return GPArrangementStrategyResult(
        session=session,
        programs=tuple(tracked_programs),
        chosen=ranked[0],
        comparisons=ranked,
        archive_summary=archive_summary,
        termination_reason=session.termination_reason,
        fallback=fallback_result,
    )


__all__ = [
    "GPArrangementStrategyResult",
    "GPInstrumentCandidate",
    "arrange_v3_gp",
]

