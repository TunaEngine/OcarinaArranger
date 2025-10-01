"""Headless helper widgets used in GUI fingering tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Callable


__all__ = ["_HeadlessTable", "_HeadlessPreview", "make_click_event"]


class _HeadlessTable:
    def __init__(self, rows: list[str], columns: tuple[str, ...]) -> None:
        self._rows = list(rows)
        self._columns = columns
        self._displaycolumns = columns
        self._selection: tuple[str, ...] = tuple()
        self._focus: str | None = None
        self._click_region = "cell"
        self._click_column = "#1"
        self._click_row = rows[0]
        self._column_settings: dict[str, dict[str, object]] = {
            column: {"width": 80, "minwidth": 20, "anchor": "center", "stretch": "0"}
            for column in columns
        }
        self._heading_settings: dict[str, dict[str, object]] = {
            column: {"text": column}
            for column in columns
        }

    def __getitem__(self, key: str) -> tuple[str, ...]:
        if key == "columns":
            return self._columns
        if key == "displaycolumns":
            return self._displaycolumns
        raise KeyError(key)

    def configure(self, **kwargs) -> None:
        if "columns" in kwargs:
            value = kwargs["columns"]
            self._columns = tuple(value)
            for column in self._columns:
                self._column_settings.setdefault(
                    column,
                    {"width": 80, "minwidth": 20, "anchor": "center", "stretch": "0"},
                )
                self._heading_settings.setdefault(column, {"text": column})
        if "displaycolumns" in kwargs:
            value = kwargs["displaycolumns"]
            if isinstance(value, str):
                self._displaycolumns = (value,)
            else:
                self._displaycolumns = tuple(value)

    def selection(self) -> tuple[str, ...]:
        return self._selection

    def selection_set(self, item: str) -> None:
        self._selection = (item,)

    def focus(self, item: str | None = None) -> str | None:
        if item is not None:
            self._focus = item
        return self._focus

    def item(self, item: str, option: str = "values") -> tuple[str, ...]:
        if option != "values":
            raise KeyError(option)
        if item == "_empty":
            return ("",)
        return (item, "●")

    def get_children(self) -> tuple[str, ...]:
        return tuple(self._rows)

    def delete(self, item: str) -> None:
        if item in self._rows:
            self._rows.remove(item)

    def insert(self, _parent: str, _index: str, iid: str, values: tuple[str, ...], tags: tuple[str, ...]) -> None:
        if iid not in self._rows:
            self._rows.append(iid)

    def heading(self, column: str, **kwargs) -> None:
        settings = self._heading_settings.setdefault(column, {"text": column})
        settings.update(kwargs)

    def column(self, column: str, option: str | None = None, **kwargs):
        settings = self._column_settings.setdefault(
            column,
            {"width": 80, "minwidth": 20, "anchor": "center", "stretch": "0"},
        )
        if kwargs:
            settings.update(kwargs)
        if option is None:
            return dict(settings)
        return settings.get(option)

    def exists(self, item: str) -> bool:
        return item in self._rows

    def selection_remove(self, item: str) -> None:
        if self._selection and self._selection[0] == item:
            self._selection = tuple()

    def selection_add(self, item: str) -> None:
        if item not in self._rows:
            self._rows.append(item)
        self._selection = (item,)

    def selection_toggle(self, item: str) -> None:
        if self._selection and self._selection[0] == item:
            self._selection = tuple()
        else:
            self.selection_add(item)

    def identify_region(self, _x: int, _y: int) -> str:
        return self._click_region

    def identify_column(self, _x: int) -> str:
        return self._click_column

    def identify_row(self, _y: int) -> str:
        return self._click_row

    def set_click_target(self, *, note: str, column_ref: str, region: str = "cell") -> None:
        self._click_row = note
        self._click_column = column_ref
        self._click_region = region

    def see(self, note: str) -> None:  # pragma: no cover - defensive safeguard
        if note not in self._rows:
            raise LookupError(note)


class _HeadlessPreview:
    def __init__(self) -> None:
        self.history: list[tuple[str | None, int | None]] = []
        self.hole_handler: Callable[[int], None] | None = None
        self.windway_handler: Callable[[int], None] | None = None

    def show_fingering(self, note_name: str | None, midi: int | None) -> None:
        self.history.append((note_name, midi))

    def clear(self) -> None:
        self.history.append((None, None))

    def set_hole_click_handler(self, handler: Callable[[int], None] | None) -> None:
        self.hole_handler = handler

    def trigger_hole_click(self, hole_index: int) -> None:
        if self.hole_handler:
            self.hole_handler(hole_index)

    def set_windway_click_handler(self, handler: Callable[[int], None] | None) -> None:
        self.windway_handler = handler

    def trigger_windway_click(self, windway_index: int) -> None:
        if self.windway_handler:
            self.windway_handler(windway_index)


def make_click_event(x: int = 10, y: int = 5) -> SimpleNamespace:
    """Create a minimal event-like object."""

    return SimpleNamespace(x=x, y=y)
