"""Theme specification objects parsed from configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from .palettes import ThemePalette


@dataclass(frozen=True)
class ThemeSpec:
    """Full theme specification loaded from configuration."""

    theme_id: str
    name: str
    ttk_theme: str
    palette: ThemePalette
    styles: Dict[str, Dict[str, Any]]
    style_maps: Dict[str, Dict[str, List[Tuple[str, str]]]]
    options: Dict[str, str]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ThemeSpec":
        theme_id = str(data["id"])
        name = str(data.get("name", theme_id.title()))
        ttk_theme = str(data.get("ttk_theme", "clam"))
        palette = ThemePalette.from_dict(data["palette"])
        styles_raw: Mapping[str, Mapping[str, Any]] = data.get("styles", {})  # type: ignore[assignment]
        styles = {style: dict(options) for style, options in styles_raw.items()}
        style_maps_raw: Mapping[str, Mapping[str, Sequence[Sequence[Any]]]] = data.get("style_maps", {})  # type: ignore[assignment]
        style_maps: Dict[str, Dict[str, List[Tuple[str, str]]]] = {}
        for style_name, option_map in style_maps_raw.items():
            parsed_options: Dict[str, List[Tuple[str, str]]] = {}
            for option_name, entries in option_map.items():
                parsed_entries: List[Tuple[str, str]] = []
                for entry in entries:
                    if not isinstance(entry, Sequence) or len(entry) != 2:
                        continue
                    state, value = entry
                    parsed_entries.append((str(state), str(value)))
                if parsed_entries:
                    parsed_options[str(option_name)] = parsed_entries
            if parsed_options:
                style_maps[str(style_name)] = parsed_options
        options_raw: Mapping[str, Any] = data.get("options", {})  # type: ignore[assignment]
        options = {str(pattern): str(value) for pattern, value in options_raw.items()}
        return cls(
            theme_id=theme_id,
            name=name,
            ttk_theme=ttk_theme,
            palette=palette,
            styles=styles,
            style_maps=style_maps,
            options=options,
        )


@dataclass(frozen=True)
class ThemeChoice:
    """Simple value/name pair for UI selections."""

    theme_id: str
    name: str


__all__ = ["ThemeChoice", "ThemeSpec"]
