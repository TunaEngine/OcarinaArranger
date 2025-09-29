"""Simple audio renderer used by preview playback."""
from __future__ import annotations

import logging

from viewmodels.preview_playback_viewmodel import (
    AudioRenderer,
    NullAudioRenderer,
)

from .deps import simpleaudio, winsound
from .players import (
    _AudioPlayer,
    _CommandHandle,
    _CommandPlayer,
    _FailoverPlayer,
    _PlaybackHandle,
    _SimpleAudioHandle,
    _SimpleAudioPlayer,
    _WinsoundHandle,
    _WinsoundPlayer,
    _build_wave_bytes,
    _select_player,
)
from .synth import (
    Event,
    _SynthPatch,
    _SynthRenderer,
    _patch_for_program,
    _midi_to_frequency,
)

logger = logging.getLogger(__name__)

_warned_backend_missing = False


def build_preview_audio_renderer() -> AudioRenderer:
    """Return an audio renderer for preview playback."""
    global _warned_backend_missing
    player = _select_player()
    if player is None:  # pragma: no cover - exercised only without any backend
        if not _warned_backend_missing:
            logger.warning("No audio backend available; preview playback will be silent")
            _warned_backend_missing = True
        return NullAudioRenderer()
    return _SynthRenderer(player)


__all__ = ["build_preview_audio_renderer"]
