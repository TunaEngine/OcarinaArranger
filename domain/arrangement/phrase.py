from __future__ import annotations

from dataclasses import dataclass, replace
from typing import FrozenSet, Iterable, Tuple

from shared.ottava import OttavaShift


@dataclass(frozen=True)
class PhraseNote:
    onset: int
    duration: int
    midi: int
    ottava_shifts: Tuple[OttavaShift, ...] = ()
    tags: FrozenSet[str] = frozenset()

    def with_duration(self, duration: int) -> "PhraseNote":
        return replace(self, duration=int(duration))

    def with_onset(self, onset: int) -> "PhraseNote":
        return replace(self, onset=int(onset))

    def with_midi(self, midi: int) -> "PhraseNote":
        return replace(self, midi=int(midi))

    def add_ottava_shift(self, shift: OttavaShift) -> "PhraseNote":
        return replace(self, ottava_shifts=self.ottava_shifts + (shift,))

    def with_tags(self, tags: Iterable[str]) -> "PhraseNote":
        return replace(self, tags=frozenset(tags))


@dataclass(frozen=True)
class PhraseSpan:
    notes: Tuple[PhraseNote, ...]
    pulses_per_quarter: int = 480

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.notes, key=lambda note: (note.onset, note.midi)))
        object.__setattr__(self, "notes", ordered)

    def with_notes(self, notes: Iterable[PhraseNote]) -> "PhraseSpan":
        return PhraseSpan(tuple(notes), self.pulses_per_quarter)

    def transpose(self, semitones: int) -> "PhraseSpan":
        if semitones == 0:
            return self
        return PhraseSpan(
            tuple(note.with_midi(note.midi + semitones) for note in self.notes),
            self.pulses_per_quarter,
        )

    @property
    def total_duration(self) -> int:
        if not self.notes:
            return 0
        return max(note.onset + note.duration for note in self.notes)

    def eighth_duration(self) -> int:
        return max(1, self.pulses_per_quarter // 2)

    @property
    def first_onset(self) -> int:
        if not self.notes:
            return 0
        return min(note.onset for note in self.notes)

    def bar_number(self, *, beats_per_measure: int = 4) -> int:
        if beats_per_measure <= 0:
            raise ValueError("beats_per_measure must be positive")

        pulses_per_bar = max(1, self.pulses_per_quarter * beats_per_measure)
        return (self.first_onset // pulses_per_bar) + 1
