"""Convenience views over MusicXML for note timelines and time signatures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Tuple
import xml.etree.ElementTree as ET

from .musicxml import first_divisions, get_pitch_data, qname
from .instruments import OCARINA_GM_PROGRAM, part_programs
from shared.tempo import TempoChange


@dataclass(frozen=True)
class NoteEvent:
    """Normalized representation of a note extracted from MusicXML."""

    onset: int
    duration: int
    midi: int
    program: int
    tied_durations: Tuple[int, ...] = field(default_factory=tuple)
    _tuple: Tuple[int, int, int, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.tied_durations:
            object.__setattr__(self, "tied_durations", (self.duration,))
        object.__setattr__(
            self,
            "_tuple",
            (int(self.onset), int(self.duration), int(self.midi), int(self.program)),
        )

    def __iter__(self):  # pragma: no cover - trivial delegation
        return iter(self._tuple)

    def __len__(self) -> int:  # pragma: no cover - tuple compatibility
        return 4

    def __getitem__(self, index: int) -> int:  # pragma: no cover - tuple compatibility
        return self._tuple[index]

    def shift(self, delta: int) -> "NoteEvent":
        """Return a new event with ``delta`` added to its onset."""

        return NoteEvent(
            self.onset + delta,
            self.duration,
            self.midi,
            self.program,
            self.tied_durations,
        )

    @property
    def tie_offsets(self) -> Tuple[int, ...]:
        """Return cumulative offsets for tied segments excluding the final note."""

        offsets: List[int] = []
        running = 0
        for segment in self.tied_durations[:-1]:
            running += segment
            offsets.append(running)
        return tuple(offsets)


def get_note_events(root: ET.Element) -> tuple[list[NoteEvent], int]:
    divisions = first_divisions(root)
    ppq = 480
    scale = ppq / max(1, divisions)
    q = lambda t: qname(root, t)
    programs = part_programs(root)
    events: List[NoteEvent] = []
    for index, part in enumerate(root.findall(q('part'))):
        part_id = (part.get('id') or f'P{index + 1}').strip()
        if not part_id:
            part_id = f'P{index + 1}'
        program = programs.get(part_id, OCARINA_GM_PROGRAM)
        voice_pos: dict[str, int] = {}
        tie_states: dict[tuple[str, int], tuple[int, List[int], int]] = {}
        for measure in part.findall(q('measure')):
            for note in measure.findall(q('note')):
                voice_el = note.find(q('voice'))
                voice = (voice_el.text.strip() if (voice_el is not None and voice_el.text) else '1')
                pos = voice_pos.get(voice, 0)
                dur_el = note.find(q('duration'))
                dur_text = (dur_el.text or '').strip() if dur_el is not None and dur_el.text else ''
                dur_div = int(dur_text) if dur_text.isdigit() else 0
                is_chord = note.find(q('chord')) is not None
                is_rest = note.find(q('rest')) is not None
                if not is_rest:
                    pitch_data = get_pitch_data(note, q)
                    if pitch_data is not None:
                        onset_ticks = int(round(pos * scale))
                        dur_ticks = max(1, int(round(dur_div * scale)))
                        tie_types = set()
                        for tie in note.findall(q('tie')):
                            tie_type = (tie.get('type') or '').strip().lower()
                            if tie_type:
                                tie_types.add(tie_type)
                        for notation in note.findall(q('notations')):
                            for tied in notation.findall(q('tied')):
                                tie_type = (tied.get('type') or '').strip().lower()
                                if tie_type:
                                    tie_types.add(tie_type)

                        tie_key = (voice, pitch_data.midi)
                        existing = tie_states.get(tie_key)

                        if 'stop' in tie_types and existing:
                            start_tick, segments, stored_program = existing
                            segments.append(dur_ticks)
                            if 'start' in tie_types:
                                tie_states[tie_key] = (start_tick, segments, stored_program)
                            else:
                                events.append(
                                    NoteEvent(
                                        start_tick,
                                        sum(segments),
                                        pitch_data.midi,
                                        stored_program,
                                        tuple(segments),
                                    )
                                )
                                tie_states.pop(tie_key, None)
                        elif 'start' in tie_types:
                            if existing:
                                start_tick, segments, stored_program = existing
                                segments.append(dur_ticks)
                                tie_states[tie_key] = (start_tick, segments, stored_program)
                            else:
                                tie_states[tie_key] = (onset_ticks, [dur_ticks], program)
                        elif 'stop' in tie_types:
                            events.append(
                                NoteEvent(
                                    onset_ticks,
                                    dur_ticks,
                                    pitch_data.midi,
                                    program,
                                    (dur_ticks,),
                                )
                            )
                        elif existing:
                            start_tick, segments, stored_program = existing
                            segments.append(dur_ticks)
                            events.append(
                                NoteEvent(
                                    start_tick,
                                    sum(segments),
                                    pitch_data.midi,
                                    stored_program,
                                    tuple(segments),
                                )
                            )
                            tie_states.pop(tie_key, None)
                        else:
                            events.append(
                                NoteEvent(
                                    onset_ticks,
                                    dur_ticks,
                                    pitch_data.midi,
                                    program,
                                )
                            )
                if not is_chord:
                    voice_pos[voice] = pos + dur_div
        for (voice, midi), (start_tick, segments, stored_program) in tie_states.items():
            events.append(
                NoteEvent(
                    start_tick,
                    sum(segments),
                    midi,
                    stored_program,
                    tuple(segments),
                )
            )
    return events, ppq


def get_time_signature(root: ET.Element) -> tuple[int, int]:
    q = lambda t: qname(root, t)
    for part in root.findall(q('part')):
        for measure in part.findall(q('measure')):
            attrs = measure.find(q('attributes'))
            if attrs is not None:
                ts = attrs.find(q('time'))
                if ts is not None:
                    beats_el = ts.find(q('beats'))
                    beat_type_el = ts.find(q('beat-type'))
                    try:
                        beats = int((beats_el.text or '4').strip()) if beats_el is not None else 4
                        beat_type = int((beat_type_el.text or '4').strip()) if beat_type_el is not None else 4
                        return beats, beat_type
                    except Exception:
                        pass
            break
        break
    return 4, 4


def detect_tempo_bpm(root: ET.Element, default_bpm: int = 120) -> int:
    """Return the first tempo marking found in ``root`` or ``default_bpm``."""

    changes = get_tempo_changes(root, default_bpm=default_bpm)
    if not changes:
        return max(20, min(300, int(default_bpm)))
    return int(round(changes[0].tempo_bpm))


def get_tempo_changes(root: ET.Element, default_bpm: int = 120) -> list[TempoChange]:
    """Extract tempo change events from ``root`` in ascending tick order."""

    q = lambda t: qname(root, t)
    ppq = 480
    divisions = max(1, first_divisions(root))
    scale = ppq / divisions

    parts = root.findall(q('part'))
    if not parts:
        return [TempoChange(tick=0, tempo_bpm=float(_clamp_tempo(default_bpm)))]

    changes: list[TempoChange] = []
    for part in parts:
        part_changes = list(_iter_tempo_changes_for_part(part, q, scale))
        if part_changes:
            changes = part_changes
            break

    if not changes:
        return [TempoChange(tick=0, tempo_bpm=float(_clamp_tempo(default_bpm)))]

    normalized: list[TempoChange] = []
    seen_tick = None
    for change in sorted(changes, key=lambda entry: max(0, entry.tick)):
        tick = max(0, int(change.tick))
        tempo_value = float(_clamp_tempo(change.tempo_bpm))
        if seen_tick == tick:
            normalized[-1] = TempoChange(tick=tick, tempo_bpm=tempo_value)
            continue
        normalized.append(TempoChange(tick=tick, tempo_bpm=tempo_value))
        seen_tick = tick

    if not normalized or normalized[0].tick > 0:
        normalized.insert(0, TempoChange(tick=0, tempo_bpm=float(_clamp_tempo(default_bpm))))

    pruned: list[TempoChange] = []
    for change in normalized:
        if pruned and abs(pruned[-1].tempo_bpm - change.tempo_bpm) <= 1e-6:
            continue
        pruned.append(change)
    return pruned


def _iter_tempo_changes_for_part(part: ET.Element, q, scale: float) -> Iterable[TempoChange]:
    measure_start = 0.0
    for measure in part.findall(q('measure')):
        position = 0.0
        max_position = 0.0
        for element in list(measure):
            tag = element.tag
            if tag == q('direction'):
                tempo_value = _tempo_from_direction(element, q)
                if tempo_value is None:
                    continue
                offset = _parse_offset(element, q)
                tick = int(round((measure_start + position + offset) * scale))
                yield TempoChange(tick=tick, tempo_bpm=tempo_value)
            elif tag == q('note'):
                duration = _parse_duration(element.find(q('duration')))
                if element.find(q('chord')) is None:
                    position += duration
                    if position > max_position:
                        max_position = position
            elif tag == q('backup'):
                duration = _parse_duration(element.find(q('duration')))
                position = max(0.0, position - duration)
            elif tag == q('forward'):
                duration = _parse_duration(element.find(q('duration')))
                position += duration
                if position > max_position:
                    max_position = position
        measure_start += max_position


def _tempo_from_direction(direction: ET.Element, q) -> float | None:
    sound = direction.find(q('sound'))
    if sound is not None:
        tempo_value = _parse_tempo(sound.get('tempo'))
        if tempo_value is not None:
            return tempo_value

    for direction_type in direction.findall(q('direction-type')):
        metronome = direction_type.find(q('metronome'))
        if metronome is None:
            continue
        per_minute = metronome.find(q('per-minute'))
        if per_minute is not None and per_minute.text:
            tempo_value = _parse_tempo(per_minute.text)
            if tempo_value is not None:
                return tempo_value
    return None


def _parse_offset(direction: ET.Element, q) -> float:
    offset_el = direction.find(q('offset'))
    if offset_el is None or offset_el.text is None:
        return 0.0
    try:
        return float(offset_el.text.strip())
    except (TypeError, ValueError):
        return 0.0


def _parse_duration(duration_el: ET.Element | None) -> float:
    if duration_el is None or duration_el.text is None:
        return 0.0
    text = duration_el.text.strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _parse_tempo(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        tempo = float(text)
    except (TypeError, ValueError):
        return None
    return tempo


def _clamp_tempo(value: float | int) -> float:
    try:
        tempo = float(value)
    except (TypeError, ValueError):
        tempo = 120.0
    return max(20.0, min(300.0, tempo))


__all__ = [
    'NoteEvent',
    'get_note_events',
    'get_time_signature',
    'detect_tempo_bpm',
    'get_tempo_changes',
    'TempoChange',
]
