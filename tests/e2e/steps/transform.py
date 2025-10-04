from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from ocarina_gui.preview import PreviewData

from tests.e2e.harness import E2EHarness


def _sample_preview() -> PreviewData:
    return PreviewData(
        original_events=[(0, 480, 60, 1)],
        arranged_events=[(0, 480, 72, 1)],
        pulses_per_quarter=480,
        beats=4,
        beat_type=4,
        original_range=(60, 72),
        arranged_range=(72, 84),
        tempo_bpm=110,
    )


@given("another preview result is queued")
def queue_additional_preview(arranger_app: E2EHarness) -> None:
    arranger_app.queue_preview_result(_sample_preview())


@when(parsers.parse("the user modifies the transpose offset to {semitones:d}"))
def modify_transpose_value(arranger_app: E2EHarness, semitones: int) -> None:
    arranger_app.window.transpose_offset.set(semitones)


@when(parsers.parse("the user applies a transpose offset of {semitones:d}"))
def apply_transpose(arranger_app: E2EHarness, semitones: int) -> None:
    arrange_window = arranger_app.window
    arrange_window.transpose_offset.set(semitones)
    arrange_window._apply_transpose_offset()


@when("the user cancels the transpose change")
def cancel_transpose(arranger_app: E2EHarness) -> None:
    arranger_app.window._cancel_transpose_offset()


@when(parsers.parse('the user switches the fingering instrument to "{instrument_id}"'))
def switch_instrument(arranger_app: E2EHarness, instrument_id: str) -> None:
    arranger_app.window.set_fingering_instrument(instrument_id)


@then(parsers.parse("the transpose offset is {semitones:d}"))
def assert_transpose(arranger_app: E2EHarness, semitones: int) -> None:
    assert arranger_app.viewmodel.state.transpose_offset == semitones


@then(parsers.parse("the arranger instrument is {instrument_id}"))
def assert_instrument(arranger_app: E2EHarness, instrument_id: str) -> None:
    assert arranger_app.viewmodel.state.instrument_id == instrument_id


@then(parsers.parse("the arranged range spans {min_note} to {max_note}"))
def assert_range(arranger_app: E2EHarness, min_note: str, max_note: str) -> None:
    assert arranger_app.viewmodel.state.range_min == min_note
    assert arranger_app.viewmodel.state.range_max == max_note

