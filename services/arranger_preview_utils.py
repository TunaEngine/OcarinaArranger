"""Utility helpers shared by arranger preview services."""

from __future__ import annotations

from typing import Callable, Iterable, Mapping, Sequence

from domain.arrangement.api import summarize_difficulty
from domain.arrangement.config import register_instrument_range
from domain.arrangement.phrase import PhraseSpan
from domain.arrangement.salvage import SalvageBudgets
from domain.arrangement.soft_key import InstrumentRange, InstrumentWindwayRange
from ocarina_tools.events import NoteEvent

from ocarina_tools.pitch import parse_note_name

from viewmodels.arranger_models import (
    ArrangerBudgetSettings,
    ArrangerEditBreakdown,
    ArrangerExplanationRow,
    ArrangerInstrumentSummary,
    ArrangerResultSummary,
    ArrangerTelemetryHint,
)


DEFAULT_DIFFICULTY_THRESHOLD = 0.65
DEFAULT_INSTRUMENT_MIN = 60
DEFAULT_INSTRUMENT_MAX = 84


def _instrument_summary(
    arrangement,
    name_map: Mapping[str, str],
    chosen_id: str,
    *,
    transposition_offset: int = 0,
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
        transposition=arrangement.result.transposition + transposition_offset,
        is_winner=arrangement.instrument_id == chosen_id,
    )


def _result_summary(
    span,
    arrangement,
    name_map: Mapping[str, str],
    *,
    threshold: float,
    transposition_offset: int = 0,
) -> ArrangerResultSummary:
    easy, medium, hard, very_hard, tessitura, _ = _normalize_difficulty(arrangement.difficulty)
    starting_summary = summarize_difficulty(span, arrangement.instrument)
    start_score = _difficulty_score(starting_summary)
    final_score = _difficulty_score(arrangement.difficulty)
    salvage = arrangement.result.salvage
    return ArrangerResultSummary(
        instrument_id=arrangement.instrument_id,
        instrument_name=name_map.get(arrangement.instrument_id, arrangement.instrument_id),
        transposition=arrangement.result.transposition + transposition_offset,
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


def _instrument_range_for(
    instrument_id: str,
    resolver: Callable[[str], object],
    *,
    preferred_override: tuple[str | None, str | None] | None = None,
) -> InstrumentRange | None:
    instrument_id = instrument_id.strip()
    if not instrument_id:
        return None
    try:
        spec = resolver(instrument_id)
    except Exception:
        return None
    instrument_range = _instrument_range_from_spec(spec, preferred_override=preferred_override)
    register_instrument_range(instrument_id, instrument_range)
    return instrument_range


def _auto_register_shift(
    span: PhraseSpan,
    instrument: InstrumentRange,
    *,
    headroom: int = 2,
) -> int:
    """Return a uniform semitone shift that keeps ``span`` comfortably in range.

    The helper nudges the phrase away from the range edges so the GP arranger
    avoids resorting to octave clamps that introduce large melodic jumps.  When
    the phrase already sits comfortably inside ``instrument`` the function
    returns ``0``.
    """

    if not getattr(span, "notes", None):
        return 0

    lowest = min(note.midi for note in span.notes)
    highest = max(note.midi for note in span.notes)

    range_lower = int(instrument.min_midi) - lowest
    range_upper = int(instrument.max_midi) - highest
    if range_lower > range_upper:
        return 0

    def _nearest_to_zero(lower: int, upper: int) -> int | None:
        if lower > upper:
            return None
        if lower <= 0 <= upper:
            return 0
        if upper < 0:
            return upper
        return lower

    if headroom > 0:
        minimum_allowed = int(instrument.min_midi) + headroom
        maximum_allowed = int(instrument.max_midi) - headroom
        if minimum_allowed <= maximum_allowed:
            headroom_lower = minimum_allowed - lowest
            headroom_upper = maximum_allowed - highest
            candidate = _nearest_to_zero(
                max(range_lower, headroom_lower),
                min(range_upper, headroom_upper),
            )
            if candidate is not None:
                return candidate

    fallback = _nearest_to_zero(range_lower, range_upper)
    return fallback or 0


def _instrument_range_from_spec(
    spec,
    *,
    preferred_override: tuple[str | None, str | None] | None = None,
) -> InstrumentRange:
    def _parse(note: str, fallback: int | None = None) -> int | None:
        if note:
            try:
                return parse_note_name(note)
            except ValueError:
                return fallback
        return fallback

    min_midi = _parse(spec.candidate_range_min, DEFAULT_INSTRUMENT_MIN)
    max_midi = _parse(spec.candidate_range_max, DEFAULT_INSTRUMENT_MAX)
    pref_min = _parse(spec.preferred_range_min, min_midi)
    pref_max = _parse(spec.preferred_range_max, max_midi)

    if min_midi is None or max_midi is None:
        min_midi = DEFAULT_INSTRUMENT_MIN
        max_midi = DEFAULT_INSTRUMENT_MAX
    if min_midi > max_midi:
        min_midi, max_midi = max_midi, min_midi

    if pref_min is None:
        pref_min = min_midi
    if pref_max is None:
        pref_max = max_midi
    if pref_min > pref_max:
        pref_min, pref_max = pref_max, pref_min

    if preferred_override is not None:
        override_min_raw, override_max_raw = preferred_override

        override_min = _parse(override_min_raw, pref_min)
        override_max = _parse(override_max_raw, pref_max)

        if override_min is not None or override_max is not None:
            if override_min is None:
                override_min = pref_min
            if override_max is None:
                override_max = pref_max

            # Fallback to instrument defaults when overrides remain undefined.
            if override_min is None:
                override_min = min_midi
            if override_max is None:
                override_max = max_midi

            override_min = max(min_midi, min(max_midi, override_min))
            override_max = max(min_midi, min(max_midi, override_max))

            if override_min > override_max:
                override_min, override_max = override_max, override_min

            min_midi = override_min
            max_midi = override_max
            pref_min = override_min
            pref_max = override_max

    center = (pref_min + pref_max) / 2.0 if pref_min is not None and pref_max is not None else None

    windway_ids: tuple[str, ...] = tuple(getattr(windway, "identifier", "") for windway in getattr(spec, "windways", ()))
    hole_count = len(getattr(spec, "holes", ()))
    windway_count = len(windway_ids)
    windway_map: dict[int, set[int]] = {}
    if windway_count:
        for note_name, pattern in getattr(spec, "note_map", {}).items():
            midi = _parse(note_name)
            if midi is None:
                continue
            sequence = list(pattern)
            total_required = hole_count + windway_count
            if len(sequence) < total_required:
                sequence.extend([0] * (total_required - len(sequence)))
            indices = []
            for offset in range(windway_count):
                value = sequence[hole_count + offset]
                try:
                    active = int(value) > 0
                except (TypeError, ValueError):
                    active = False
                if active:
                    indices.append(offset)
            if not indices:
                continue
            bucket = windway_map.setdefault(midi, set())
            bucket.update(indices)

    assignments = {midi: tuple(sorted(indices)) for midi, indices in windway_map.items()}
    return InstrumentWindwayRange(
        min_midi=min_midi,
        max_midi=max_midi,
        comfort_center=center,
        windway_ids=windway_ids,
        windway_map=assignments,
    )


def _normalize_difficulty(difficulty) -> tuple[float, float, float, float, float, float]:
    total = difficulty.easy + difficulty.medium + difficulty.hard + difficulty.very_hard
    if total <= 0:
        return (0.0, 0.0, 0.0, 0.0, float(difficulty.tessitura_distance), 0.0)
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
    "DEFAULT_DIFFICULTY_THRESHOLD",
    "DEFAULT_INSTRUMENT_MAX",
    "DEFAULT_INSTRUMENT_MIN",
    "_instrument_summary",
    "_result_summary",
    "_instrument_name_map",
    "_first_program",
    "_instrument_range_for",
    "_normalize_difficulty",
    "_difficulty_score",
    "_edit_breakdown",
    "_explanations_from",
    "_telemetry_from",
    "_to_salvage_budgets",
    "_normalize_instrument_id",
]
