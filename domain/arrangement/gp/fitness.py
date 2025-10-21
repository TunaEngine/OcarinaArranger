"""Fitness evaluation helpers for arrangement GP candidates."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from typing import Callable, Iterable, MutableMapping, Sequence

from ..config import GraceSettings
from ..difficulty import DifficultySummary, difficulty_score, summarize_difficulty
from ..phrase import PhraseNote, PhraseSpan
from ..soft_key import InstrumentRange
from .ops import GPPrimitive
from ..melody import isolate_melody


@dataclass(frozen=True)
class FitnessVector:
    """Container describing the weighted objectives for a candidate."""

    playability: float
    fidelity: float
    tessitura: float
    program_size: float

    def as_tuple(self) -> tuple[float, float, float, float]:
        """Return the values in a deterministic ordering."""

        return (self.playability, self.fidelity, self.tessitura, self.program_size)

    def __iter__(self) -> Iterable[float]:
        return iter(self.as_tuple())


@dataclass(frozen=True)
class FitnessObjective:
    """Configuration for a single objective."""

    weight: float = 1.0
    normalizer: Callable[[float], float] | None = None

    def apply(self, value: float) -> float:
        normalized = self.normalizer(value) if self.normalizer else value
        return normalized * self.weight


@dataclass(frozen=True)
class FidelityConfig:
    """Fine-grained tuning for fidelity sub-metrics."""

    contour_weight: float = 0.3
    lcs_weight: float = 0.4
    pitch_weight: float = 0.3
    contour_normalizer: Callable[[float], float] | None = None
    lcs_normalizer: Callable[[float], float] | None = None
    pitch_normalizer: Callable[[float], float] | None = None

    def combine(
        self,
        contour_penalty: float,
        lcs_penalty: float,
        pitch_penalty: float = 0.0,
    ) -> float:
        contour_value = (
            self.contour_normalizer(contour_penalty)
            if self.contour_normalizer
            else contour_penalty
        )
        lcs_value = self.lcs_normalizer(lcs_penalty) if self.lcs_normalizer else lcs_penalty
        pitch_value = (
            self.pitch_normalizer(pitch_penalty)
            if self.pitch_normalizer
            else pitch_penalty
        )

        total_weight = self.contour_weight + self.lcs_weight + self.pitch_weight
        if total_weight <= 0:
            return 0.0
        weighted = (
            (contour_value * self.contour_weight)
            + (lcs_value * self.lcs_weight)
            + (pitch_value * self.pitch_weight)
        )
        return weighted / total_weight


@dataclass(frozen=True)
class FitnessConfig:
    """Configuration hooks controlling normalization and objective weighting."""

    playability: FitnessObjective = field(default_factory=FitnessObjective)
    fidelity: FitnessObjective = field(default_factory=FitnessObjective)
    tessitura: FitnessObjective = field(default_factory=FitnessObjective)
    program_size: FitnessObjective = field(default_factory=FitnessObjective)
    fidelity_components: FidelityConfig = field(default_factory=FidelityConfig)


def _melodic_contour(span: PhraseSpan) -> tuple[int, ...]:
    if len(span.notes) < 2:
        return ()
    contour: list[int] = []
    for prev, current in zip(span.notes, span.notes[1:]):
        if current.midi > prev.midi:
            contour.append(1)
        elif current.midi < prev.midi:
            contour.append(-1)
        else:
            contour.append(0)
    return tuple(contour)


def _contour_similarity(original: PhraseSpan, candidate: PhraseSpan) -> float:
    original_contour = _melodic_contour(original)
    candidate_contour = _melodic_contour(candidate)

    if not original_contour and not candidate_contour:
        return 1.0

    max_length = max(len(original_contour), len(candidate_contour))
    if max_length == 0:
        return 1.0

    matched = sum(
        1 for index in range(min(len(original_contour), len(candidate_contour)))
        if original_contour[index] == candidate_contour[index]
    )
    return matched / max_length


def _longest_common_subsequence_ratio(original: PhraseSpan, candidate: PhraseSpan) -> float:
    original_midis = [note.midi for note in original.notes]
    candidate_midis = [note.midi for note in candidate.notes]

    if not original_midis and not candidate_midis:
        return 1.0

    len_a = len(original_midis)
    len_b = len(candidate_midis)
    if len_a == 0 or len_b == 0:
        return 0.0

    dp = [[0] * (len_b + 1) for _ in range(len_a + 1)]
    for i in range(len_a):
        for j in range(len_b):
            if original_midis[i] == candidate_midis[j]:
                dp[i + 1][j + 1] = dp[i][j] + 1
            else:
                dp[i + 1][j + 1] = max(dp[i][j + 1], dp[i + 1][j])

    lcs_length = dp[len_a][len_b]
    denominator = max(len_a, len_b)
    if denominator == 0:
        return 1.0
    return lcs_length / denominator


def _normalized_tessitura_distance(summary: DifficultySummary, instrument: InstrumentRange) -> float:
    span = max(1.0, float(instrument.span))
    return min(1.0, summary.tessitura_distance / span)


def _pitch_penalty_for_shift(
    original_notes: Sequence[PhraseNote],
    candidate_notes: Sequence[PhraseNote],
    shift: int,
) -> float:
    max_length = max(len(original_notes), len(candidate_notes))
    if max_length == 0:
        return 0.0

    paired_length = min(len(original_notes), len(candidate_notes))
    mismatches = max_length - paired_length
    distance_total = 0

    for source, arranged in zip(original_notes, candidate_notes):
        adjusted = arranged.midi - shift
        if source.midi != adjusted:
            mismatches += 1
        distance_total += abs(source.midi - adjusted)

    mismatch_ratio = mismatches / max_length
    if paired_length == 0:
        distance_ratio = 1.0
    else:
        distance_ratio = min(1.0, distance_total / (12.0 * paired_length))

    return max(mismatch_ratio, distance_ratio)


def pitch_penalty(original: PhraseSpan, candidate: PhraseSpan) -> float:
    if not original.notes and not candidate.notes:
        return 0.0

    original_notes = original.notes
    candidate_notes = candidate.notes
    max_length = max(len(original_notes), len(candidate_notes))
    if max_length == 0:
        return 0.0

    paired_length = min(len(original_notes), len(candidate_notes))
    if paired_length == 0:
        return 1.0

    shift_candidates: set[int] = {0}
    for source, arranged in zip(original_notes, candidate_notes):
        diff = arranged.midi - source.midi
        if diff == 0:
            continue
        aligned_values = {
            int(round(diff / 12.0)) * 12,
            int(math.floor(diff / 12.0)) * 12,
            int(math.ceil(diff / 12.0)) * 12,
        }
        for aligned in aligned_values:
            if aligned != 0:
                shift_candidates.add(aligned)

    penalties = [
        _pitch_penalty_for_shift(original_notes, candidate_notes, shift)
        for shift in shift_candidates
    ]
    return min(penalties)


def _top_voice_span(span: PhraseSpan) -> PhraseSpan:
    if not span.notes:
        return span

    grouped: dict[int, list[PhraseNote]] = {}
    for note in span.notes:
        grouped.setdefault(note.onset, []).append(note)

    top_notes = [
        max(group, key=lambda item: item.midi)
        for _, group in sorted(grouped.items())
    ]
    return span.with_notes(top_notes)


def melody_pitch_penalty(
    original: PhraseSpan,
    candidate: PhraseSpan,
    *,
    beats_per_measure: int = 4,
) -> float:
    """Return a penalty reflecting pitch drift in the isolated melody line."""

    if beats_per_measure <= 0:
        raise ValueError("beats_per_measure must be positive")

    original_isolated = isolate_melody(
        original, beats_per_measure=beats_per_measure
    ).span
    candidate_isolated = isolate_melody(
        candidate, beats_per_measure=beats_per_measure
    ).span

    top_original = _top_voice_span(original)
    top_candidate = _top_voice_span(candidate)
    top_penalty = _pitch_penalty_for_shift(
        top_original.notes,
        top_candidate.notes,
        0,
    )
    if top_penalty == 0.0:
        return 0.0

    isolated_penalty = pitch_penalty(original_isolated, candidate_isolated)
    return max(isolated_penalty, top_penalty)


def _program_parsimony_penalty(
    program: Sequence[GPPrimitive],
    phrase: PhraseSpan,
) -> float:
    if not program:
        return 0.0

    span_counts: MutableMapping[tuple[str, tuple[int, int]], int] = {}
    for operation in program:
        try:
            resolved = operation.span.resolve(phrase)
        except ValueError:
            continue
        key = (operation.span.label, resolved)
        span_counts[key] = span_counts.get(key, 0) + 1

    repeated_penalty = sum(count - 1 for count in span_counts.values() if count > 1)
    return float(len(program) + repeated_penalty)


def compute_fitness(
    *,
    original: PhraseSpan,
    candidate: PhraseSpan,
    instrument: InstrumentRange,
    program: Sequence[GPPrimitive] | None = None,
    difficulty: DifficultySummary | None = None,
    config: FitnessConfig | None = None,
    grace_settings: GraceSettings | None = None,
) -> FitnessVector:
    """Compute the weighted fitness vector for *candidate* relative to *original*."""

    program_values = program or ()
    applied_config = config or FitnessConfig()
    difficulty_summary = difficulty or summarize_difficulty(
        candidate, instrument, grace_settings=grace_settings
    )

    playability_penalty = difficulty_score(
        difficulty_summary, grace_settings=grace_settings
    )
    playability_value = applied_config.playability.apply(playability_penalty)

    contour_similarity = _contour_similarity(original, candidate)
    contour_penalty = 1.0 - contour_similarity
    lcs_ratio = _longest_common_subsequence_ratio(original, candidate)
    lcs_penalty = 1.0 - lcs_ratio
    pitch_penalty_value = pitch_penalty(original, candidate)
    fidelity_penalty = applied_config.fidelity_components.combine(
        contour_penalty,
        lcs_penalty,
        pitch_penalty_value,
    )
    fidelity_value = applied_config.fidelity.apply(fidelity_penalty)

    tessitura_distance = _normalized_tessitura_distance(difficulty_summary, instrument)
    tessitura_value = applied_config.tessitura.apply(tessitura_distance)

    program_size_penalty = _program_parsimony_penalty(program_values, original)
    program_size_value = applied_config.program_size.apply(program_size_penalty)

    return FitnessVector(
        playability=round(playability_value, 12),
        fidelity=round(fidelity_value, 12),
        tessitura=round(tessitura_value, 12),
        program_size=round(program_size_value, 12),
    )


__all__ = [
    "FitnessConfig",
    "FitnessObjective",
    "FitnessVector",
    "FidelityConfig",
    "melody_pitch_penalty",
    "pitch_penalty",
    "compute_fitness",
]
