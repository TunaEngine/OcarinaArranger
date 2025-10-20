"""Headless-compatible container widgets used in tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


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
    _items: Dict[int, Dict[str, object]] = field(default_factory=dict)
    _tempo_item_ids: Tuple[int, ...] = ()
    _next_item_id: int = 1

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

    def set_tempo_markers(
        self,
        markers: Tuple[tuple[int, str], ...],
        *,
        left_pad: float,
        px_per_tick: float,
        base_y: float,
        left_padding: float,
        barline_padding: float,
    ) -> None:
        """Populate lightweight tempo marker items for assertion-based tests."""

        self._items.clear()
        self._tempo_item_ids = ()
        self._next_item_id = 1
        created: list[int] = []
        for tick, label in markers:
            raw_left = left_pad + tick * px_per_tick + barline_padding
            minimum_left = left_pad + left_padding if tick == 0 else raw_left
            left = float(max(minimum_left, raw_left))
            text = str(label)
            # Derive a deterministic width large enough for bbox comparisons.
            width = max(24.0, len(text) * 6.0)
            item_id = self._next_item_id
            self._next_item_id += 1
            self._items[item_id] = {
                "tags": ("tempo_marker",),
                "text": text,
                "coords": (left, float(base_y)),
                "bbox": (left, float(base_y) - 6.0, left + width, float(base_y) + 6.0),
            }
            created.append(item_id)
        self._tempo_item_ids = tuple(created)

    def find_withtag(self, tag: str) -> Tuple[int, ...]:
        if tag == "tempo_marker":
            return self._tempo_item_ids
        return tuple()

    def itemcget(self, item_id: int, option: str) -> object:
        item = self._items.get(int(item_id), {})
        if option == "text":
            return item.get("text", "")
        return item.get(option)

    def coords(self, item_id: int) -> Tuple[float, float]:
        item = self._items.get(int(item_id))
        if not item:
            return (0.0, 0.0)
        coords = item.get("coords")
        if isinstance(coords, tuple):
            return tuple(float(value) for value in coords)  # type: ignore[return-value]
        return (0.0, 0.0)

    def bbox(self, item_id: int) -> Tuple[float, float, float, float]:
        item = self._items.get(int(item_id))
        if not item:
            return (0.0, 0.0, 0.0, 0.0)
        bounds = item.get("bbox")
        if isinstance(bounds, tuple):
            return tuple(float(value) for value in bounds)  # type: ignore[return-value]
        return (0.0, 0.0, 0.0, 0.0)

    def tag_raise(self, tag: str) -> None:  # pragma: no cover - ordering not required in tests
        return None


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
