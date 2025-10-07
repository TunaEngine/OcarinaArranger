"""Convenience views over MusicXML for note timelines and time signatures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple
import xml.etree.ElementTree as ET

from .musicxml import first_divisions, get_pitch_data, qname
from .instruments import OCARINA_GM_PROGRAM, part_programs


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

    def _parse_tempo(value: str | None) -> int | None:
        if not value:
            return None
        try:
            bpm = int(float(value))
        except (TypeError, ValueError):
            return None
        return max(20, min(300, bpm))

    q = lambda t: qname(root, t)
    for part in root.findall(q('part')):
        for measure in part.findall(q('measure')):
            for direction in measure.findall(q('direction')):
                sound = direction.find(q('sound'))
                tempo = _parse_tempo(sound.get('tempo') if sound is not None else None)
                if tempo is not None:
                    return tempo
            sound = measure.find(q('sound'))
            tempo = _parse_tempo(sound.get('tempo') if sound is not None else None)
            if tempo is not None:
                return tempo
    return max(20, min(300, int(default_bpm)))


__all__ = [
    'NoteEvent',
    'get_note_events',
    'get_time_signature',
    'detect_tempo_bpm',
]
