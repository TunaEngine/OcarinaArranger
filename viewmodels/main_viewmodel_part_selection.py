"""Helpers for normalising MusicXML part metadata and selections."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ocarina_tools.parts import MusicXmlPartInfo


def normalize_available_parts(
    available_parts: Iterable[MusicXmlPartInfo | Mapping[str, Any]]
) -> tuple[MusicXmlPartInfo, ...]:
    """Coerce arbitrary part metadata into deterministic ``MusicXmlPartInfo`` values."""

    normalized_parts: list[MusicXmlPartInfo] = []
    seen_ids: set[str] = set()

    def _coerce_optional_int(value: object) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _coerce_count(value: object) -> int:
        maybe = _coerce_optional_int(value)
        if maybe is None:
            return 0
        return max(0, maybe)

    def _coerce_pitch(value: object) -> str | None:
        if value in (None, ""):
            return None
        text = str(value).strip()
        return text or None

    def _get(entry: MusicXmlPartInfo | Mapping[str, Any], key: str) -> Any:
        if isinstance(entry, Mapping):
            return entry.get(key)
        return getattr(entry, key, None)

    for entry in available_parts:
        if not isinstance(entry, (MusicXmlPartInfo, Mapping)):
            continue
        part_id = str(_get(entry, "part_id") or "").strip()
        if not part_id or part_id in seen_ids:
            continue
        seen_ids.add(part_id)
        normalized_parts.append(
            MusicXmlPartInfo(
                part_id=part_id,
                name=str(_get(entry, "name") or "").strip(),
                midi_program=_coerce_optional_int(_get(entry, "midi_program")),
                note_count=_coerce_count(_get(entry, "note_count")),
                min_midi=_coerce_optional_int(_get(entry, "min_midi")),
                max_midi=_coerce_optional_int(_get(entry, "max_midi")),
                min_pitch=_coerce_pitch(_get(entry, "min_pitch")),
                max_pitch=_coerce_pitch(_get(entry, "max_pitch")),
            )
        )
    return tuple(normalized_parts)


def normalize_selected_part_ids(
    selected_part_ids: Iterable[str | Any],
    allowed_part_ids: Iterable[str] | None = None,
) -> tuple[str, ...]:
    """Sanitize a collection of part identifiers for storage in view-model state."""

    allowed_set = set(allowed_part_ids) if allowed_part_ids is not None else None
    ordered_parts: list[str] = []
    seen_parts: set[str] = set()

    for identifier in selected_part_ids:
        if not isinstance(identifier, str):
            identifier = str(identifier)
        cleaned = identifier.strip()
        if not cleaned or cleaned in seen_parts:
            continue
        if allowed_set is not None and cleaned not in allowed_set:
            continue
        seen_parts.add(cleaned)
        ordered_parts.append(cleaned)
    return tuple(ordered_parts)

