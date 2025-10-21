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
    """Canvas stub with simplified drawing semantics for UI tests."""

    _x: float = 0.0
    _y: float = 0.0
    _items: Dict[int, Dict[str, object]] = field(default_factory=dict)
    _tempo_item_ids: Tuple[int, ...] = ()
    _next_item_id: int = 1
    _width: float = 800.0
    _height: float = 600.0

    def clear(self) -> None:
        self._items.clear()
        self._tempo_item_ids = ()
        self._next_item_id = 1

    def xview(self) -> Tuple[float, float]:
        return (self._x, min(1.0, self._x + 1.0))

    def xview_moveto(self, fraction: float) -> None:
        self._x = max(0.0, min(1.0, float(fraction)))

    def yview(self, *args) -> None:  # pragma: no cover - vertical scroll unused in tests
        pass

    def yview_moveto(self, fraction: float) -> None:  # pragma: no cover - emulate offset
        self._y = max(0.0, float(fraction)) * self._height

    def canvasy(self, value: float) -> float:  # pragma: no cover - simple offset helper
        return float(value) + self._y

    def configure(self, **kwargs) -> None:  # pragma: no cover - store size hints
        width = kwargs.get("width")
        height = kwargs.get("height")
        try:
            if width is not None:
                self._width = float(width)
        except (TypeError, ValueError):
            pass
        try:
            if height is not None:
                self._height = float(height)
        except (TypeError, ValueError):
            pass

    config = configure

    def update_idletasks(self) -> None:  # pragma: no cover - synchronisation no-op
        pass

    def delete(self, *tags: str) -> None:  # pragma: no cover - optional cleanup
        if not tags:
            return
        to_remove = []
        for item_id, data in list(self._items.items()):
            item_tags = data.get("tags", ())
            if any(tag in item_tags for tag in tags):
                to_remove.append(item_id)
        for item_id in to_remove:
            self._items.pop(item_id, None)
        self._tempo_item_ids = tuple(
            item_id for item_id in self._tempo_item_ids if item_id in self._items
        )

    def _compute_bbox(self, item_type: str, coords: Tuple[float, ...], text: str) -> Tuple[float, float, float, float]:
        if item_type == "rectangle" and len(coords) >= 4:
            x1, y1, x2, y2 = coords[:4]
            return (x1, y1, x2, y2)
        if item_type == "line" and len(coords) >= 4:
            x1, y1, x2, y2 = coords[:4]
            left, right = sorted((x1, x2))
            top, bottom = sorted((y1, y2))
            return (left, top, right, bottom)
        if item_type == "text" and len(coords) >= 2:
            x, y = coords[:2]
            width = max(24.0, len(text) * 6.0)
            height = 12.0
            return (x, y - height / 2.0, x + width, y + height / 2.0)
        return (0.0, 0.0, 0.0, 0.0)

    def _add_item(
        self,
        item_type: str,
        coords: Tuple[float, ...],
        *,
        tags: Tuple[str, ...] = (),
        fill: str = "",
        text: str = "",
    ) -> int:
        item_id = self._next_item_id
        self._next_item_id += 1
        metadata = {
            "type": item_type,
            "coords": tuple(float(value) for value in coords),
            "tags": tuple(tags),
            "fill": str(fill),
            "text": str(text),
        }
        metadata["bbox"] = self._compute_bbox(item_type, metadata["coords"], metadata["text"])
        self._items[item_id] = metadata
        return item_id

    def create_rectangle(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        fill: str = "",
        tags: Tuple[str, ...] = (),
    ) -> int:
        return self._add_item("rectangle", (x1, y1, x2, y2), tags=tags, fill=fill)

    def create_line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        fill: str = "",
        tags: Tuple[str, ...] = (),
    ) -> int:
        return self._add_item("line", (x1, y1, x2, y2), tags=tags, fill=fill)

    def create_text(
        self,
        x: float,
        y: float,
        *,
        text: str,
        fill: str = "",
        tags: Tuple[str, ...] = (),
    ) -> int:
        return self._add_item("text", (x, y), tags=tags, fill=fill, text=text)

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

        for item_id in self._tempo_item_ids:
            self._items.pop(item_id, None)
        created: list[int] = []
        for tick, label in markers:
            raw_left = left_pad + tick * px_per_tick + barline_padding
            minimum_left = left_pad + left_padding if tick == 0 else raw_left
            left = float(max(minimum_left, raw_left))
            item_id = self.create_text(
                left,
                float(base_y),
                text=str(label),
                fill="black",
                tags=("tempo_marker",),
            )
            created.append(item_id)
        self._tempo_item_ids = tuple(created)

    def find_withtag(self, tag: str) -> Tuple[int, ...]:
        if tag == "tempo_marker":
            return self._tempo_item_ids
        return tuple(
            item_id
            for item_id, data in self._items.items()
            if tag in data.get("tags", ())
        )

    def itemcget(self, item_id: int, option: str) -> object:
        item = self._items.get(int(item_id), {})
        if option == "text":
            return item.get("text", "")
        if option == "fill":
            return item.get("fill", "")
        return item.get(option)

    def coords(self, item_id: int) -> Tuple[float, ...]:
        item = self._items.get(int(item_id))
        if not item:
            return (0.0,)
        return item.get("coords", (0.0,))  # type: ignore[return-value]

    def bbox(self, item_id: int) -> Tuple[float, float, float, float]:
        item = self._items.get(int(item_id))
        if not item:
            return (0.0, 0.0, 0.0, 0.0)
        bounds = item.get("bbox")
        if isinstance(bounds, tuple):
            return tuple(float(value) for value in bounds)  # type: ignore[return-value]
        return (0.0, 0.0, 0.0, 0.0)

    def type(self, item_id: int) -> str:
        item = self._items.get(int(item_id))
        return str(item.get("type", "")) if item else ""

    def gettags(self, item_id: int) -> Tuple[str, ...]:
        item = self._items.get(int(item_id))
        if not item:
            return tuple()
        return tuple(item.get("tags", ()))

    def tag_raise(self, tag: str) -> None:  # pragma: no cover - ordering not required
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
