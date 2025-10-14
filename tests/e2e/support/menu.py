from __future__ import annotations

from typing import Any, Callable, Optional, Sequence


class HeadlessMenu:
    """A minimal stand-in for :class:`tkinter.Menu` usable in headless tests."""

    def __init__(self, master: Any | None = None, *, tearoff: bool = False) -> None:
        self.master = master
        self.tearoff = tearoff
        self._entries: list[dict[str, Any]] = []
        self._children: list[HeadlessMenu] = []
        if master is not None:
            registry = getattr(master, "_test_menu_registry", None)
            if registry is None:
                registry = {}
                setattr(master, "_test_menu_registry", registry)
            registry[id(self)] = self
            if not isinstance(master, HeadlessMenu) and not hasattr(master, "_test_menubar"):
                setattr(master, "_test_menubar", self)

    # Construction helpers -------------------------------------------------
    def add_command(
        self,
        *,
        label: str,
        command: Callable[[], None] | None = None,
        state: str = "normal",
        accelerator: str | None = None,
    ) -> None:
        self._entries.append({
            "type": "command",
            "label": label,
            "command": command,
            "state": state,
            "accelerator": accelerator,
        })

    def add_separator(self) -> None:
        self._entries.append({"type": "separator"})

    def add_cascade(self, *, label: str, menu: "HeadlessMenu", state: str = "normal") -> None:
        self._children.append(menu)
        self._entries.append({
            "type": "cascade",
            "label": label,
            "menu": menu,
            "state": state,
        })

    def add_radiobutton(
        self,
        *,
        label: str,
        variable: Any | None = None,
        value: Any | None = None,
        command: Callable[[], None] | None = None,
        state: str = "normal",
    ) -> None:
        self._entries.append({
            "type": "radiobutton",
            "label": label,
            "variable": variable,
            "value": value,
            "command": command,
            "state": state,
        })

    def add_checkbutton(
        self,
        *,
        label: str,
        variable: Any | None = None,
        command: Callable[[], None] | None = None,
        onvalue: Any = True,
        offvalue: Any = False,
        state: str = "normal",
    ) -> None:
        self._entries.append({
            "type": "checkbutton",
            "label": label,
            "variable": variable,
            "onvalue": onvalue,
            "offvalue": offvalue,
            "command": command,
            "state": state,
        })

    # Tk compatibility methods ---------------------------------------------
    def delete(self, first: int | str, last: int | str | None = None) -> None:
        if first == 0 and (last in (None, "end")):
            self._entries.clear()
            return
        start = self.index(first)
        if last is None:
            if 0 <= start < len(self._entries):
                del self._entries[start]
            return
        end = self.index(last)
        if end < start:
            start, end = end, start
        del self._entries[start : end + 1]

    def index(self, index: int | str) -> int:
        if index == "end":
            return len(self._entries) - 1
        if isinstance(index, str):
            return int(index)
        return index

    def entrycget(self, index: int | str, option: str) -> Any:
        entry = self._entries[self.index(index)]
        return entry.get(option)

    def entryconfigure(self, index: int | str, **kwargs: Any) -> None:
        entry = self._entries[self.index(index)]
        entry.update(kwargs)

    def type(self, index: int | str) -> str | None:
        entry = self._entries[self.index(index)]
        return entry.get("type")

    def invoke(self, index: int | str) -> None:
        entry = self._entries[self.index(index)]
        if entry.get("state") == "disabled":
            return
        entry_type = entry.get("type")
        if entry_type == "command":
            callback = entry.get("command")
            if callable(callback):
                callback()
        elif entry_type == "radiobutton":
            variable = entry.get("variable")
            value = entry.get("value")
            if variable is not None:
                try:
                    variable.set(value)
                except Exception:
                    pass
            callback = entry.get("command")
            if callable(callback):
                callback()
        elif entry_type == "checkbutton":
            variable = entry.get("variable")
            onvalue = entry.get("onvalue")
            offvalue = entry.get("offvalue")
            if variable is not None:
                try:
                    current = variable.get()
                except Exception:
                    current = offvalue
                new_value = offvalue if current == onvalue else onvalue
                try:
                    variable.set(new_value)
                except Exception:
                    pass
            callback = entry.get("command")
            if callable(callback):
                callback()
        # Cascades and separators have no direct invocation behaviour

    # Misc helpers ---------------------------------------------------------
    def destroy(self) -> None:  # pragma: no cover - compatibility no-op
        self._entries.clear()
        self._children.clear()

    # Introspection helpers used by tests ---------------------------------
    def labels(self) -> Sequence[str]:
        return [entry.get("label", "") for entry in self._entries]


def _resolve_menubar(widget: Any) -> HeadlessMenu:
    try:
        menu_name = widget.cget("menu")
    except Exception:
        menu_name = None
    if menu_name:
        try:
            menubar = widget.nametowidget(menu_name)
        except Exception:
            menubar = None
        if menubar is not None:
            return menubar
    menubar = getattr(widget, "_test_menubar", None)
    if menubar is None:
        raise AssertionError("Application window has no menubar available")
    return menubar


def _find_menu_entry(menu: HeadlessMenu, label: str) -> tuple[int, dict[str, Any]]:
    for index, entry in enumerate(menu._entries):  # noqa: SLF001 - internal access for tests
        if entry.get("label") == label:
            return index, entry
    raise AssertionError(f"Menu item {label!r} was not found")


def get_submenu(menu: HeadlessMenu, label: str) -> HeadlessMenu:
    index, entry = _find_menu_entry(menu, label)
    if entry.get("type") != "cascade":
        raise AssertionError(f"Menu item {label!r} is not a cascade")
    submenu = entry.get("menu")
    if not isinstance(submenu, HeadlessMenu):
        raise AssertionError(f"Cascade {label!r} has no submenu")
    return submenu


def invoke_menu_path(widget: Any, *labels: str) -> None:
    if not labels:
        raise AssertionError("No menu path specified")
    menu = _resolve_menubar(widget)
    for label in labels[:-1]:
        menu = get_submenu(menu, label)
    target_label = labels[-1]
    index, _entry = _find_menu_entry(menu, target_label)
    menu.invoke(index)


def list_menu_entries(widget: Any, *path: str) -> Sequence[str]:
    menu = _resolve_menubar(widget)
    for label in path:
        menu = get_submenu(menu, label)
    return menu.labels()


def set_menu_command(widget: Any, *labels: str, command: Optional[Callable[[], None]]) -> Optional[Callable[[], None]]:
    """Replace the command associated with a menu entry.

    Returns the previous command so callers can restore it after wrapping.
    """

    if not labels:
        raise AssertionError("No menu path specified")
    menu = _resolve_menubar(widget)
    for label in labels[:-1]:
        menu = get_submenu(menu, label)
    index, entry = _find_menu_entry(menu, labels[-1])
    previous = entry.get("command")
    entry["command"] = command
    return previous
