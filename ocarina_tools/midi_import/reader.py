"""Facade for reading MIDI files into MusicXML with reporting."""
from __future__ import annotations

import io
import struct
from typing import Dict, List, Set

from .decoders import LenientMidiDecoder, StrictMidiDecoder
from .models import (
    DEFAULT_TEMPO_BPM,
    DEFAULT_TIME_SIGNATURE,
    MidiImportReport,
    MidiSong,
    MidiTrackIssue,
    NoteEvent,
    TempoEvent,
)
from .musicxml_builder import build_musicxml

_VALID_MODES = {"strict", "lenient", "auto"}


def read_chunk(stream: io.BufferedReader) -> tuple[bytes, bytes]:
    """Read a MIDI chunk from the stream, returning its type and payload."""

    header = stream.read(8)
    if len(header) < 8:
        raise ValueError("Unexpected end of MIDI file.")
    chunk_type = header[:4]
    length = struct.unpack(">I", header[4:])[0]
    payload = stream.read(length)
    if len(payload) < length:
        raise ValueError("Unexpected end of MIDI chunk.")
    return chunk_type, payload


def read_midi(path: str, mode: str = "auto") -> tuple[MidiSong, MidiImportReport]:
    """Decode a MIDI file, falling back to lenient mode when requested."""

    mode_normalized = mode.lower()
    if mode_normalized not in _VALID_MODES:
        raise ValueError(f"Unsupported MIDI import mode: {mode}")

    with open(path, "rb") as handle:
        chunk_type, header = read_chunk(handle)
        if chunk_type != b"MThd" or len(header) < 6:
            raise ValueError("Invalid MIDI header.")
        _format_type, num_tracks, division = struct.unpack(">HHH", header[:6])
        division = max(1, division & 0x7FFF)

        track_events: List[NoteEvent] = []
        channel_programs: Dict[int, int] = {}
        issues: List[MidiTrackIssue] = []
        synthetic_eot_tracks: Set[int] = set()
        tempo_events: List[TempoEvent] = []
        used_mode = "strict"

        track_count = num_tracks or 1
        for track_index in range(track_count):
            try:
                chunk_type, data = read_chunk(handle)
            except ValueError as exc:
                issues.append(
                    MidiTrackIssue(
                        track_index=track_index,
                        offset=int(handle.tell()),
                        tick=0,
                        detail=str(exc),
                    )
                )
                break
            if chunk_type != b"MTrk":
                continue

            try:
                events, programs, tempos = StrictMidiDecoder.decode(data)
            except ValueError as exc:
                if mode_normalized == "strict":
                    raise
                issues.append(
                    MidiTrackIssue(
                        track_index=track_index,
                        offset=0,
                        tick=0,
                        detail=str(exc),
                    )
                )
                result = LenientMidiDecoder.decode_with_report(data, track_index=track_index)
                events = result.events
                programs = result.programs
                tempos = result.tempo_changes
                issues.extend(result.issues)
                if result.synthetic_eot:
                    synthetic_eot_tracks.add(track_index)
                used_mode = "lenient"
            else:
                for channel, program in programs.items():
                    channel_programs.setdefault(channel, program)
                tempo_events.extend((int(tick), float(tempo)) for tick, tempo in tempos)
                track_events.extend(events)
                continue

            for channel, program in programs.items():
                channel_programs.setdefault(channel, program)
            tempo_events.extend((int(tick), float(tempo)) for tick, tempo in tempos)
            track_events.extend(events)

        if not track_events:
            raise ValueError("No note events found in MIDI file.")

    tempo_sequence: list[TempoEvent] = []
    for tick, tempo in sorted(tempo_events, key=lambda entry: (max(0, entry[0]), entry[1])):
        tick_clamped = max(0, int(tick))
        tempo_value = float(tempo)
        if tempo_sequence and tempo_sequence[-1][0] == tick_clamped:
            tempo_sequence[-1] = (tick_clamped, tempo_value)
            continue
        if tempo_sequence and tempo_sequence[-1][1] == tempo_value:
            continue
        tempo_sequence.append((tick_clamped, tempo_value))

    if not tempo_sequence:
        tempo_sequence.append((0, float(DEFAULT_TEMPO_BPM)))

    tree = build_musicxml(track_events, division, channel_programs, tempo_sequence)
    root = tree.getroot()
    song = MidiSong(tree=tree, root=root, pulses_per_quarter=division)

    assumed_tempo = tempo_sequence[0][1] if tempo_sequence else float(DEFAULT_TEMPO_BPM)
    report = MidiImportReport(
        mode=used_mode,
        issues=tuple(sorted(issues, key=lambda issue: (issue.track_index, issue.offset, issue.tick, issue.detail))),
        synthetic_eot_tracks=tuple(sorted(synthetic_eot_tracks)),
        assumed_tempo_bpm=int(round(max(1.0, assumed_tempo))),
        assumed_time_signature=DEFAULT_TIME_SIGNATURE,
    )
    return song, report


__all__ = ["read_chunk", "read_midi"]
