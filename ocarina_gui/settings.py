"""Dataclasses representing GUI transform settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Tuple

from domain.arrangement.config import (
    GraceSettings as DomainGraceSettings,
    FAST_WINDWAY_SWITCH_WEIGHT_MAX,
)
from domain.arrangement.constraints import (
    SubholeConstraintSettings as DomainSubholeConstraintSettings,
    SubholePairLimit,
)
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
    fast_windway_switch_weight: float = 0.6

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

        try:
            fast_windway_switch_weight = float(self.fast_windway_switch_weight)
        except (TypeError, ValueError):
            fast_windway_switch_weight = 0.6
        if fast_windway_switch_weight < 0.0:
            fast_windway_switch_weight = 0.0
        if fast_windway_switch_weight > FAST_WINDWAY_SWITCH_WEIGHT_MAX:
            fast_windway_switch_weight = FAST_WINDWAY_SWITCH_WEIGHT_MAX

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
            fast_windway_switch_weight=fast_windway_switch_weight,
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
            fast_windway_switch_weight=normalized.fast_windway_switch_weight,
        )


def _normalize_positive_float(value: object, fallback: float, *, minimum: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return fallback
    if numeric < minimum:
        return fallback
    return numeric


@dataclass(frozen=True)
class SubholeTransformSettings:
    """GUI-level subhole comfort configuration for arranger transforms."""

    max_changes_per_second: float = 6.0
    max_subhole_changes_per_second: float = 4.0
    pair_limits: tuple[tuple[int, int, float, float], ...] = ()

    def normalized(self) -> "SubholeTransformSettings":
        max_changes = _normalize_positive_float(
            self.max_changes_per_second, 6.0, minimum=0.01
        )
        max_subhole_changes = _normalize_positive_float(
            self.max_subhole_changes_per_second, 4.0, minimum=0.01
        )

        normalized_pairs: dict[frozenset[int], tuple[int, int, float, float]] = {}
        for entry in self.pair_limits:
            first: int | None = None
            second: int | None = None
            max_hz: float | None = None
            ease: float | None = None

            if isinstance(entry, Mapping):
                pair = entry.get("pair") or entry.get("pitches")
                if isinstance(pair, (list, tuple)) and len(pair) == 2:
                    try:
                        first = int(pair[0])
                        second = int(pair[1])
                    except (TypeError, ValueError):
                        first = second = None
                else:
                    try:
                        first = int(entry.get("first"))
                        second = int(entry.get("second"))
                    except (TypeError, ValueError):
                        first = second = None
                max_hz_value = entry.get("max_hz")
                ease_value = entry.get("ease")
            else:
                values = tuple(entry) if isinstance(entry, Iterable) else ()
                if len(values) >= 3:
                    try:
                        first = int(values[0])
                        second = int(values[1])
                    except (TypeError, ValueError):
                        first = second = None
                    max_hz_value = values[2]
                    ease_value = values[3] if len(values) > 3 else None
                else:
                    max_hz_value = None
                    ease_value = None

            try:
                max_hz = float(max_hz_value) if max_hz_value is not None else None
            except (TypeError, ValueError):
                max_hz = None

            try:
                ease = float(ease_value) if ease_value is not None else None
            except (TypeError, ValueError):
                ease = None

            if first is None or second is None or first == second or max_hz is None:
                continue
            if max_hz <= 0:
                continue
            if ease is None or ease < 0:
                ease = 1.0

            ordered = tuple(sorted((first, second)))
            normalized_pairs[frozenset(ordered)] = (ordered[0], ordered[1], max_hz, ease)

        normalized_tuple = tuple(normalized_pairs.values())

        return SubholeTransformSettings(
            max_changes_per_second=max_changes,
            max_subhole_changes_per_second=max_subhole_changes,
            pair_limits=normalized_tuple,
        )

    def to_domain(
        self,
        base: DomainSubholeConstraintSettings | None = None,
    ) -> DomainSubholeConstraintSettings:
        normalized = self.normalized()
        if base is None:
            pair_limits: dict[frozenset[int], SubholePairLimit] = {}
            alternate = {}
        else:
            pair_limits = dict(base.pair_limits)
            alternate = dict(base.alternate_fingerings)

        for first, second, max_hz, ease in normalized.pair_limits:
            pair = frozenset({first, second})
            existing_limit = pair_limits.get(pair)
            baseline_ease = existing_limit.ease if isinstance(existing_limit, SubholePairLimit) else 1.0
            effective_ease = ease if ease is not None else baseline_ease
            pair_limits[pair] = SubholePairLimit(max_hz=max_hz, ease=effective_ease)

        return DomainSubholeConstraintSettings(
            max_changes_per_second=normalized.max_changes_per_second,
            max_subhole_changes_per_second=normalized.max_subhole_changes_per_second,
            pair_limits=pair_limits,
            alternate_fingerings=alternate,
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
    subhole_settings: SubholeTransformSettings = SubholeTransformSettings()
    lenient_midi_import: bool = True


__all__ = [
    "GraceTransformSettings",
    "SubholeTransformSettings",
    "TransformSettings",
]
