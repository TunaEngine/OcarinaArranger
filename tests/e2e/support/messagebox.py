from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque


@dataclass(slots=True)
class MessageboxRecorder:
    showinfo_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)
    showerror_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)
    askyesno_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)
    askyesnocancel_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)
    _yesno_responses: Deque[bool] = field(default_factory=deque)
    _yesnocancel_responses: Deque[bool | None] = field(default_factory=deque)

    def showinfo(self, *args: Any, **kwargs: Any) -> None:
        self.showinfo_calls.append((args, kwargs))

    def showerror(self, *args: Any, **kwargs: Any) -> None:
        self.showerror_calls.append((args, kwargs))

    def queue_yesno_response(self, response: bool) -> None:
        self._yesno_responses.append(response)

    def queue_yesnocancel_response(self, response: bool | None) -> None:
        self._yesnocancel_responses.append(response)

    def askyesno(self, *args: Any, **kwargs: Any) -> bool:
        self.askyesno_calls.append((args, kwargs))
        if self._yesno_responses:
            return self._yesno_responses.popleft()
        return True

    def askyesnocancel(self, *args: Any, **kwargs: Any) -> bool | None:
        self.askyesnocancel_calls.append((args, kwargs))
        if self._yesnocancel_responses:
            return self._yesnocancel_responses.popleft()
        return True
