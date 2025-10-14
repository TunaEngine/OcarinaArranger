from __future__ import annotations

import inspect
import logging
import queue
import threading
import time
from tkinter import messagebox
from typing import Any

from ocarina_gui.preview import PreviewData
from shared.result import Result

logger = logging.getLogger(__name__)


class PreviewRenderHandle:
    """Track asynchronous preview rendering dispatched to a worker thread."""

    def __init__(self, owner: Any) -> None:
        self._owner = owner
        self._done = threading.Event()
        self.result: Result[PreviewData, str] | None = None
        self.error: BaseException | None = None

    @property
    def done(self) -> bool:
        return self._done.is_set()

    def _finalise(
        self,
        *,
        result: Result[PreviewData, str] | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self._done.set()

    def wait(self, timeout: float | None = None) -> Result[PreviewData, str]:
        """Block until the preview worker completes, pumping Tk events."""

        owner = self._owner
        deadline: float | None = None
        if timeout is not None:
            deadline = time.monotonic() + timeout
        while True:
            remaining: float | None
            if deadline is None:
                remaining = None
            else:
                remaining = max(0.0, deadline - time.monotonic())
                if remaining == 0.0 and not self._done.is_set():
                    raise TimeoutError("Preview rendering did not complete in time")
            if self._done.wait(timeout=0.05 if remaining is None else min(0.05, remaining)):
                break
            try:
                owner.update()
            except Exception:  # pragma: no cover - best-effort event pump
                pass
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise RuntimeError("Preview rendering completed without a result")
        return self.result


def render_previews_for_ui(ui: Any) -> PreviewRenderHandle:
    """Run preview rendering logic for the provided UI mixin."""

    ui._sync_viewmodel_settings()
    suppress_errors = getattr(ui, "_suppress_preview_error_dialogs", False)
    logger.info(
        "Render previews requested",
        extra={"input_path": ui._viewmodel.state.input_path.strip()},
    )
    sides = ("original", "arranged")
    arranger_mode = (ui._viewmodel.state.arranger_mode or "classic").strip().lower()
    for side in sides:
        message = "Loading preview…"
        if side == "arranged" and arranger_mode in {"best_effort", "gp"}:
            message = "Arranging preview…"
        ui._set_preview_initial_loading(side, True, message=message)
        playback = ui._preview_playback.get(side)
        if playback is not None:
            playback.state.is_rendering = True
            playback.state.render_progress = 0.0
    latest_arranger_progress: dict[str, float | str | None] = {
        "percent": 0.0,
        "message": None,
    }
    showing_arranger_progress = False
    progress_enabled = False
    if hasattr(ui, "_set_arranger_results_loading") and arranger_mode in {"best_effort", "gp"}:
        try:
            ui._set_arranger_results_loading(True, message="Arranging preview…")
            showing_arranger_progress = True
            latest_arranger_progress["message"] = "Arranging preview…"
            if hasattr(ui, "_update_arranger_progress"):
                progress_enabled = True
        except Exception:  # pragma: no cover - defensive UI safeguard
            logger.exception("Failed to display arranger progress indicator")
    ui.update_idletasks()
    ui._set_transpose_controls_enabled(False)
    events: queue.Queue[tuple[str, object]] = queue.Queue()
    handle = PreviewRenderHandle(ui)

    render_callable = ui._viewmodel.render_previews
    parameters = inspect.signature(render_callable).parameters
    use_progress = "progress_callback" in parameters and progress_enabled

    viewmodel_cls = type(ui._viewmodel)
    original_method = getattr(viewmodel_cls, "render_previews", None)
    run_on_worker_thread = (
        inspect.ismethod(render_callable)
        and getattr(render_callable, "__func__", None) is original_method
    )

    def safe_update_arranger_progress(percent: float, message: str | None = None) -> None:
        try:
            ui._update_arranger_progress(percent, message=message)
        except Exception:  # pragma: no cover - defensive UI safeguard
            logger.exception("Failed to refresh arranger progress")

    def _invoke_render() -> Result[PreviewData, str]:
        if use_progress:
            return render_callable(
                progress_callback=lambda percent, message=None: events.put(
                    ("progress", percent, message)
                )
            )
        return render_callable()

    def _worker() -> None:
        try:
            if run_on_worker_thread:
                result = _invoke_render()
            else:
                response: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=1)
                events.put(("ui_call_with_response", _invoke_render, response))
                kind, payload = response.get()
                if kind == "err":
                    raise payload
                result = payload
        except Exception as exc:  # pragma: no cover - propagated via UI thread
            logger.exception("Preview rendering failed")
            events.put(("exception", exc))
            return
        events.put(("result", result))

    thread = threading.Thread(target=_worker, name="preview-render", daemon=True)
    thread.start()

    def _hide_arranger_progress() -> None:
        if not showing_arranger_progress:
            return
        try:
            ui._set_arranger_results_loading(False)
        except Exception:  # pragma: no cover - defensive UI safeguard
            logger.exception("Failed to hide arranger progress indicator")

    def _finalise(
        *,
        result: Result[PreviewData, str] | None = None,
        error: BaseException | None = None,
        delay_hide: bool = False,
    ) -> None:
        if delay_hide:
            try:
                ui.after(120, _hide_arranger_progress)
            except Exception:  # pragma: no cover - best-effort Tk scheduling
                logger.exception("Failed to schedule arranger progress hide")
                _hide_arranger_progress()
        else:
            _hide_arranger_progress()
        ui._set_transpose_controls_enabled(True)
        handle._finalise(result=result, error=error)

    def _handle_result(result: Result[PreviewData, str]) -> None:
        handle.result = result
        if result.is_err():
            logger.error("Render previews failed: %s", result.error)
            if not suppress_errors:
                messagebox.showerror("Preview failed", result.error)
            else:
                logger.info("Preview error dialog suppressed during automatic render")
            ui.status.set(ui._viewmodel.state.status_message)
            for side in sides:
                ui._set_preview_initial_loading(side, False)
            _finalise(result=result)
            return
        try:
            preview_data = result.unwrap()
            logger.info(
                "Preview rendered successfully",
                extra={
                    "original_event_count": len(preview_data.original_events),
                    "arranged_event_count": len(preview_data.arranged_events),
                },
            )
            ui._apply_preview_data(preview_data)
            if hasattr(ui, "_render_arranger_summary"):
                try:
                    ui._render_arranger_summary()
                except Exception:
                    logger.exception("Failed to refresh arranger summary after preview")
            if hasattr(ui, "_refresh_arranger_results_from_state"):
                try:
                    ui._refresh_arranger_results_from_state()
                except Exception:
                    logger.exception("Failed to refresh arranger results after preview")
            ui.status.set(ui._viewmodel.state.status_message)
            ui._record_preview_import()
        finally:
            force_final_progress = (
                progress_enabled and showing_arranger_progress and not result.is_err()
            )
            if force_final_progress:
                try:
                    current_progress = float(
                        latest_arranger_progress.get("percent", 0.0) or 0.0
                    )
                except (TypeError, ValueError):
                    current_progress = 0.0
                if current_progress < 100.0:
                    final_message = (
                        latest_arranger_progress.get("message")
                        or "Arrangement complete"
                    )
                    logger.info(
                        "Arranger progress finalised at %.1f%% (%s)",
                        100.0,
                        final_message,
                    )
                    try:
                        safe_update_arranger_progress(100.0, final_message)
                        ui.update_idletasks()
                    except Exception:  # pragma: no cover - defensive UI safeguard
                        logger.exception(
                            "Failed to publish final arranger progress update"
                        )
            _finalise(result=result, delay_hide=force_final_progress)

    def _process_events() -> None:
        if handle.done:
            return
        processed_count = 0
        max_batch = 3
        had_progress_update = False
        while processed_count < max_batch:
            try:
                event = events.get_nowait()
            except queue.Empty:
                break
            kind = event[0]
            if kind == "progress":
                _, percent, message = event
                had_progress_update = True
                if progress_enabled:
                    try:
                        try:
                            numeric_percent = float(percent)
                        except (TypeError, ValueError):
                            numeric_percent = 0.0
                        suffix = f" - {message}" if message else ""
                        logger.info(
                            "Arranger progress update: %.1f%%%s",
                            numeric_percent,
                            suffix,
                        )
                        safe_update_arranger_progress(percent, message)
                        try:
                            arranged_playback = ui._preview_playback.get("arranged")
                            if arranged_playback is not None:
                                arranged_playback.state.render_progress = numeric_percent / 100.0
                                arranged_playback.state.is_rendering = True
                                ui._update_preview_render_progress("arranged")
                        except Exception:  # pragma: no cover - defensive UI safeguard
                            logger.exception("Failed to update preview overlay progress")
                        try:
                            latest_arranger_progress["percent"] = float(percent)
                        except (TypeError, ValueError):
                            latest_arranger_progress["percent"] = 0.0
                        if message is not None:
                            latest_arranger_progress["message"] = message
                    except Exception:  # pragma: no cover - defensive UI safeguard
                        logger.exception("Failed to apply arranger progress update")
            elif kind == "ui_call":
                _, func = event
                try:
                    func()
                except Exception:  # pragma: no cover - failures reported via queue
                    logger.exception("UI call raised during preview render")
            elif kind == "ui_call_with_response":
                _, func, response_queue = event
                try:
                    response_queue.put(("ok", func()))
                except Exception as exc:  # pragma: no cover - propagate to worker
                    logger.exception("UI call with response raised during preview render")
                    response_queue.put(("err", exc))
            elif kind == "result":
                _, result = event
                _handle_result(result)
            elif kind == "exception":
                _, exc = event
                for side in sides:
                    ui._set_preview_initial_loading(side, False)
                _finalise(error=exc)
                raise exc
            processed_count += 1

        if had_progress_update:
            try:
                ui.update()
            except Exception as e:
                logger.warning(f"UI update() failed: {e}")

        if not handle.done:
            ui.after(10, _process_events)

    ui.after(20, _process_events)
    return handle

