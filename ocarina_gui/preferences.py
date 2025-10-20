"""Helpers for persisting lightweight GUI preferences."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

from .scrolling import normalize_auto_scroll_mode
from services.update.constants import UPDATE_CHANNELS, UPDATE_CHANNEL_STABLE

_ENV_PREFERENCES_PATH = "OCARINA_GUI_PREFERENCES_PATH"


PREVIEW_LAYOUT_MODES = {
    "piano_staff",
    "piano_vertical",
    "staff",
}

ARRANGER_MODES = {"classic", "best_effort", "gp"}
DEFAULT_ARRANGER_MODE = "gp"


@dataclass
class Preferences:
    """Serializable preferences persisted between application launches."""

    theme_id: str | None = None
    log_verbosity: str | None = None
    recent_projects: list[str] = field(default_factory=list)
    auto_scroll_mode: str | None = None
    preview_layout_mode: str | None = None
    auto_update_enabled: bool | None = None
    update_channel: str | None = UPDATE_CHANNEL_STABLE
    arranger_mode: str | None = None
    lenient_midi_import: bool | None = None


def _default_preferences_path() -> Path:
    """Return the configured preferences path, falling back to the user home."""

    override = os.environ.get(_ENV_PREFERENCES_PATH)
    if override:
        return Path(override)
    return Path.home() / ".ocarina_arranger" / "preferences.json"


def load_preferences(path: Path | None = None) -> Preferences:
    """Load persisted preferences, returning defaults when missing or invalid."""

    location = path or _default_preferences_path()
    try:
        raw = location.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Preferences()
    except OSError:
        return Preferences()

    try:
        data: Dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        return Preferences()

    theme_id = data.get("theme_id")
    if not isinstance(theme_id, str):
        theme_id = None

    log_verbosity = data.get("log_verbosity")
    if not isinstance(log_verbosity, str):
        log_verbosity = None

    recent = data.get("recent_projects", [])
    recent_projects: list[str] = []
    if isinstance(recent, list):
        for entry in recent:
            if isinstance(entry, str) and entry:
                recent_projects.append(entry)
            elif isinstance(entry, str):
                continue
    if len(recent_projects) > 10:
        recent_projects = recent_projects[:10]

    raw_auto_scroll_mode = data.get("auto_scroll_mode")
    auto_scroll_mode: str | None
    if isinstance(raw_auto_scroll_mode, str):
        auto_scroll_mode = normalize_auto_scroll_mode(raw_auto_scroll_mode).value
    else:
        auto_scroll_mode = None

    layout_mode = data.get("preview_layout_mode")
    preview_layout_mode: str | None
    if isinstance(layout_mode, str):
        if layout_mode == "piano_horizontal":
            preview_layout_mode = "piano_vertical"
        elif layout_mode in PREVIEW_LAYOUT_MODES:
            preview_layout_mode = layout_mode
        else:
            preview_layout_mode = None
    else:
        preview_layout_mode = None

    raw_auto_update_enabled = data.get("auto_update_enabled")
    if isinstance(raw_auto_update_enabled, bool):
        auto_update_enabled = raw_auto_update_enabled
    else:
        auto_update_enabled = None

    raw_update_channel = data.get("update_channel")
    if isinstance(raw_update_channel, str):
        lowered_channel = raw_update_channel.strip().lower()
        update_channel = lowered_channel if lowered_channel in UPDATE_CHANNELS else UPDATE_CHANNEL_STABLE
    else:
        update_channel = UPDATE_CHANNEL_STABLE

    raw_arranger_mode = data.get("arranger_mode")
    if isinstance(raw_arranger_mode, str):
        normalized_mode = raw_arranger_mode.strip().lower()
        if normalized_mode in {"v1", "classic"}:
            arranger_mode = "classic"
        elif normalized_mode in {"v2", "best_effort"}:
            arranger_mode = "best_effort"
        elif normalized_mode in {"v3", "gp", "genetic"}:
            arranger_mode = "gp"
        elif normalized_mode in ARRANGER_MODES:
            arranger_mode = normalized_mode
        else:
            arranger_mode = None
    else:
        arranger_mode = None

    raw_lenient_import = data.get("lenient_midi_import")
    if isinstance(raw_lenient_import, bool):
        lenient_midi_import = raw_lenient_import
    elif isinstance(raw_lenient_import, (int, float)):
        try:
            lenient_midi_import = bool(int(raw_lenient_import))
        except (TypeError, ValueError):
            lenient_midi_import = None
    elif isinstance(raw_lenient_import, str):
        normalized = raw_lenient_import.strip().lower()
        if normalized in {"1", "true", "t", "yes", "on"}:
            lenient_midi_import = True
        elif normalized in {"0", "false", "f", "no", "off", ""}:
            lenient_midi_import = False
        else:
            lenient_midi_import = None
    else:
        lenient_midi_import = None

    return Preferences(
        theme_id=theme_id,
        log_verbosity=log_verbosity,
        recent_projects=recent_projects,
        auto_scroll_mode=auto_scroll_mode,
        preview_layout_mode=preview_layout_mode,
        auto_update_enabled=auto_update_enabled,
        update_channel=update_channel,
        arranger_mode=arranger_mode,
        lenient_midi_import=lenient_midi_import,
    )


def save_preferences(preferences: Preferences, path: Path | None = None) -> None:
    """Persist preferences to disk, ignoring errors to keep the UI responsive."""

    location = path or _default_preferences_path()
    data: Dict[str, Any] = {}
    if preferences.theme_id:
        data["theme_id"] = preferences.theme_id
    if preferences.log_verbosity:
        data["log_verbosity"] = preferences.log_verbosity
    if preferences.recent_projects:
        data["recent_projects"] = list(dict.fromkeys(preferences.recent_projects))[:10]
    if preferences.auto_scroll_mode:
        data["auto_scroll_mode"] = normalize_auto_scroll_mode(preferences.auto_scroll_mode).value

    if preferences.preview_layout_mode and preferences.preview_layout_mode in PREVIEW_LAYOUT_MODES:
        data["preview_layout_mode"] = preferences.preview_layout_mode
    if isinstance(preferences.auto_update_enabled, bool):
        data["auto_update_enabled"] = preferences.auto_update_enabled
    if (
        isinstance(preferences.update_channel, str)
        and preferences.update_channel in UPDATE_CHANNELS
    ):
        data["update_channel"] = preferences.update_channel
    if (
        isinstance(preferences.arranger_mode, str)
        and preferences.arranger_mode in ARRANGER_MODES
    ):
        data["arranger_mode"] = preferences.arranger_mode
    if isinstance(preferences.lenient_midi_import, bool):
        data["lenient_midi_import"] = preferences.lenient_midi_import

    try:
        location.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
        location.write_text(payload, encoding="utf-8")
    except OSError:
        # Preference persistence is best-effort; ignore filesystem errors.
        return


__all__ = [
    "Preferences",
    "load_preferences",
    "save_preferences",
    "PREVIEW_LAYOUT_MODES",
    "ARRANGER_MODES",
    "DEFAULT_ARRANGER_MODE",
]

