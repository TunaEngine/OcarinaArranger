"""Synth patch definitions and lookup utilities."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class _SynthPatch:
    harmonics: tuple[tuple[float, float], ...]
    attack_ratio: float = 0.02
    release_ratio: float = 0.1
    gain: float = 1.0
    vibrato_hz: float = 0.0
    vibrato_depth: float = 0.0


_DEFAULT_PATCH = _SynthPatch(harmonics=((1.0, 1.0),))
_PIANO_PATCH = _SynthPatch(
    harmonics=((1.0, 1.0), (2.0, 0.35), (3.0, 0.2)), attack_ratio=0.01, release_ratio=0.35, gain=1.1
)
_MALLET_PATCH = _SynthPatch(
    harmonics=((1.0, 1.0), (2.0, 0.6), (3.0, 0.3)), attack_ratio=0.005, release_ratio=0.25, gain=1.0
)
_ORGAN_PATCH = _SynthPatch(
    harmonics=((1.0, 1.0), (2.0, 0.9), (3.0, 0.7), (4.0, 0.5)), attack_ratio=0.02, release_ratio=0.08, gain=0.9
)
_GUITAR_PATCH = _SynthPatch(
    harmonics=((1.0, 1.0), (2.0, 0.55), (3.0, 0.25)), attack_ratio=0.01, release_ratio=0.28, gain=0.9
)
_BASS_PATCH = _SynthPatch(
    harmonics=((1.0, 1.0), (2.0, 0.4), (3.0, 0.15)), attack_ratio=0.02, release_ratio=0.22, gain=1.0
)
_STRINGS_PATCH = _SynthPatch(
    harmonics=((1.0, 0.9), (2.0, 0.45), (3.0, 0.2)),
    attack_ratio=0.08,
    release_ratio=0.35,
    gain=0.95,
    vibrato_hz=5.0,
    vibrato_depth=0.003,
)
_BRASS_PATCH = _SynthPatch(
    harmonics=((1.0, 1.0), (2.0, 0.6), (3.0, 0.3)), attack_ratio=0.04, release_ratio=0.28, gain=1.05
)
_REED_PATCH = _SynthPatch(
    harmonics=((1.0, 1.0), (2.0, 0.5), (3.0, 0.25)),
    attack_ratio=0.05,
    release_ratio=0.25,
    gain=0.95,
    vibrato_hz=5.5,
    vibrato_depth=0.004,
)
_FLUTE_PATCH = _SynthPatch(
    harmonics=((1.0, 1.0), (2.0, 0.12)),
    attack_ratio=0.03,
    release_ratio=0.18,
    gain=0.9,
    vibrato_hz=5.5,
    vibrato_depth=0.006,
)
_SYNTH_LEAD_PATCH = _SynthPatch(
    harmonics=((1.0, 1.0), (2.0, 0.7), (3.0, 0.5), (4.0, 0.3)), attack_ratio=0.01, release_ratio=0.12, gain=1.0
)
_SYNTH_PAD_PATCH = _SynthPatch(
    harmonics=((1.0, 1.0), (2.0, 0.7), (3.0, 0.4)),
    attack_ratio=0.08,
    release_ratio=0.45,
    gain=1.0,
    vibrato_hz=4.0,
    vibrato_depth=0.005,
)
_PLUCKED_PATCH = _SynthPatch(
    harmonics=((1.0, 1.0), (2.0, 0.4), (4.0, 0.2)), attack_ratio=0.005, release_ratio=0.2, gain=0.9
)


def _patch_for_program(program: int) -> _SynthPatch:
    program = max(0, min(127, program))
    if program < 8:
        return _PIANO_PATCH
    if program < 16:
        return _MALLET_PATCH
    if program < 24:
        return _ORGAN_PATCH
    if program < 32:
        return _GUITAR_PATCH
    if program < 40:
        return _BASS_PATCH
    if program < 48:
        return _STRINGS_PATCH
    if program < 56:
        return _STRINGS_PATCH
    if program < 64:
        return _BRASS_PATCH
    if program < 72:
        return _REED_PATCH
    if program < 80:
        return _FLUTE_PATCH
    if program < 88:
        return _SYNTH_LEAD_PATCH
    if program < 96:
        return _SYNTH_PAD_PATCH
    if program < 104:
        return _PLUCKED_PATCH
    return _DEFAULT_PATCH


__all__ = ["_SynthPatch", "_patch_for_program", "_DEFAULT_PATCH"]
