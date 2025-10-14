"""Dataclasses representing GUI transform settings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TransformSettings:
    prefer_mode: str
    range_min: str
    range_max: str
    prefer_flats: bool
    collapse_chords: bool
    favor_lower: bool
    transpose_offset: int = 0
    instrument_id: str = ""
    selected_part_ids: tuple[str, ...] = ()
