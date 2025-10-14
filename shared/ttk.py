"""Shared access to ttk widgets with runtime bootstrap fallbacks."""

from __future__ import annotations

from types import ModuleType
from typing import Any, Iterable

from tkinter import ttk as _native_ttk

try:
    import ttkbootstrap as _bootstrap_ttk  # type: ignore
except ModuleNotFoundError as exc:  # pragma: no cover - dependency optional
    _bootstrap_ttk = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

_active_module: ModuleType = _bootstrap_ttk or _native_ttk


def _module_dir(module: ModuleType) -> Iterable[str]:
    try:
        return dir(module)
    except Exception:  # pragma: no cover - defensive
        return ()


class _DynamicTTK:
    """Proxy object that resolves attributes against the active ttk module."""

    def __getattr__(self, name: str) -> Any:
        return getattr(_active_module, name)

    def __dir__(self) -> list[str]:  # pragma: no cover - used for introspection
        names = set(_module_dir(_native_ttk))
        if _bootstrap_ttk is not None:
            names.update(_module_dir(_bootstrap_ttk))
        return sorted(names)


ttk = _DynamicTTK()


def use_native_ttk() -> None:
    """Route future ttk lookups to the standard :mod:`tkinter.ttk` module."""

    global _active_module
    _active_module = _native_ttk


def use_bootstrap_ttk() -> None:
    """Route future ttk lookups to :mod:`ttkbootstrap` if available."""

    if _bootstrap_ttk is None:
        raise ModuleNotFoundError("ttkbootstrap is not installed") from _IMPORT_ERROR

    global _active_module
    _active_module = _bootstrap_ttk


def is_bootstrap_enabled() -> bool:
    """Return ``True`` when ttkbootstrap widgets are actively being used."""

    return _bootstrap_ttk is not None and _active_module is _bootstrap_ttk


__all__ = ["ttk", "use_bootstrap_ttk", "use_native_ttk", "is_bootstrap_enabled"]
