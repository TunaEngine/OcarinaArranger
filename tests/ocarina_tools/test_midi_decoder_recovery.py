"""Regression coverage for lenient MIDI decoder recovery paths."""
from __future__ import annotations

import pytest

from ocarina_tools.midi_import.decoders import LenientMidiDecoder, StrictMidiDecoder
from ocarina_tools.midi_import.streams import SafeStream


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(bytes([0xFF, 0xFF, 0xFF, 0xFF]), id="exactly-four"),
        pytest.param(bytes([0xFF, 0xFF, 0xFF, 0xFF, 0x7F]), id="with-terminator"),
    ],
)
def test_safe_stream_rejects_overlong_vlq(data: bytes) -> None:
    stream = SafeStream(data)
    with pytest.raises(ValueError, match="Variable-length quantity"):
        stream.read_varlen()


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(bytes([0xFF, 0xFF, 0xFF, 0xFF, 0x7F]), id="allow-partial"),
    ],
)
def test_safe_stream_truncates_overlong_vlq_when_allowed(data: bytes) -> None:
    stream = SafeStream(data)
    value = stream.read_varlen(allow_partial=True)
    # Ensure we advanced through the bytes even though they exceeded the max length.
    assert stream.tell() == 4
    assert stream.read_up_to(1) == b"\x7f"
    assert value >= 0


def test_strict_decoder_rejects_overlong_vlq_delta_time() -> None:
    track = bytes(
        [
            0xFF,
            0xFF,
            0xFF,
            0xFF,  # delta-time that exceeds four-byte VLQ limit
            0x90,
            0x3C,
            0x40,
        ]
    )

    with pytest.raises(ValueError, match="Variable-length quantity"):
        StrictMidiDecoder.decode(track)


def test_lenient_decoder_reports_truncated_note_payload() -> None:
    # Missing velocity byte should be reported as a truncated note event.
    track = bytes(
        [
            0x00, 0x90, 0x3C,  # note-on status + key without velocity
            0x00, 0xFF, 0x2F, 0x00,  # end-of-track so the decoder stops cleanly
        ]
    )

    result = LenientMidiDecoder.decode_with_report(track, track_index=2)

    assert result.events == []
    assert any(
        issue.detail == "Truncated note event" and issue.track_index == 2
        for issue in result.issues
    )
    assert result.synthetic_eot


def test_lenient_decoder_reports_truncated_meta_payload() -> None:
    track = bytes(
        [
            0x00,
            0xFF,
            0x03,
            0x04,  # claims four bytes of track-name payload, only one follows
            0x41,
        ]
    )

    result = LenientMidiDecoder.decode_with_report(track, track_index=4)

    assert result.events == []
    assert any("Truncated meta payload" == issue.detail for issue in result.issues)
    assert result.synthetic_eot


def test_lenient_decoder_reports_truncated_sysex_payload() -> None:
    track = bytes(
        [
            0x00,
            0xF0,
            0x04,  # claims four bytes of payload, only two follow
            0x7D,
            0x10,
        ]
    )

    result = LenientMidiDecoder.decode_with_report(track, track_index=5)

    assert result.events == []
    assert any("Truncated sysex payload" == issue.detail for issue in result.issues)
    assert result.synthetic_eot


def test_lenient_decoder_recovers_running_status_after_stray_data() -> None:
    track = bytes(
        [
            0x00,
            0x40,  # stray data without running status
            0x00,
            0x90,
            0x3C,
            0x40,
            0x81,
            0x00,
            0x3C,
            0x00,  # running-status note-off
            0x00,
            0xFF,
            0x2F,
            0x00,
        ]
    )

    result = LenientMidiDecoder.decode_with_report(track, track_index=1)

    assert result.events == [(0, 0x80, 0x3C, 0x00)]
    assert any(
        "Ignored data byte" in issue.detail and issue.track_index == 1
        for issue in result.issues
    )
    assert not result.synthetic_eot


def test_lenient_decoder_ignores_trailing_junk_after_end_of_track() -> None:
    track = bytes(
        [
            0x00,
            0x90,
            0x3C,
            0x40,
            0x20,
            0x80,
            0x3C,
            0x00,
            0x00,
            0xFF,
            0x2F,
            0x00,
            0x7F,
            0x7F,
            0x7F,
        ]
    )

    result = LenientMidiDecoder.decode_with_report(track)

    assert result.events == [(0, 0x20, 0x3C, 0x00)]
    assert result.issues == ()
    assert not result.synthetic_eot


def test_strict_decoder_collects_tempo_meta_events() -> None:
    track = bytes(
        [
            0x00,
            0xFF,
            0x51,
            0x03,
            0x09,
            0x27,
            0xC0,  # 100 BPM
            0x00,
            0xFF,
            0x2F,
            0x00,
        ]
    )

    events, programs, tempos = StrictMidiDecoder.decode(track)

    assert events == []
    assert programs == {}
    assert len(tempos) == 1
    tick, tempo = tempos[0]
    assert tick == 0
    assert tempo == pytest.approx(100.0)


def test_lenient_decoder_collects_tempo_meta_events() -> None:
    track = bytes(
        [
            0x00,
            0x40,  # stray data forcing lenient recovery
            0x00,
            0xFF,
            0x51,
            0x03,
            0x08,
            0x52,
            0xAF,  # 110 BPM
            0x83,
            0x60,
            0xFF,
            0x51,
            0x03,
            0x0B,
            0x71,
            0xB0,  # 80 BPM
            0x00,
            0xFF,
            0x2F,
            0x00,
        ]
    )

    result = LenientMidiDecoder.decode_with_report(track)

    assert [round(change[1]) for change in result.tempo_changes] == [110, 80]
    assert any("Ignored data byte" in issue.detail for issue in result.issues)
