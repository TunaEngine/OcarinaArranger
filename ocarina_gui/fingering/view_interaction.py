"""Interaction helpers for the fingering canvas."""

from __future__ import annotations

import logging
from typing import Callable, Optional, TYPE_CHECKING

import tkinter as tk


_LOGGER = logging.getLogger("ocarina_gui.fingering.view")


class FingeringInteractionMixin:
    """Encapsulates hole and windway click handling."""

    _hole_tags: list[str]
    _windway_tags: list[str]
    _hole_click_handler: Optional[Callable[[int], None]]
    _windway_click_handler: Optional[Callable[[int], None]]
    _hole_canvas_binding: str | None
    _last_handled_serial: int | None
    _hole_hitboxes: list[tuple[float, float, float, float]]
    _handled_hole_event_count: int

    def set_hole_click_handler(self, handler: Optional[Callable[[int], None]]) -> None:
        """Set a callback invoked when a hole is clicked."""

        self._hole_click_handler = handler
        self._refresh_hole_bindings()
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Registered hole click handler=%s total_tags=%s canvas_binding=%s",
                bool(handler),
                len(self._hole_tags),
                self._hole_canvas_binding,
            )

    def _hole_tag(self, index: int) -> str:
        return f"hole:{index}"

    def _windway_tag(self, index: int) -> str:
        return f"windway:{index}"

    def _refresh_hole_bindings(self) -> None:
        tags = list(self._hole_tags)
        for tag in tags:
            self.tag_unbind(tag, "<Button-1>")
        self.tag_unbind("hole-hitbox", "<Button-1>")
        self.tag_unbind("all", "<Button-1>")
        if self._hole_canvas_binding is not None:
            self.unbind("<Button-1>", self._hole_canvas_binding)
            self._hole_canvas_binding = None

        handler = self._hole_click_handler
        if handler is None:
            return

        self.tag_bind("hole-hitbox", "<Button-1>", self._handle_hole_hitbox_click)
        for tag in tags:
            self.tag_bind(tag, "<Button-1>", self._handle_hole_hitbox_click, add="+")
        self.tag_bind(
            "all",
            "<Button-1>",
            self._handle_canvas_hole_click,
            add="+",
        )
        binding_id = self.bind("<Button-1>", self._handle_canvas_hole_click, add="+")
        if binding_id:
            self._hole_canvas_binding = binding_id
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Refreshed hole bindings tags=%s canvas_binding=%s",
                tags,
                self._hole_canvas_binding,
            )

    def _handle_hole_click(self, _event: tk.Event, hole_index: int) -> bool:
        handler = self._hole_click_handler
        if handler is None:
            return False
        serial_value = getattr(_event, "serial", None) if hasattr(_event, "serial") else None
        if serial_value is not None and serial_value == self._last_handled_serial:
            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "Ignoring duplicate hole click for serial=%s index=%s",
                    serial_value,
                    hole_index,
                )
            return False
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Dispatching hole click index=%s handler_present=%s serial=%s",
                hole_index,
                True,
                getattr(_event, "serial", None),
            )
        handler(hole_index)
        self._handled_hole_event_count += 1
        if serial_value is not None:
            self._last_handled_serial = serial_value
        else:
            self._last_handled_serial = None
        return True

    def _handle_hole_hitbox_click(self, event: tk.Event) -> None:
        current_tags = self.gettags("current")
        hole_index = self._extract_hole_index_from_tags(current_tags)
        serial_value = getattr(event, "serial", None) if hasattr(event, "serial") else None
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Hole click event: coords=(%s,%s) current_tags=%s initial_index=%s",
                event.x,
                event.y,
                current_tags,
                hole_index,
            )
        if hole_index is None:
            hole_index = self._hole_index_from_point(event.x, event.y)
            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "Hole click fallback overlap search result index=%s", hole_index
                )
        if hole_index is None:
            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "Ignoring hole click: no matching hitbox at coords=(%s,%s)",
                    event.x,
                    event.y,
                )
            return
        if self._handle_hole_click(event, hole_index):
            return "break"

    def _handle_canvas_hole_click(self, event: tk.Event) -> None:
        hole_index = self._hole_index_from_point(event.x, event.y)
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Canvas click fallback resolved hole index=%s at coords=(%s,%s)",
                hole_index,
                event.x,
                event.y,
            )
        if hole_index is None:
            return
        self._handle_hole_click(event, hole_index)

    def _extract_hole_index_from_tags(self, tags: tuple[str, ...]) -> int | None:
        for tag in tags:
            if not tag.startswith("hole:"):
                continue
            try:
                return int(tag.split(":", 1)[1])
            except ValueError:
                continue
        return None

    def _hole_index_from_point(self, x: float, y: float) -> int | None:
        overlap = self.find_overlapping(x, y, x, y)
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Hole overlap query at coords=(%s,%s) returned items=%s",
                x,
                y,
                overlap,
            )
        for item in overlap:
            hole_index = self._extract_hole_index_from_tags(self.gettags(item))
            if hole_index is not None:
                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug(
                        "Resolved hole index=%s from item=%s tags=%s",
                        hole_index,
                        item,
                        self.gettags(item),
                    )
                return hole_index
        for index, (left, top, right, bottom) in enumerate(self._hole_hitboxes):
            contains = left <= x <= right and top <= y <= bottom
            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "Manual hole hit test index=%s bbox=(%s,%s,%s,%s) contains=%s",
                    index,
                    left,
                    top,
                    right,
                    bottom,
                    contains,
                )
            if contains:
                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug(
                        "Manual hitbox match returning hole index=%s for coords=(%s,%s)",
                        index,
                        x,
                        y,
                    )
                return index
        return None

    def set_windway_click_handler(self, handler: Optional[Callable[[int], None]]) -> None:
        """Set a callback invoked when a windway is clicked."""

        self._windway_click_handler = handler
        self._refresh_windway_bindings()

    def _refresh_windway_bindings(self) -> None:
        tags = list(self._windway_tags)
        for tag in tags:
            self.tag_unbind(tag, "<Button-1>")

        handler = self._windway_click_handler
        if handler is None:
            return

        for index, tag in enumerate(tags):
            self.tag_bind(
                tag,
                "<Button-1>",
                lambda event, windway=index: self._handle_windway_click(event, windway),
            )

    def _handle_windway_click(self, _event: tk.Event, windway_index: int) -> None:
        handler = self._windway_click_handler
        if handler is None:
            return
        handler(windway_index)


__all__ = ["FingeringInteractionMixin"]
