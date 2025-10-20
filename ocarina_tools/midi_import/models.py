"""Data models and constants for MIDI import reporting."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Tuple

NoteEvent = Tuple[int, int, int, int]
TempoEvent = Tuple[int, float]

DEFAULT_TEMPO_BPM = 120
DEFAULT_TIME_SIGNATURE = (4, 4)


@dataclass(frozen=True)
class MidiSong:
    """Container for the MusicXML tree produced by the MIDI import."""

    tree: "ET.ElementTree"
    root: "ET.Element"
    pulses_per_quarter: int


@dataclass(frozen=True)
class MidiTrackIssue:
    """Represents a problem encountered while decoding a specific track."""

    track_index: int
    offset: int
    tick: int
    detail: str


@dataclass(frozen=True)
class MidiImportReport:
    """Aggregated outcome for a full MIDI import run."""

    mode: str
    issues: Tuple[MidiTrackIssue, ...]
    synthetic_eot_tracks: Tuple[int, ...]
    assumed_tempo_bpm: int
    assumed_time_signature: Tuple[int, int]


@dataclass(frozen=True)
class MidiTrackDecodeResult:
    """Decoded events, metadata, and issues for a single MIDI track."""

    events: List[NoteEvent]
    programs: Dict[int, int]
    tempo_changes: List[TempoEvent]
    issues: Tuple[MidiTrackIssue, ...]
    synthetic_eot: bool


if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    import xml.etree.ElementTree as ET  # noqa: WPS433 (import inside block)


__all__ = [
    "DEFAULT_TEMPO_BPM",
    "DEFAULT_TIME_SIGNATURE",
    "MidiImportReport",
    "MidiSong",
    "MidiTrackDecodeResult",
    "MidiTrackIssue",
    "NoteEvent",
    "TempoEvent",
]
