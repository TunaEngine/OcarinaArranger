"""Convenience views over MusicXML for note timelines and time signatures."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, List, Tuple
import xml.etree.ElementTree as ET

from .musicxml import first_divisions, get_pitch_data, make_qname_getter
from .instruments import OCARINA_GM_PROGRAM, part_programs
from .grace_settings import (
    GraceSettings,
    _PendingGrace,
    _allocate_grace_durations,
    _classify_grace,
    _fold_grace_midi,
)
from .ottava_utils import (
    _active_shifts,
    _extract_note_ottavas,
    _handle_direction_octaves,
    _pop_ottava,
    _total_shift,
)
from shared.tempo import TempoChange
from shared.ottava import OttavaShift


@dataclass(frozen=True)
class NoteEvent:
    """Normalized representation of a note extracted from MusicXML."""

    onset: int
    duration: int
    midi: int
    program: int
    tied_durations: Tuple[int, ...] = field(default_factory=tuple)
    ottava_shifts: Tuple[OttavaShift, ...] = field(default_factory=tuple)
    is_grace: bool = False
    grace_type: str | None = None
    _tuple: Tuple[int, int, int, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.tied_durations:
            object.__setattr__(self, "tied_durations", (self.duration,))
        if not self.ottava_shifts:
            object.__setattr__(self, "ottava_shifts", tuple())
        object.__setattr__(
            self,
            "_tuple",
            (int(self.onset), int(self.duration), int(self.midi), int(self.program)),
        )
        object.__setattr__(self, "is_grace", bool(self.is_grace))
        if self.grace_type is not None:
            normalized = str(self.grace_type).strip()
            object.__setattr__(self, "grace_type", normalized or None)

    def __iter__(self):  # pragma: no cover - trivial delegation
        return iter(self._tuple)

    def __len__(self) -> int:  # pragma: no cover - tuple compatibility
        return 4

    def __getitem__(self, index: int) -> int:  # pragma: no cover - tuple compatibility
        return self._tuple[index]

    def shift(self, delta: int) -> "NoteEvent":
        """Return a new event with ``delta`` added to its onset."""

        return NoteEvent(
            onset=self.onset + delta,
            duration=self.duration,
            midi=self.midi,
            program=self.program,
            tied_durations=self.tied_durations,
            ottava_shifts=self.ottava_shifts,
            is_grace=self.is_grace,
            grace_type=self.grace_type,
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


def get_note_events(
    root: ET.Element, *, grace_settings: GraceSettings | None = None
) -> tuple[list[NoteEvent], int]:
    divisions = first_divisions(root)
    ppq = 480
    scale = ppq / max(1, divisions)
    q = make_qname_getter(root)
    programs = part_programs(root)
    settings = grace_settings or GraceSettings()
    tempo_bpm = detect_tempo_bpm(root)
    events: List[NoteEvent] = []
    for index, part in enumerate(root.findall(q('part'))):
        part_id = (part.get('id') or f'P{index + 1}').strip()
        if not part_id:
            part_id = f'P{index + 1}'
        program = programs.get(part_id, OCARINA_GM_PROGRAM)
        voice_pos: dict[str, int] = {}
        voice_ottavas: defaultdict[str, list[tuple[OttavaShift, str | None]]] = defaultdict(list)
        grace_buffers: defaultdict[str, list[_PendingGrace]] = defaultdict(list)
        voice_anchor_onset: dict[str, int] = {}
        tie_states: dict[tuple[str, int], tuple[int, List[int], int, Tuple[OttavaShift, ...]]] = {}
        for measure in part.findall(q('measure')):
            measure_start = max(voice_pos.values(), default=0)
            for element in list(measure):
                if element.tag == q('direction'):
                    _handle_direction_octaves(element, q, voice_ottavas, voice_pos)
                    continue
                if element.tag != q('note'):
                    continue
                note = element
                voice_el = note.find(q('voice'))
                voice = (voice_el.text.strip() if (voice_el is not None and voice_el.text) else '1')
                pos = voice_pos.get(voice, measure_start)
                dur_el = note.find(q('duration'))
                dur_text = (dur_el.text or '').strip() if dur_el is not None and dur_el.text else ''
                dur_div = int(dur_text) if dur_text.isdigit() else 0
                is_chord = note.find(q('chord')) is not None
                starts, stops = _extract_note_ottavas(note, q)
                for shift in starts:
                    voice_ottavas[voice].append((shift, shift.number))
                active_stack = voice_ottavas[voice]
                active_shifts = _active_shifts(active_stack)
                base_onset_ticks = int(round(pos * scale))
                onset_ticks = base_onset_ticks
                if is_chord and voice in voice_anchor_onset:
                    onset_ticks = voice_anchor_onset[voice]

                grace_el = note.find(q('grace'))
                is_rest = note.find(q('rest')) is not None

                if is_rest:
                    grace_buffers.pop(voice, None)
                    voice_anchor_onset.pop(voice, None)
                    for number in stops:
                        _pop_ottava(voice_ottavas[voice], number)
                    if not is_chord:
                        voice_pos[voice] = pos + dur_div
                    continue

                pitch_data = get_pitch_data(note, q)
                if pitch_data is None:
                    grace_buffers.pop(voice, None)
                    voice_anchor_onset.pop(voice, None)
                    for number in stops:
                        _pop_ottava(voice_ottavas[voice], number)
                    if not is_chord:
                        voice_pos[voice] = pos + dur_div
                    continue

                midi = pitch_data.midi + _total_shift(active_stack)

                if grace_el is not None:
                    grace_buffers[voice].append(
                        _PendingGrace(
                            midi=midi,
                            ottava_shifts=active_shifts,
                            grace_type=_classify_grace(grace_el),
                        )
                    )
                    for number in stops:
                        _pop_ottava(voice_ottavas[voice], number)
                    continue

                dur_ticks = max(1, int(round(dur_div * scale)))
                pending = grace_buffers.get(voice, [])
                trimmed: list[_PendingGrace] = []
                if pending and settings.max_chain != 0:
                    limit = settings.max_chain if settings.max_chain > 0 else len(pending)
                    trimmed = list(pending[-limit:])
                durations = _allocate_grace_durations(dur_ticks, len(trimmed), tempo_bpm, settings)
                if durations and len(durations) < len(trimmed):
                    trimmed = trimmed[-len(durations):]
                else:
                    trimmed = trimmed[: len(durations)]
                if voice in grace_buffers:
                    grace_buffers[voice].clear()

                stolen_total = 0
                current_onset = onset_ticks
                for pending_grace, grace_duration in zip(trimmed, durations):
                    resolved_midi = _fold_grace_midi(pending_grace.midi, midi, settings)
                    if resolved_midi is None:
                        continue
                    events.append(
                        NoteEvent(
                            onset=current_onset,
                            duration=grace_duration,
                            midi=resolved_midi,
                            program=program,
                            tied_durations=(grace_duration,),
                            ottava_shifts=pending_grace.ottava_shifts,
                            is_grace=True,
                            grace_type=pending_grace.grace_type,
                        )
                    )
                    current_onset += grace_duration
                    stolen_total += grace_duration

                effective_onset = onset_ticks + stolen_total
                effective_duration = max(1, dur_ticks - stolen_total)
                voice_anchor_onset[voice] = effective_onset

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

                tie_key = (voice, midi)
                existing = tie_states.get(tie_key)

                if 'stop' in tie_types and existing:
                    start_tick, segments, stored_program, stored_shifts = existing
                    segments.append(effective_duration)
                    if 'start' in tie_types:
                        tie_states[tie_key] = (start_tick, segments, stored_program, stored_shifts)
                    else:
                        events.append(
                            NoteEvent(
                                onset=start_tick,
                                duration=sum(segments),
                                midi=midi,
                                program=stored_program,
                                tied_durations=tuple(segments),
                                ottava_shifts=stored_shifts,
                            )
                        )
                        tie_states.pop(tie_key, None)
                elif 'start' in tie_types:
                    if existing:
                        start_tick, segments, stored_program, stored_shifts = existing
                        segments.append(effective_duration)
                        tie_states[tie_key] = (start_tick, segments, stored_program, stored_shifts)
                    else:
                        tie_states[tie_key] = (
                            effective_onset,
                            [effective_duration],
                            program,
                            active_shifts,
                        )
                elif 'stop' in tie_types:
                    events.append(
                        NoteEvent(
                            onset=effective_onset,
                            duration=effective_duration,
                            midi=midi,
                            program=program,
                            tied_durations=(effective_duration,),
                            ottava_shifts=active_shifts,
                        )
                    )
                elif existing:
                    start_tick, segments, stored_program, stored_shifts = existing
                    segments.append(effective_duration)
                    events.append(
                        NoteEvent(
                            onset=start_tick,
                            duration=sum(segments),
                            midi=midi,
                            program=stored_program,
                            tied_durations=tuple(segments),
                            ottava_shifts=stored_shifts,
                        )
                    )
                    tie_states.pop(tie_key, None)
                else:
                    events.append(
                        NoteEvent(
                            onset=effective_onset,
                            duration=effective_duration,
                            midi=midi,
                            program=program,
                            tied_durations=(effective_duration,),
                            ottava_shifts=active_shifts,
                        )
                    )

                for number in stops:
                    _pop_ottava(voice_ottavas[voice], number)
                if not is_chord:
                    voice_pos[voice] = pos + dur_div
        for (voice, midi), (start_tick, segments, stored_program, stored_shifts) in tie_states.items():
            events.append(
                NoteEvent(
                    onset=start_tick,
                    duration=sum(segments),
                    midi=midi,
                    program=stored_program,
                    tied_durations=tuple(segments),
                    ottava_shifts=stored_shifts,
                )
            )
    return events, ppq


def get_time_signature(root: ET.Element) -> tuple[int, int]:
    q = make_qname_getter(root)
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

    q = make_qname_getter(root)
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
    'GraceSettings',
    'TempoChange',
]
