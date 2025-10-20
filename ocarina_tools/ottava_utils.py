from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Tuple
import xml.etree.ElementTree as ET

from shared.ottava import OttavaShift


__all__ = [
    "_parse_size",
    "_resolve_direction_voices",
    "_pop_ottava",
    "_active_shifts",
    "_total_shift",
    "_handle_direction_octaves",
    "_extract_note_ottavas",
]


def _parse_size(value: str | None) -> int:
    if value is None:
        return 8
    try:
        return max(1, int(float(value.strip())))
    except (TypeError, ValueError, AttributeError):
        return 8


def _resolve_direction_voices(direction: ET.Element, q, voice_pos: dict[str, int]) -> list[str]:
    voice_el = direction.find(q("voice"))
    if voice_el is not None and voice_el.text and voice_el.text.strip():
        return [voice_el.text.strip()]
    if voice_pos:
        return list(voice_pos.keys())
    return ["1"]


def _pop_ottava(stack: list[tuple[OttavaShift, str | None]], number: str | None) -> None:
    if not stack:
        return
    if number is None:
        stack.pop()
        return
    for idx in range(len(stack) - 1, -1, -1):
        _, current = stack[idx]
        if current == number:
            stack.pop(idx)
            return
    stack.pop()


def _active_shifts(stack: list[tuple[OttavaShift, str | None]]) -> Tuple[OttavaShift, ...]:
    return tuple(shift for shift, _ in stack)


def _total_shift(stack: list[tuple[OttavaShift, str | None]]) -> int:
    return sum(shift.semitones for shift, _ in stack)


def _handle_direction_octaves(
    direction: ET.Element,
    q,
    voice_ottavas: defaultdict[str, list[tuple[OttavaShift, str | None]]],
    voice_pos: dict[str, int],
) -> None:
    direction_type = direction.find(q("direction-type"))
    if direction_type is None:
        return
    voices = _resolve_direction_voices(direction, q, voice_pos)
    for shift_el in direction_type.findall(q("octave-shift")):
        shift_type = (shift_el.get("type") or "").strip().lower()
        number = (shift_el.get("number") or "").strip() or None
        if shift_type in {"up", "down"}:
            size = _parse_size(shift_el.get("size"))
            shift = OttavaShift(
                source="octave-shift",
                direction="up" if shift_type == "up" else "down",
                size=size,
                number=number,
            )
            for voice in voices:
                voice_ottavas[voice].append((shift, number))
        elif shift_type == "stop":
            for voice in voices:
                _pop_ottava(voice_ottavas[voice], number)


def _extract_note_ottavas(note: ET.Element, q) -> tuple[list[OttavaShift], list[str | None]]:
    starts: list[OttavaShift] = []
    stops: list[str | None] = []
    for notation in note.findall(q("notations")):
        for technical in notation.findall(q("technical")):
            for ottava_el in technical.findall(q("ottava")):
                ott_type = (ottava_el.get("type") or "").strip().lower()
                number = (ottava_el.get("number") or "").strip() or None
                if ott_type in {"up", "down"}:
                    size = _parse_size(ottava_el.get("size"))
                    starts.append(
                        OttavaShift(
                            source="ottava",
                            direction="up" if ott_type == "up" else "down",
                            size=size,
                            number=number,
                        )
                    )
                elif ott_type == "stop":
                    stops.append(number)
    return starts, stops
