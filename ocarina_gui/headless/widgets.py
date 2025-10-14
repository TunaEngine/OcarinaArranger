"""Primitive widget stand-ins for headless GUI tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, Optional, Sequence


class _HeadlessWidget:
    """Common behaviour for headless widget stand-ins."""

    def __init__(self) -> None:
        self._options: dict[str, object] = {}
        self._bindings: dict[str, list[Callable[[SimpleNamespace], object | None]]] = {}
        self._manager: str = ""
        self._grid_options: dict[str, object] = {}
        self._width: int = 24
        self._height: int = 24

    def configure(self, **kwargs: object) -> None:
        if not kwargs:
            return
        image = kwargs.pop("image", None)
        if image is not None:
            if image in ("", None):
                self._options["image"] = ""
            else:
                self._options["image"] = str(image)
        for key, value in kwargs.items():
            self._options[key] = value
        width = self._options.get("width")
        if width is not None:
            try:
                self._width = int(width) if int(width) > 0 else self._width
            except (TypeError, ValueError):
                pass
        length = self._options.get("length")
        if length is not None:
            try:
                length_value = int(length)
            except (TypeError, ValueError):
                length_value = None
            if length_value:
                self._width = max(1, length_value)
        height = self._options.get("height")
        if height is not None:
            try:
                height_value = int(height)
            except (TypeError, ValueError):
                height_value = None
            if height_value:
                self._height = max(1, height_value)

    config = configure

    def cget(self, option: str) -> object:
        if option == "image":
            return self._options.get("image", "")
        return self._options.get(option, "")

    def bind(
        self, sequence: str, func: Callable[[SimpleNamespace], object | None] | None, add: str | None = None
    ) -> None:
        if func is None:
            return
        if add == "+" and sequence in self._bindings:
            self._bindings[sequence].append(func)
        else:
            self._bindings[sequence] = [func]

    def event_generate(self, sequence: str, **kwargs: object) -> None:
        callbacks = list(self._bindings.get(sequence, ()))
        if not callbacks:
            return
        event = SimpleNamespace(widget=self, **kwargs)
        for callback in callbacks:
            callback(event)

    def grid(self, **kwargs: object) -> None:
        if kwargs:
            self._grid_options.update(kwargs)
        self._manager = "grid"

    def grid_configure(self, **kwargs: object) -> None:
        if kwargs:
            self._grid_options.update(kwargs)
        self._manager = "grid"

    def grid_remove(self) -> None:
        self._manager = ""

    def grid_info(self) -> dict[str, object]:
        return dict(self._grid_options)

    def update_idletasks(self) -> None:  # pragma: no cover - compatibility shim
        return None

    def winfo_height(self) -> int:
        return self._height

    def winfo_manager(self) -> str:
        return self._manager

    def winfo_width(self) -> int:
        return self._width


class _HeadlessStateful:
    def __init__(self) -> None:
        self._states: set[str] = set()

    def state(self, states: Optional[Sequence[str]] = None) -> tuple[str, ...]:
        if states is None:
            return tuple(self._states)
        for flag in states:
            if flag.startswith("!"):
                self._states.discard(flag[1:])
            else:
                self._states.add(flag)
        return tuple(self._states)

    def instate(self, states: Sequence[str]) -> bool:
        for flag in states:
            if flag.startswith("!"):
                if flag[1:] in self._states:
                    return False
            elif flag not in self._states:
                return False
        return True


class HeadlessButton(_HeadlessStateful, _HeadlessWidget):
    """Minimal stand-in for ttk.Button in headless tests."""

    def __init__(
        self,
        command: Optional[Callable[[], None]] = None,
        *,
        text: str = "",
        enabled: bool = False,
    ) -> None:
        _HeadlessStateful.__init__(self)
        _HeadlessWidget.__init__(self)
        self._command = command
        self._options.update(
            {
                "text": text,
                "compound": "center",
                "bootstyle": None,
                "width": 24,
            }
        )
        if not enabled:
            self._states.add("disabled")

    def configure(self, **kwargs: object) -> None:
        if "text" in kwargs:
            text_value = kwargs["text"]
            self._options["text"] = "" if text_value is None else str(text_value)
        _HeadlessWidget.configure(self, **kwargs)

    def invoke(self) -> None:
        if "disabled" in self._states:
            return
        if self._command is not None:
            self._command()


class HeadlessSpinbox(_HeadlessStateful, _HeadlessWidget):
    def __init__(self) -> None:
        _HeadlessStateful.__init__(self)
        _HeadlessWidget.__init__(self)


class HeadlessCheckbutton(_HeadlessStateful, _HeadlessWidget):
    def __init__(self) -> None:
        _HeadlessStateful.__init__(self)
        _HeadlessWidget.__init__(self)


class HeadlessScale(_HeadlessStateful, _HeadlessWidget):
    """Headless replacement for ``ttk.Scale`` used in GUI tests."""

    def __init__(
        self,
        *,
        variable: Any,
        from_: float = 0.0,
        to: float = 100.0,
        length: int = 120,
    ) -> None:
        _HeadlessStateful.__init__(self)
        _HeadlessWidget.__init__(self)
        self._variable = variable
        self._options.update({"from": float(from_), "to": float(to), "length": length})
        self._width = max(1, int(length))
        self._height = 16
        try:
            initial = float(variable.get())
        except Exception:
            initial = float(from_)
        self._value = float(from_)
        self.set(initial)

    def configure(self, **kwargs: object) -> None:
        if "from_" in kwargs:
            kwargs = dict(kwargs)
            kwargs["from"] = kwargs.pop("from_")
        super().configure(**kwargs)
        for key in ("from", "to"):
            if key in kwargs:
                try:
                    self._options[key] = float(kwargs[key])
                except (TypeError, ValueError):
                    continue

    def cget(self, option: str) -> object:
        if option == "from":
            return self._options.get("from", 0.0)
        if option == "to":
            return self._options.get("to", 100.0)
        return super().cget(option)

    def get(self) -> float:
        return float(self._value)

    def set(self, value: float) -> None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return
        lower = float(self._options.get("from", 0.0))
        upper = float(self._options.get("to", 100.0))
        self._value = max(lower, min(upper, numeric))
        variable = self._variable
        if variable is not None:
            try:
                variable.set(self._value)
            except Exception:
                pass


class HeadlessFrame:
    """Simple frame stub that tracks geometry manager interactions."""

    def __init__(self) -> None:
        self._manager = ""
        self._place_info: dict[str, object] = {}

    def pack(self, **_kwargs: object) -> None:
        self._manager = "pack"

    def pack_forget(self) -> None:
        self._manager = ""

    def place(self, **kwargs: object) -> None:
        self._manager = "place"
        self._place_info = kwargs

    def place_forget(self) -> None:
        self._manager = ""
        self._place_info = {}

    def lift(self) -> None:  # pragma: no cover - no-op for tests
        pass

    def lower(self) -> None:  # pragma: no cover - no-op for tests
        pass

    def winfo_manager(self) -> str:
        return self._manager

    def place_info(self) -> dict[str, object]:  # pragma: no cover - debugging helper
        return self._place_info

    def winfo_ismapped(self) -> bool:
        return bool(self._manager)

    def focus_set(self) -> None:  # pragma: no cover - no-op for tests
        pass
