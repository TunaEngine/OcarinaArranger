"""Lightweight MusicXML and MIDI exporters used by the arranger."""

from __future__ import annotations

import struct
import zipfile
from typing import Dict, List, Tuple
import xml.etree.ElementTree as ET

from .events import detect_tempo_bpm
from .musicxml import first_divisions, iter_pitched_notes_first_part, make_qname_getter
from .instruments import OCARINA_GM_PROGRAM, part_programs
from .pitch import pitch_to_midi


def export_musicxml(tree: ET.ElementTree, out_path: str) -> None:
    tree.write(out_path, encoding="utf-8", xml_declaration=True)


def export_mxl(tree: ET.ElementTree, out_path: str) -> None:
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        xml_bytes = ET.tostring(tree.getroot(), encoding="utf-8", xml_declaration=True)
        archive.writestr("score.xml", xml_bytes)
        container_xml = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<container version=\"1.0\" xmlns=\"urn:oasis:names:tc:opendocument:xmlns:container\">
  <rootfiles>
    <rootfile full-path=\"score.xml\" media-type=\"application/vnd.recordare.musicxml+xml\"/>
  </rootfiles>
</container>
"""
        archive.writestr("META-INF/container.xml", container_xml)


def export_midi(root: ET.Element, out_path: str, tempo_bpm: int | None = None) -> None:
    divisions = first_divisions(root)
    ppq = 480
    scale = ppq / max(1, divisions)

    tempo_value: float | int | None = tempo_bpm
    if tempo_value is None:
        tempo_value = detect_tempo_bpm(root, 120)
    try:
        tempo_int = int(float(tempo_value))
    except (TypeError, ValueError):
        tempo_int = 120
    tempo_int = max(1, tempo_int)

    def varlen(number: int) -> bytes:
        bytes_ = [number & 0x7F]
        number >>= 7
        while number:
            bytes_.append((number & 0x7F) | 0x80)
            number >>= 7
        return bytes(bytearray(reversed(bytes_)))

    track = bytearray()
    microseconds_per_quarter = int(60000000 // tempo_int)
    track += b'\x00' + b'\xff\x51\x03' + struct.pack('>I', microseconds_per_quarter)[1:]
    track += b'\x00' + bytes([0xC0, OCARINA_GM_PROGRAM])

    current_time = 0
    for item in iter_pitched_notes_first_part(root):
        ticks = int(round(item.get("duration", 0) * scale))
        if item.get("rest"):
            current_time += ticks
            continue
        track += varlen(current_time) + bytes([0x90, item["midi"], 0x60])
        track += varlen(ticks) + bytes([0x80, item["midi"], 0x40])
        current_time = 0

    track += b'\x00\xff\x2f\x00'

    header = b'MThd' + struct.pack('>IHHH', 6, 0, 1, ppq)
    track_chunk = b'MTrk' + struct.pack('>I', len(track)) + bytes(track)
    with open(out_path, 'wb') as handle:
        handle.write(header)
        handle.write(track_chunk)




def export_midi_poly(
    root: ET.Element,
    out_path: str,
    tempo_bpm: int | None = None,
    *,
    use_original_instruments: bool = False,
) -> None:
    divisions = max(1, first_divisions(root))
    ppq = divisions
    if tempo_bpm is None:
        tempo_bpm = detect_tempo_bpm(root, 120)

    def varlen(number: int) -> bytes:
        bytes_ = [number & 0x7F]
        number >>= 7
        while number:
            bytes_.append((number & 0x7F) | 0x80)
            number >>= 7
        return bytes(bytearray(reversed(bytes_)))

    q = make_qname_getter(root)
    programs = part_programs(root) if use_original_instruments else {}
    events: List[Tuple[int, int, int, int, int]] = []
    channel_programs: Dict[int, int] = {}
    assigned_channels: Dict[str, int] = {}
    next_channel = 0

    def allocate_channel(part_id: str) -> int:
        nonlocal next_channel
        if part_id in assigned_channels:
            return assigned_channels[part_id]
        channel = min(next_channel, 15)
        if next_channel < 15:
            next_channel += 1
        assigned_channels[part_id] = channel
        return channel
    for index, part in enumerate(root.findall(q('part'))):
        part_id = (part.get('id') or f'P{index + 1}').strip()
        if not part_id:
            part_id = f'P{index + 1}'
        channel = allocate_channel(part_id)
        program = programs.get(part_id, OCARINA_GM_PROGRAM)
        channel_programs.setdefault(channel, program if use_original_instruments else OCARINA_GM_PROGRAM)
        voice_cursor: dict[str, int] = {}
        voice_onset: dict[str, int] = {}
        for measure in part.findall(q('measure')):
            for note in measure.findall(q('note')):
                voice_el = note.find(q('voice'))
                voice = (voice_el.text.strip() if (voice_el is not None and voice_el.text) else '1')
                dur_el = note.find(q('duration'))
                dur_text = (dur_el.text or '').strip() if dur_el is not None and dur_el.text else ''
                dur_div = int(dur_text) if dur_text.isdigit() else 0
                dur_div = max(1, dur_div)
                is_chord = note.find(q('chord')) is not None
                is_rest = note.find(q('rest')) is not None

                start_attr = note.get('data-start-div') or note.get('data-start')
                attr_onset: int | None = None
                if start_attr:
                    try:
                        attr_onset = int(start_attr)
                    except ValueError:
                        attr_onset = None

                if attr_onset is not None:
                    onset_div = attr_onset
                elif is_chord:
                    onset_div = voice_onset.get(voice, voice_cursor.get(voice, 0))
                else:
                    onset_div = voice_cursor.get(voice, 0)

                if not is_rest:
                    pitch_el = note.find(q('pitch'))
                    if pitch_el is None:
                        continue
                    step_el = pitch_el.find(q('step'))
                    octave_el = pitch_el.find(q('octave'))
                    if step_el is None or octave_el is None or step_el.text is None or octave_el.text is None:
                        continue
                    step = step_el.text.strip()
                    alter_el = pitch_el.find(q('alter'))
                    alter = int(alter_el.text.strip()) if (alter_el is not None and alter_el.text) else 0
                    octave = int(octave_el.text.strip())
                    midi = pitch_to_midi(step, alter, octave)
                    onset_ticks = int(onset_div)
                    dur_ticks = int(dur_div)
                    events.append((onset_ticks, 1, midi, 96, channel))
                    events.append((onset_ticks + max(1, dur_ticks), 0, midi, 64, channel))
                    voice_onset[voice] = onset_div

                if not is_chord:
                    next_cursor = onset_div + dur_div
                    if attr_onset is not None:
                        next_cursor = attr_onset + dur_div
                    voice_cursor[voice] = max(voice_cursor.get(voice, 0), next_cursor)
                    if is_rest:
                        voice_onset.pop(voice, None)
                elif attr_onset is not None:
                    voice_onset[voice] = attr_onset

    events.sort(key=lambda item: (item[0], item[1], item[4], item[2]))

    track = bytearray()
    microseconds_per_quarter = int(60000000 // max(1, int(tempo_bpm)))
    track += b'\x00' + b'\xff\x51\x03' + struct.pack('>I', microseconds_per_quarter)[1:]
    for channel in sorted(channel_programs):
        program = channel_programs[channel]
        track += b'\x00' + bytes([(0xC0 | (channel & 0x0F)), program & 0x7F])

    last_tick = 0
    for tick, kind, midi, velocity, channel in events:
        delta = tick - last_tick
        last_tick = tick
        track += varlen(max(0, delta))
        status = (0x80 if kind == 0 else 0x90) | (channel & 0x0F)
        track += bytes([status, midi & 0x7F, velocity & 0x7F])

    track += b'\x00\xff\x2f\x00'
    header = b'MThd' + struct.pack('>IHHH', 6, 0, 1, ppq)
    track_chunk = b'MTrk' + struct.pack('>I', len(track)) + bytes(track)
    with open(out_path, 'wb') as handle:
        handle.write(header)
        handle.write(track_chunk)
__all__ = [
    'export_midi',
    'export_midi_poly',
    'export_musicxml',
    'export_mxl',
]

