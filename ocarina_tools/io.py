"""File loading utilities for plain MusicXML, zipped MXL, and MIDI files."""
from __future__ import annotations

import io
import re
import struct
import zipfile
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple
import xml.etree.ElementTree as ET

from .musicxml import build_pitch_element


NoteEvent = Tuple[int, int, int, int]


def load_score(path: str) -> tuple[ET.ElementTree, ET.Element]:
    lower = path.lower()
    is_zip = zipfile.is_zipfile(path)
    expects_mxl_archive = lower.endswith(('.mxl', '.mxl.zip'))
    if expects_mxl_archive or (is_zip and lower.endswith(('.xml', '.musicxml'))):
        with zipfile.ZipFile(path, 'r') as archive:
            candidate = None
            if 'score.xml' in archive.namelist():
                candidate = 'score.xml'
            else:
                try:
                    with archive.open('META-INF/container.xml') as handle:
                        data = handle.read().decode('utf-8', errors='ignore')
                    match = re.search(r'full-path="([^"]+)"', data)
                    if match and match.group(1) in archive.namelist():
                        candidate = match.group(1)
                except KeyError:
                    pass
            if not candidate:
                for name in archive.namelist():
                    if name.lower().endswith(('.xml', '.musicxml')):
                        candidate = name
                        break
            if not candidate:
                raise ValueError('No XML found inside MXL.')
            with archive.open(candidate) as handle:
                data = handle.read()
        tree = ET.ElementTree(ET.fromstring(data))
        return tree, tree.getroot()
    if lower.endswith(('.mid', '.midi')):
        tree = _load_midi_as_musicxml(path)
        return tree, tree.getroot()
    tree = ET.parse(path)
    return tree, tree.getroot()


def _read_chunk(stream: io.BufferedReader) -> tuple[bytes, bytes]:
    header = stream.read(8)
    if len(header) < 8:
        raise ValueError('Unexpected end of MIDI file.')
    chunk_type = header[:4]
    length = struct.unpack('>I', header[4:])[0]
    payload = stream.read(length)
    if len(payload) < length:
        raise ValueError('Unexpected end of MIDI chunk.')
    return chunk_type, payload


def _read_varlen(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    consumed = 0
    while pos + consumed < len(data):
        byte = data[pos + consumed]
        value = (value << 7) | (byte & 0x7F)
        consumed += 1
        if byte & 0x80 == 0:
            break
    else:
        raise ValueError('Malformed variable-length quantity in MIDI track.')
    return value, consumed


def _parse_midi_events(track_data: bytes) -> tuple[List[NoteEvent], Dict[int, int]]:
    position = 0
    tick = 0
    running_status: int | None = None
    active: Dict[tuple[int, int], int] = {}
    events: List[NoteEvent] = []
    programs: Dict[int, int] = {}

    while position < len(track_data):
        delta, consumed = _read_varlen(track_data, position)
        position += consumed
        tick += delta
        if position >= len(track_data):
            break

        status = track_data[position]
        if status & 0x80:
            position += 1
            running_status = status
        else:
            if running_status is None:
                raise ValueError('Running status encountered before any status byte.')
            status = running_status

        if status == 0xFF:  # Meta event
            if position >= len(track_data):
                break
            meta_type = track_data[position]
            position += 1
            length, consumed = _read_varlen(track_data, position)
            position += consumed
            position += length
            if meta_type == 0x2F:  # End of track
                break
            continue

        if status in (0xF0, 0xF7):  # SysEx
            length, consumed = _read_varlen(track_data, position)
            position += consumed + length
            continue

        event_type = status & 0xF0
        channel = status & 0x0F

        if event_type in (0x90, 0x80):
            if position + 2 > len(track_data):
                break
            note = track_data[position]
            velocity = track_data[position + 1]
            position += 2
            key = (channel, note)
            if event_type == 0x90 and velocity > 0:
                active[key] = tick
            else:
                start_tick = active.pop(key, None)
                if start_tick is not None and tick > start_tick:
                    events.append((start_tick, tick - start_tick, note, channel))
            continue

        if event_type == 0xC0:  # Program change
            if position >= len(track_data):
                break
            program = track_data[position]
            position += 1
            programs[channel] = program & 0x7F
            continue

        data_length = 2
        if event_type in (0xC0, 0xD0):
            data_length = 1
        position += data_length

    return events, programs


def _group_events(events: Iterable[NoteEvent]) -> List[tuple[int, List[NoteEvent]]]:
    grouped: Dict[int, List[NoteEvent]] = defaultdict(list)
    for event in events:
        grouped[event[0]].append(event)
    return sorted(
        ((start, sorted(items, key=lambda x: x[2]))) for start, items in grouped.items()
    )


def _build_musicxml(
    events: Iterable[NoteEvent], divisions: int, programs: Dict[int, int]
) -> ET.ElementTree:
    events_by_channel: Dict[int, List[NoteEvent]] = defaultdict(list)
    for event in events:
        _, _, _, channel = event
        events_by_channel[channel].append(event)

    root = ET.Element('score-partwise', version='3.1')
    part_list = ET.SubElement(root, 'part-list')

    for index, channel in enumerate(sorted(events_by_channel)):
        part_id = f'CH{channel + 1}'
        score_part = ET.SubElement(part_list, 'score-part', attrib={'id': part_id})
        ET.SubElement(score_part, 'part-name').text = f'Channel {channel + 1}'
        midi_instr = ET.SubElement(
            score_part, 'midi-instrument', attrib={'id': f'{part_id}-I1'}
        )
        ET.SubElement(midi_instr, 'midi-channel').text = str(channel + 1)
        program = programs.get(channel)
        if program is not None:
            ET.SubElement(midi_instr, 'midi-program').text = str(
                max(1, min(128, program + 1))
            )

        part = ET.SubElement(root, 'part', attrib={'id': part_id})
        measure = ET.SubElement(part, 'measure', attrib={'number': '1'})

        attrs = ET.SubElement(measure, 'attributes')
        ET.SubElement(attrs, 'divisions').text = str(max(1, divisions))
        time_el = ET.SubElement(attrs, 'time')
        ET.SubElement(time_el, 'beats').text = '4'
        ET.SubElement(time_el, 'beat-type').text = '4'
        key_el = ET.SubElement(attrs, 'key')
        ET.SubElement(key_el, 'fifths').text = '0'
        clef = ET.SubElement(attrs, 'clef')
        ET.SubElement(clef, 'sign').text = 'G'
        ET.SubElement(clef, 'line').text = '2'

        grouped = _group_events(sorted(events_by_channel[channel], key=lambda e: e[0]))

        current_tick = 0
        for start_tick, chord_events in grouped:
            gap = start_tick - current_tick
            if gap > 0:
                rest_note = ET.SubElement(measure, 'note')
                ET.SubElement(rest_note, 'rest')
                ET.SubElement(rest_note, 'duration').text = str(gap)
                ET.SubElement(rest_note, 'voice').text = '1'
                current_tick += gap

            max_duration = 0
            for idx, (_, duration, midi, _) in enumerate(chord_events):
                duration_div = max(1, duration)
                note_el = ET.SubElement(measure, 'note')
                note_el.set('data-start-div', str(start_tick))
                note_el.set('data-duration-div', str(duration_div))
                if idx > 0:
                    ET.SubElement(note_el, 'chord')
                note_el.append(build_pitch_element(lambda t: t, midi, prefer_flats=True))
                ET.SubElement(note_el, 'duration').text = str(duration_div)
                ET.SubElement(note_el, 'voice').text = '1'
                max_duration = max(max_duration, duration)

            current_tick = max(current_tick, start_tick + max_duration)

    tree = ET.ElementTree(root)
    return tree


def _load_midi_as_musicxml(path: str) -> ET.ElementTree:
    with open(path, 'rb') as handle:
        chunk_type, header = _read_chunk(handle)
        if chunk_type != b'MThd' or len(header) < 6:
            raise ValueError('Invalid MIDI header.')
        format_type, num_tracks, division = struct.unpack('>HHH', header[:6])
        division = max(1, division & 0x7FFF)

        track_events: List[NoteEvent] = []
        channel_programs: Dict[int, int] = {}
        for _ in range(num_tracks or 1):
            try:
                chunk_type, data = _read_chunk(handle)
            except ValueError:
                break
            if chunk_type != b'MTrk':
                continue
            events, programs = _parse_midi_events(data)
            track_events.extend(events)
            for channel, program in programs.items():
                channel_programs.setdefault(channel, program)
            if format_type == 0:
                break

    if not track_events:
        raise ValueError('No note events found in MIDI file.')
    return _build_musicxml(track_events, division, channel_programs)


__all__ = ['load_score']
