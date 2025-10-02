"""Theme configuration and runtime management for the Ocarina GUI."""

from __future__ import annotations

import json
import tkinter as tk
from collections import deque
from dataclasses import dataclass
from importlib import resources
from tkinter import ttk
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .preferences import Preferences, load_preferences, save_preferences


@dataclass(frozen=True)
class PianoRollPalette:
    """Color palette for the piano roll widget."""

    background: str
    natural_row_fill: str
    accidental_row_fill: str
    grid_line: str
    measure_line: str
    measure_number_text: str
    note_fill_sharp: str
    note_fill_natural: str
    note_outline: str
    note_label_text: str
    placeholder_text: str
    header_text: str
    highlight_fill: str
    loop_start_line: str
    loop_end_line: str
    cursor_primary: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PianoRollPalette":
        return cls(
            background=str(data["background"]),
            natural_row_fill=str(data.get("natural_row_fill", data["background"])),
            accidental_row_fill=str(data.get("accidental_row_fill", data["background"])),
            grid_line=str(data["grid_line"]),
            measure_line=str(data.get("measure_line", data["grid_line"])),
            measure_number_text=str(
                data.get(
                    "measure_number_text",
                    data.get("measure_line", data["grid_line"]),
                )
            ),
            note_fill_sharp=str(data["note_fill_sharp"]),
            note_fill_natural=str(data["note_fill_natural"]),
            note_outline=str(data["note_outline"]),
            note_label_text=str(data["note_label_text"]),
            placeholder_text=str(data["placeholder_text"]),
            header_text=str(data.get("header_text", data["placeholder_text"])),
            highlight_fill=str(data["highlight_fill"]),
            loop_start_line=str(data.get("loop_start_line", data["note_outline"])),
            loop_end_line=str(data.get("loop_end_line", data["note_fill_sharp"])),
            cursor_primary=str(
                data.get(
                    "cursor_primary",
                    data.get("note_outline", data.get("note_fill", data["note_fill_natural"])),
                )
            ),
        )


@dataclass(frozen=True)
class StaffPalette:
    """Color palette for the treble staff widget."""

    background: str
    outline: str
    staff_line: str
    measure_line: str
    measure_number_text: str
    accidental_text: str
    note_fill: str
    note_outline: str
    header_text: str
    cursor_primary: str
    cursor_secondary: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StaffPalette":
        return cls(
            background=str(data["background"]),
            outline=str(data["outline"]),
            staff_line=str(data["staff_line"]),
            measure_line=str(data["measure_line"]),
            measure_number_text=str(
                data.get("measure_number_text", data["measure_line"])
            ),
            accidental_text=str(data["accidental_text"]),
            note_fill=str(data["note_fill"]),
            note_outline=str(data.get("note_outline", data["note_fill"])),
            header_text=str(data["header_text"]),
            cursor_primary=str(data.get("cursor_primary", data.get("note_outline", data["note_fill"]))),
            cursor_secondary=str(data.get("cursor_secondary", data["measure_line"])),
        )


@dataclass(frozen=True)
class ListboxPalette:
    """Color palette for classic Tk listboxes."""

    background: str
    foreground: str
    select_background: str
    select_foreground: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ListboxPalette":
        return cls(
            background=str(data["background"]),
            foreground=str(data["foreground"]),
            select_background=str(data.get("select_background", data["background"])),
            select_foreground=str(data.get("select_foreground", data["foreground"])),
        )


@dataclass(frozen=True)
class TablePalette:
    """Color palette for table-like ttk widgets such as :class:`Treeview`."""

    background: str
    foreground: str
    heading_background: str
    heading_foreground: str
    row_stripe: str
    selection_background: str
    selection_foreground: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TablePalette":
        if not data:
            # Sensible defaults matching classic Tk colors.
            return cls(
                background="#ffffff",
                foreground="#000000",
                heading_background="#f0f0f0",
                heading_foreground="#000000",
                row_stripe="#ffffff",
                selection_background="#cde4ff",
                selection_foreground="#000000",
            )
        background = str(data["background"])
        foreground = str(data["foreground"])
        row_stripe = str(data.get("row_stripe", background))
        return cls(
            background=background,
            foreground=foreground,
            heading_background=str(data.get("heading_background", background)),
            heading_foreground=str(data.get("heading_foreground", foreground)),
            row_stripe=row_stripe,
            selection_background=str(data.get("selection_background", row_stripe)),
            selection_foreground=str(data.get("selection_foreground", foreground)),
        )


@dataclass(frozen=True)
class ThemePalette:
    """Collection of colors used throughout the application widgets."""

    window_background: str
    text_primary: str
    text_muted: str
    text_cursor: str
    piano_roll: PianoRollPalette
    staff: StaffPalette
    listbox: ListboxPalette
    table: "TablePalette"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ThemePalette":
        return cls(
            window_background=str(data["window_background"]),
            text_primary=str(data["text_primary"]),
            text_muted=str(data["text_muted"]),
            text_cursor=str(data.get("text_cursor", data["text_primary"])),
            piano_roll=PianoRollPalette.from_dict(data["piano_roll"]),
            staff=StaffPalette.from_dict(data["staff"]),
            listbox=ListboxPalette.from_dict(data["listbox"]),
            table=TablePalette.from_dict(data.get("table", {})),
        )


INSERT_BACKGROUND_PATTERNS: Tuple[str, ...] = (
    "*Entry.insertBackground",
    "*Text.insertBackground",
    "*Spinbox.insertBackground",
    "*TEntry*insertBackground",
    "*TSpinbox*insertBackground",
    "*TCombobox*insertBackground",
)
TTK_INSERT_STYLE_NAMES: Tuple[str, ...] = (
    "TEntry",
    "TSpinbox",
    "TCombobox",
)

try:
    _TTK_INSERT_WIDGET_TYPES: Tuple[type, ...] = tuple(
        getattr(ttk, name)
        for name in ("Entry", "Spinbox", "Combobox")
        if hasattr(ttk, name)
    )
except Exception:  # pragma: no cover - minimal Tk distributions
    _TTK_INSERT_WIDGET_TYPES = ()


def _configure_ttk_insert_color(style: ttk.Style, style_name: str, color: str) -> None:
    try:
        style.configure(style_name, insertcolor=color)
    except tk.TclError:
        pass


def _ensure_default_ttk_insert_colors(style: ttk.Style, color: str) -> None:
    for style_name in TTK_INSERT_STYLE_NAMES:
        _configure_ttk_insert_color(style, style_name, color)


def _maybe_set_widget_style_insert_color(widget: tk.Misc, color: str) -> None:
    if not _TTK_INSERT_WIDGET_TYPES or not isinstance(widget, _TTK_INSERT_WIDGET_TYPES):
        return

    style_name = ""
    try:
        style_name = widget.cget("style")
    except tk.TclError:
        style_name = ""

    if not style_name:
        style_name = widget.winfo_class()

    style = ttk.Style(widget)
    _configure_ttk_insert_color(style, style_name, color)


def set_ttk_caret_color(style: ttk.Style, color: str) -> None:
    """Apply ``color`` to the insertion cursor for common ttk entry styles."""

    _ensure_default_ttk_insert_colors(style, color)


def apply_insert_cursor_color(widget: tk.Misc, color: str) -> None:
    """Force ``insertbackground`` on ``widget`` and all descendants."""

    queue: deque[tk.Misc] = deque([widget])
    seen: set[str] = set()

    while queue:
        current = queue.popleft()
        identifier = str(current)
        if identifier in seen:
            continue
        seen.add(identifier)

        if hasattr(current, "configure"):
            try:
                current.configure(insertbackground=color)
            except tk.TclError:
                pass
            except AttributeError:  # pragma: no cover - non-configurable object
                pass

        _maybe_set_widget_style_insert_color(current, color)

        try:
            children = current.winfo_children()
        except tk.TclError:
            continue
        for child in children:
            if isinstance(child, tk.Misc):
                queue.append(child)


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


class ThemeLibrary:
    """Maintains loaded themes and notifies listeners when switching."""

    def __init__(self, themes: Sequence[ThemeSpec], default_theme_id: str) -> None:
        if not themes:
            raise ValueError("At least one theme specification is required.")
        self._themes: Dict[str, ThemeSpec] = {theme.theme_id: theme for theme in themes}
        if default_theme_id not in self._themes:
            raise ValueError(f"Unknown default theme: {default_theme_id}")
        self._order: List[str] = [theme.theme_id for theme in themes]
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
        return [ThemeChoice(theme_id=theme_id, name=self._themes[theme_id].name) for theme_id in self._order]

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


def _load_library() -> ThemeLibrary:
    try:
        config_text = resources.files(__package__).joinpath("config/themes.json").read_text(encoding="utf-8")
    except FileNotFoundError as exc:  # pragma: no cover - configuration must exist in source tree
        raise RuntimeError("Theme configuration file not found. Ensure themes.json is available.") from exc
    except OSError as exc:  # pragma: no cover - resource access issues
        raise RuntimeError(f"Unable to read theme configuration: {exc}") from exc
    try:
        raw = json.loads(config_text)
    except json.JSONDecodeError as exc:  # pragma: no cover - invalid configuration
        raise RuntimeError(f"Invalid theme configuration: {exc}") from exc

    themes_data: Iterable[Mapping[str, Any]] = raw.get("themes", [])  # type: ignore[assignment]
    themes = [ThemeSpec.from_dict(entry) for entry in themes_data]
    if not themes:
        raise RuntimeError("Theme configuration must define at least one theme.")
    default_theme_id = str(raw.get("default_theme", themes[0].theme_id))
    library = ThemeLibrary(themes, default_theme_id)

    preferences = load_preferences()
    if preferences.theme_id and preferences.theme_id in {theme.theme_id for theme in themes}:
        try:
            library.set_current(preferences.theme_id)
        except ValueError:
            pass

    return library




def _get_library() -> ThemeLibrary:
    """Lazily initialize the theme library so environment overrides apply."""

    global _LIBRARY
    if _LIBRARY is None:
        _LIBRARY = _load_library()
    return _LIBRARY


_LIBRARY: ThemeLibrary | None = None


def get_available_themes() -> List[ThemeChoice]:
    """Return available themes for selection widgets."""

    return _get_library().choices()


def get_current_theme() -> ThemeSpec:
    """Return the currently active theme specification."""

    return _get_library().current()


def get_current_theme_id() -> str:
    """Return the identifier of the currently active theme."""

    return _get_library().current_id()


def get_theme(theme_id: str) -> ThemeSpec:
    """Lookup a theme by identifier."""

    return _get_library().get(theme_id)


def set_active_theme(theme_id: str) -> ThemeSpec:
    """Activate the theme with the given identifier."""

    theme = _get_library().set_current(theme_id)
    preferences = load_preferences()
    preferences.theme_id = theme.theme_id
    save_preferences(preferences)
    return theme


def register_theme_listener(listener: Callable[[ThemeSpec], None]) -> Callable[[], None]:
    """Register a listener to be notified when the theme changes."""

    return _get_library().register(listener)


def apply_theme_to_toplevel(window: tk.Misc) -> ThemePalette:
    """Apply the current theme's Tk option defaults to ``window``.

    The main window configures ttk styles globally, but individual toplevels need
    their own option database entries so classic Tk widgets (``Entry``, ``Text``,
    ``Listbox``) and the window background inherit the palette.  This helper makes
    the process reusable for dialogs created outside the main window lifecycle.
    """

    theme = get_current_theme()
    palette = theme.palette

    try:
        window.configure(background=palette.window_background)
    except tk.TclError:
        pass

    for pattern, value in theme.options.items():
        try:
            window.option_add(pattern, value)
        except tk.TclError:
            continue

    for pattern in INSERT_BACKGROUND_PATTERNS:
        try:
            window.option_add(pattern, palette.text_cursor)
        except tk.TclError:
            continue

    try:
        style = ttk.Style(window)
    except tk.TclError:
        style = None
    else:
        set_ttk_caret_color(style, palette.text_cursor)

    apply_insert_cursor_color(window, palette.text_cursor)

    return palette


__all__ = [
    "INSERT_BACKGROUND_PATTERNS",
    "PianoRollPalette",
    "StaffPalette",
    "ListboxPalette",
    "TablePalette",
    "ThemePalette",
    "ThemeSpec",
    "ThemeChoice",
    "ThemeLibrary",
    "get_available_themes",
    "get_current_theme",
    "get_current_theme_id",
    "get_theme",
    "set_active_theme",
    "register_theme_listener",
    "apply_theme_to_toplevel",
    "apply_insert_cursor_color",
    "set_ttk_caret_color",
]


