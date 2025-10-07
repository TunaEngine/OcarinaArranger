"""Shared access to ttk widgets provided by :mod:`ttkbootstrap`."""

from __future__ import annotations

from typing import Any

try:
    import ttkbootstrap as ttk  # type: ignore
except ModuleNotFoundError as exc:  # pragma: no cover - triggered when dependency missing

    _IMPORT_ERROR = exc

    class _MissingBootstrap:
        def __getattr__(self, name: str) -> Any:  # pragma: no cover - defensive
            raise AttributeError("ttkbootstrap is not installed") from _IMPORT_ERROR

        def __call__(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover
            raise ModuleNotFoundError("ttkbootstrap is not installed") from _IMPORT_ERROR

    ttk = _MissingBootstrap()  # type: ignore[assignment]
else:
    _IMPORT_ERROR = None

__all__ = ["ttk"]
