"""Headless-compatible replacements for Tk image objects."""

from __future__ import annotations


class HeadlessPhotoImage:
    """Simple placeholder for ``tk.PhotoImage`` when Tk is unavailable."""

    _COUNTER = 0

    def __init__(
        self,
        master=None,
        *,
        width: int | float | None = None,
        height: int | float | None = None,
        file: str | None = None,
        **_kwargs: object,
    ) -> None:
        type(self)._COUNTER += 1
        self._name = f"headless_image_{type(self)._COUNTER}"
        self._width = self._coerce_int(width, default=1)
        self._height = self._coerce_int(height, default=1)
        self._file = file

    @staticmethod
    def _coerce_int(value: int | float | None, *, default: int) -> int:
        if value is None:
            return default
        try:
            numeric = int(round(float(value)))
        except (TypeError, ValueError):
            return default
        return max(1, numeric)

    def __str__(self) -> str:  # pragma: no cover - exercised indirectly
        return self._name

    def copy(self) -> "HeadlessPhotoImage":
        return HeadlessPhotoImage(width=self._width, height=self._height, file=self._file)

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height

    def zoom(self, x: int = 1, y: int | None = None) -> "HeadlessPhotoImage":
        factor_x = max(1, int(x))
        factor_y = factor_x if y is None else max(1, int(y))
        return HeadlessPhotoImage(
            width=self._width * factor_x,
            height=self._height * factor_y,
            file=self._file,
        )

    def subsample(self, x: int = 1, y: int | None = None) -> "HeadlessPhotoImage":
        factor_x = max(1, int(x))
        factor_y = factor_x if y is None else max(1, int(y))
        return HeadlessPhotoImage(
            width=max(1, self._width // factor_x),
            height=max(1, self._height // factor_y),
            file=self._file,
        )


def install_headless_photoimage() -> None:
    """Replace ``tk.PhotoImage`` with a lightweight stub for headless tests."""

    try:
        import tkinter as tk
    except Exception:  # pragma: no cover - Tk unavailable
        return
    current = getattr(tk, "PhotoImage", None)
    if current is HeadlessPhotoImage:
        return
    tk.PhotoImage = HeadlessPhotoImage  # type: ignore[attr-defined]
