"""Utilities to build MusicXML trees from decoded MIDI events."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Dict, Iterable, List, Sequence, Tuple

from ..musicxml import build_pitch_element
from .models import DEFAULT_TIME_SIGNATURE, NoteEvent, TempoEvent


def _format_tempo_value(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text or "0"


def _append_tempo_direction(measure: ET.Element, tempo_bpm: float, offset: int) -> None:
    direction = ET.SubElement(measure, "direction")
    if offset:
        ET.SubElement(direction, "offset").text = str(offset)
    direction_type = ET.SubElement(direction, "direction-type")
    metronome = ET.SubElement(direction_type, "metronome")
    ET.SubElement(metronome, "beat-unit").text = "quarter"
    ET.SubElement(metronome, "per-minute").text = _format_tempo_value(tempo_bpm)
    sound = ET.SubElement(direction, "sound")
    sound.set("tempo", _format_tempo_value(tempo_bpm))


def _group_events(events: Iterable[NoteEvent]) -> List[Tuple[int, List[NoteEvent]]]:
    grouped: Dict[int, List[NoteEvent]] = defaultdict(list)
    for event in events:
        grouped[event[0]].append(event)
    return sorted(((start, sorted(items, key=lambda item: item[2]))) for start, items in grouped.items())


def build_musicxml(
    events: Iterable[NoteEvent],
    divisions: int,
    programs: Dict[int, int],
    tempo_changes: Sequence[TempoEvent],
) -> ET.ElementTree:
    events_by_channel: Dict[int, List[NoteEvent]] = defaultdict(list)
    for event in events:
        _, _, _, channel = event
        events_by_channel[channel].append(event)

    tempo_list = sorted(
        ((max(0, int(tick)), float(tempo)) for tick, tempo in tempo_changes),
        key=lambda entry: entry[0],
    )

    root = ET.Element("score-partwise", version="3.1")
    part_list = ET.SubElement(root, "part-list")

    tempo_index = 0

    for part_number, channel in enumerate(sorted(events_by_channel)):
        part_id = f"CH{channel + 1}"
        score_part = ET.SubElement(part_list, "score-part", attrib={"id": part_id})
        ET.SubElement(score_part, "part-name").text = f"Channel {channel + 1}"
        midi_instr = ET.SubElement(score_part, "midi-instrument", attrib={"id": f"{part_id}-I1"})
        ET.SubElement(midi_instr, "midi-channel").text = str(channel + 1)
        program = programs.get(channel)
        if program is not None:
            ET.SubElement(midi_instr, "midi-program").text = str(max(1, min(128, program + 1)))

        part = ET.SubElement(root, "part", attrib={"id": part_id})
        measure = ET.SubElement(part, "measure", attrib={"number": "1"})

        attrs = ET.SubElement(measure, "attributes")
        ET.SubElement(attrs, "divisions").text = str(max(1, divisions))
        time_el = ET.SubElement(attrs, "time")
        ET.SubElement(time_el, "beats").text = str(DEFAULT_TIME_SIGNATURE[0])
        ET.SubElement(time_el, "beat-type").text = str(DEFAULT_TIME_SIGNATURE[1])
        key_el = ET.SubElement(attrs, "key")
        ET.SubElement(key_el, "fifths").text = "0"
        clef = ET.SubElement(attrs, "clef")
        ET.SubElement(clef, "sign").text = "G"
        ET.SubElement(clef, "line").text = "2"

        grouped = _group_events(sorted(events_by_channel[channel], key=lambda e: e[0]))

        cursor = 0

        def emit_tempos(up_to_tick: int, baseline: int) -> None:
            nonlocal tempo_index
            if part_number != 0:
                return
            while tempo_index < len(tempo_list) and tempo_list[tempo_index][0] <= up_to_tick:
                tick, tempo_bpm = tempo_list[tempo_index]
                offset = tick - baseline
                if offset < 0:
                    offset = 0
                _append_tempo_direction(measure, tempo_bpm, offset)
                tempo_index += 1

        for start_tick, chord_events in grouped:
            max_duration = max((event[1] for event in chord_events), default=0)
            segment_end = max(start_tick + max_duration, cursor)

            emit_tempos(segment_end, cursor)

            gap = start_tick - cursor
            if gap > 0:
                rest_note = ET.SubElement(measure, "note")
                ET.SubElement(rest_note, "rest")
                ET.SubElement(rest_note, "duration").text = str(gap)
                ET.SubElement(rest_note, "voice").text = "1"
                cursor += gap

            for idx, (_, duration, midi, _) in enumerate(chord_events):
                duration_div = max(1, duration)
                note_el = ET.SubElement(measure, "note")
                note_el.set("data-start-div", str(start_tick))
                note_el.set("data-duration-div", str(duration_div))
                if idx > 0:
                    ET.SubElement(note_el, "chord")
                note_el.append(build_pitch_element(lambda token: token, midi, prefer_flats=True))
                ET.SubElement(note_el, "duration").text = str(duration_div)
                ET.SubElement(note_el, "voice").text = "1"
                if idx == 0:
                    cursor = max(cursor, start_tick) + duration_div

            cursor = max(cursor, start_tick + max_duration)

        emit_tempos(tempo_list[-1][0] if tempo_list else cursor, cursor)

    tree = ET.ElementTree(root)
    return tree


__all__ = ["build_musicxml"]
