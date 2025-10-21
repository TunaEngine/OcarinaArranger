"""Scoring and ranking helpers for GP arrangement strategies."""

from __future__ import annotations

from collections import Counter
from typing import Sequence, Tuple

from domain.arrangement.config import GraceSettings
from domain.arrangement.melody import isolate_melody
from domain.arrangement.phrase import PhraseNote, PhraseSpan

from .ops import GlobalTranspose, LocalOctave, SimplifyRhythm
from .penalties import ScoringPenalties
from .strategy_types import GPInstrumentCandidate
from .session_logging import IndividualSummary


FIDELITY_WEIGHT = 3.0
RANGE_CLAMP_PENALTY = 1000.0
RANGE_CLAMP_MELODY_BIAS = 1.0
MELODY_SHIFT_WEIGHT = 2.0

SortKey = tuple[int, float, float, float, float, float, float, float, float, float, float, float, float]


def _top_voice_notes(span: PhraseSpan) -> Tuple[PhraseNote, ...]:
    if not span.notes:
        return tuple()

    grouped: dict[int, list[PhraseNote]] = {}
    for note in span.notes:
        grouped.setdefault(note.onset, []).append(note)

    top_voice = [
        max(group, key=lambda item: item.midi)
        for _, group in sorted(grouped.items())
    ]
    return tuple(top_voice)


def _shift_drift_penalty(
    original_notes: Sequence[PhraseNote],
    candidate_notes: Sequence[PhraseNote],
) -> float:
    max_length = max(len(original_notes), len(candidate_notes))
    if max_length == 0:
        return 0.0

    paired_length = min(len(original_notes), len(candidate_notes))
    if paired_length == 0:
        return 1.0

    differences = [
        candidate_notes[index].midi - original_notes[index].midi
        for index in range(paired_length)
    ]

    mode_shift, mode_count = Counter(differences).most_common(1)[0]
    consistency_penalty = 1.0 - (mode_count / paired_length)

    magnitude_total = sum(
        abs(shift - mode_shift) for shift in differences if shift != mode_shift
    )
    mismatch_count = sum(1 for shift in differences if shift != mode_shift)
    if mismatch_count:
        magnitude_penalty = min(1.0, magnitude_total / (12.0 * mismatch_count))
    else:
        magnitude_penalty = 0.0

    length_penalty = (max_length - paired_length) / max_length

    return max(consistency_penalty, magnitude_penalty, length_penalty)


def _melody_shift_penalty(
    original: PhraseSpan,
    candidate: PhraseSpan,
    *,
    beats_per_measure: int = 4,
) -> float:
    """Return a penalty for inconsistent octave drift in the melody line."""

    if beats_per_measure <= 0:
        raise ValueError("beats_per_measure must be positive")

    original_isolated = isolate_melody(
        original, beats_per_measure=beats_per_measure
    ).span
    candidate_isolated = isolate_melody(
        candidate, beats_per_measure=beats_per_measure
    ).span

    melody_penalty = _shift_drift_penalty(
        original_isolated.notes,
        candidate_isolated.notes,
    )

    top_original = _top_voice_notes(original)
    top_candidate = _top_voice_notes(candidate)
    top_penalty = _shift_drift_penalty(top_original, top_candidate)

    penalty = max(melody_penalty, top_penalty)

    if top_penalty < melody_penalty:
        def _note_bounds(notes: Sequence[PhraseNote]) -> tuple[int, int] | None:
            if not notes:
                return None
            midis = [note.midi for note in notes]
            return min(midis), max(midis)

        def _is_submelody(
            primary_bounds: tuple[int, int] | None,
            top_bounds: tuple[int, int] | None,
        ) -> bool:
            if primary_bounds is None or top_bounds is None:
                return False
            _, primary_max = primary_bounds
            _, top_max = top_bounds
            return primary_max <= top_max - 2

        original_bounds = _note_bounds(original_isolated.notes)
        candidate_bounds = _note_bounds(candidate_isolated.notes)
        top_original_bounds = _note_bounds(top_original)
        top_candidate_bounds = _note_bounds(top_candidate)

        if _is_submelody(original_bounds, top_original_bounds) and _is_submelody(
            candidate_bounds, top_candidate_bounds
        ):
            penalty = top_penalty

    return round(penalty, 12)


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
    penalties: ScoringPenalties | None = None,
    grace_settings: GraceSettings | None = None,
) -> SortKey:
    """Return a tuple that ranks candidates by melodic fidelity before difficulty."""

    penalties = penalties or ScoringPenalties()
    difficulty = candidate.difficulty
    try:
        fast_switch_weight = max(
            0.0,
            float(getattr(grace_settings, "fast_windway_switch_weight", 0.0)),
        )
    except (TypeError, ValueError, AttributeError):  # pragma: no cover - defensive
        fast_switch_weight = 0.0
    has_range_clamp = any(
        event.reason_code == "range-clamp" for event in candidate.explanations
    )
    range_key = 1 if has_range_clamp else 0
    range_penalty = 0.0
    if has_range_clamp and len(candidate.program) > 0:
        has_non_global = any(
            not isinstance(operation, GlobalTranspose)
            for operation in candidate.program
        )
        if has_non_global:
            # Mixed local edits that still require clamping represent more
            # aggressive alterations, so they should remain heavily
            # penalised compared to register-faithful alternatives.
            range_penalty = penalties.range_clamp_penalty * 2
        else:
            # Pure global transpositions that keep the melody intact often
            # still need to clamp sustained pedals.  Allow them to compete on
            # melodic fidelity by avoiding the large penalty while leaving a
            # smaller bias in the melodic score below.
            range_penalty = 0.0

    fidelity_penalty = candidate.fitness.fidelity
    program_length = len(candidate.program)
    effective_program_length = 0
    zero_transpose_count = 0
    base_complexity = sum(
        0
        if isinstance(operation, GlobalTranspose)
        and getattr(operation, "semitones", 0)
        in (0, 0.0)
        else 0
        if isinstance(operation, GlobalTranspose)
        else 1
        for operation in candidate.program
    )
    simplify_count = sum(
        1 for operation in candidate.program if isinstance(operation, SimplifyRhythm)
    )
    rhythm_weight = max(0.0, penalties.rhythm_simplify_weight)
    program_complexity = base_complexity + simplify_count * (rhythm_weight - 1.0)
    if simplify_count:
        program_complexity = max(0.0, round(program_complexity, 6))
    apply_transpose_bias = penalties.melody_shift_weight >= 1.0
    transpose_magnitude = None
    transpose_octave_bias = 0
    transpose_is_non_octave = False
    local_octave_shifts: list[int] = []
    local_octave_ranges: list[tuple[int, int | None, int | None]] = []
    full_span_local_octave: list[int] = []
    has_global_transpose = False
    for operation in candidate.program:
        if isinstance(operation, GlobalTranspose):
            magnitude_raw = getattr(operation, "semitones", 0)
            try:
                magnitude = abs(int(magnitude_raw))
            except (TypeError, ValueError):  # pragma: no cover - defensive guard
                magnitude = 0
            if magnitude == 0:
                zero_transpose_count += 1
                continue
            has_global_transpose = True
            effective_program_length += 1
            transpose_magnitude = (
                magnitude
                if transpose_magnitude is None or magnitude < transpose_magnitude
                else transpose_magnitude
            )
            if magnitude % 12 != 0:
                transpose_is_non_octave = True
                if apply_transpose_bias and transpose_octave_bias == 0:
                    transpose_octave_bias = 1
        elif isinstance(operation, LocalOctave):
            if operation.octaves:
                effective_program_length += 1
                shift_value = int(operation.octaves)
                local_octave_shifts.append(shift_value)
                start = getattr(operation.span, "start_onset", None)
                end = getattr(operation.span, "end_onset", None)
                local_octave_ranges.append((shift_value, start, end))
                if shift_value and (start in (None, 0)):
                    full_span = False
                    if end is None:
                        full_span = True
                    else:
                        try:
                            full_span = int(end) >= candidate.span.total_duration
                        except (TypeError, ValueError):
                            full_span = False
                    if full_span:
                        full_span_local_octave.append(abs(shift_value))
        elif isinstance(operation, SimplifyRhythm):
            effective_program_length += 1
        else:
            effective_program_length += 1
    if transpose_magnitude is None:
        transpose_key = (
            0.0 if effective_program_length == 0 or not apply_transpose_bias else 120.0
        )
        if effective_program_length > 0 and apply_transpose_bias:
            transpose_octave_bias = 1
    else:
        transpose_key = float(transpose_magnitude) if apply_transpose_bias else 0.0
    importance = max(1.0, fidelity_importance)

    melody_penalty = candidate.melody_penalty
    shift_penalty = candidate.melody_shift_penalty
    has_shift_drift = 1 if shift_penalty > 1e-9 else 0
    melody_weight = max(1.0, melody_importance)
    if len(candidate.program) > 0 and baseline_melody is not None:
        melody_diff = melody_penalty - baseline_melody
        if melody_diff > 0:
            melody_factor = melody_weight * (
                penalties.fidelity_weight if has_range_clamp else 1.0
            )
            melody_penalty = baseline_melody + melody_diff * melody_factor
    melody_total = melody_penalty
    if shift_penalty > 0:
        melody_total += shift_penalty * melody_weight * penalties.melody_shift_weight
    melody_shift_value = shift_penalty
    if has_range_clamp:
        melody_total += penalties.range_clamp_melody_bias * melody_weight
        if effective_program_length == 0 and shift_penalty >= 0.5:
            clamp_bias = melody_weight * penalties.range_clamp_penalty * max(1.0, shift_penalty)
            melody_total += clamp_bias
            melody_shift_value += clamp_bias
            has_shift_drift = max(has_shift_drift, 2)
        if candidate.instrument is not None:
            top_voice = _top_voice_notes(candidate.span)
            if top_voice:
                floor_hits = sum(
                    1 for note in top_voice if note.midi <= candidate.instrument.min_midi
                )
                ceiling_hits = sum(
                    1 for note in top_voice if note.midi >= candidate.instrument.max_midi
                )
                if floor_hits or ceiling_hits:
                    total_notes = len(top_voice)
                    # Weight lower-bound clashes more heavily than upper-bound
                    # clamps so pure transpositions favour staying above the
                    # floor instead of dimming the melody near the instrument's
                    # base notes.
                    floor_weight = 2.0 if has_global_transpose else 1.5
                    ceiling_weight = 1.0
                    weighted_hits = floor_hits * floor_weight + ceiling_hits * ceiling_weight
                    hit_ratio = weighted_hits / total_notes
                    if (floor_hits + ceiling_hits) >= 3 or hit_ratio >= 0.05:
                        base_factor = shift_penalty + hit_ratio * penalties.melody_shift_weight
                        boundary_bias = melody_weight * penalties.range_clamp_penalty * (
                            1.0 + base_factor
                        )
                        drift_rank = 3 if not has_global_transpose else 2
                        if has_global_transpose and shift_penalty <= 1e-9:
                            boundary_bias *= 0.75
                        elif effective_program_length == 0:
                            # Baseline (identity) candidates rely entirely on range
                            # enforcement to stay playable. They should not be
                            # punished as heavily as modified programs when the
                            # clamp merely trims a handful of out-of-range notes,
                            # otherwise we'll incorrectly prefer octave shifts that
                            # distort the melody shape.
                            boundary_bias *= 0.25
                            if shift_penalty < 1.0:
                                drift_rank = 1
                            else:
                                drift_rank = max(1, min(drift_rank, 2))
                        melody_total += boundary_bias
                        melody_shift_value += boundary_bias
                        has_shift_drift = max(has_shift_drift, drift_rank)
        if zero_transpose_count:
            zero_bias = melody_weight * penalties.range_clamp_penalty * max(
                1.0, shift_penalty + zero_transpose_count
            )
            melody_total += zero_bias
            melody_shift_value += zero_bias
            has_shift_drift = max(has_shift_drift, 2)
    if apply_transpose_bias and transpose_is_non_octave and has_range_clamp:
        # Strongly discourage non-octave global transpositions so the arranger
        # favours the nearest uniform octave shift even when the raw melody
        # penalty slightly prefers an uneven adjustment.
        melody_total += melody_weight * penalties.melody_shift_weight
    elif not apply_transpose_bias and transpose_is_non_octave:
        melody_total = max(
            0.0,
            melody_total - melody_weight * (1.0 - penalties.melody_shift_weight),
        )
    if simplify_count:
        delta = simplify_count * abs(rhythm_weight - 1.0)
        if rhythm_weight >= 1.0:
            melody_total += delta
        else:
            melody_total = max(0.0, melody_total - delta)

    if apply_transpose_bias and transpose_is_non_octave and has_range_clamp:
        melody_shift_value += melody_weight * penalties.melody_shift_weight

    has_conflicting_local_octaves = local_octave_shifts and (
        any(shift > 0 for shift in local_octave_shifts)
        and any(shift < 0 for shift in local_octave_shifts)
    )
    if has_conflicting_local_octaves:
        conflict_weight = melody_weight * max(1.0, penalties.melody_shift_weight)
        clamp_scale = max(24.0, penalties.range_clamp_penalty * 24.0)
        extent = max(1, max(abs(shift) for shift in local_octave_shifts))
        conflict_bias = conflict_weight * clamp_scale * extent
        melody_total += conflict_bias
        melody_shift_value += conflict_bias
        has_shift_drift = max(has_shift_drift, 2)
    elif local_octave_ranges:
        total_duration = candidate.span.total_duration
        positive_spans = [
            (start if start is not None else 0, end)
            for shift, start, end in local_octave_ranges
            if shift > 0
        ]
        negative_spans = [
            (start, end if end is not None else total_duration)
            for shift, start, end in local_octave_ranges
            if shift < 0
        ]
        if positive_spans:
            min_start = min(start for start, _ in positive_spans)
            if min_start > 0:
                coverage_bias = melody_weight * penalties.range_clamp_penalty
                melody_total += coverage_bias
                melody_shift_value += coverage_bias
                has_shift_drift = max(has_shift_drift, 2)
        if negative_spans:
            max_end = max(end for _, end in negative_spans)
            if max_end < total_duration:
                coverage_bias = melody_weight * penalties.range_clamp_penalty
                melody_total += coverage_bias
                melody_shift_value += coverage_bias
                has_shift_drift = max(has_shift_drift, 2)

    excess_octave_shift = 0
    if transpose_magnitude is not None and transpose_magnitude % 12 == 0:
        excess_octave_shift = max(0, (transpose_magnitude // 12) - 1)
    if full_span_local_octave:
        excess_octave_shift = max(excess_octave_shift, max(full_span_local_octave) - 1)
    if excess_octave_shift > 0:
        octave_bias = melody_weight * penalties.range_clamp_penalty * excess_octave_shift
        if has_range_clamp:
            octave_bias *= 1.0 + (penalties.melody_shift_weight * 0.25)
        melody_total += octave_bias
        melody_shift_value += octave_bias
        if full_span_local_octave:
            has_shift_drift = max(has_shift_drift, 3)
        else:
            has_shift_drift = max(has_shift_drift, 2)

    if transpose_magnitude is not None and candidate.instrument is not None:
        instrument_span = max(
            1,
            int(candidate.instrument.max_midi) - int(candidate.instrument.min_midi),
        )
        if transpose_magnitude > instrument_span:
            overshoot = transpose_magnitude - instrument_span
            overshoot_scale = overshoot / instrument_span
            overshoot_penalty = melody_weight * penalties.range_clamp_penalty * (
                1.0 + overshoot_scale * penalties.melody_shift_weight
            )
            melody_total += overshoot_penalty
            melody_shift_value += overshoot_penalty
            has_shift_drift = max(has_shift_drift, 2)

    melody_key = round(melody_total, 12)
    melody_shift_key = round(melody_shift_value, 12)

    if effective_program_length > 0:
        if baseline_fidelity is not None:
            diff = fidelity_penalty - baseline_fidelity
            if diff > 0:
                fidelity_penalty = baseline_fidelity + diff * importance * penalties.fidelity_weight
        else:
            fidelity_penalty = fidelity_penalty * importance * penalties.fidelity_weight

    # Prioritise melodic fidelity ahead of range clamps and the other
    # difficulty heuristics so larger instruments prefer solutions that keep
    # the phrase intact whenever possible while still favouring un-clamped
    # phrases when the melodic penalty is comparable.
    fast_switch_key = round(
        difficulty.fast_windway_switch_exposure * fast_switch_weight, 12
    )
    return (
        has_shift_drift,
        melody_shift_key,
        fast_switch_key,
        melody_key,
        transpose_octave_bias,
        transpose_key,
        range_key,
        round(fidelity_penalty, 12),
        program_complexity,
        effective_program_length,
        difficulty.hard_and_very_hard + range_penalty,
        difficulty.medium,
        difficulty.tessitura_distance,
        candidate.fitness.playability,
    )


__all__ = [
    "FIDELITY_WEIGHT",
    "MELODY_SHIFT_WEIGHT",
    "ScoringPenalties",
    "RANGE_CLAMP_MELODY_BIAS",
    "RANGE_CLAMP_PENALTY",
    "SortKey",
    "_difficulty_sort_key",
    "_melody_shift_penalty",
    "_summarize_individual",
]
