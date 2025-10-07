from __future__ import annotations

from tests.helpers import require_ttkbootstrap

require_ttkbootstrap()

import pytest

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

    def prepare(self, events, pulses_per_quarter):  # type: ignore[override]
        self._begin_render()

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
    stub_library = FingeringLibrary([stub_instrument])
    monkeypatch.setattr("ocarina_gui.fingering._LIBRARY", stub_library)

    monkeypatch.setattr(
        "ocarina_gui.audio.build_preview_audio_renderer",
        lambda: _StubAudioRenderer(),
    )
    app = App()
    app.withdraw()
    app.update_idletasks()

    app._test_audio_renderers = {}
    for key in ("original", "arranged"):
        stub_renderer = _StubAudioRenderer()
        app._preview_playback[key] = PreviewPlaybackViewModel(audio_renderer=stub_renderer)
        app._bind_preview_render_observer(key)
        app._test_audio_renderers[key] = stub_renderer
        app._sync_preview_playback_controls(key)

    def _cleanup() -> None:
        try:
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
