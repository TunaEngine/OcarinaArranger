"""Helpers for identifying likely melody parts in a score."""

from __future__ import annotations

from collections.abc import Sequence

from ocarina_tools.parts import MusicXmlPartInfo


def select_melody_candidate(parts: Sequence[MusicXmlPartInfo]) -> str | None:
    """Return the part identifier that most likely represents the melody."""

    parts_list = list(parts)
    if not parts_list:
        return None

    keyword_priorities: dict[str, int] = {
        "melody": 5,
        "lead": 4,
        "vocal": 4,
        "voice": 4,
        "soprano": 4,
        "solo": 3,
        "singer": 3,
        "ocarina": 3,
        "flute": 2,
        "violin": 2,
    }

    def _keyword_score(name: str) -> int:
        lowered = name.lower()
        return max(
            (score for keyword, score in keyword_priorities.items() if keyword in lowered),
            default=0,
        )

    def _pitch_center(part: MusicXmlPartInfo) -> int:
        if part.min_midi is not None and part.max_midi is not None:
            return (part.min_midi + part.max_midi) // 2
        if part.max_midi is not None:
            return part.max_midi
        if part.min_midi is not None:
            return part.min_midi
        return -1

    def _top_pitch(part: MusicXmlPartInfo) -> int:
        if part.max_midi is not None:
            return part.max_midi
        if part.min_midi is not None:
            return part.min_midi
        return -1

    def _range_score(part: MusicXmlPartInfo) -> int:
        if part.min_midi is not None and part.max_midi is not None:
            return -(part.max_midi - part.min_midi)
        return -1000

    def _activity_bucket(part: MusicXmlPartInfo) -> int:
        if part.note_count >= 64:
            return 2
        if part.note_count >= 16:
            return 1
        if part.note_count > 0:
            return 0
        return -1

    def _part_sort_key(entry: tuple[int, MusicXmlPartInfo]) -> tuple[int, int, int, int, int, int]:
        index, part = entry
        return (
            _keyword_score(part.name or ""),
            _activity_bucket(part),
            _pitch_center(part),
            _top_pitch(part),
            _range_score(part),
            -index,
        )

    _best_index, best_part = max(
        enumerate(parts_list),
        key=_part_sort_key,
    )

    if (
        best_part.note_count == 0
        and not best_part.name
        and (best_part.max_midi is None or best_part.max_midi < 0)
    ):
        return parts_list[0].part_id

    return best_part.part_id


__all__ = ["select_melody_candidate"]

