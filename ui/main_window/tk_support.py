from __future__ import annotations

import gc
import logging
import tkinter as tk
import weakref
from typing import Iterator

logger = logging.getLogger(__name__)

_TK_VARIABLE_REFS: list[weakref.ReferenceType[tk.Variable]] = []


def _track_tk_variable(var: tk.Variable) -> None:
    """Record ``var`` so it can be detached from the Tcl interpreter later."""

    try:
        _TK_VARIABLE_REFS.append(weakref.ref(var))
    except TypeError:
        # ``tkinter.Variable`` instances support weak references, but play nice if
        # that ever changes.
        pass


def _tracked_tk_variables() -> tuple[tk.Variable, ...]:
    """Return the live Tk variables captured via :func:`_track_tk_variable`."""

    alive: list[tk.Variable] = []
    keep: list[weakref.ReferenceType[tk.Variable]] = []
    for ref in _TK_VARIABLE_REFS:
        var = ref()
        if var is None:
            continue
        alive.append(var)
        keep.append(ref)
    if len(keep) != len(_TK_VARIABLE_REFS):
        _TK_VARIABLE_REFS[:] = keep
    return tuple(alive)


def _wrap_tk_variable_init() -> None:
    """Ensure ``tkinter.Variable`` instances are tracked on construction."""

    if hasattr(tk.Variable.__init__, "_ocarina_tracked"):
        return

    original_init = tk.Variable.__init__

    def _tracked_init(self, *args, **kwargs):  # type: ignore[override]
        original_init(self, *args, **kwargs)
        _track_tk_variable(self)

    _tracked_init._ocarina_tracked = True  # type: ignore[attr-defined]
    _tracked_init.__wrapped__ = original_init  # type: ignore[attr-defined]
    tk.Variable.__init__ = _tracked_init  # type: ignore[assignment]


_wrap_tk_variable_init()


def _iter_tk_variables(value: object, visited: set[int]) -> Iterator[tk.Variable]:
    if value is None:
        return
    obj_id = id(value)
    if obj_id in visited:
        return
    visited.add(obj_id)
    if isinstance(value, tk.Variable):
        yield value
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _iter_tk_variables(item, visited)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _iter_tk_variables(item, visited)
        return


def collect_tk_variables_from_attrs(obj: object) -> tuple[tk.Variable, ...]:
    """Collect Tk variables referenced by ``obj`` instance attributes."""

    visited: set[int] = set()
    collected: list[tk.Variable] = []
    for attribute in getattr(obj, "__dict__", {}).values():
        collected.extend(_iter_tk_variables(attribute, visited))
    return tuple(collected)


def release_tracked_tk_variables(
    obj: object,
    interpreter: object | None = None,
    *,
    log: logging.Logger | None = None,
) -> None:
    """Detach Tk interpreter references from Tkinter variables.

    On Windows the ``tkinter.Variable`` destructor attempts to talk to the
    Tcl interpreter.  Once the window has been destroyed that call raises a
    ``RuntimeError`` complaining that the main thread is not in the main
    loop.  Clearing the interpreter reference prevents the destructor from
    making that call when the variables are eventually garbage collected.
    """

    if log is None:
        log = logger

    visited: set[int] = set()

    def detach(var: tk.Variable | None) -> None:
        if var is None:
            return
        if interpreter is not None and getattr(var, "_tk", None) is not interpreter:
            return
        var_id = id(var)
        if var_id in visited:
            return
        visited.add(var_id)
        for attr in ("_tk", "_root"):
            if hasattr(var, attr):
                try:
                    setattr(var, attr, None)
                except Exception:
                    continue

    for var in collect_tk_variables_from_attrs(obj):
        detach(var)

    for var in _tracked_tk_variables():
        detach(var)

    if interpreter is None:
        return

    try:
        for candidate in gc.get_objects():
            if isinstance(candidate, tk.Variable):
                detach(candidate)
    except Exception:
        log.debug("Failed scanning gc objects for Tk variables", exc_info=True)


__all__ = [
    "collect_tk_variables_from_attrs",
    "release_tracked_tk_variables",
]
