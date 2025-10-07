"""Static canvas rendering helpers for fingering views."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .outline_renderer import OutlineImage, render_outline_photoimage
from .view_colors import FingeringColorMixin
from .view_scaling import FingeringScalingMixin

if TYPE_CHECKING:
    from ocarina_gui.themes import ThemeSpec
    from .specs import InstrumentSpec


_LOGGER = logging.getLogger(__name__)


class FingeringStaticCanvasMixin(FingeringScalingMixin, FingeringColorMixin):
    """Renders and caches the static portion of the fingering canvas."""

    _instrument: "InstrumentSpec"
    _theme: "ThemeSpec | None"
    _outline_image: OutlineImage | None
    _outline_cache_key: tuple | None
    _static_signature: tuple | None
    _static_revision: int
    _instrument_revision: int
    _next_static_signature: tuple | None
    _hole_tags: list[str]
    _hole_hitboxes: list[tuple[float, float, float, float]]
    _windway_tags: list[str]
    _note_text_id: int | None
    _title_text_id: int | None
    _status_text_id: int | None
    _outline_canvas_id: int | None

    def _static_signature_for(self, instrument: "InstrumentSpec") -> tuple:
        scaled_size = self._scaled_canvas_size(instrument)
        style = instrument.style
        colors = self._resolve_canvas_colors(instrument)
        if instrument.outline is None:
            outline_signature: tuple | None = None
        else:
            pixel_points = [
                (self._scale_distance(x), self._scale_distance(y))
                for x, y in instrument.outline.points
            ]
            if (
                instrument.outline.closed
                and pixel_points
                and pixel_points[0] != pixel_points[-1]
            ):
                pixel_points = pixel_points + [pixel_points[0]]
            outline_signature = (
                bool(instrument.outline.closed),
                tuple((round(x, 4), round(y, 4)) for x, y in pixel_points),
            )
        hole_signature = tuple(
            (
                round(self._scale_distance(hole.x), 4),
                round(self._scale_distance(hole.y), 4),
                round(self._scale_radius(hole.radius), 4),
            )
            for hole in instrument.holes
        )
        windway_signature = tuple(
            (
                round(self._scale_distance(windway.x), 4),
                round(self._scale_distance(windway.y), 4),
                round(max(1.0, self._scale_distance(windway.width / 2.0)), 4),
                round(max(1.0, self._scale_distance(windway.height / 2.0)), 4),
            )
            for windway in instrument.windways
        )
        palette = getattr(self._theme, "palette", None)
        palette_key = (
            getattr(palette, "text_primary", None),
            getattr(palette, "text_muted", None),
        )
        theme_identity = getattr(self._theme, "theme_id", None) or getattr(
            self._theme, "name", None
        )
        return (
            instrument.instrument_id,
            instrument.title,
            scaled_size,
            outline_signature,
            hole_signature,
            windway_signature,
            round(self._scale_outline_width(style.outline_width), 4),
            bool(style.outline_smooth),
            int(getattr(style, "outline_spline_steps", 48)),
            colors.background,
            colors.outline,
            colors.hole_outline,
            colors.covered_fill,
            theme_identity,
            palette_key,
        )

    def _draw_static(self, *, precomputed_signature: tuple | None = None) -> None:
        signature = precomputed_signature or self._next_static_signature
        self._next_static_signature = None
        if signature is None:
            signature = self._static_signature_for(self._instrument)

        if (
            signature == self._static_signature
            and self._static_revision == self._instrument_revision
        ):
            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "Skipping static redraw: signature unchanged (revision=%s)",
                    self._instrument_revision,
                )
            return
        if signature == self._static_signature:
            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "Static signature unchanged; updating revision %s→%s without redraw",
                    self._static_revision,
                    self._instrument_revision,
                )
            self._static_revision = self._instrument_revision
            return
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Drawing static canvas revision=%s cached_signature=%s incoming_signature_changed=%s",
                self._instrument_revision,
                self._static_signature is not None,
                signature != self._static_signature,
            )
        self.delete("static")
        self.delete("note")
        self._note_text_id = None
        self._title_text_id = None
        self._status_text_id = None
        self._outline_canvas_id = None
        instrument = self._instrument
        scaled_width, scaled_height = self._scaled_canvas_size(instrument)
        colors = self._resolve_canvas_colors()
        palette = getattr(self._theme, "palette", None)
        text_primary = getattr(palette, "text_primary", "#222222")
        text_muted = getattr(palette, "text_muted", "#333333")
        self.configure(width=scaled_width, height=scaled_height, bg=colors.background)

        outline_image: OutlineImage | None = None
        if instrument.outline is not None:
            outline_points = list(instrument.outline.points)
            pixel_points = [
                (self._scale_distance(x), self._scale_distance(y))
                for x, y in outline_points
            ]
            if instrument.outline.closed and pixel_points and pixel_points[0] != pixel_points[-1]:
                pixel_points = pixel_points + [pixel_points[0]]
            spline_steps = max(1, int(getattr(instrument.style, "outline_spline_steps", 48)))
            stroke_width = self._scale_outline_width(instrument.style.outline_width)
            cache_key = (
                tuple((round(x, 4), round(y, 4)) for x, y in pixel_points),
                int(scaled_width),
                int(scaled_height),
                round(stroke_width, 4),
                colors.outline,
                colors.background,
                bool(instrument.style.outline_smooth),
                bool(instrument.outline.closed),
                int(spline_steps),
            )
            if self._outline_image is None or self._outline_cache_key != cache_key:
                outline_image = render_outline_photoimage(
                    self,
                    pixel_points,
                    canvas_size=(scaled_width, scaled_height),
                    stroke_width=stroke_width,
                    stroke_color=colors.outline,
                    background_color=colors.background,
                    smooth=instrument.style.outline_smooth,
                    closed=instrument.outline.closed,
                    spline_steps=spline_steps,
                )
                if outline_image is not None:
                    self._outline_image = outline_image
                    self._outline_cache_key = cache_key
                else:
                    self._outline_image = None
                    self._outline_cache_key = None
            outline_image = self._outline_image
            if outline_image is not None:
                outline_canvas_id = self.create_image(
                    0,
                    0,
                    image=outline_image.photo_image,
                    anchor="nw",
                    tags=("static", "outline"),
                )
                self.tag_lower(outline_canvas_id)
                self._outline_canvas_id = outline_canvas_id
        else:
            self._outline_image = None
            self._outline_cache_key = None
            self._outline_canvas_id = None

        hole_tags: list[str] = []
        hole_hitboxes: list[tuple[float, float, float, float]] = []
        for index, hole in enumerate(instrument.holes):
            radius = max(1.0, self._scale_radius(hole.radius))
            center_x = self._scale_distance(hole.x)
            center_y = self._scale_distance(hole.y)
            hole_tag = self._hole_tag(index)
            hole_tags.append(hole_tag)
            hole_hitboxes.append(
                (
                    center_x - radius,
                    center_y - radius,
                    center_x + radius,
                    center_y + radius,
                )
            )
            self.create_oval(
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
                outline=colors.hole_outline,
                width=1,
                fill=colors.background,
                tags=("static", "hole", "hole-hitbox", hole_tag),
            )
        self._hole_tags = hole_tags
        self._hole_hitboxes = hole_hitboxes
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Cached %s hole hitboxes: %s",
                len(hole_hitboxes),
                [tuple(round(value, 2) for value in box) for box in hole_hitboxes],
            )
        self._refresh_hole_bindings()

        windway_tags: list[str] = []
        for index, windway in enumerate(instrument.windways):
            half_width = max(1.0, self._scale_distance(windway.width / 2.0))
            half_height = max(1.0, self._scale_distance(windway.height / 2.0))
            center_x = self._scale_distance(windway.x)
            center_y = self._scale_distance(windway.y)
            windway_tag = self._windway_tag(index)
            windway_tags.append(windway_tag)
            self.create_rectangle(
                center_x - half_width,
                center_y - half_height,
                center_x + half_width,
                center_y + half_height,
                outline=colors.hole_outline,
                width=1,
                fill=colors.background,
                tags=("static", "windway", "windway-hitbox", windway_tag),
            )
        self._windway_tags = windway_tags
        self._refresh_windway_bindings()

        padding_x = self._scale_distance(12)
        padding_y = self._scale_distance(12)
        title_x = padding_x
        title_y = padding_y
        note_y = title_y + self._scale_distance(18)
        title_font_size = max(1, int(round(9 * self._scale)))
        note_font_size = max(1, int(round(11 * self._scale)))
        self._title_text_id = self.create_text(
            title_x,
            title_y,
            text=instrument.title,
            fill=text_muted,
            font=("TkDefaultFont", title_font_size),
            anchor="nw",
            tags=("static", "title"),
        )
        self._note_text_id = self.create_text(
            title_x,
            note_y,
            text="",
            fill=text_primary,
            font=("TkDefaultFont", note_font_size),
            anchor="nw",
            tags=("note",),
        )
        status_y = note_y + self._scale_distance(16)
        status_font_size = max(1, int(round(9 * self._scale)))
        self._status_text_id = self.create_text(
            title_x,
            status_y,
            text="",
            fill="#aa0000",
            font=("TkDefaultFont", status_font_size),
            anchor="nw",
            tags=("note", "status"),
        )
        self.tag_raise("note")
        self._static_signature = signature
        self._static_revision = self._instrument_revision


__all__ = ["FingeringStaticCanvasMixin"]
