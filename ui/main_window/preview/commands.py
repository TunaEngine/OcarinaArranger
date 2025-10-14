from __future__ import annotations

import logging
import os
from tkinter import messagebox

from ocarina_gui.conversion import ConversionResult
from ocarina_gui.preview import PreviewData
from ocarina_tools import (
    export_midi_poly,
    favor_lower_register,
    load_score,
    transform_to_ocarina,
)
from shared.result import Result

from ui.dialogs.pdf_export import ask_pdf_export_options

logger = logging.getLogger(__name__)


class PreviewCommandsMixin:
    """High-level commands that drive preview rendering and conversion."""

    def browse(self) -> None:
        self._viewmodel.browse_for_input()
        state = self._viewmodel.state
        self.input_path.set(state.input_path)
        self.pitch_list = list(state.pitch_list)

    def render_previews(self) -> Result[PreviewData, str]:
        self._sync_viewmodel_settings()
        suppress_errors = getattr(self, "_suppress_preview_error_dialogs", False)
        logger.info(
            "Render previews requested",
            extra={"input_path": self._viewmodel.state.input_path.strip()},
        )
        sides = ("original", "arranged")
        for side in sides:
            self._set_preview_initial_loading(side, True, message="Loading preview…")
        self.update_idletasks()
        self._set_transpose_controls_enabled(False)
        try:
            result = self._viewmodel.render_previews()
        except Exception:
            for side in sides:
                self._set_preview_initial_loading(side, False)
            raise
        finally:
            self._set_transpose_controls_enabled(True)
        if result.is_err():
            logger.error("Render previews failed: %s", result.error)
            if not suppress_errors:
                messagebox.showerror("Preview failed", result.error)
            else:
                logger.info("Preview error dialog suppressed during automatic render")
            self.status.set(self._viewmodel.state.status_message)
            for side in sides:
                self._set_preview_initial_loading(side, False)
            return result
        preview_data = result.unwrap()
        logger.info(
            "Preview rendered successfully",
            extra={
                "original_event_count": len(preview_data.original_events),
                "arranged_event_count": len(preview_data.arranged_events),
            },
        )
        self._apply_preview_data(preview_data)
        if hasattr(self, "_render_arranger_summary"):
            try:
                self._render_arranger_summary()
            except Exception:
                logger.exception("Failed to refresh arranger summary after preview")
        if hasattr(self, "_refresh_arranger_results_from_state"):
            try:
                self._refresh_arranger_results_from_state()
            except Exception:
                logger.exception("Failed to refresh arranger results after preview")
        self.status.set(self._viewmodel.state.status_message)
        self._record_preview_import()
        return result

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
        logger.info("Re-import requested", extra={"input_path": path})
        self._select_preview_tab("arranged")
        self.render_previews()

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
            )
            if settings.favor_lower:
                favor_lower_register(root, range_min=settings.range_min)
            tmp_mid = os.path.join(os.path.dirname(__file__), "_preview_arranged.mid")
            export_midi_poly(root, tmp_mid, tempo_bpm=None)
            self._open_path(tmp_mid)
        except Exception as exc:
            messagebox.showerror("Playback failed", str(exc))
