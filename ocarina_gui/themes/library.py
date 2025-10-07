"""Loading and managing theme specifications."""

from __future__ import annotations

import json
from importlib import resources
from typing import Callable, Dict, Iterable, List, Optional

from ocarina_gui.preferences import load_preferences, save_preferences
from .spec import ThemeChoice, ThemeSpec


class ThemeLibrary:
    """Maintains loaded themes and notifies listeners when switching."""

    def __init__(self, themes: Iterable[ThemeSpec], default_theme_id: str) -> None:
        themes_list = list(themes)
        if not themes_list:
            raise ValueError("At least one theme specification is required.")
        self._themes: Dict[str, ThemeSpec] = {
            theme.theme_id: theme for theme in themes_list
        }
        if default_theme_id not in self._themes:
            raise ValueError(f"Unknown default theme: {default_theme_id}")
        self._order: List[str] = [theme.theme_id for theme in themes_list]
        self._current_id: str = default_theme_id
        self._listeners: List[Callable[[ThemeSpec], None]] = []

    def get(self, theme_id: str) -> ThemeSpec:
        try:
            return self._themes[theme_id]
        except KeyError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Unknown theme: {theme_id}") from exc

    def current(self) -> ThemeSpec:
        return self._themes[self._current_id]

    def current_id(self) -> str:
        return self._current_id

    def choices(self) -> List[ThemeChoice]:
        return [
            ThemeChoice(theme_id=theme_id, name=self._themes[theme_id].name)
            for theme_id in self._order
        ]

    def register(self, listener: Callable[[ThemeSpec], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def _unsubscribe() -> None:
            try:
                self._listeners.remove(listener)
            except ValueError:  # pragma: no cover - already removed
                pass

        return _unsubscribe

    def set_current(self, theme_id: str) -> ThemeSpec:
        if theme_id == self._current_id:
            return self._themes[theme_id]
        theme = self.get(theme_id)
        self._current_id = theme_id
        for listener in list(self._listeners):
            listener(theme)
        return theme


_LIBRARY: Optional[ThemeLibrary] = None


def _load_library() -> ThemeLibrary:
    try:
        config_text = (
            resources.files("ocarina_gui").joinpath("config/themes.json").read_text(
                encoding="utf-8"
            )
        )
    except FileNotFoundError as exc:  # pragma: no cover - configuration must exist
        raise RuntimeError(
            "Theme configuration file not found. Ensure themes.json is available."
        ) from exc
    except OSError as exc:  # pragma: no cover - resource access issues
        raise RuntimeError(f"Unable to read theme configuration: {exc}") from exc
    try:
        raw = json.loads(config_text)
    except json.JSONDecodeError as exc:  # pragma: no cover - invalid configuration
        raise RuntimeError(f"Invalid theme configuration: {exc}") from exc

    themes_data = raw.get("themes", [])  # type: ignore[assignment]
    themes = [ThemeSpec.from_dict(entry) for entry in themes_data]
    if not themes:
        raise RuntimeError("Theme configuration must define at least one theme.")
    default_theme_id = str(raw.get("default_theme", themes[0].theme_id))
    library = ThemeLibrary(themes, default_theme_id)

    preferences = load_preferences()
    if preferences.theme_id and preferences.theme_id in {t.theme_id for t in themes}:
        try:
            library.set_current(preferences.theme_id)
        except ValueError:
            pass

    return library


def _get_library() -> ThemeLibrary:
    global _LIBRARY
    if _LIBRARY is None:
        _LIBRARY = _load_library()
    return _LIBRARY


def get_available_themes() -> List[ThemeChoice]:
    return _get_library().choices()


def get_current_theme() -> ThemeSpec:
    return _get_library().current()


def get_current_theme_id() -> str:
    return _get_library().current_id()


def get_theme(theme_id: str) -> ThemeSpec:
    return _get_library().get(theme_id)


def set_active_theme(theme_id: str) -> ThemeSpec:
    theme = _get_library().set_current(theme_id)
    preferences = load_preferences()
    preferences.theme_id = theme.theme_id
    save_preferences(preferences)
    return theme


def register_theme_listener(listener: Callable[[ThemeSpec], None]) -> Callable[[], None]:
    return _get_library().register(listener)


__all__ = [
    "ThemeLibrary",
    "_load_library",
    "get_available_themes",
    "get_current_theme",
    "get_current_theme_id",
    "get_theme",
    "register_theme_listener",
    "set_active_theme",
]
