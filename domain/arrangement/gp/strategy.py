"""High-level orchestration helpers for GP-backed arrangement strategies."""

from __future__ import annotations

import logging
from typing import Callable, Iterable, Sequence, Tuple, TYPE_CHECKING

from domain.arrangement.config import (
    DEFAULT_GRACE_SETTINGS,
    GraceSettings,
    get_instrument_range,
)
from domain.arrangement.explanations import ExplanationEvent
from domain.arrangement.melody import isolate_melody as _isolate_melody
from domain.arrangement.phrase import PhraseSpan
from domain.arrangement.soft_key import InstrumentRange
from domain.arrangement.logging_utils import (
    describe_difficulty,
    describe_instrument,
    describe_span,
    span_note_names,
)

from .fitness import FitnessConfig, compute_fitness, melody_pitch_penalty
from .ops import GPPrimitive
from .session import GPSessionConfig, GPSessionResult, run_gp_session
from .session_logging import serialize_individual
from .program_utils import (
    describe_program as _describe_program,
    program_candidates as _program_candidates,
)
from .strategy_scoring import (
    ScoringPenalties,
    _difficulty_sort_key,
    _melody_shift_penalty,
    _summarize_individual,
)
from .program_utils import auto_range_programs as _auto_range_programs
from .strategy_candidates import generate_candidate_programs
from .strategy_types import GPArrangementStrategyResult, GPInstrumentCandidate
from .strategy_alignment import _align_top_voice_to_target
from .strategy_evaluation import _evaluate_program_candidate


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
    preferred_register_shift: int | None = None,
    penalties: ScoringPenalties | None = None,
    grace_settings: GraceSettings | None = None,
) -> tuple[
    GPInstrumentCandidate,
    tuple[int, float, float, float, float, float, float, float, float, float, float],
    tuple[tuple[GPPrimitive, ...], ...],
]:
    penalties = penalties or ScoringPenalties()
    allow_range_clamp = penalties.allow_range_clamp()

    candidate_programs, auto_programs = generate_candidate_programs(
        programs,
        phrase=phrase,
        instrument=instrument,
        beats_per_measure=beats_per_measure,
        manual_transposition=manual_transposition,
        preferred_register_shift=preferred_register_shift,
        auto_range_factory=_auto_range_programs,
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

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "arrange_v3_gp:score start instrument_id=%s instrument=%s programs=%d",
            instrument_id,
            describe_instrument(instrument),
            len(program_spans),
        )

    for program, candidate_span in program_spans.items():
        candidate, range_event = _evaluate_program_candidate(
            program,
            instrument_id=instrument_id,
            instrument=instrument,
            phrase=phrase,
            beats_per_measure=beats_per_measure,
            fitness_config=fitness_config,
            candidate_span=candidate_span,
            allow_range_clamp=allow_range_clamp,
            grace_settings=grace_settings,
        )
        if not program:
            identity_candidate = candidate
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "arrange_v3_gp:score candidate instrument_id=%s program=%s %s fitness=%s melody_penalty=%.3f range_clamped=%s span=%s",
                instrument_id,
                _describe_program(candidate.program),
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

    if not candidates:
        candidates = fallback_candidates
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
                penalties=penalties,
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
    preferred_register_shift: int | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    grace_settings: GraceSettings | None = None,
) -> GPArrangementStrategyResult:
    """Run a GP session for ``instrument_id`` and rank starred instruments.

    The return value surfaces the winning candidate, the ordered comparison list,
    the serialized Pareto archive, termination metadata, and any best-effort
    fallback computed via the arranger v2 pipeline when the GP loop exits early.
    """

    manual_offset = manual_transposition or 0
    active_grace = grace_settings or DEFAULT_GRACE_SETTINGS

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

    beats_per_measure = config.constraints.beats_per_measure if config.constraints else 4

    winner_program = tuple(session.winner.program)
    penalties = getattr(config, "scoring_penalties", None)
    allow_range_clamp = penalties.allow_range_clamp() if penalties is not None else True

    winner_candidate, _ = _evaluate_program_candidate(
        winner_program,
        instrument_id=instrument_id,
        instrument=base_instrument,
        phrase=phrase,
        beats_per_measure=beats_per_measure,
        fitness_config=config.fitness_config,
        allow_range_clamp=allow_range_clamp,
        grace_settings=active_grace,
    )

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "arrange_v3_gp:winner note names instrument_id=%s program=%s original=%s arranged=%s",
            instrument_id,
            _describe_program(winner_program),
            span_note_names(phrase),
            span_note_names(winner_candidate.span),
        )

    programs: list[Tuple[GPPrimitive, ...]] = [tuple()]
    if winner_program and winner_program not in programs:
        programs.append(winner_program)
    elif not winner_program:
        # Winner already represents the identity transformation; keep the list stable.
        pass

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "arrange_v3_gp:programs=%s",
            [_describe_program(program) for program in programs],
        )

    tracked_programs: list[Tuple[GPPrimitive, ...]] = list(programs)
    archive_summary = tuple(serialize_individual(individual) for individual in session.archive)

    starred_order = tuple(dict.fromkeys(starred_ids or ()))
    candidate_ids: list[str] = []
    if not starred_order:
        candidate_ids.append(instrument_id)
    else:
        if instrument_id in starred_order:
            candidate_ids.append(instrument_id)
        for starred in starred_order:  # preserve declaration order
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
            preferred_register_shift=preferred_register_shift,
            penalties=penalties,
            grace_settings=active_grace,
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

    best_requested = next(
        (candidate for candidate in ranked if candidate.instrument_id == instrument_id),
        ranked[0],
    )

    if winner_candidate.instrument_id == instrument_id:
        winner_candidate = _align_top_voice_to_target(
            winner_candidate,
            target=best_requested,
            instrument=base_instrument,
            phrase=phrase,
            beats_per_measure=beats_per_measure,
            fitness_config=config.fitness_config,
        )

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "arrange_v3_gp:ranked order=%s",
            [candidate.instrument_id for candidate in ranked],
        )

    chosen_candidate = ranked[0]

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "arrange_v3_gp:note names instrument_id=%s program=%s original=%s arranged=%s",
            chosen_candidate.instrument_id,
            _describe_program(chosen_candidate.program),
            span_note_names(phrase),
            span_note_names(chosen_candidate.span),
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
        winner_candidate=winner_candidate,
        archive_summary=archive_summary,
        termination_reason=session.termination_reason,
        fallback=fallback_result,
    )


__all__ = [
    "GPArrangementStrategyResult",
    "GPInstrumentCandidate",
    "arrange_v3_gp",
    "compute_fitness",
    "melody_pitch_penalty",
]

