"""MIDI track decoding logic with strict and lenient strategies."""
from __future__ import annotations

from typing import Dict, List, Tuple

from .models import MidiTrackDecodeResult, MidiTrackIssue, NoteEvent, TempoEvent
from .streams import SafeStream


class StrictMidiDecoder:
    """Parse MIDI track bytes without applying recovery heuristics."""

    def __init__(self, track_data: bytes):
        self.stream = SafeStream(track_data)
        self.tick = 0
        self.running_status: int | None = None
        self.active: Dict[Tuple[int, int], int] = {}
        self.events: List[NoteEvent] = []
        self.programs: Dict[int, int] = {}
        self.tempo_changes: List[TempoEvent] = []

    @classmethod
    def decode(cls, track_data: bytes) -> tuple[List[NoteEvent], Dict[int, int], List[TempoEvent]]:
        decoder = cls(track_data)
        decoder._decode()
        return decoder.events, decoder.programs, decoder.tempo_changes

    def _decode(self) -> None:
        stream = self.stream
        while stream.remaining > 0:
            delta = stream.read_varlen()
            self.tick += delta
            if stream.remaining <= 0:
                break

            status = self._consume_status_byte()

            if status == 0xFF:
                self._parse_meta()
                continue

            if status in (0xF0, 0xF7):
                self._parse_sysex()
                continue

            event_type = status & 0xF0
            channel = status & 0x0F

            if event_type in (0x90, 0x80):
                self._parse_note_event(event_type, channel)
                continue

            if event_type == 0xC0:
                program = stream.read_byte()
                self.programs[channel] = program & 0x7F
                continue

            data_length = 1 if event_type in (0xC0, 0xD0) else 2
            stream.skip(data_length)

    def _consume_status_byte(self) -> int:
        stream = self.stream
        status = stream.peek_byte()
        if status & 0x80:
            status = stream.read_byte()
            self.running_status = status
        else:
            if self.running_status is None:
                raise ValueError("Running status encountered before any status byte.")
            status = self.running_status
        return status

    def _parse_meta(self) -> None:
        stream = self.stream
        meta_type = stream.read_byte()
        length = stream.read_varlen()
        payload = stream.read_exact(length)
        if meta_type == 0x51 and length >= 3:
            microseconds = int.from_bytes(payload[:3], "big", signed=False)
            if microseconds > 0:
                tempo_bpm = 60_000_000.0 / float(microseconds)
                self.tempo_changes.append((int(self.tick), tempo_bpm))
        if meta_type == 0x2F:
            stream.consume_all()

    def _parse_sysex(self) -> None:
        stream = self.stream
        length = stream.read_varlen()
        stream.skip(length)

    def _parse_note_event(self, event_type: int, channel: int) -> None:
        stream = self.stream
        note_data = stream.read_exact(2)
        note = note_data[0]
        velocity = note_data[1]
        key = (channel, note)
        if event_type == 0x90 and velocity > 0:
            self.active[key] = self.tick
        else:
            start_tick = self.active.pop(key, None)
            if start_tick is not None and self.tick > start_tick:
                self.events.append((start_tick, self.tick - start_tick, note, channel))


class LenientMidiDecoder:
    """Parse MIDI track bytes with recovery heuristics for malformed files."""

    def __init__(self, track_data: bytes, *, track_index: int = 0):
        self.track_data = track_data
        self.track_index = track_index
        self.stream = SafeStream(track_data)
        self.tick = 0
        self.running_status: int | None = None
        self.active: Dict[Tuple[int, int], int] = {}
        self.events: List[NoteEvent] = []
        self.programs: Dict[int, int] = {}
        self.tempo_changes: List[TempoEvent] = []
        self._issues: List[MidiTrackIssue] = []
        self._reached_eot = False

    @classmethod
    def decode(
        cls, track_data: bytes, *, track_index: int = 0
    ) -> tuple[List[NoteEvent], Dict[int, int], List[TempoEvent]]:
        decoder = cls(track_data, track_index=track_index)
        result = decoder._decode_with_recovery()
        return result.events, result.programs, result.tempo_changes

    @classmethod
    def decode_with_report(cls, track_data: bytes, *, track_index: int = 0) -> MidiTrackDecodeResult:
        decoder = cls(track_data, track_index=track_index)
        return decoder._decode_with_recovery()

    def _record_issue(self, detail: str, *, offset: int | None = None) -> None:
        offset_value = int(offset if offset is not None else self.stream.tell())
        self._issues.append(
            MidiTrackIssue(
                track_index=self.track_index,
                offset=offset_value,
                tick=int(self.tick),
                detail=detail,
            )
        )

    def _decode_with_recovery(self) -> MidiTrackDecodeResult:
        stream = self.stream

        while stream.remaining > 0:
            delta_offset = stream.tell()
            try:
                delta = stream.read_varlen(allow_partial=True)
            except ValueError:
                self._record_issue("Malformed delta-time; stopped decoding track", offset=delta_offset)
                break
            self.tick += delta
            if stream.remaining <= 0:
                break

            status_offset = stream.tell()
            try:
                status = stream.peek_byte()
            except ValueError:
                break

            if status & 0x80:
                status = stream.read_byte()
                if status < 0x80:
                    self._record_issue(
                        f"Discarded invalid status byte 0x{status:02X}", offset=status_offset
                    )
                    self.running_status = None
                    continue
                self.running_status = status
            else:
                if self.running_status is None:
                    discarded = stream.read_up_to(1)
                    if discarded:
                        self._record_issue(
                            f"Ignored data byte 0x{discarded[0]:02X} without running status",
                            offset=status_offset,
                        )
                    continue
                status = self.running_status

            if status == 0xFF:
                if stream.remaining <= 0:
                    break
                meta_type = stream.read_up_to(1)
                if not meta_type:
                    self._record_issue("Truncated meta event", offset=status_offset)
                    break
                length_offset = stream.tell()
                length = stream.read_varlen(allow_partial=True)
                payload_offset = stream.tell()
                payload = stream.read_up_to(length)
                if len(payload) < length:
                    self._record_issue("Truncated meta payload", offset=payload_offset)
                    self.running_status = None
                if meta_type[0] == 0x51 and len(payload) >= 3:
                    microseconds = int.from_bytes(payload[:3], "big", signed=False)
                    if microseconds > 0:
                        tempo_bpm = 60_000_000.0 / float(microseconds)
                        self.tempo_changes.append((int(self.tick), tempo_bpm))
                if meta_type[0] == 0x2F:
                    self._reached_eot = True
                    break
                continue

            if status in (0xF0, 0xF7):
                length_offset = stream.tell()
                length = stream.read_varlen(allow_partial=True)
                payload = stream.read_up_to(length)
                if len(payload) < length:
                    self._record_issue("Truncated sysex payload", offset=length_offset)
                self.running_status = None
                continue

            event_type = status & 0xF0
            channel = status & 0x0F

            if event_type in (0x90, 0x80):
                payload_offset = stream.tell()
                payload = stream.read_up_to(2)
                if len(payload) < 2:
                    self._record_issue("Truncated note event", offset=payload_offset)
                    break
                note, velocity = payload
                key = (channel, note)
                if event_type == 0x90 and velocity > 0:
                    self.active[key] = self.tick
                else:
                    start_tick = self.active.pop(key, None)
                    if start_tick is not None and self.tick > start_tick:
                        self.events.append((start_tick, self.tick - start_tick, note, channel))
                continue

            if event_type == 0xC0:
                payload_offset = stream.tell()
                payload = stream.read_up_to(1)
                if not payload:
                    self._record_issue("Truncated program change", offset=payload_offset)
                    break
                self.programs[channel] = payload[0] & 0x7F
                continue

            data_length = 1 if event_type in (0xC0, 0xD0) else 2
            skipped = stream.read_up_to(data_length)
            if len(skipped) < data_length:
                self._record_issue("Incomplete channel event", offset=status_offset)
                break

        issues = tuple(
            sorted(self._issues, key=lambda issue: (issue.track_index, issue.offset, issue.tick, issue.detail))
        )
        synthetic_eot = not self._reached_eot
        if synthetic_eot:
            issues = issues + (
                MidiTrackIssue(
                    track_index=self.track_index,
                    offset=len(self.track_data),
                    tick=int(self.tick),
                    detail="Inserted synthetic end-of-track",
                ),
            )

        return MidiTrackDecodeResult(
            events=self.events,
            programs=self.programs,
            tempo_changes=self.tempo_changes,
            issues=issues,
            synthetic_eot=synthetic_eot,
        )
def _parse_midi_events(track_data: bytes, *, strict: bool = True, track_index: int = 0) -> tuple[List[NoteEvent], Dict[int, int]]:
    """Compatibility wrapper returning MIDI events and channel programs."""

    if strict:
        events, programs, _ = StrictMidiDecoder.decode(track_data)
        return events, programs
    result = LenientMidiDecoder.decode_with_report(track_data, track_index=track_index)
    return result.events, result.programs


__all__ = [
    "LenientMidiDecoder",
    "StrictMidiDecoder",
    "_parse_midi_events",
]
