from __future__ import annotations

from ocarina_tools import NoteEvent

from ocarina_gui.staff.rendering.wrapped import WrappedRenderer


class _DummyPalette:
    header_text = "#"
    background = "bg"
    outline = "outline"
    staff_line = "line"
    measure_line = "measure"
    measure_number_text = "m"
    note_fill = "fill"
    note_outline = "outline"


class _DummyScrollbars:
    def __init__(self) -> None:
        self.shown = False

    def show_vertical_scrollbar(self) -> None:
        self.shown = True


class _DummyCursor:
    def create_cursor_lines(self, _height: float) -> None:  # pragma: no cover - noop
        return None

    def create_loop_lines(self, _height: float) -> None:  # pragma: no cover - noop
        return None

    def set_cursor(self, _tick: int) -> None:  # pragma: no cover - noop
        return None

    def set_secondary_cursor(self, _tick: int) -> None:  # pragma: no cover - noop
        return None

    def update_loop_markers(self) -> None:  # pragma: no cover - noop
        return None

    def raise_cursor_lines(self) -> None:  # pragma: no cover - noop
        return None


class _DummyCanvas:
    def __init__(self) -> None:
        self._width = 800
        self.configured = {}
        self.deleted_tags: tuple[str, ...] | None = None

    def winfo_width(self) -> int:
        return self._width

    def config(self, **kwargs) -> None:
        self.configured.update(kwargs)

    configure = config

    def delete(self, *tags: str) -> None:
        self.deleted_tags = tuple(tags)

    def create_text(self, *_args, **_kwargs) -> int:
        return 1

    def create_rectangle(self, *_args, **_kwargs) -> int:
        return 2

    def create_line(self, *_args, **_kwargs) -> int:
        return 3

    def create_oval(self, *_args, **_kwargs) -> int:
        return 4

    def find_withtag(self, _tag: str):  # pragma: no cover - not used
        return ()

    def tag_lower(self, *_args) -> None:  # pragma: no cover - noop
        return None


class _DummyNotePainter:
    def __init__(self) -> None:
        self.available_spaces: list[float | None] = []

    def staff_pos(self, midi: int) -> int:
        return midi - 60

    def y_for_pos(self, y_top: float, pos: int, spacing: float) -> float:
        return y_top + pos * spacing

    def draw_ledger_lines(self, *_args, **_kwargs) -> None:
        return None

    def draw_note_stem_and_flags(self, *_args, **_kwargs) -> None:
        return None

    def draw_dots(self, *_args, available_space=None, **_kwargs) -> None:
        self.available_spaces.append(available_space)

    def draw_tie(self, *_args, **_kwargs) -> None:
        return None


class _DummyView:
    LEFT_PAD = 10
    RIGHT_PAD = 10
    staff_spacing = 8
    px_per_tick = 1.0
    _total_ticks = 200
    _ticks_per_measure = 1920
    _cursor_tick = 0
    _secondary_cursor_tick = None
    scrollbars = _DummyScrollbars()
    cursor = _DummyCursor()
    _wrap_pending_rerender = False

    def __init__(self, events: tuple[NoteEvent, ...]):
        self._palette = _DummyPalette()
        self.canvas = _DummyCanvas()
        self._events = events
        self._event_onsets = tuple(event.onset for event in events)
        self._event_spacing_offsets = (0.0,) * len(events)
        self._cached = (events, 480, 4, 4)

    def set_cursor(self, tick: int) -> None:  # pragma: no cover - noop
        self._cursor_tick = tick

    def set_secondary_cursor(self, tick):  # pragma: no cover - noop
        self._secondary_cursor_tick = tick


def test_wrapped_renderer_tracks_available_space_between_events() -> None:
    events = (
        NoteEvent(0, 24, 60, 0),
        NoteEvent(8, 24, 62, 0),
    )
    view = _DummyView(events)
    painter = _DummyNotePainter()

    renderer = WrappedRenderer(view, painter)
    renderer.render(events, pulses_per_quarter=480, beats=4, beat_type=4)

    assert painter.available_spaces[0] is not None
    assert painter.available_spaces[0] == -4
