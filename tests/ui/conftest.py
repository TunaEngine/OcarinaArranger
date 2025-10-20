from __future__ import annotations

from types import SimpleNamespace

from tests.helpers import require_ttkbootstrap

require_ttkbootstrap()

import pytest

from domain.arrangement.difficulty import DifficultySummary
from domain.arrangement.gp.fitness import FitnessVector
from domain.arrangement.soft_key import InstrumentRange
from ocarina_gui import App, themes
from ocarina_gui.fingering import FingeringLibrary, InstrumentSpec
from viewmodels.preview_playback_viewmodel import AudioRenderer, PreviewPlaybackViewModel


class _StubAudioRenderer(AudioRenderer):
    """Minimal renderer used in GUI tests to keep playback logic active."""

    def __init__(self) -> None:
        self._is_playing = False
        self.metronome = (False, 4, 4)
        self._listener = None
        self._generation = 0
        self.auto_complete_render = True
        self._pending_generation: int | None = None
        self.loop_region = None
        self.volume = 1.0
        self.volume_requires_render = False
        self.tempo_changes = ()
        self._shutdown = False

    def prepare(self, events, pulses_per_quarter, tempo_changes=None):  # type: ignore[override]
        self._begin_render()
        self.tempo_changes = tuple(tempo_changes or ())

    def start(self, position_tick: int, tempo_bpm: float) -> bool:  # noqa: D401 - protocol compliance
        self._is_playing = True
        return True

    def pause(self) -> None:  # noqa: D401 - protocol compliance
        self._is_playing = False

    def stop(self) -> None:  # noqa: D401 - protocol compliance
        self._is_playing = False

    def seek(self, tick: int) -> None:  # noqa: D401 - protocol compliance
        return None

    def set_tempo(self, tempo_bpm: float) -> None:  # noqa: D401 - protocol compliance
        self._begin_render()

    def set_loop(self, loop) -> None:  # noqa: D401 - protocol compliance
        self.loop_region = loop

    def set_metronome(self, enabled: bool, beats_per_measure: int, beat_unit: int) -> None:
        self.metronome = (enabled, beats_per_measure, beat_unit)
        self._begin_render()

    def set_render_listener(self, listener) -> None:  # type: ignore[override]
        self._listener = listener

    def set_volume(self, volume: float) -> bool:  # noqa: D401 - protocol compliance
        self.volume = volume
        if self.volume_requires_render:
            self._begin_render()
            return True
        return False

    def finish_render(self, success: bool = True) -> None:
        if self._pending_generation is None:
            return
        listener = self._listener
        generation = self._pending_generation
        self._pending_generation = None
        if listener is not None:
            listener.render_progress(generation, 1.0)
            listener.render_complete(generation, success)

    def emit_progress(self, value: float) -> None:
        if self._pending_generation is None:
            return
        listener = self._listener
        if listener is not None:
            listener.render_progress(self._pending_generation, value)

    def shutdown(self) -> None:
        self._is_playing = False
        self._pending_generation = None
        self._listener = None
        self._shutdown = True

    def _begin_render(self) -> None:
        self._generation += 1
        listener = self._listener
        generation = self._generation
        if listener is not None:
            listener.render_started(generation)
            listener.render_progress(generation, 0.0)
        if self.auto_complete_render:
            if listener is not None:
                listener.render_progress(generation, 1.0)
                listener.render_complete(generation, True)
        else:
            self._pending_generation = generation


@pytest.fixture
def gui_app(request, monkeypatch):
    original_theme = themes.get_current_theme_id()

    stub_instrument = InstrumentSpec.from_dict(
        {
            "id": "test",
            "name": "Test instrument",
            "title": "Test instrument",
            "canvas": {"width": 160, "height": 120},
            "holes": [
                {"id": "hole_1", "x": 40, "y": 40, "radius": 10},
                {"id": "hole_2", "x": 80, "y": 40, "radius": 10},
                {"id": "hole_3", "x": 120, "y": 40, "radius": 10},
            ],
            "note_order": ["A4", "B4"],
            "note_map": {"A4": [2, 2, 2], "B4": [0, 0, 0]},
            "candidate_notes": ["A4", "B4", "C5"],
        }
    )
    secondary_instrument = InstrumentSpec.from_dict(
        {
            "id": "test_alt",
            "name": "Secondary test instrument",
            "title": "Secondary test instrument",
            "canvas": {"width": 160, "height": 120},
            "holes": [
                {"id": "hole_1", "x": 35, "y": 35, "radius": 10},
                {"id": "hole_2", "x": 75, "y": 35, "radius": 10},
                {"id": "hole_3", "x": 115, "y": 35, "radius": 10},
            ],
            "note_order": ["G4", "A4"],
            "note_map": {"G4": [1, 1, 1], "A4": [0, 0, 0]},
            "candidate_notes": ["G4", "A4", "B4"],
        }
    )
    stub_library = FingeringLibrary([stub_instrument, secondary_instrument])
    monkeypatch.setattr("ocarina_gui.fingering._LIBRARY", stub_library)

    monkeypatch.setattr(
        "ocarina_gui.audio.build_preview_audio_renderer",
        lambda: _StubAudioRenderer(),
    )

    def _stub_arrange_v3_gp(
        span,
        *,
        instrument_id,
        config,
        starred_ids=None,
        manual_transposition=0,
        progress_callback=None,
        **_kwargs,
    ):
        total_generations = max(1, int(getattr(config, "generations", 1) or 1))
        if progress_callback is not None:
            try:
                progress_callback(total_generations - 1, total_generations)
            except Exception:
                pass

        instrument_range = InstrumentRange(60, 84)
        difficulty = DifficultySummary(
            easy=float(span.total_duration or 1),
            medium=0.0,
            hard=0.0,
            very_hard=0.0,
            tessitura_distance=0.0,
            leap_exposure=0.0,
        )

        candidate = SimpleNamespace(
            instrument_id=instrument_id or "test",
            instrument=instrument_range,
            program=(),
            span=span,
            difficulty=difficulty,
            explanations=(),
            fitness=FitnessVector(0.0, 0.0, 0.0, 0.0),
        )

        return SimpleNamespace(
            chosen=candidate,
            comparisons=(candidate,),
            strategy="stub-gp",
            session=SimpleNamespace(
                generations=total_generations,
                elapsed_seconds=0.0,
            ),
            archive_summary=(),
            termination_reason="stubbed",
            fallback=None,
        )

    monkeypatch.setattr(
        "services.arranger_preview.arrange_v3_gp",
        _stub_arrange_v3_gp,
    )
    app = App()
    app.withdraw()
    app.update_idletasks()
    app._preview_render_async = False

    app._test_audio_renderers = {}
    for key in ("original", "arranged"):
        stub_renderer = _StubAudioRenderer()
        app._preview_playback[key] = PreviewPlaybackViewModel(audio_renderer=stub_renderer)
        app._bind_preview_render_observer(key)
        app._test_audio_renderers[key] = stub_renderer
        app._sync_preview_playback_controls(key)

    original_render_previews = app.render_previews

    def _render_previews_and_wait(*args, **kwargs):
        handle = original_render_previews(*args, **kwargs)
        if hasattr(handle, "wait"):
            return handle.wait()
        return handle

    app.render_previews = _render_previews_and_wait  # type: ignore[assignment]

    def _cleanup() -> None:
        try:
            try:
                test_renderers = getattr(app, "_test_audio_renderers", {})
                for renderer in test_renderers.values():
                    shutdown = getattr(renderer, "shutdown", None)
                    if callable(shutdown):
                        shutdown()
            except Exception:
                pass
            try:
                playback_map = getattr(app, "_preview_playback", {})
                for playback in playback_map.values():
                    audio = getattr(playback, "_audio", None)
                    shutdown = getattr(audio, "shutdown", None)
                    if callable(shutdown):
                        shutdown()
            except Exception:
                pass
            try:
                cancel_loop = getattr(app, "_cancel_playback_loop", None)
                if callable(cancel_loop):
                    cancel_loop()
            except Exception:
                pass
            try:
                handles = list(getattr(app, "_preview_render_handles", ()))
                for handle in handles:
                    join = getattr(handle, "join", None)
                    if callable(join):
                        join(timeout=5.0)
            except Exception:
                pass
            app.destroy()
        finally:
            themes.set_active_theme(original_theme)

    request.addfinalizer(_cleanup)
    return app


@pytest.fixture
def ensure_original_preview(gui_app):
    gui_app._ensure_preview_tab_initialized("original")
    gui_app.update_idletasks()
    return gui_app
