"""Scrollbar management for the staff view widget."""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .view import StaffView


logger = logging.getLogger(__name__)


class ScrollbarManager:
    """Encapsulates grid configuration and bookkeeping for scrollbars."""

    def __init__(self, view: "StaffView", placeholder_minsize: int = 70) -> None:
        self._view = view
        self._placeholder_minsize = placeholder_minsize
        self._hbar_grid_kwargs = self._capture_grid_kwargs(view.hbar)
        self._vbar_grid_kwargs = self._capture_grid_kwargs(view.vbar)
        self._last_scroll_fraction: Optional[float] = None

    # ------------------------------------------------------------------
    # Public API used by :class:`StaffView`
    # ------------------------------------------------------------------
    def configure_for_layout(self, layout_mode: str) -> None:
        view = self._view
        if layout_mode == "horizontal":
            if self._hbar_grid_kwargs is not None:
                try:
                    view.hbar.grid(**self._hbar_grid_kwargs)
                except Exception:  # pragma: no cover - Tkinter quirk
                    pass
            if self._vbar_grid_kwargs is not None:
                try:
                    view.vbar.grid(**self._vbar_grid_kwargs)
                except Exception:  # pragma: no cover - Tkinter quirk
                    pass
            view.canvas.configure(xscrollcommand=view._xsync_from_staff, yscrollcommand=None)
            view.hbar.configure(command=view.canvas.xview)
            view.vbar.configure(command=view.canvas.yview)
        else:
            if self._hbar_grid_kwargs is not None:
                try:
                    view.hbar.grid_remove()
                except Exception:  # pragma: no cover - Tkinter quirk
                    pass
            if self._vbar_grid_kwargs is not None:
                self.grid_vertical_scrollbar(self._vbar_grid_kwargs)
            view.canvas.configure(xscrollcommand=None, yscrollcommand=self.ysync_wrapped)
            view.hbar.configure(command=view.canvas.xview)
            view.vbar.configure(command=view.canvas.yview)

        self.configure_placeholder_column(layout_mode)
        self.log_state("configure_scrollbars", layout_mode)

    def ysync_wrapped(self, *args) -> None:
        view = self._view
        try:
            view.vbar.set(*args)
        except Exception:  # pragma: no cover - Tkinter quirk
            pass
        try:
            fraction = view.canvas.yview()[0]
        except Exception:  # pragma: no cover - Tkinter quirk
            return
        self.update_last_scroll_fraction(fraction)

    def ensure_visible(self, layout_mode: str) -> None:
        view = self._view
        if layout_mode == "wrapped":
            self.show_vertical_scrollbar()
            return
        if self._hbar_grid_kwargs is not None:
            try:
                view.hbar.grid(**self._hbar_grid_kwargs)
            except Exception:  # pragma: no cover - Tkinter quirk
                pass
        if self._vbar_grid_kwargs is not None:
            try:
                view.vbar.grid(**self._vbar_grid_kwargs)
            except Exception:  # pragma: no cover - Tkinter quirk
                pass
        self.log_state("ensure_scrollbars_visible", layout_mode)

    def show_vertical_scrollbar(self) -> None:
        mapped = self.remap_vertical_scrollbar("show_vertical_scrollbar")
        self.log_state("show_vertical_scrollbar")
        if not mapped:
            self.ensure_vertical_bar_mapped()
        view = self._view
        try:
            view.after_idle(self.ensure_vertical_bar_mapped)
        except Exception:  # pragma: no cover - Tkinter quirk
            self.ensure_vertical_bar_mapped()

    def ensure_vertical_bar_mapped(self) -> None:
        view = self._view
        if view._layout_mode != "wrapped":
            return
        if self.is_vbar_mapped():
            return
        self.remap_vertical_scrollbar("ensure_vertical_bar_mapped")
        self.log_state("ensure_vertical_bar_mapped")

    def configure_placeholder_column(self, layout_mode: str) -> None:
        view = self._view
        width = 0 if layout_mode == "wrapped" else self._placeholder_minsize
        view.grid_columnconfigure(0, minsize=width)
        if layout_mode == "wrapped":
            try:
                requested = max(12, int(view.vbar.winfo_reqwidth()))
            except Exception:  # pragma: no cover - Tkinter quirk
                requested = 16
            view.grid_columnconfigure(2, minsize=requested)
        else:
            view.grid_columnconfigure(2, minsize=0)

    def remap_vertical_scrollbar(self, context: str) -> bool:
        fallback = {"row": 0, "column": 2, "sticky": "ns"}
        base_options = dict(self._vbar_grid_kwargs or {})
        attempt_configs: list[dict[str, object]] = []
        seen: set[tuple[tuple[str, object], ...]] = set()

        for candidate in (base_options, fallback):
            config = dict(candidate) if candidate else dict(fallback)
            signature = tuple(sorted(config.items()))
            if signature in seen:
                continue
            seen.add(signature)
            attempt_configs.append(config)

        mapped = False
        used_config: dict[str, object] = attempt_configs[-1]
        for index, config in enumerate(attempt_configs, start=1):
            self.grid_vertical_scrollbar(config, context=f"{context}[attempt={index}]")
            self.finalize_vertical_scrollbar()
            mapped = self.is_vbar_mapped()
            if mapped:
                used_config = config
                break
        else:
            mapped = self.is_vbar_mapped()

        if logger.isEnabledFor(logging.DEBUG):
            try:
                mapped_state = bool(self._view.vbar.winfo_ismapped())
            except Exception:  # pragma: no cover - Tkinter quirk
                mapped_state = None
            logger.debug(
                "StaffView vertical scrollbar remap context=%s mapped=%s options=%s",
                context,
                mapped_state,
                used_config,
                extra={"widget": repr(self._view)},
            )
        return mapped

    def grid_vertical_scrollbar(self, options: dict[str, object] | None, *, context: str = "direct") -> None:
        fallback = {"row": 0, "column": 2, "sticky": "ns"}
        params = dict(options or fallback)
        view = self._view
        try:
            if options:
                view.vbar.grid(**params)
                view.vbar.grid_configure(**params)
            else:
                view.vbar.grid(**params)
        except Exception:  # pragma: no cover - Tkinter quirk
            pass
        try:
            view.vbar.tkraise()
        except Exception:  # pragma: no cover - Tkinter quirk
            pass
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "StaffView grid vertical scrollbar context=%s params=%s",
                context,
                params,
                extra={"widget": repr(view)},
            )

    def finalize_vertical_scrollbar(self) -> None:
        try:
            self._view.vbar.update_idletasks()
        except Exception:  # pragma: no cover - Tkinter quirk
            pass

    def is_vbar_mapped(self) -> bool:
        try:
            return bool(self._view.vbar.winfo_ismapped())
        except Exception:  # pragma: no cover - Tkinter quirk
            return False

    def update_last_scroll_fraction(self, fraction: float) -> None:
        self._last_scroll_fraction = fraction

    def last_scroll_fraction(self) -> Optional[float]:
        return self._last_scroll_fraction

    def reset_scroll_fraction(self) -> None:
        self._last_scroll_fraction = None

    def log_state(self, context: str, layout_mode: Optional[str] = None) -> None:
        if not logger.isEnabledFor(logging.DEBUG):
            return
        view = self._view
        layout = layout_mode or view._layout_mode
        try:
            vbar_mapped = bool(view.vbar.winfo_ismapped())
        except Exception:  # pragma: no cover - Tkinter quirk
            vbar_mapped = None
        try:
            hbar_mapped = bool(view.hbar.winfo_ismapped())
        except Exception:  # pragma: no cover - Tkinter quirk
            hbar_mapped = None
        vbar_info = {}
        hbar_info = {}
        if vbar_mapped and hasattr(view.vbar, "grid_info"):
            try:
                vbar_info = view.vbar.grid_info()
            except Exception:  # pragma: no cover - Tkinter quirk
                vbar_info = {}
        elif self._vbar_grid_kwargs:
            vbar_info = dict(self._vbar_grid_kwargs)
        if hbar_mapped and hasattr(view.hbar, "grid_info"):
            try:
                hbar_info = view.hbar.grid_info()
            except Exception:  # pragma: no cover - Tkinter quirk
                hbar_info = {}
        elif self._hbar_grid_kwargs:
            hbar_info = dict(self._hbar_grid_kwargs)
        logger.debug(
            "StaffView scrollbar state context=%s layout=%s vbar_mapped=%s hbar_mapped=%s vbar_grid=%s hbar_grid=%s",
            context,
            layout,
            vbar_mapped,
            hbar_mapped,
            vbar_info,
            hbar_info,
            extra={"widget": repr(view)},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _capture_grid_kwargs(self, widget) -> dict[str, object] | None:
        try:
            info = widget.grid_info()
        except Exception:  # pragma: no cover - Tkinter quirk
            return None
        info.pop("in", None)
        result: dict[str, object] = {}
        for key in ("row", "column", "rowspan", "columnspan"):
            if key in info:
                value = info[key]
                try:
                    result[key] = int(value)
                except (TypeError, ValueError):
                    result[key] = value
        for key in ("sticky", "padx", "pady", "ipadx", "ipady"):
            if key in info:
                result[key] = info[key]
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "StaffView captured grid kwargs widget=%s raw=%s parsed=%s",
                repr(widget),
                info,
                result,
                extra={"widget": repr(self._view)},
            )
        return result or None

