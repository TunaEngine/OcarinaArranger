"""Event utilities for the piano roll widget."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple, Union, cast

from ocarina_tools import NoteEvent

Event = NoteEvent
EventLike = Union[Tuple[int, int, int], Tuple[int, int, int, int], NoteEvent]


@dataclass(frozen=True)
class NormalizedEvents:
    """Container for normalized events sorted by onset."""

    values: Tuple[NoteEvent, ...]

    @classmethod
    def from_events(cls, events: Sequence[EventLike]) -> "NormalizedEvents":
        normalized = _normalize(events)
        normalized.sort(key=lambda item: item[0])
        return cls(tuple(normalized))

    def __iter__(self) -> Iterable[NoteEvent]:
        return iter(self.values)

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self.values)


def _normalize(events: Sequence[EventLike]) -> List[NoteEvent]:
    normalized: List[NoteEvent] = []
    for event in events:
        if isinstance(event, NoteEvent):
            normalized.append(event)
            continue
        length = len(event)
        if length == 3:
            onset, duration, midi = event
            program = 0
        elif length == 4:
            onset, duration, midi, program = cast(Tuple[int, int, int, int], event)
        else:  # pragma: no cover - defensive
            raise ValueError(f"Unsupported event tuple length: {length}")
        normalized.append(NoteEvent(onset, duration, midi, program))
    return normalized


def normalize_events(events: Sequence[EventLike]) -> Tuple[NoteEvent, ...]:
    """Normalize event tuples into the consistent internal representation."""

    return NormalizedEvents.from_events(events).values
