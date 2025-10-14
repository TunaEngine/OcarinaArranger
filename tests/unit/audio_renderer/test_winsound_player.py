from __future__ import annotations

from pathlib import Path

from ocarina_gui import audio

from .helpers import FakeWinsound


def test_winsound_player_writes_wave_file_and_stops(monkeypatch) -> None:
    fake = FakeWinsound()
    monkeypatch.setattr(audio, "winsound", fake)
    player = audio._WinsoundPlayer()

    pcm = (b"\x00\x01" * 2000)
    handle = player.play(pcm, 22050)

    assert handle is not None
    assert fake.calls, "winsound should be invoked"
    path_str, flags = fake.calls[0]
    assert path_str is not None
    wave_path = Path(path_str)
    assert wave_path.exists()
    assert flags & fake.SND_FILENAME

    handle.stop()

    assert fake.calls[-1] == (None, fake.SND_PURGE)
    assert not wave_path.exists()


def test_winsound_player_stop_all_silences_handles(monkeypatch) -> None:
    fake = FakeWinsound()
    monkeypatch.setattr(audio, "winsound", fake)
    player = audio._WinsoundPlayer()

    pcm = (b"\x00\x01" * 500)
    handle = player.play(pcm, 22050)

    assert handle is not None
    player.stop_all()

    assert fake.calls[-1] == (None, fake.SND_PURGE)
