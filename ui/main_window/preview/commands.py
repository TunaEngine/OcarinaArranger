from __future__ import annotations

import logging
import os
import queue
import threading
from tkinter import messagebox
from ocarina_tools.parts import MusicXmlPartInfo

from ocarina_gui.conversion import ConversionResult
from ocarina_tools import (
    export_midi_poly,
    favor_lower_register,
    load_score,
    transform_to_ocarina,
)
from shared.melody_part import select_melody_candidate

from ui.dialogs.pdf_export import ask_pdf_export_options
from .render_runner import PreviewRenderHandle, render_previews_for_ui

logger = logging.getLogger(__name__)


class PreviewCommandsMixin:
    """High-level commands that drive preview rendering and conversion."""

    def _call_in_ui_thread(self, func, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        """Execute *func* on the Tk UI thread and return its result."""

        if threading.current_thread() is threading.main_thread():
            return func(*args, **kwargs)

        result: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=1)

        def _invoke() -> None:
            try:
                result.put(("ok", func(*args, **kwargs)))
            except BaseException as exc:  # pragma: no cover - propagated to caller
                result.put(("err", exc))

        try:
            self.after(0, _invoke)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Failed to schedule UI-thread call")
            raise

        kind, payload = result.get()
        if kind == "err":
            raise payload
        return payload

    def browse(self) -> None:
        changed = self._viewmodel.browse_for_input()
        if not changed:
            return
        selected_ids = self._resolve_part_selection(reload_metadata=True)
        if selected_ids is None:
            logger.info("Part selection cancelled; aborting import")
            return
        self._viewmodel.apply_part_selection(selected_ids)
        state = self._viewmodel.state
        self.input_path.set(state.input_path)
        self.pitch_list = list(state.pitch_list)

    def render_previews(self) -> PreviewRenderHandle:
        return render_previews_for_ui(self)

    def convert(self) -> Result[ConversionResult, str] | None:
        self._sync_viewmodel_settings()
        logger.info(
            "Conversion requested",
            extra={"input_path": self._viewmodel.state.input_path.strip()},
        )
        options = ask_pdf_export_options(self)
        if options is None:
            logger.info("Conversion cancelled from PDF options dialog")
            return None
        result = self._viewmodel.convert(options)
        if result is None:
            logger.info("Conversion cancelled by user")
            return None
        if result.is_err():
            logger.error("Conversion failed: %s", result.error)
            messagebox.showerror("Conversion failed", result.error)
            self.status.set(self._viewmodel.state.status_message)
            return result
        conversion = result.unwrap()
        logger.info(
            "Conversion completed",
            extra={
                "xml_path": str(conversion.output_xml_path),
                "mxl_path": str(conversion.output_mxl_path),
            },
        )
        self._after_conversion(conversion)
        self.status.set(self._viewmodel.state.status_message)
        return result

    def reimport_and_arrange(self) -> None:
        path = self._require_input_path("Please choose a valid input file first.")
        if not path:
            return
        selected_ids = self._resolve_part_selection(reload_metadata=False)
        if selected_ids is None:
            logger.info("Re-import cancelled from part selection dialog")
            return
        self._viewmodel.apply_part_selection(selected_ids)
        logger.info("Re-import requested", extra={"input_path": path})
        self._select_preview_tab("arranged")
        self.render_previews()

    def _resolve_part_selection(
        self, *, reload_metadata: bool
    ) -> tuple[str, ...] | None:
        parts: tuple[MusicXmlPartInfo, ...]
        if reload_metadata or not self._viewmodel.state.available_parts:
            parts = self._viewmodel.load_part_metadata()
        else:
            parts = self._viewmodel.state.available_parts
        if not parts:
            return ()
        if len(parts) == 1:
            return (parts[0].part_id,)
        if self._viewmodel.state.selected_part_ids:
            preselected = self._viewmodel.state.selected_part_ids
        else:
            melody_part_id = select_melody_candidate(parts)
            if melody_part_id is not None:
                preselected = (melody_part_id,)
            else:
                preselected = (parts[0].part_id,)
        selection = self._viewmodel.ask_select_parts(parts, preselected)
        if selection is None:
            return None
        return tuple(selection)

    def play_original(self) -> None:
        in_path = self._require_input_path("Please choose a valid input file first.")
        if not in_path:
            return
        try:
            tree, root = load_score(in_path)
            tmp_mid = os.path.join(os.path.dirname(__file__), "_preview_original.mid")
            export_midi_poly(
                root,
                tmp_mid,
                tempo_bpm=None,
                use_original_instruments=True,
            )
            self._open_path(tmp_mid)
        except Exception as exc:
            messagebox.showerror("Playback failed", str(exc))

    def play_arranged(self) -> None:
        in_path = self._require_input_path("Please choose a valid input file first.")
        if not in_path:
            return
        settings = self._current_settings()
        try:
            tree, root = load_score(in_path)
            transform_to_ocarina(
                tree,
                root,
                prefer_mode=settings.prefer_mode,
                range_min=settings.range_min,
                range_max=settings.range_max,
                prefer_flats=settings.prefer_flats,
                collapse_chords=settings.collapse_chords,
                transpose_offset=settings.transpose_offset,
                selected_part_ids=settings.selected_part_ids,
            )
            if settings.favor_lower:
                favor_lower_register(root, range_min=settings.range_min)
            tmp_mid = os.path.join(os.path.dirname(__file__), "_preview_arranged.mid")
            export_midi_poly(root, tmp_mid, tempo_bpm=None)
            self._open_path(tmp_mid)
        except Exception as exc:
            messagebox.showerror("Playback failed", str(exc))
