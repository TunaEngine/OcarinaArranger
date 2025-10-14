"""High-level orchestration helpers for GP-backed arrangement strategies."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence, Tuple, TYPE_CHECKING

from domain.arrangement.config import get_instrument_range
from domain.arrangement.difficulty import DifficultySummary, summarize_difficulty
from domain.arrangement.explanations import ExplanationEvent
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
from .ops import GPPrimitive, GlobalTranspose, LocalOctave, SimplifyRhythm
from .session import GPSessionConfig, GPSessionResult, run_gp_session
from .session_logging import IndividualSummary, serialize_individual
from .program_utils import (
    apply_program as _apply_program,
    auto_range_programs as _auto_range_programs,
    describe_program as _describe_program,
    program_candidates as _program_candidates,
    span_within_instrument_range as _span_within_instrument_range,
)


if TYPE_CHECKING:
    from domain.arrangement.api import ArrangementStrategyResult


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GPInstrumentCandidate:
    """Arrangement outcome for a single instrument using a GP program."""

    instrument_id: str
    instrument: InstrumentRange
    program: Tuple[GPPrimitive, ...]
    span: PhraseSpan
    difficulty: DifficultySummary
    fitness: FitnessVector
    melody_penalty: float
    explanations: Tuple[ExplanationEvent, ...] = ()


@dataclass(frozen=True)
class GPArrangementStrategyResult:
    """Return value capturing GP session data and ranked instrument outcomes."""

    session: GPSessionResult
    programs: Tuple[Tuple[GPPrimitive, ...], ...]
    chosen: GPInstrumentCandidate
    comparisons: Tuple[GPInstrumentCandidate, ...]
    archive_summary: Tuple[IndividualSummary, ...]
    termination_reason: str
    fallback: "ArrangementStrategyResult | None" = None


FIDELITY_WEIGHT = 3.0
RANGE_CLAMP_PENALTY = 1000.0


def _summarize_individual(summary: IndividualSummary) -> str:
    fitness = summary.fitness
    program_entries = summary.program
    if not program_entries:
        program_desc = "<identity>"
    else:
        parts: list[str] = []
        for entry in program_entries:
            entry_type = entry.get("type", "<unknown>")
            span_info = entry.get("span", {})
            label = span_info.get("label", "span")
            parameters = [
                f"{key}={value}"
                for key, value in entry.items()
                if key not in {"type", "span"}
            ]
            param_desc = ", ".join(parameters)
            if param_desc:
                parts.append(f"{entry_type}({param_desc}@{label})")
            else:
                parts.append(f"{entry_type}@{label}")
        program_desc = " -> ".join(parts)
    return (
        f"{program_desc} play={fitness['playability']:.3f} "
        f"fid={fitness['fidelity']:.3f} tess={fitness['tessitura']:.3f} "
        f"size={fitness['program_size']:.3f}"
    )


def _difficulty_sort_key(
    candidate: GPInstrumentCandidate,
    *,
    baseline_fidelity: float | None = None,
    fidelity_importance: float = 1.0,
    baseline_melody: float | None = None,
    melody_importance: float = 1.0,
) -> tuple[float, float, float, float, float, float, float]:
    """Return a tuple that ranks candidates by melodic fidelity before difficulty."""

    melody_penalty = candidate.melody_penalty
    melody_weight = max(1.0, melody_importance)
    if len(candidate.program) > 0 and baseline_melody is not None:
        melody_diff = melody_penalty - baseline_melody
        if melody_diff > 0:
            melody_penalty = baseline_melody + melody_diff * melody_weight * FIDELITY_WEIGHT
    melody_key = round(melody_penalty, 12)

    difficulty = candidate.difficulty
    has_range_clamp = any(
        event.reason_code == "range-clamp" for event in candidate.explanations
    )
    range_key = 1 if has_range_clamp else 0
    range_penalty = 0.0
    if has_range_clamp and len(candidate.program) > 0:
        # Non-identity programs that still require clamping should be strongly
        # disfavoured so register-faithful candidates stay ahead.
        range_penalty = RANGE_CLAMP_PENALTY * 2

    fidelity_penalty = candidate.fitness.fidelity
    program_length = len(candidate.program)
    program_complexity = sum(
        0 if isinstance(operation, GlobalTranspose) else 1
        for operation in candidate.program
    )
    importance = max(1.0, fidelity_importance)

    if program_length > 0:
        if baseline_fidelity is not None:
            diff = fidelity_penalty - baseline_fidelity
            if diff > 0:
                fidelity_penalty = baseline_fidelity + diff * importance * FIDELITY_WEIGHT
        else:
            fidelity_penalty = fidelity_penalty * importance * FIDELITY_WEIGHT

    return (
        range_key,
        melody_key,
        round(fidelity_penalty, 12),
        program_complexity,
        program_length,
        difficulty.hard_and_very_hard + range_penalty,
        difficulty.medium,
        difficulty.tessitura_distance,
        candidate.fitness.playability,
    )


def _score_instrument(
    *,
    instrument_id: str,
    instrument: InstrumentRange,
    phrase: PhraseSpan,
    programs: Sequence[Sequence[GPPrimitive]],
    fitness_config: FitnessConfig | None,
    beats_per_measure: int,
) -> tuple[
    GPInstrumentCandidate,
    tuple[float, float, float, float, float, float, float],
    tuple[tuple[GPPrimitive, ...], ...],
]:
    program_keys = {tuple(program) for program in programs}
    candidate_programs: list[tuple[GPPrimitive, ...]] = [tuple(program) for program in programs]

    auto_programs = _auto_range_programs(phrase, instrument)
    if auto_programs and logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "arrange_v3_gp:auto programs instrument_id=%s programs=%s",
            instrument_id,
            [_describe_program(program) for program in auto_programs],
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
) -> GPArrangementStrategyResult:
    """Run a GP session for ``instrument_id`` and rank starred instruments.

    The return value surfaces the winning candidate, the ordered comparison list,
    the serialized Pareto archive, termination metadata, and any best-effort
    fallback computed via the arranger v2 pipeline when the GP loop exits early.
    """

    base_instrument = get_instrument_range(instrument_id)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "arrange_v3_gp:start instrument_id=%s instrument=%s starred=%s transposition=%+d span=%s config=%s",
            instrument_id,
            describe_instrument(base_instrument),
            tuple(starred_ids or ()),
            transposition,
            describe_span(phrase),
            config,
        )
    session = run_gp_session(
        phrase,
        base_instrument,
        config=config,
        salvage_events=salvage_events,
        transposition=transposition,
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
    candidate_keys: dict[str, tuple[float, float, float, float, float, float, float]] = {}
    for candidate_id in candidate_ids:
        instrument = get_instrument_range(candidate_id)
        candidate, sort_key, used_programs = _score_instrument(
            instrument_id=candidate_id,
            instrument=instrument,
            phrase=phrase,
            programs=tuple(programs),
            fitness_config=config.fitness_config,
            beats_per_measure=beats_per_measure,
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

