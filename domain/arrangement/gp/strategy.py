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
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.logging_utils import (
    describe_difficulty,
    describe_instrument,
    describe_span,
    span_note_names,
)

from .fitness import compute_fitness, melody_pitch_penalty
from .ops import GPPrimitive
from .program_utils import (
    auto_range_programs as _auto_range_programs,
    describe_program as _describe_program,
)
from .session import GPSessionConfig, run_gp_session
from .session_logging import serialize_individual
from .strategy_alignment import _align_top_voice_to_target
from .strategy_evaluation import _evaluate_program_candidate
from .strategy_instrument import score_instrument as _score_instrument
from .strategy_scoring import (
    _difficulty_sort_key,
    _melody_shift_penalty,
    _summarize_individual,
    _top_voice_notes,
)
from .strategy_types import GPArrangementStrategyResult, GPInstrumentCandidate


if TYPE_CHECKING:
    from domain.arrangement.api import ArrangementStrategyResult


logger = logging.getLogger(__name__)
# Re-export the melody isolation helper so existing tests can monkeypatch via this module.
isolate_melody = _isolate_melody


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
    candidate_ids: list[str] = [instrument_id]
    for starred in starred_order:  # preserve declaration order
        if starred not in candidate_ids:
            candidate_ids.append(starred)

    candidates: list[GPInstrumentCandidate] = []
    candidate_keys: dict[
        str,
        tuple[int, float, float, float, float, float, float, float, float, float, float],
    ] = {}
    baseline_top_voice: tuple[PhraseNote, ...] | None = None
    for candidate_id in candidate_ids:
        instrument = get_instrument_range(candidate_id)
        expected_offset = None
        if baseline_top_voice is not None:
            expected_offset = instrument.min_midi - base_instrument.min_midi
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
            baseline_top_voice=baseline_top_voice,
            expected_offset=expected_offset,
        )
        candidates.append(candidate)
        candidate_keys[candidate.instrument_id] = sort_key
        if candidate_id == instrument_id and baseline_top_voice is None:
            baseline_top_voice = _top_voice_notes(candidate.span)
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

    if starred_order:
        comparison_ids: list[str] = []
        if instrument_id in starred_order:
            comparison_ids.append(instrument_id)
        for starred in starred_order:
            if starred not in comparison_ids:
                comparison_ids.append(starred)
    else:
        comparison_ids = [instrument_id]
    candidate_by_id = {candidate.instrument_id: candidate for candidate in candidates}
    ranked = tuple(
        sorted(
            (
                candidate_by_id[candidate_id]
                for candidate_id in comparison_ids
                if candidate_id in candidate_by_id
            ),
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
    "_auto_range_programs",
    "_difficulty_sort_key",
    "_melody_shift_penalty",
    "_score_instrument",
    "_evaluate_program_candidate",
]

