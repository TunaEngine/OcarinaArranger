import pytest

from shared.tempo import (
    TempoChange,
    first_tempo,
    normalized_tempo_changes,
    scaled_tempo_changes,
    scaled_tempo_markings,
    scaled_tempo_values,
    slowest_tempo,
)


def test_scaled_tempo_values_scale_relative_to_slowest() -> None:
    changes = (
        TempoChange(tick=0, tempo_bpm=180.0),
        TempoChange(tick=480, tempo_bpm=120.0),
        TempoChange(tick=960, tempo_bpm=210.0),
    )

    values = scaled_tempo_values(changes, 90.0)

    assert values == pytest.approx((90.0, 60.0, 105.0))


def test_scaled_tempo_markings_deduplicate_consecutive_values() -> None:
    changes = (
        TempoChange(tick=0, tempo_bpm=120.0),
        TempoChange(tick=240, tempo_bpm=120.0),
        TempoChange(tick=480, tempo_bpm=180.0),
    )

    markings = scaled_tempo_markings(changes, 120.0)

    assert markings == ("♩ = 120", "♩ = 180")


def test_scaled_tempo_changes_align_with_markings() -> None:
    changes = (
        TempoChange(tick=0, tempo_bpm=180.0),
        TempoChange(tick=480, tempo_bpm=120.0),
        TempoChange(tick=960, tempo_bpm=210.0),
    )

    scaled_changes = scaled_tempo_changes(changes, 90.0)
    markings = scaled_tempo_markings(changes, 90.0)

    assert [change.tick for change in scaled_changes] == [0, 480, 960]
    assert [change.tempo_bpm for change in scaled_changes] == pytest.approx(
        [90.0, 60.0, 105.0]
    )
    assert list(markings) == ["♩ = 90", "♩ = 60", "♩ = 105"]


def test_slowest_tempo_returns_default_when_missing() -> None:
    assert slowest_tempo((), default=96.0) == pytest.approx(96.0)

    changes = (
        TempoChange(tick=0, tempo_bpm=180.0),
        TempoChange(tick=480, tempo_bpm=90.0),
    )

    assert slowest_tempo(changes, default=120.0) == pytest.approx(90.0)


def test_first_tempo_prefers_initial_change() -> None:
    changes = (
        TempoChange(tick=480, tempo_bpm=100.0),
        TempoChange(tick=0, tempo_bpm=150.0),
    )

    assert first_tempo(changes, default=120.0) == pytest.approx(150.0)


def test_normalized_tempo_changes_scale_from_first() -> None:
    changes = (
        TempoChange(tick=0, tempo_bpm=120.0),
        TempoChange(tick=480, tempo_bpm=60.0),
    )

    normalized = normalized_tempo_changes(90.0, changes)
    assert [round(change.tempo_bpm, 6) for change in normalized] == pytest.approx(
        [90.0, 45.0]
    )
