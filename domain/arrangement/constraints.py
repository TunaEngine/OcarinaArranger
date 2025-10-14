from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Mapping, Tuple

from .micro_edits import drop_ornamental_eighth
from .phrase import PhraseNote, PhraseSpan


@dataclass(frozen=True)
class TempoContext:
    bpm: float
    pulses_per_quarter: int

    def __post_init__(self) -> None:
        if self.bpm <= 0:
            raise ValueError("bpm must be positive")
        if self.pulses_per_quarter <= 0:
            raise ValueError("pulses_per_quarter must be positive")

    def seconds_for_pulses(self, pulses: int) -> float:
        if pulses <= 0:
            return 0.0
        quarter_seconds = 60.0 / self.bpm
        return (pulses / self.pulses_per_quarter) * quarter_seconds

    def seconds_between(self, start: int, end: int) -> float:
        if end <= start:
            return 0.0
        return self.seconds_for_pulses(end - start)


@dataclass(frozen=True)
class AlternativeFingering:
    """Descriptor for an alternate fingering used to ease difficult passages."""

    shape: str
    ease: float
    intonation: float

    def __post_init__(self) -> None:
        if not self.shape:
            raise ValueError("shape must be a non-empty string")
        if self.ease < 0:
            raise ValueError("ease must be non-negative")
        if not (0.0 <= self.intonation <= 1.0):
            raise ValueError("intonation must be in the [0, 1] range")


@dataclass(frozen=True)
class SubholePairLimit:
    """Per-subhole transition metadata describing allowable frequency."""

    max_hz: float
    ease: float

    def __post_init__(self) -> None:
        if self.max_hz <= 0:
            raise ValueError("max_hz must be positive")
        if self.ease < 0:
            raise ValueError("ease must be non-negative")


@dataclass(frozen=True)
class SubholeConstraintSettings:
    """Instrument-specific limits for subhole usage and alternate fingerings."""

    max_changes_per_second: float = 6.0
    max_subhole_changes_per_second: float = 4.0
    pair_limits: Mapping[FrozenSet[int], SubholePairLimit] = field(default_factory=dict)
    alternate_fingerings: Mapping[int, Tuple[AlternativeFingering, ...]] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        normalized_pairs: Dict[FrozenSet[int], SubholePairLimit] = {}
        for pair, limit in self.pair_limits.items():
            normalized_pair = frozenset(pair)
            if len(normalized_pair) != 2:
                raise ValueError("subhole pair must contain exactly two distinct pitches")
            if not isinstance(limit, SubholePairLimit):
                raise TypeError("pair_limits values must be SubholePairLimit instances")
            normalized_pairs[normalized_pair] = limit
        object.__setattr__(self, "pair_limits", normalized_pairs)

        alt_map: Dict[int, Tuple[AlternativeFingering, ...]] = {}
        for pitch, fingerings in self.alternate_fingerings.items():
            normalized_pitch = int(pitch)
            tupled = tuple(fingerings)
            for fingering in tupled:
                if not isinstance(fingering, AlternativeFingering):
                    raise TypeError(
                        "alternate_fingerings values must be AlternativeFingering instances"
                    )
            alt_map[normalized_pitch] = tupled
        object.__setattr__(self, "alternate_fingerings", alt_map)

        subhole_pitches: FrozenSet[int] = frozenset(
            pitch for pair in normalized_pairs for pitch in pair
        )
        object.__setattr__(self, "_subhole_pitches", subhole_pitches)

        if self.max_changes_per_second <= 0:
            raise ValueError("max_changes_per_second must be positive")
        if self.max_subhole_changes_per_second <= 0:
            raise ValueError("max_subhole_changes_per_second must be positive")

    @property
    def subhole_pitches(self) -> FrozenSet[int]:
        return self._subhole_pitches


@dataclass(frozen=True)
class SubholeSpeedMetrics:
    changes_per_second: float
    subhole_changes_per_second: float
    span_seconds: float
    pair_rates: Tuple[Tuple[FrozenSet[int], float], ...] = ()


@dataclass(frozen=True)
class SubholeSpeedResult:
    span: PhraseSpan
    metrics: SubholeSpeedMetrics
    edits_applied: Tuple[str, ...]


def _is_subhole_note(note: PhraseNote, settings: SubholeConstraintSettings) -> bool:
    if "subhole" in note.tags:
        return True
    return note.midi in settings.subhole_pitches


def calculate_subhole_speed(
    span: PhraseSpan, tempo: TempoContext, settings: SubholeConstraintSettings
) -> SubholeSpeedMetrics:
    notes = span.notes
    if len(notes) <= 1:
        return SubholeSpeedMetrics(0.0, 0.0, 0.0, ())

    span_seconds = tempo.seconds_for_pulses(span.total_duration)
    if span_seconds <= 0:
        return SubholeSpeedMetrics(0.0, 0.0, 0.0, ())

    transitions = max(0, len(notes) - 1)
    changes_per_second = transitions / span_seconds

    subhole_transitions = 0
    pair_counts: Dict[FrozenSet[int], int] = {}
    tagged_transitions = 0
    for current, nxt in zip(notes, notes[1:]):
        pair = frozenset((current.midi, nxt.midi))
        if pair in settings.pair_limits:
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
        elif _is_subhole_note(current, settings) or _is_subhole_note(nxt, settings):
            tagged_transitions += 1

    subhole_transitions = tagged_transitions + sum(pair_counts.values())
    subhole_changes_per_second = subhole_transitions / span_seconds if span_seconds else 0.0

    pair_rates: Tuple[Tuple[FrozenSet[int], float], ...] = tuple(
        (pair, count / span_seconds)
        for pair, count in pair_counts.items()
        if span_seconds > 0
    )

    return SubholeSpeedMetrics(
        changes_per_second,
        subhole_changes_per_second,
        span_seconds,
        pair_rates,
    )


def _suggest_alternative_fingering(
    violating_pairs: Tuple[FrozenSet[int], ...],
    settings: SubholeConstraintSettings,
) -> Tuple[int, AlternativeFingering] | None:
    for pair in violating_pairs:
        limit = settings.pair_limits.get(pair)
        if limit is None:
            continue
        for pitch in pair:
            for fingering in settings.alternate_fingerings.get(int(pitch), ()):  # pragma: no branch
                if fingering.ease <= limit.ease:
                    return int(pitch), fingering
    return None


def enforce_subhole_and_speed(
    span: PhraseSpan,
    tempo: TempoContext,
    settings: SubholeConstraintSettings,
    *,
    max_iterations: int = 4,
) -> SubholeSpeedResult:
    current = span
    edits: list[str] = []

    for _ in range(max_iterations):
        metrics = calculate_subhole_speed(current, tempo, settings)
        violating_pairs: Tuple[FrozenSet[int], ...] = tuple(
            pair
            for pair, rate in metrics.pair_rates
            if rate > settings.pair_limits[pair].max_hz
        )
        within_limits = (
            metrics.changes_per_second <= settings.max_changes_per_second
            and metrics.subhole_changes_per_second <= settings.max_subhole_changes_per_second
            and not violating_pairs
        )
        if within_limits:
            return SubholeSpeedResult(current, metrics, tuple(edits))

        if violating_pairs:
            updated = drop_ornamental_eighth(current)
            if updated != current:
                edits.append("drop-ornamental")
                current = updated
                continue

            suggestion = _suggest_alternative_fingering(violating_pairs, settings)
            if suggestion is not None:
                pitch, fingering = suggestion
                edits.append(f"alt-fingering:{pitch}:{fingering.shape}")
                return SubholeSpeedResult(current, metrics, tuple(edits))

        updated = drop_ornamental_eighth(current)
        if updated == current:
            return SubholeSpeedResult(current, metrics, tuple(edits))

        edits.append("drop-ornamental")
        current = updated

    metrics = calculate_subhole_speed(current, tempo, settings)
    return SubholeSpeedResult(current, metrics, tuple(edits))


_BREATH_PRIORITY: Tuple[Tuple[str, int], ...] = (
    ("barline", 0),
    ("repeat-pitch", 1),
    ("rest", 2),
    ("breath-candidate", 3),
)


@dataclass(frozen=True)
class BreathSettings:
    base_limit_seconds: float = 7.0
    tempo_factor: float = 0.02
    register_factor: float = 1.25
    min_limit_seconds: float = 2.0
    max_limit_seconds: float = 8.0
    register_reference_midi: int = 76

    def __post_init__(self) -> None:
        if self.base_limit_seconds <= 0:
            raise ValueError("base_limit_seconds must be positive")
        if self.tempo_factor < 0:
            raise ValueError("tempo_factor must be non-negative")
        if self.register_factor < 0:
            raise ValueError("register_factor must be non-negative")
        if self.min_limit_seconds <= 0:
            raise ValueError("min_limit_seconds must be positive")
        if self.max_limit_seconds <= 0:
            raise ValueError("max_limit_seconds must be positive")
        if self.min_limit_seconds > self.max_limit_seconds:
            raise ValueError("min_limit_seconds cannot exceed max_limit_seconds")
        if not (self.min_limit_seconds <= self.base_limit_seconds <= self.max_limit_seconds):
            raise ValueError(
                "base_limit_seconds must fall between min_limit_seconds and max_limit_seconds"
            )

    def limit_for(self, tempo_bpm: float, segment_max_midi: int) -> float:
        tempo_component = max(0.0, tempo_bpm)
        register_index = max(0.0, (segment_max_midi - self.register_reference_midi) / 12.0)
        limit = self.base_limit_seconds
        limit -= self.tempo_factor * tempo_component
        limit -= self.register_factor * register_index
        if limit < self.min_limit_seconds:
            return self.min_limit_seconds
        if limit > self.max_limit_seconds:
            return self.max_limit_seconds
        return limit


@dataclass(frozen=True)
class BreathPlan:
    breath_points: Tuple[int, ...]
    segment_durations: Tuple[float, ...]


def _candidate_priority(tags: FrozenSet[str]) -> int | None:
    best: int | None = None
    for label, priority in _BREATH_PRIORITY:
        if label in tags:
            if best is None or priority < best:
                best = priority
    return best


def plan_breaths(span: PhraseSpan, tempo: TempoContext, settings: BreathSettings) -> BreathPlan:
    notes = span.notes
    if not notes:
        return BreathPlan((), ())

    breath_points: list[int] = []
    segments: list[float] = []

    segment_start = notes[0].onset
    segment_max_midi: int | None = notes[0].midi
    candidate: tuple[int, int] | None = None
    index = 0

    while index < len(notes):
        note = notes[index]
        note_end = note.onset + note.duration
        if segment_max_midi is None:
            segment_max_midi = note.midi
        else:
            segment_max_midi = max(segment_max_midi, note.midi)

        limit = settings.limit_for(tempo.bpm, segment_max_midi)
        segment_seconds = tempo.seconds_between(segment_start, note_end)

        if segment_seconds > limit:
            advance_index = False
            if candidate is not None:
                breath_onset = candidate[1]
            else:
                breath_onset = note.onset
            if breath_onset <= segment_start:
                breath_onset = note_end
                advance_index = True
            breath_points.append(breath_onset)
            segments.append(tempo.seconds_between(segment_start, breath_onset))
            segment_start = breath_onset
            segment_max_midi = None if advance_index else note.midi
            candidate = None
            if advance_index:
                index += 1
            continue

        priority = _candidate_priority(note.tags)
        if priority is not None:
            if candidate is None or priority < candidate[0] or (
                priority == candidate[0] and note.onset >= candidate[1]
            ):
                candidate = (priority, note.onset)

        index += 1

    segments.append(tempo.seconds_between(segment_start, span.total_duration))
    return BreathPlan(tuple(breath_points), tuple(segments))


@dataclass(frozen=True)
class TessituraSettings:
    comfort_center: float
    tolerance: float = 5.0
    weight: float = 0.02


def compute_tessitura_bias(span: PhraseSpan, settings: TessituraSettings) -> float:
    total_duration = sum(note.duration for note in span.notes)
    if total_duration <= 0:
        return 0.0

    penalty = 0.0
    for note in span.notes:
        distance = abs(note.midi - settings.comfort_center)
        excess = max(0.0, distance - settings.tolerance)
        if excess <= 0:
            continue
        penalty += excess * note.duration

    normalized = penalty / total_duration
    return normalized * settings.weight


def should_keep_high_octave_duplicate(
    salience: float,
    contrast_gain: float,
    added_difficulty: float,
    *,
    threshold: float = 0.0,
) -> bool:
    return (salience * contrast_gain) - added_difficulty > threshold


__all__ = [
    "AlternativeFingering",
    "BreathPlan",
    "BreathSettings",
    "SubholeConstraintSettings",
    "SubholePairLimit",
    "SubholeSpeedMetrics",
    "SubholeSpeedResult",
    "TempoContext",
    "TessituraSettings",
    "calculate_subhole_speed",
    "compute_tessitura_bias",
    "enforce_subhole_and_speed",
    "plan_breaths",
    "should_keep_high_octave_duplicate",
]
