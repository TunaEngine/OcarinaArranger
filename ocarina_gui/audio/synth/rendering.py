"""Audio rendering helpers for the preview synthesiser."""

from __future__ import annotations

import math
import threading
from array import array
from collections import namedtuple
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from .patches import _patch_for_program
from .tone import _midi_to_frequency

Event = tuple[int, int, int, int]


@dataclass(frozen=True)
class MetronomeSettings:
    enabled: bool
    beats_per_measure: int
    beat_unit: int


@dataclass(frozen=True)
class RenderConfig:
    sample_rate: int
    amplitude: float
    chunk_size: int
    metronome: MetronomeSettings


def tempo_cache_key(tempo: float) -> int:
    return int(round(max(tempo, 1e-3) * 1000.0))


def _pitch_normalization_gain(midi: int) -> float:
    frequency = _midi_to_frequency(midi)
    if frequency <= 0.0:
        return 1.0
    reference = _midi_to_frequency(69)
    if reference <= 0.0:
        return 1.0
    ratio = reference / frequency
    if ratio <= 1.0:
        return 1.0
    return min(3.0, ratio**0.35)


_note_segment_cache: dict[tuple, tuple[float, ...]] = {}
_note_segment_lock = threading.Lock()
_cache_hits = 0
_cache_misses = 0
CacheInfo = namedtuple("CacheInfo", ["hits", "misses", "currsize"])


def clear_note_segment_cache() -> None:
    """Clear the cache used by the note_segment function."""
    global _cache_hits, _cache_misses
    with _note_segment_lock:
        _note_segment_cache.clear()
        _cache_hits = 0
        _cache_misses = 0


def get_note_segment_cache_info() -> CacheInfo:
    """Get statistics for the note_segment cache."""
    with _note_segment_lock:
        return CacheInfo(_cache_hits, _cache_misses, len(_note_segment_cache))


def note_segment(
    program: int,
    midi: int,
    duration_ticks: int,
    tempo_key: int,
    pulses_per_quarter: int,
    sample_rate: int,
) -> tuple[float, ...]:
    """Generate a single note segment, using a thread-safe cache."""
    global _cache_hits, _cache_misses
    key = (program, midi, duration_ticks, tempo_key, pulses_per_quarter, sample_rate)

    # Lock the entire operation. This is a robust but less concurrent solution
    # to prevent memory corruption from simultaneous heavy calculations.
    with _note_segment_lock:
        if key in _note_segment_cache:
            _cache_hits += 1
            return _note_segment_cache[key]

        _cache_misses += 1
        ticks = max(1, int(duration_ticks))
        tempo_units = max(tempo_key, 1)
        ppq = max(1, int(pulses_per_quarter))
        tempo = tempo_units / 1000.0
        ticks_per_second = max((tempo / 60.0) * ppq, 1e-6)
        segment_seconds = ticks / ticks_per_second
        length = max(1, int(round(segment_seconds * sample_rate)))
        frequency = _midi_to_frequency(midi)

        if frequency <= 0.0 or length <= 0:
            result = (0.0,) * length
        else:
            patch = _patch_for_program(program)
            base_step = 2.0 * math.pi * frequency / sample_rate
            vibrato_step = (
                2.0 * math.pi * patch.vibrato_hz / sample_rate
                if patch.vibrato_hz
                else 0.0
            )
            vibrato_depth = patch.vibrato_depth
            harmonics = patch.harmonics
            gain = patch.gain
            pitch_gain = _pitch_normalization_gain(midi)

            attack = max(1, min(length, int(length * patch.attack_ratio)))
            release = max(1, min(length, int(length * patch.release_ratio)))
            attack_scale = 1.0 / attack if attack else 1.0
            release_scale = 1.0 / release if release else 1.0
            release_start = max(0, length - release)

            segment: list[float] = [0.0] * length
            base_phase = 0.0
            vibrato_phase = 0.0

            for index in range(length):
                if index < attack:
                    envelope = index * attack_scale
                elif index >= release_start:
                    envelope = (length - index) * release_scale
                else:
                    envelope = 1.0

                vibrato_scale = 1.0
                if vibrato_depth and vibrato_step:
                    vibrato_scale += vibrato_depth * math.sin(vibrato_phase)
                    vibrato_phase += vibrato_step

                sample_value = 0.0
                phase = base_phase
                for multiple, amplitude in harmonics:
                    sample_value += math.sin(phase * multiple) * amplitude

                segment[index] = sample_value * envelope * gain * pitch_gain
                step_scale = vibrato_scale if vibrato_scale > 0.0 else 0.0
                base_phase += base_step * step_scale
            result = tuple(segment)

        if len(_note_segment_cache) > 2048:
            _note_segment_cache.clear()
        _note_segment_cache[key] = result
        return result


def render_events(
    events: Sequence[Event],
    tempo: float,
    pulses_per_quarter: int,
    config: RenderConfig,
    progress_callback: Callable[[float], None] | None = None,
) -> tuple[bytes, float]:
    sample_rate = config.sample_rate
    ticks_per_second = max((tempo / 60.0) * pulses_per_quarter, 1e-3)
    if not events:
        if progress_callback is not None:
            progress_callback(1.0)
        return b"", ticks_per_second

    max_tick = max((start + duration) for start, duration, _midi, _program in events)
    total_seconds = max_tick / ticks_per_second if max_tick else 0.0
    sample_count = (
        max(1, int(math.ceil(total_seconds * sample_rate)) + int(sample_rate * 0.5))
    )
    mix = [0.0] * sample_count

    tempo_key_value = tempo_cache_key(tempo)
    chunk_size = max(1, int(config.chunk_size))

    total_work = 0
    if progress_callback is not None:
        for onset, duration, midi, program in events:
            if _midi_to_frequency(midi) <= 0.0:
                continue
            start_index = int(round(onset / ticks_per_second * sample_rate))
            if start_index >= sample_count:
                continue
            duration_ticks = max(1, int(duration))
            segment_seconds = duration_ticks / ticks_per_second
            estimated_samples = max(1, int(round(segment_seconds * sample_rate)))
            limit = min(estimated_samples, sample_count - max(0, start_index))
            if limit <= 0:
                continue
            total_work += limit

        if config.metronome.enabled:
            total_work += estimate_metronome_samples(
                sample_count,
                ticks_per_second,
                config.metronome,
                pulses_per_quarter,
                sample_rate,
            )

    completed_work = 0

    def _report_progress(units: int) -> None:
        nonlocal completed_work
        if progress_callback is None or total_work <= 0 or units <= 0:
            return
        completed_work += units
        if completed_work > total_work:
            completed_work = total_work
        progress_callback(min(1.0, completed_work / total_work))

    if progress_callback is not None and total_work > 0:
        progress_callback(0.0)

    for onset, duration, midi, program in events:
        frequency = _midi_to_frequency(midi)
        if frequency <= 0.0:
            continue
        start_index = int(round(onset / ticks_per_second * sample_rate))
        if start_index >= sample_count:
            continue
        segment = note_segment(
            program,
            midi,
            int(duration),
            tempo_key_value,
            pulses_per_quarter,
            sample_rate,
        )
        if not segment:
            continue
        base_index = max(0, start_index)
        limit = min(len(segment), sample_count - base_index)
        if limit <= 0:
            continue
        segment_slice = segment[:limit]
        remaining = limit
        dest_index = base_index
        processed = 0
        while remaining > 0:
            step = remaining
            if progress_callback is not None and total_work > 0:
                step = min(step, chunk_size)
            dest_end = dest_index + step
            src_slice = segment_slice[processed : processed + step]
            existing = mix[dest_index:dest_end]
            mix[dest_index:dest_end] = [
                current + addition for current, addition in zip(existing, src_slice)
            ]
            dest_index = dest_end
            processed += step
            remaining -= step
            _report_progress(step)

    if config.metronome.enabled:
        overlay_metronome(
            mix,
            ticks_per_second,
            sample_count,
            config.metronome,
            pulses_per_quarter,
            sample_rate,
            report_progress=_report_progress if total_work > 0 else None,
        )

    if progress_callback is not None and total_work > 0 and completed_work < total_work:
        _report_progress(total_work - completed_work)

    peak = max((abs(val) for val in mix), default=0.0)
    if peak <= 1e-9:
        return b"", ticks_per_second
    scale = (config.amplitude * 32767.0) / peak
    samples = array("h", (int(max(-32767, min(32767, val * scale))) for val in mix))
    return samples.tobytes(), ticks_per_second


def overlay_metronome(
    mix: list[float],
    ticks_per_second: float,
    sample_count: int,
    settings: MetronomeSettings,
    pulses_per_quarter: int,
    sample_rate: int,
    *,
    report_progress: Callable[[int], None] | None = None,
) -> None:
    beat_length_ticks = int(
        round((pulses_per_quarter * 4) / max(1, settings.beat_unit))
    )
    if beat_length_ticks <= 0:
        return
    max_tick = int(sample_count / max(sample_rate, 1) * ticks_per_second)
    if max_tick <= 0:
        return
    click_duration_samples = max(1, int(sample_rate * 0.08))
    accent_frequency = 1760.0
    weak_frequency = 1320.0
    beats_per_measure = max(1, settings.beats_per_measure)
    tick = 0
    beat_index = 0
    while tick <= max_tick:
        start_sample = int(round(tick / ticks_per_second * sample_rate))
        if start_sample >= sample_count:
            break
        end_sample = min(sample_count, start_sample + click_duration_samples)
        if end_sample <= start_sample:
            break
        is_accent = beat_index % beats_per_measure == 0
        frequency = accent_frequency if is_accent else weak_frequency
        amplitude = 1.0 if is_accent else 0.6
        phase = 0.0
        phase_step = 2.0 * math.pi * frequency / sample_rate
        decay = max(1, int(click_duration_samples * 0.8))
        for index in range(start_sample, end_sample):
            step = index - start_sample
            envelope = 1.0 - (step / decay) if step < decay else 0.0
            mix[index] += math.sin(phase) * amplitude * envelope
            phase += phase_step
        if report_progress is not None:
            report_progress(end_sample - start_sample)
        beat_index += 1
        tick += beat_length_ticks


def estimate_metronome_samples(
    sample_count: int,
    ticks_per_second: float,
    settings: MetronomeSettings,
    pulses_per_quarter: int,
    sample_rate: int,
) -> int:
    beat_length_ticks = int(
        round((pulses_per_quarter * 4) / max(1, settings.beat_unit))
    )
    if beat_length_ticks <= 0:
        return 0
    max_tick = int(sample_count / max(sample_rate, 1) * ticks_per_second)
    if max_tick <= 0:
        return 0
    click_duration_samples = max(1, int(sample_rate * 0.08))
    tick = 0
    total = 0
    while tick <= max_tick:
        start_sample = int(round(tick / ticks_per_second * sample_rate))
        if start_sample >= sample_count:
            break
        end_sample = min(sample_count, start_sample + click_duration_samples)
        if end_sample <= start_sample:
            break
        total += end_sample - start_sample
        tick += beat_length_ticks
    return total


__all__ = [
    "Event",
    "MetronomeSettings",
    "RenderConfig",
    "tempo_cache_key",
    "note_segment",
    "render_events",
    "overlay_metronome",
    "estimate_metronome_samples",
    "clear_note_segment_cache",
    "get_note_segment_cache_info",
]
