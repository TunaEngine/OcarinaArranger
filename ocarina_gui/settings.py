"""Dataclasses representing GUI transform settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

from domain.arrangement.config import GraceSettings as DomainGraceSettings
from ocarina_tools.events import GraceSettings as ImporterGraceSettings


def _normalize_bool(value: object, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        try:
            return bool(int(value))
        except (TypeError, ValueError):
            return fallback
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return fallback


def _normalize_fraction_sequence(values: Iterable[object], fallback: Tuple[float, ...]) -> tuple[float, ...]:
    normalized: list[float] = []
    for value in values:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric < 0.0:
            continue
        normalized.append(numeric)
    if not normalized:
        return fallback
    return tuple(normalized)


@dataclass(frozen=True)
class GraceTransformSettings:
    """GUI-level grace configuration shared by importer and arranger."""

    policy: str = "tempo-weighted"
    fractions: tuple[float, ...] = (0.125, 0.08333333333333333, 0.0625)
    max_chain: int = 3
    anchor_min_fraction: float = 0.25
    fold_out_of_range: bool = True
    drop_out_of_range: bool = True
    slow_tempo_bpm: float = 60.0
    fast_tempo_bpm: float = 132.0
    grace_bonus: float = 0.25

    def normalized(self) -> "GraceTransformSettings":
        policy = (self.policy or "tempo-weighted").strip().lower()
        if not policy:
            policy = "tempo-weighted"

        fractions = _normalize_fraction_sequence(
            self.fractions, (0.125, 0.08333333333333333, 0.0625)
        )

        try:
            max_chain = int(self.max_chain)
        except (TypeError, ValueError):
            max_chain = 3
        if max_chain < 0:
            max_chain = 0

        try:
            anchor_min_fraction = float(self.anchor_min_fraction)
        except (TypeError, ValueError):
            anchor_min_fraction = 0.25
        if anchor_min_fraction < 0.0:
            anchor_min_fraction = 0.0
        if anchor_min_fraction > 1.0:
            anchor_min_fraction = 1.0

        fold_out_of_range = _normalize_bool(self.fold_out_of_range, True)
        drop_out_of_range = _normalize_bool(self.drop_out_of_range, True)

        try:
            slow_tempo_bpm = float(self.slow_tempo_bpm)
        except (TypeError, ValueError):
            slow_tempo_bpm = 60.0
        if slow_tempo_bpm < 1.0:
            slow_tempo_bpm = 1.0

        try:
            fast_tempo_bpm = float(self.fast_tempo_bpm)
        except (TypeError, ValueError):
            fast_tempo_bpm = 132.0
        if fast_tempo_bpm < slow_tempo_bpm:
            fast_tempo_bpm = slow_tempo_bpm

        try:
            grace_bonus = float(self.grace_bonus)
        except (TypeError, ValueError):
            grace_bonus = 0.25
        if grace_bonus < 0.0:
            grace_bonus = 0.0
        if grace_bonus > 1.0:
            grace_bonus = 1.0

        return GraceTransformSettings(
            policy=policy,
            fractions=fractions,
            max_chain=max_chain,
            anchor_min_fraction=anchor_min_fraction,
            fold_out_of_range=fold_out_of_range,
            drop_out_of_range=drop_out_of_range,
            slow_tempo_bpm=slow_tempo_bpm,
            fast_tempo_bpm=fast_tempo_bpm,
            grace_bonus=grace_bonus,
        )

    def to_importer(self) -> ImporterGraceSettings:
        normalized = self.normalized()
        return ImporterGraceSettings(
            policy=normalized.policy,
            fractions=normalized.fractions,
            max_chain=normalized.max_chain,
            fold_out_of_range=normalized.fold_out_of_range,
            drop_out_of_range=normalized.drop_out_of_range,
            slow_tempo_bpm=normalized.slow_tempo_bpm,
            fast_tempo_bpm=normalized.fast_tempo_bpm,
        )

    def to_domain(self) -> DomainGraceSettings:
        normalized = self.normalized()
        return DomainGraceSettings(
            policy=normalized.policy,
            fractions=normalized.fractions,
            max_chain=normalized.max_chain,
            anchor_min_fraction=normalized.anchor_min_fraction,
            fold_out_of_range=normalized.fold_out_of_range,
            drop_out_of_range=normalized.drop_out_of_range,
            slow_tempo_bpm=normalized.slow_tempo_bpm,
            fast_tempo_bpm=normalized.fast_tempo_bpm,
            grace_bonus=normalized.grace_bonus,
        )


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
    grace_settings: GraceTransformSettings = GraceTransformSettings()


__all__ = [
    "GraceTransformSettings",
    "TransformSettings",
]
