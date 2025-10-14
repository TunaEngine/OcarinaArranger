"""Scoring and ranking helpers for GP arrangement strategies."""

from __future__ import annotations

from collections import Counter
from typing import Sequence, Tuple

from domain.arrangement.melody import isolate_melody
from domain.arrangement.phrase import PhraseNote, PhraseSpan

from .ops import GlobalTranspose
from .strategy_types import GPInstrumentCandidate
from .session_logging import IndividualSummary


FIDELITY_WEIGHT = 3.0
RANGE_CLAMP_PENALTY = 1000.0
RANGE_CLAMP_MELODY_BIAS = 1.0
MELODY_SHIFT_WEIGHT = 2.0


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
    magnitude_penalty = min(1.0, magnitude_total / (12.0 * paired_length))

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
) -> tuple[int, float, float, float, float, float, float, float, float, float, float]:
    """Return a tuple that ranks candidates by melodic fidelity before difficulty."""

    difficulty = candidate.difficulty
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
            range_penalty = RANGE_CLAMP_PENALTY * 2
        else:
            # Pure global transpositions that keep the melody intact often
            # still need to clamp sustained pedals.  Allow them to compete on
            # melodic fidelity by avoiding the large penalty while leaving a
            # smaller bias in the melodic score below.
            range_penalty = 0.0

    fidelity_penalty = candidate.fitness.fidelity
    program_length = len(candidate.program)
    program_complexity = sum(
        0 if isinstance(operation, GlobalTranspose) else 1
        for operation in candidate.program
    )
    transpose_magnitude = None
    transpose_octave_bias = 0
    transpose_is_non_octave = False
    for operation in candidate.program:
        if isinstance(operation, GlobalTranspose):
            magnitude = abs(operation.semitones)
            transpose_magnitude = (
                magnitude
                if transpose_magnitude is None or magnitude < transpose_magnitude
                else transpose_magnitude
            )
            if magnitude % 12 != 0:
                transpose_is_non_octave = True
                if transpose_octave_bias == 0:
                    transpose_octave_bias = 1
    if transpose_magnitude is None:
        transpose_key = 0.0 if program_length == 0 else 120.0
        if program_length > 0:
            transpose_octave_bias = 1
    else:
        transpose_key = float(transpose_magnitude)
    importance = max(1.0, fidelity_importance)

    melody_penalty = candidate.melody_penalty
    shift_penalty = candidate.melody_shift_penalty
    has_shift_drift = 1 if shift_penalty > 1e-9 else 0
    melody_weight = max(1.0, melody_importance)
    if len(candidate.program) > 0 and baseline_melody is not None:
        melody_diff = melody_penalty - baseline_melody
        if melody_diff > 0:
            melody_factor = melody_weight * (FIDELITY_WEIGHT if has_range_clamp else 1.0)
            melody_penalty = baseline_melody + melody_diff * melody_factor
    melody_total = melody_penalty
    if shift_penalty > 0:
        melody_total += shift_penalty * melody_weight * MELODY_SHIFT_WEIGHT
    if has_range_clamp:
        melody_total += RANGE_CLAMP_MELODY_BIAS * melody_weight
    if transpose_is_non_octave and has_range_clamp:
        # Strongly discourage non-octave global transpositions so the arranger
        # favours the nearest uniform octave shift even when the raw melody
        # penalty slightly prefers an uneven adjustment.
        melody_total += melody_weight * MELODY_SHIFT_WEIGHT
    melody_key = round(melody_total, 12)
    melody_shift_value = shift_penalty
    if transpose_is_non_octave and has_range_clamp:
        melody_shift_value += melody_weight * MELODY_SHIFT_WEIGHT
    melody_shift_key = round(melody_shift_value, 12)

    if program_length > 0:
        if baseline_fidelity is not None:
            diff = fidelity_penalty - baseline_fidelity
            if diff > 0:
                fidelity_penalty = baseline_fidelity + diff * importance * FIDELITY_WEIGHT
        else:
            fidelity_penalty = fidelity_penalty * importance * FIDELITY_WEIGHT

    # Prioritise melodic fidelity ahead of range clamps and the other
    # difficulty heuristics so larger instruments prefer solutions that keep
    # the phrase intact whenever possible while still favouring un-clamped
    # phrases when the melodic penalty is comparable.
    return (
        has_shift_drift,
        melody_shift_key,
        melody_key,
        transpose_octave_bias,
        transpose_key,
        range_key,
        round(fidelity_penalty, 12),
        program_complexity,
        program_length,
        difficulty.hard_and_very_hard + range_penalty,
        difficulty.medium,
        difficulty.tessitura_distance,
        candidate.fitness.playability,
    )


__all__ = [
    "FIDELITY_WEIGHT",
    "MELODY_SHIFT_WEIGHT",
    "RANGE_CLAMP_MELODY_BIAS",
    "RANGE_CLAMP_PENALTY",
    "_difficulty_sort_key",
    "_melody_shift_penalty",
    "_summarize_individual",
]
