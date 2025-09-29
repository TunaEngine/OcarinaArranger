"""Application-wide configuration loaded from JSON resources."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from math import isfinite
from pathlib import Path
from typing import Any, Mapping

_CONFIG_RESOURCE = "app.json"
_APP_CONFIG_CACHE: AppConfig | None = None


@dataclass(frozen=True)
class PlaybackTiming:
    """Frame timing configuration for preview playback loops."""

    idle_fps: int
    active_fps: int

    @property
    def idle_interval_ms(self) -> int:
        return _fps_to_interval(self.idle_fps)

    @property
    def active_interval_ms(self) -> int:
        return _fps_to_interval(self.active_fps)


@dataclass(frozen=True)
class FlipAutoScrollConfig:
    """Settings that control flip-style auto-scroll behavior."""

    threshold_percent: int
    page_offset_percent: int

    @property
    def threshold_fraction(self) -> float:
        return self.threshold_percent / 100.0

    @property
    def page_offset_fraction(self) -> float:
        return self.page_offset_percent / 100.0


@dataclass(frozen=True)
class AutoScrollConfig:
    """Auto-scroll behavior configuration bucketed by mode."""

    flip: FlipAutoScrollConfig


@dataclass(frozen=True)
class AppConfig:
    """Structured configuration values for the desktop app."""

    playback: PlaybackTiming
    auto_scroll: AutoScrollConfig


def get_app_config() -> AppConfig:
    """Return the cached application configuration."""

    global _APP_CONFIG_CACHE
    if _APP_CONFIG_CACHE is None:
        _APP_CONFIG_CACHE = load_app_config()
    return _APP_CONFIG_CACHE


def reset_app_config_cache() -> None:
    """Reset the cached configuration for subsequent reloads."""

    global _APP_CONFIG_CACHE
    _APP_CONFIG_CACHE = None


def load_app_config(path: str | Path | None = None) -> AppConfig:
    """Load configuration from ``path`` or the bundled JSON resource."""

    data = _read_config_data(path)
    playback_section = data.get("playback") if isinstance(data, Mapping) else None
    playback = _parse_playback_section(playback_section)
    auto_scroll_section = data.get("auto_scroll") if isinstance(data, Mapping) else None
    auto_scroll = _parse_auto_scroll_section(auto_scroll_section)
    return AppConfig(playback=playback, auto_scroll=auto_scroll)


def get_playback_timing() -> PlaybackTiming:
    """Convenience accessor for the playback timing configuration."""

    return get_app_config().playback


def get_auto_scroll_config() -> AutoScrollConfig:
    """Convenience accessor for the auto-scroll configuration."""

    return get_app_config().auto_scroll


def _read_config_data(path: str | Path | None) -> Mapping[str, Any]:
    if path is not None:
        return _load_json_from_path(Path(path).expanduser())
    return _load_default_config_data()


def _load_json_from_path(path: Path) -> Mapping[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    return _parse_json(raw)


def _load_default_config_data() -> Mapping[str, Any]:
    try:
        resource = resources.files(__package__).joinpath(_CONFIG_RESOURCE)
        raw = resource.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return {}
    return _parse_json(raw)


def _parse_json(raw: str) -> Mapping[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, Mapping):
        return parsed
    return {}


def _parse_playback_section(section: Mapping[str, Any] | None) -> PlaybackTiming:
    if not isinstance(section, Mapping):
        return PlaybackTiming(idle_fps=30, active_fps=60)
    idle = _coerce_positive_int(section.get("idle_fps"), default=30)
    active = _coerce_positive_int(section.get("active_fps"), default=60)
    return PlaybackTiming(idle_fps=idle, active_fps=active)


def _parse_auto_scroll_section(section: Mapping[str, Any] | None) -> AutoScrollConfig:
    if not isinstance(section, Mapping):
        flip = FlipAutoScrollConfig(threshold_percent=75, page_offset_percent=25)
    else:
        flip_section = section.get("flip")
        flip = _parse_flip_auto_scroll_section(flip_section)
    return AutoScrollConfig(flip=flip)


def _parse_flip_auto_scroll_section(section: Mapping[str, Any] | None) -> FlipAutoScrollConfig:
    if not isinstance(section, Mapping):
        return FlipAutoScrollConfig(threshold_percent=75, page_offset_percent=25)
    threshold = _coerce_percent(section.get("threshold_percent"), default=75)
    offset = _coerce_percent(section.get("page_offset_percent"), default=25)
    return FlipAutoScrollConfig(threshold_percent=threshold, page_offset_percent=offset)


def _coerce_positive_int(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        candidate = int(value)
    elif isinstance(value, str):
        try:
            candidate = int(float(value))
        except ValueError:
            return default
    else:
        return default
    if candidate <= 0:
        return default
    return candidate


def _coerce_percent(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    candidate_float: float
    if isinstance(value, (int, float)):
        candidate_float = float(value)
    elif isinstance(value, str):
        try:
            candidate_float = float(value.strip())
        except ValueError:
            return default
    else:
        return default
    if not isfinite(candidate_float):
        return default
    candidate = int(round(candidate_float))
    if not 0 <= candidate <= 100:
        return default
    return candidate


def _fps_to_interval(fps: int) -> int:
    safe_fps = max(1, int(fps))
    return max(1, int(1000 / safe_fps))


__all__ = [
    "AppConfig",
    "AutoScrollConfig",
    "FlipAutoScrollConfig",
    "PlaybackTiming",
    "get_auto_scroll_config",
    "get_app_config",
    "get_playback_timing",
    "load_app_config",
    "reset_app_config_cache",
]
