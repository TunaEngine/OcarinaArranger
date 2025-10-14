from __future__ import annotations

from ocarina_gui import audio

from .helpers import CountingPlayer, FailingPlayer


def test_failover_player_falls_back_when_first_player_fails() -> None:
    failing = FailingPlayer()
    succeeding = CountingPlayer()
    player = audio._FailoverPlayer([failing, succeeding])

    player.play(b"pcm", 22050)

    assert failing.play_calls == 1
    assert succeeding.play_calls == 1
    assert failing.stop_all_calls >= 1

    # Second play should no longer call the failing backend once it has been dropped.
    player.play(b"pcm", 22050)

    assert failing.play_calls == 1
    assert succeeding.play_calls == 2


def test_failover_player_stop_all_cascades() -> None:
    first = CountingPlayer()
    second = CountingPlayer()
    player = audio._FailoverPlayer([first, second])

    player.stop_all()

    assert first.stop_all_calls == 1
    assert second.stop_all_calls == 1
