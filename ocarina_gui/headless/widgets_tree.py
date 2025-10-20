from typing import Callable, Sequence

from .widgets_base import _HeadlessContainer, _HeadlessWidget


class HeadlessTreeview(_HeadlessWidget):
    def __init__(
        self,
        *,
        columns: Sequence[str] = (),
        show: str = "headings",
        selectmode: str = "none",
        height: int = 0,
        parent: _HeadlessContainer | None = None,
    ) -> None:
        super().__init__(parent)
        self._columns = tuple(columns)
        self._show = show
        self._selectmode = selectmode
        if height:
            try:
                self._height = int(height)
            except (TypeError, ValueError):
                pass
        self._items: list[tuple[str, tuple[object, ...], tuple[str, ...]]] = []
        self._headings: dict[str, dict[str, object]] = {}
        self._column_options: dict[str, dict[str, object]] = {}
        self._tag_options: dict[str, dict[str, object]] = {}
        self._yscrollcommand: Callable[[float, float], object] | None = None
        self._selection: tuple[str, ...] = ()

    def configure(self, **kwargs: object) -> None:
        if "columns" in kwargs:
            try:
                self._columns = tuple(kwargs["columns"])  # type: ignore[arg-type]
            except Exception:
                pass
        if "yscrollcommand" in kwargs:
            command = kwargs["yscrollcommand"]
            if callable(command):
                self._yscrollcommand = command  # type: ignore[assignment]
        super().configure(**kwargs)

    config = configure

    def heading(self, column: str, **options: object) -> None:
        self._headings[column] = dict(options)

    def column(self, column: str, **options: object) -> None:
        self._column_options[column] = dict(options)

    def get_children(self, item: str | None = None) -> tuple[str, ...]:
        if item not in (None, "", ()):  # pragma: no cover
            return ()
        return tuple(item_id for item_id, _values, _tags in self._items)

    def delete(self, *item_ids: str) -> None:
        if not item_ids:
            self._items.clear()
            self._selection = ()
            return
        targets = set(item_ids)
        self._items = [entry for entry in self._items if entry[0] not in targets]
        self._selection = tuple(item for item in self._selection if item not in targets)

    def insert(
        self,
        parent: str,
        index: int | str,
        iid: str | None = None,
        **options: object,
    ) -> str:
        values = tuple(options.get("values", ()))
        tags = tuple(options.get("tags", ()))
        item_id = iid or f"I{len(self._items)}"
        entry = (item_id, values, tags)
        if index == "end":
            self._items.append(entry)
        else:
            try:
                numeric_index = int(index)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                self._items.append(entry)
            else:
                self._items.insert(max(0, min(len(self._items), numeric_index)), entry)
        return item_id

    def item(
        self,
        item_id: str,
        option: str | None = None,
        **options: object,
    ) -> dict[str, object] | tuple[object, ...]:
        for index, (stored_id, values, tags) in enumerate(self._items):
            if stored_id != item_id:
                continue
            new_values = values
            new_tags = tags
            if "values" in options:
                new_values = tuple(options["values"])  # type: ignore[arg-type]
            if "tags" in options:
                new_tags = tuple(options["tags"])  # type: ignore[arg-type]
            if new_values is not values or new_tags is not tags:
                self._items[index] = (stored_id, new_values, new_tags)
            result: dict[str, object] = {"values": new_values, "tags": new_tags}
            if option is not None and not options:
                return result.get(option, ())  # type: ignore[return-value]
            if options:
                return result
            return result
        return {"values": (), "tags": ()} if option is None else ()

    def tag_configure(self, tag: str, **options: object) -> None:
        self._tag_options[tag] = dict(options)

    def yview_moveto(self, fraction: float) -> None:
        try:
            value = float(fraction)
        except (TypeError, ValueError):
            value = 0.0
        self._options["yview"] = value
        if self._yscrollcommand is not None:
            try:
                self._yscrollcommand(value, value)
            except Exception:  # pragma: no cover
                pass

    def selection(self) -> tuple[str, ...]:
        return self._selection

    def selection_set(self, items: Sequence[str] | str) -> None:
        if isinstance(items, str):
            self._selection = (items,)
        else:
            self._selection = tuple(items)

    def selection_clear(self) -> None:
        self._selection = ()

