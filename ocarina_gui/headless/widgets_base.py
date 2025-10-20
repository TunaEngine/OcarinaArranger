from types import SimpleNamespace
from typing import Any, Callable, Optional, Sequence


class _HeadlessWidget:
    def __init__(self, parent: "_HeadlessContainer | None" = None) -> None:
        self._options: dict[str, object] = {}
        self._bindings: dict[str, list[Callable[[SimpleNamespace], object | None]]] = {}
        self._manager: str = ""
        self._grid_options: dict[str, object] = {}
        self._column_config: dict[int, dict[str, object]] = {}
        self._row_config: dict[int, dict[str, object]] = {}
        self._width: int = 24
        self._height: int = 24
        self._parent: "_HeadlessContainer | None" = None
        if parent is not None:
            self._set_parent(parent)

    def _set_parent(self, parent: "_HeadlessContainer") -> None:
        self._parent = parent
        parent._add_child(self)

    def configure(self, **kwargs: object) -> None:
        if not kwargs:
            return
        image = kwargs.pop("image", None)
        if image is not None:
            self._options["image"] = "" if image in ("", None) else str(image)
        for key, value in kwargs.items():
            self._options[key] = value
        width = self._options.get("width")
        if width is not None:
            try:
                numeric = int(width)
            except (TypeError, ValueError):
                numeric = None
            if numeric and numeric > 0:
                self._width = numeric
        length = self._options.get("length")
        if length is not None:
            try:
                numeric = int(length)
            except (TypeError, ValueError):
                numeric = None
            if numeric and numeric > 0:
                self._width = numeric
        height = self._options.get("height")
        if height is not None:
            try:
                numeric = int(height)
            except (TypeError, ValueError):
                numeric = None
            if numeric and numeric > 0:
                self._height = numeric

    config = configure
    def cget(self, option: str) -> object:
        if option == "image":
            return self._options.get("image", "")
        return self._options.get(option, "")

    def bind(
        self,
        sequence: str,
        func: Callable[[SimpleNamespace], object | None] | None,
        add: str | None = None,
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

    def pack(self, **kwargs: object) -> None:
        if kwargs:
            self._grid_options.update(kwargs)
        self._manager = "pack"

    def pack_forget(self) -> None:
        self._manager = ""

    def update_idletasks(self) -> None: return None

    def winfo_height(self) -> int: return self._height

    def winfo_manager(self) -> str: return self._manager

    def winfo_width(self) -> int: return self._width

    def winfo_ismapped(self) -> bool: return bool(self._manager)

    def columnconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None:
        self._column_config[index] = {"weight": weight, **kwargs}

    def rowconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None:
        self._row_config[index] = {"weight": weight, **kwargs}

    def destroy(self) -> None:
        self.grid_remove()
        parent = self._parent
        if parent is not None:
            parent._remove_child(self)
        self._options["destroyed"] = True


class _HeadlessContainer(_HeadlessWidget):
    def __init__(self, parent: "_HeadlessContainer | None" = None) -> None:
        super().__init__(parent)
        self._children: list[_HeadlessWidget] = []

    def _add_child(self, widget: _HeadlessWidget) -> None:
        self._children.append(widget)

    def _remove_child(self, widget: _HeadlessWidget) -> None:
        self._children = [child for child in self._children if child is not widget]

    def winfo_children(self) -> tuple[_HeadlessWidget, ...]:
        return tuple(self._children)


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
    def __init__(
        self,
        command: Optional[Callable[[], None]] = None,
        *,
        text: str = "",
        enabled: bool = False,
        parent: _HeadlessContainer | None = None,
    ) -> None:
        _HeadlessStateful.__init__(self)
        _HeadlessWidget.__init__(self, parent)
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
        if "command" in kwargs:
            command_value = kwargs["command"]
            self._command = command_value if callable(command_value) else None
        _HeadlessWidget.configure(self, **kwargs)

    config = configure
    def invoke(self) -> None:
        if "disabled" in self._states:
            return
        if self._command is not None:
            self._command()


class HeadlessSpinbox(_HeadlessStateful, _HeadlessWidget):
    def __init__(self, parent: _HeadlessContainer | None = None) -> None:
        _HeadlessStateful.__init__(self)
        _HeadlessWidget.__init__(self, parent)


class HeadlessCheckbutton(_HeadlessStateful, _HeadlessWidget):
    def __init__(
        self,
        *,
        text: str = "",
        variable: Any | None = None,
        command: Optional[Callable[[], None]] = None,
        parent: _HeadlessContainer | None = None,
    ) -> None:
        _HeadlessStateful.__init__(self)
        _HeadlessWidget.__init__(self, parent)
        self._options.update({"text": text})
        self._variable = variable
        self._command = command

    def configure(self, **kwargs: object) -> None:
        if "text" in kwargs:
            text_value = kwargs["text"]
            self._options["text"] = "" if text_value is None else str(text_value)
        if "variable" in kwargs:
            self._variable = kwargs["variable"]
        if "command" in kwargs:
            command_value = kwargs["command"]
            self._command = command_value if callable(command_value) else None
        _HeadlessWidget.configure(self, **kwargs)

    config = configure
    def cget(self, option: str) -> object:
        if option == "text":
            return self._options.get("text", "")
        if option == "variable":
            return self._variable
        return super().cget(option)

    def invoke(self) -> None:
        if "disabled" in self._states:
            return
        var = self._variable
        if var is not None:
            try:
                current = bool(var.get())
            except Exception:
                current = False
            try:
                var.set(not current)
            except Exception:
                pass
        if self._command is not None:
            self._command()


class HeadlessScale(_HeadlessStateful, _HeadlessWidget):
    def __init__(
        self,
        *,
        variable: Any,
        from_: float = 0.0,
        to: float = 100.0,
        length: int = 120,
        parent: _HeadlessContainer | None = None,
    ) -> None:
        _HeadlessStateful.__init__(self)
        _HeadlessWidget.__init__(self, parent)
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
        _HeadlessWidget.configure(self, **kwargs)
        for key in ("from", "to"):
            if key in kwargs:
                try:
                    self._options[key] = float(kwargs[key])
                except (TypeError, ValueError):
                    continue

    config = configure
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


class HeadlessLabel(_HeadlessWidget):
    def __init__(
        self,
        text: str = "",
        *,
        parent: _HeadlessContainer | None = None,
        **options: object,
    ) -> None:
        super().__init__(parent)
        self._options["text"] = "" if text is None else str(text)
        if options:
            self.configure(**options)

    def configure(self, **kwargs: object) -> None:
        if "text" in kwargs:
            text_value = kwargs["text"]
            self._options["text"] = "" if text_value is None else str(text_value)
        _HeadlessWidget.configure(self, **kwargs)

    config = configure
    def cget(self, option: str) -> object:
        if option == "text":
            return self._options.get("text", "")
        return super().cget(option)

    def destroy(self) -> None:
        super().destroy()


class HeadlessRadiobutton(_HeadlessStateful, _HeadlessWidget):
    def __init__(
        self,
        *,
        text: str = "",
        variable: Any | None = None,
        value: Any = None,
        command: Optional[Callable[[], None]] = None,
        parent: _HeadlessContainer | None = None,
    ) -> None:
        _HeadlessStateful.__init__(self)
        _HeadlessWidget.__init__(self, parent)
        self._options.update({"text": text, "value": value})
        self._variable = variable
        self._command = command

    def configure(self, **kwargs: object) -> None:
        if "text" in kwargs:
            text_value = kwargs["text"]
            self._options["text"] = "" if text_value is None else str(text_value)
        if "value" in kwargs:
            self._options["value"] = kwargs["value"]
        if "variable" in kwargs:
            self._variable = kwargs["variable"]
        if "command" in kwargs:
            command_value = kwargs["command"]
            self._command = command_value if callable(command_value) else None
        _HeadlessWidget.configure(self, **kwargs)

    config = configure
    def cget(self, option: str) -> object:
        if option == "text":
            return self._options.get("text", "")
        if option == "value":
            return self._options.get("value")
        return super().cget(option)

    def invoke(self) -> None:
        if "disabled" in self._states:
            return
        variable = self._variable
        if variable is not None:
            try:
                variable.set(self._options.get("value"))
            except Exception:
                pass
        if self._command is not None:
            self._command()


class HeadlessCombobox(_HeadlessStateful, _HeadlessWidget):
    def __init__(
        self,
        *,
        textvariable: Any | None = None,
        values: Sequence[object] = (),
        parent: _HeadlessContainer | None = None,
    ) -> None:
        _HeadlessStateful.__init__(self)
        _HeadlessWidget.__init__(self, parent)
        self._textvariable = textvariable
        self._values: tuple[object, ...] = tuple(values)

    def configure(self, **kwargs: object) -> None:
        if "values" in kwargs:
            try:
                self._values = tuple(kwargs["values"])  # type: ignore[arg-type]
            except Exception:
                self._values = tuple(self._values)
        _HeadlessWidget.configure(self, **kwargs)

    config = configure
    def cget(self, option: str) -> object:
        if option == "values":
            return self._values
        return super().cget(option)


class HeadlessProgressbar(_HeadlessWidget):
    def __init__(
        self,
        *,
        maximum: float = 100.0,
        variable: Any | None = None,
        parent: _HeadlessContainer | None = None,
    ) -> None:
        super().__init__(parent)
        self._options.update({"maximum": float(maximum), "value": 0.0})
        self._variable = variable

    def configure(self, **kwargs: object) -> None:
        if "value" in kwargs:
            try:
                self._options["value"] = float(kwargs["value"])
            except (TypeError, ValueError):
                self._options["value"] = 0.0
        if "variable" in kwargs:
            self._variable = kwargs["variable"]
        _HeadlessWidget.configure(self, **kwargs)

    config = configure
    def cget(self, option: str) -> object:
        if option in {"value", "maximum"}:
            return self._options.get(option, 0.0)
        if option == "variable":
            return self._variable
        return super().cget(option)


class HeadlessNotebook(_HeadlessContainer):
    def __init__(self, parent: _HeadlessContainer | None = None) -> None:
        super().__init__(parent)
        self._tabs: list[tuple[_HeadlessWidget, dict[str, object]]] = []

    def add(self, child: _HeadlessWidget, **options: object) -> None:
        self._tabs.append((child, dict(options)))


class HeadlessFrame(_HeadlessContainer):
    def __init__(self, parent: _HeadlessContainer | None = None) -> None:
        super().__init__(parent)
        self._place_info: dict[str, object] = {}

    def place(self, **kwargs: object) -> None:
        self._manager = "place"
        self._place_info = kwargs

    def place_forget(self) -> None:
        self._manager = ""
        self._place_info = {}

    def place_info(self) -> dict[str, object]:
        return dict(self._place_info)
