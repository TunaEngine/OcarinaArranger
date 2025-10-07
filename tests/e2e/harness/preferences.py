from __future__ import annotations

from typing import Callable

from ocarina_gui.preferences import Preferences
from ocarina_gui.scrolling import AutoScrollMode

_SKIPPED_ATTR = "_e2e_skip_preference_recording"


def build_preferences() -> Preferences:
    return Preferences(
        auto_scroll_mode=AutoScrollMode.FLIP.value,
        preview_layout_mode="piano_staff",
        auto_update_enabled=False,
        update_channel="stable",
    )


def clone_preferences(source: object) -> Preferences:
    return Preferences(
        theme_id=getattr(source, "theme_id", None),
        log_verbosity=getattr(source, "log_verbosity", None),
        recent_projects=list(getattr(source, "recent_projects", []) or []),
        auto_scroll_mode=getattr(source, "auto_scroll_mode", None),
        preview_layout_mode=getattr(source, "preview_layout_mode", None),
        auto_update_enabled=getattr(source, "auto_update_enabled", None),
        update_channel=getattr(source, "update_channel", "stable"),
    )


def create_save_preferences_stub(
    preferences: Preferences,
    saved_preferences: list[Preferences],
) -> Callable[[object], None]:
    def _save(updated: object, *_args, **_kwargs) -> None:  # noqa: ANN001
        snapshot = clone_preferences(updated)
        preferences.theme_id = snapshot.theme_id
        preferences.log_verbosity = snapshot.log_verbosity
        preferences.recent_projects = list(snapshot.recent_projects)
        preferences.auto_scroll_mode = snapshot.auto_scroll_mode
        preferences.preview_layout_mode = snapshot.preview_layout_mode
        preferences.auto_update_enabled = snapshot.auto_update_enabled
        preferences.update_channel = snapshot.update_channel
        if getattr(updated, _SKIPPED_ATTR, False):
            try:
                delattr(updated, _SKIPPED_ATTR)
            except AttributeError:
                pass
            return
        saved_preferences.append(snapshot)

    return _save


def mark_preferences_unrecorded(preferences: Preferences) -> None:
    setattr(preferences, _SKIPPED_ATTR, True)


def clear_unrecorded_flag(preferences: Preferences) -> None:
    if hasattr(preferences, _SKIPPED_ATTR):
        delattr(preferences, _SKIPPED_ATTR)


__all__ = [
    "build_preferences",
    "clone_preferences",
    "create_save_preferences_stub",
    "mark_preferences_unrecorded",
    "clear_unrecorded_flag",
]
