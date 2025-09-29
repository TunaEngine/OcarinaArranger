"""Audio playback backend selection and handle management."""
from __future__ import annotations

import io
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Callable, Optional, Sequence

from .deps import simpleaudio as _deps_simpleaudio, winsound as _deps_winsound

logger = logging.getLogger(__name__)


class _PlaybackHandle:
    def stop(self) -> None:  # pragma: no cover - interface only
        raise NotImplementedError


class _AudioPlayer:
    def play(self, pcm: bytes, sample_rate: int) -> Optional[_PlaybackHandle]:  # pragma: no cover - interface only
        raise NotImplementedError

    def stop_all(self) -> None:  # pragma: no cover - interface only
        """Best-effort attempt to silence any playback started by this player."""
        raise NotImplementedError


class _SimpleAudioHandle(_PlaybackHandle):
    def __init__(self, play_obj) -> None:  # type: ignore[no-untyped-def]
        self._play_obj = play_obj

    def stop(self) -> None:
        play_obj = self._play_obj
        if play_obj is None:
            return
        try:
            play_obj.stop()
            try:
                play_obj.wait_done()
            except Exception:  # pragma: no cover - backend specific quirks
                logger.warning("simpleaudio wait_done failed", exc_info=True)
        except Exception:  # pragma: no cover - backend specific failures
            logger.warning("Failed stopping simpleaudio playback", exc_info=True)
        self._play_obj = None


def _current_audio_module():
    return sys.modules.get("ocarina_gui.audio")


def _current_simpleaudio():
    module = _current_audio_module()
    if module is not None and getattr(module, "simpleaudio", None) is not None:
        return getattr(module, "simpleaudio")
    return _deps_simpleaudio


def _current_winsound():
    module = _current_audio_module()
    if module is not None and getattr(module, "winsound", None) is not None:
        return getattr(module, "winsound")
    return _deps_winsound


class _SimpleAudioPlayer(_AudioPlayer):
    def play(self, pcm: bytes, sample_rate: int) -> Optional[_PlaybackHandle]:
        backend = _current_simpleaudio()
        if backend is None or not pcm:
            return None
        try:
            play_obj = backend.play_buffer(pcm, 1, 2, sample_rate)
        except Exception:  # pragma: no cover - backend errors
            logger.exception("simpleaudio playback failed")
            self.stop_all()
            return None
        return _SimpleAudioHandle(play_obj)

    def stop_all(self) -> None:
        backend = _current_simpleaudio()
        if backend is None:
            return
        try:
            backend.stop_all()
        except Exception:  # pragma: no cover - backend errors
            logger.warning("simpleaudio stop_all failed", exc_info=True)


class _WinsoundHandle(_PlaybackHandle):
    def __init__(
        self,
        wave_path: Path,
        duration_s: float,
        dispose_callback: Callable[["_WinsoundHandle"], None],
    ) -> None:
        self._wave_path = wave_path
        self._duration_s = max(0.0, duration_s)
        self._dispose_callback = dispose_callback
        self._lock = threading.Lock()
        self._cleaned = False
        threading.Thread(target=self._auto_cleanup, daemon=True).start()

    def stop(self) -> None:
        backend = _current_winsound()
        if backend is not None:
            try:
                backend.PlaySound(None, backend.SND_PURGE)  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - backend specific failures
                logger.warning("winsound stop failed", exc_info=True)
        self._cleanup()

    def _auto_cleanup(self) -> None:
        try:
            time.sleep(min(max(self._duration_s + 0.5, 0.5), 60.0))
        except Exception:  # pragma: no cover - platform specific sleep interruptions
            logger.warning("winsound cleanup sleep interrupted", exc_info=True)
        self._cleanup()

    def _cleanup(self) -> None:
        with self._lock:
            if self._cleaned:
                return
            self._cleaned = True
        try:
            if self._wave_path.exists():
                self._wave_path.unlink()
        except OSError:  # pragma: no cover - filesystem races
            pass
        finally:
            try:
                self._dispose_callback(self)
            except Exception:  # pragma: no cover - defensive cleanup
                logger.warning("winsound dispose callback failed", exc_info=True)


class _WinsoundPlayer(_AudioPlayer):
    def __init__(self) -> None:
        self._handles: set[_WinsoundHandle] = set()
        self._lock = threading.Lock()

    def play(self, pcm: bytes, sample_rate: int) -> Optional[_PlaybackHandle]:
        backend = _current_winsound()
        if backend is None or not pcm:
            return None
        wave_bytes = _build_wave_bytes(pcm, sample_rate)
        try:
            fd, tmp_path = tempfile.mkstemp(prefix="ocarina_preview_", suffix=".wav")
            with os.fdopen(fd, "wb") as handle:
                handle.write(wave_bytes)
        except OSError:  # pragma: no cover - filesystem errors
            logger.exception("Unable to write winsound wave file")
            return None

        wave_path = Path(tmp_path)
        duration_s = len(pcm) / max(sample_rate * 2, 1)
        handle = _WinsoundHandle(wave_path, duration_s, self._unregister_handle)
        self._register_handle(handle)
        try:
            backend.PlaySound(  # type: ignore[attr-defined]
                str(wave_path),
                backend.SND_FILENAME | backend.SND_ASYNC,  # type: ignore[attr-defined]
            )
        except Exception:  # pragma: no cover - backend errors
            logger.exception("winsound playback failed")
            handle.stop()
            return None
        return handle

    def stop_all(self) -> None:
        backend = _current_winsound()
        if backend is None:
            return
        with self._lock:
            handles = list(self._handles)
        for handle in handles:
            try:
                handle.stop()
            except Exception:  # pragma: no cover - backend specific failures
                logger.warning("winsound handle stop failed", exc_info=True)
        try:
            backend.PlaySound(None, backend.SND_PURGE)  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - backend specific failures
            logger.warning("winsound global stop failed", exc_info=True)

    def _register_handle(self, handle: _WinsoundHandle) -> None:
        with self._lock:
            self._handles.add(handle)

    def _unregister_handle(self, handle: _WinsoundHandle) -> None:
        with self._lock:
            self._handles.discard(handle)


class _CommandHandle(_PlaybackHandle):
    def __init__(self, process: subprocess.Popen[bytes], wave_path: Path) -> None:
        self._process = process
        self._wave_path = wave_path
        self._lock = threading.Lock()
        self._cleaned = False
        threading.Thread(target=self._wait_for_exit, daemon=True).start()

    def stop(self) -> None:
        proc = self._process
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:  # pragma: no cover - slow external command
                try:
                    proc.kill()
                except Exception:  # pragma: no cover - platform specific
                    pass
            except Exception:  # pragma: no cover - platform specific
                logger.warning("Audio command stop failed", exc_info=True)
        self._cleanup()

    def _wait_for_exit(self) -> None:
        try:
            self._process.wait()
        except Exception:  # pragma: no cover - platform specific
            logger.warning("Audio command wait failed", exc_info=True)
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        with self._lock:
            if self._cleaned:
                return
            self._cleaned = True
        try:
            if self._wave_path.exists():
                self._wave_path.unlink()
        except OSError:  # pragma: no cover - filesystem races
            pass


class _CommandPlayer(_AudioPlayer):
    def __init__(self, command: Sequence[str]) -> None:
        self._command = list(command)

    @classmethod
    def build(cls) -> Optional["_CommandPlayer"]:
        candidates = [
            ("afplay", []),
            ("aplay", ["-q"]),
            ("paplay", []),
            ("ffplay", ["-autoexit", "-nodisp", "-loglevel", "quiet"]),
        ]
        for executable, extra in candidates:
            path = shutil.which(executable)
            if path:
                return cls([path, *extra])
        return None

    def play(self, pcm: bytes, sample_rate: int) -> Optional[_PlaybackHandle]:
        if not pcm:
            return None
        wave_bytes = _build_wave_bytes(pcm, sample_rate)
        try:
            fd, tmp_path = tempfile.mkstemp(prefix="ocarina_preview_", suffix=".wav")
            with os.fdopen(fd, "wb") as handle:
                handle.write(wave_bytes)
        except OSError:  # pragma: no cover - filesystem errors
            logger.exception("Unable to write temporary audio file")
            return None
        try:
            process = subprocess.Popen(
                [*self._command, tmp_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:  # pragma: no cover - platform specific command failures
            logger.exception("Audio command launch failed")
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return None
        return _CommandHandle(process, Path(tmp_path))

    def stop_all(self) -> None:
        # No global stop mechanism; handled per-handle.
        return None


class _FailoverPlayer(_AudioPlayer):
    """Chain together multiple players and fall back if one fails."""

    def __init__(self, players: Sequence[_AudioPlayer]) -> None:
        self._players: list[_AudioPlayer] = list(players)

    def play(self, pcm: bytes, sample_rate: int) -> Optional[_PlaybackHandle]:
        if not self._players:
            return None

        for player in list(self._players):
            handle: Optional[_PlaybackHandle]
            try:
                handle = player.play(pcm, sample_rate)
            except Exception:  # pragma: no cover - backend specific failures
                logger.warning("Audio player raised", exc_info=True)
                handle = None

            if handle is not None:
                logger.debug("Audio player %s started playback", type(player).__name__)
                self._promote(player)
                return handle

            # Drop players that fail so we do not continually retry them.
            try:
                player.stop_all()
            except Exception:  # pragma: no cover - backend specific failures
                logger.warning("Audio player stop_all raised", exc_info=True)
            logger.debug("Audio player %s failed to start", type(player).__name__)
            self._remove(player)

        return None

    def stop_all(self) -> None:
        for player in list(self._players):
            try:
                player.stop_all()
            except Exception:  # pragma: no cover - backend specific failures
                logger.warning("Audio player stop_all raised", exc_info=True)

    def _promote(self, player: _AudioPlayer) -> None:
        self._players = [player, *[p for p in self._players if p is not player]]

    def _remove(self, player: _AudioPlayer) -> None:
        self._players = [p for p in self._players if p is not player]


def _select_player() -> Optional[_AudioPlayer]:
    candidates: list[_AudioPlayer] = []
    if _current_simpleaudio() is not None:
        candidates.append(_SimpleAudioPlayer())
    if sys.platform.startswith("win") and _current_winsound() is not None:
        candidates.append(_WinsoundPlayer())
    command_player = _CommandPlayer.build()
    if command_player is not None:
        candidates.append(command_player)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    return _FailoverPlayer(candidates)


def _build_wave_bytes(pcm: bytes, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm)
    return buffer.getvalue()


__all__ = [
    "_AudioPlayer",
    "_CommandHandle",
    "_CommandPlayer",
    "_FailoverPlayer",
    "_PlaybackHandle",
    "_SimpleAudioHandle",
    "_SimpleAudioPlayer",
    "_WinsoundHandle",
    "_WinsoundPlayer",
    "_build_wave_bytes",
    "_select_player",
]
