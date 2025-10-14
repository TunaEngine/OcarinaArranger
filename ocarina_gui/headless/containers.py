"""Headless-compatible container widgets used in tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


class HeadlessListbox:
    """Minimal listbox replacement that stores strings in memory."""

    def __init__(self) -> None:
        self._items: List[str] = []

    def delete(self, start: int, end: Optional[str] = None) -> None:
        if start == 0 and (end in (None, "end")):
            self._items.clear()
        else:
            try:
                del self._items[start]
            except Exception:
                pass

    def insert(self, index: int | str, value: str) -> None:
        if index == "end" or index >= len(self._items):  # type: ignore[operator]
            self._items.append(value)
        else:
            self._items.insert(int(index), value)

    def size(self) -> int:
        return len(self._items)

    def get(self, index: int) -> str:
        return self._items[index]


@dataclass
class HeadlessCanvas:
    """Canvas stub with just enough behaviour for previews."""

    _x: float = 0.0

    def xview(self) -> Tuple[float, float]:
        return (self._x, min(1.0, self._x + 1.0))

    def xview_moveto(self, fraction: float) -> None:
        self._x = max(0.0, min(1.0, fraction))

    def yview(self, *args) -> None:  # pragma: no cover - no behaviour needed
        pass

    def yview_moveto(self, fraction: float) -> None:  # pragma: no cover
        pass

    def configure(self, **kwargs) -> None:  # pragma: no cover
        pass

    config = configure

    def delete(self, *args) -> None:  # pragma: no cover
        pass


@dataclass
class HeadlessScrollbar:
    """Simplified scrollbar stand-in for headless previews."""

    name: str
    mapped: bool = True
    _grid_kwargs: dict[str, object] = field(default_factory=dict)

    def grid(self, **kwargs) -> None:
        if kwargs:
            self._grid_kwargs.update(kwargs)
        self.mapped = True

    def grid_configure(self, **kwargs) -> None:
        if kwargs:
            self._grid_kwargs.update(kwargs)
        self.mapped = True

    def grid_remove(self) -> None:
        self.mapped = False

    def grid_info(self) -> dict[str, object]:
        return dict(self._grid_kwargs)

    def tkraise(self) -> None:  # pragma: no cover - no-op for tests
        pass

    def update_idletasks(self) -> None:  # pragma: no cover - no-op for tests
        pass

    def winfo_ismapped(self) -> bool:
        return self.mapped

    def winfo_reqwidth(self) -> int:  # pragma: no cover - provide a default width
        return int(self._grid_kwargs.get("minsize", 16) or 16)
