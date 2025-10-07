"""Headless fallbacks for running the GUI logic without a display."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Callable, List, Optional, Sequence, Tuple

from ocarina_tools import NoteEvent


class HeadlessListbox:
    """Minimal listbox replacement that stores strings in memory."""

    def __init__(self) -> None:
        self._items: List[str] = []

    def delete(self, start: int, end: Optional[str] = None) -> None:
        if start == 0 and (end in (None, "end")):
            self._items.clear()
        else:
            try:
                del self._items[start]
            except Exception:
                pass

    def insert(self, index: int | str, value: str) -> None:
        if index == "end" or index >= len(self._items):  # type: ignore[operator]
            self._items.append(value)
        else:
            self._items.insert(int(index), value)

    def size(self) -> int:
        return len(self._items)

    def get(self, index: int) -> str:
        return self._items[index]


@dataclass
class HeadlessCanvas:
    """Canvas stub with just enough behaviour for previews."""

    _x: float = 0.0

    def xview(self) -> Tuple[float, float]:
        return (self._x, min(1.0, self._x + 1.0))

    def xview_moveto(self, fraction: float) -> None:
        self._x = max(0.0, min(1.0, fraction))

    def yview(self, *args) -> None:  # pragma: no cover - no behaviour needed
        pass

    def yview_moveto(self, fraction: float) -> None:  # pragma: no cover
        pass

    def configure(self, **kwargs) -> None:  # pragma: no cover
        pass

    config = configure

    def delete(self, *args) -> None:  # pragma: no cover
        pass


@dataclass
class HeadlessScrollbar:
    """Simplified scrollbar stand-in for headless previews."""

    name: str
    mapped: bool = True
    _grid_kwargs: dict[str, object] = field(default_factory=dict)

    def grid(self, **kwargs) -> None:
        if kwargs:
            self._grid_kwargs.update(kwargs)
        self.mapped = True

    def grid_configure(self, **kwargs) -> None:
        if kwargs:
            self._grid_kwargs.update(kwargs)
        self.mapped = True

    def grid_remove(self) -> None:
        self.mapped = False

    def grid_info(self) -> dict[str, object]:
        return dict(self._grid_kwargs)

    def tkraise(self) -> None:  # pragma: no cover - no-op for tests
        pass

    def update_idletasks(self) -> None:  # pragma: no cover - no-op for tests
        pass

    def winfo_ismapped(self) -> bool:
        return self.mapped

    def winfo_reqwidth(self) -> int:  # pragma: no cover - provide a default width
        return int(self._grid_kwargs.get("minsize", 16) or 16)


class HeadlessFingeringView:
    def __init__(self) -> None:
        self.midi: Optional[int] = None
        self.note_name: Optional[str] = None
        self.status: str = ""
        self._hole_click_handler: Optional[Callable[[int], None]] = None
        self._windway_click_handler: Optional[Callable[[int], None]] = None

    def set_midi(self, midi: Optional[int]) -> None:
        if midi is None:
            self.show_fingering(None, None)
            return

        try:
            from .fingering import midi_to_name

            self.show_fingering(midi_to_name(midi), midi)
        except Exception:
            self.midi = midi
            self.note_name = None
            self.status = ""

    def show_fingering(self, note_name: Optional[str], midi: Optional[int]) -> None:
        self.note_name = note_name.strip() if note_name else None
        self.midi = midi
        if not self.note_name:
            self.status = ""
            return

        try:
            from .fingering import get_current_instrument, midi_to_name, natural_of
            from ocarina_tools.pitch import parse_note_name

            instrument = get_current_instrument()
            mapping = instrument.note_map.get(self.note_name)

            midi_value = midi
            if midi_value is None:
                try:
                    midi_value = parse_note_name(self.note_name)
                except Exception:
                    midi_value = None

            if midi_value is not None:
                if mapping is None:
                    mapping = instrument.note_map.get(midi_to_name(midi_value))
                if mapping is None:
                    mapping = instrument.note_map.get(natural_of(midi_value))

            self.status = "" if mapping is not None else "No fingering available"
        except Exception:
            self.status = ""

    def set_hole_click_handler(self, handler: Optional[Callable[[int], None]]) -> None:
        self._hole_click_handler = handler

    def trigger_hole_click(self, hole_index: int) -> None:
        if self._hole_click_handler:
            self._hole_click_handler(hole_index)

    def set_windway_click_handler(self, handler: Optional[Callable[[int], None]]) -> None:
        self._windway_click_handler = handler

    def trigger_windway_click(self, windway_index: int) -> None:
        if self._windway_click_handler:
            self._windway_click_handler(windway_index)


@dataclass
class HeadlessPianoRoll:
    label_width: int = 70
    LEFT_PAD: int = 10
    canvas: HeadlessCanvas = field(default_factory=HeadlessCanvas)
    _cached: Optional[Tuple[Sequence[NoteEvent], int, int, int]] = None
    _fingering_cb: Optional[Callable[[Optional[int]], None]] = None
    _cursor_cb: Optional[Callable[[int], None]] = None
    _cursor_drag_state_cb: Optional[Callable[[bool], None]] = None
    _cursor_tick: int = 0
    loop_region: Optional[Tuple[int, int, bool]] = None
    auto_scroll_mode: str = "flip"

    def set_range(self, minimum: int, maximum: int) -> None:  # pragma: no cover - stored for completeness
        self.range = (minimum, maximum)

    def render(
        self,
        events: Sequence[Event],
        pulses_per_quarter: int,
        *,
        beats: int = 4,
        beat_unit: int = 4,
    ) -> None:
        self._cached = (events, pulses_per_quarter, beats, beat_unit)
        if self._fingering_cb:
            self._fingering_cb(None)

    def set_fingering_cb(self, callback: Callable[[Optional[int]], None]) -> None:
        self._fingering_cb = callback

    def set_cursor_callback(self, callback: Callable[[int], None]) -> None:
        self._cursor_cb = callback

    def set_cursor_drag_state_cb(self, callback: Callable[[bool], None]) -> None:
        self._cursor_drag_state_cb = callback

    def set_auto_scroll_mode(self, mode: object) -> None:
        if isinstance(mode, str):
            self.auto_scroll_mode = mode
        elif hasattr(mode, "value"):
            self.auto_scroll_mode = getattr(mode, "value")

    def set_cursor(self, tick: int, allow_autoscroll: bool = True) -> None:
        self._cursor_tick = max(0, tick)

    def sync_x_with(self, _target: HeadlessCanvas) -> None:  # pragma: no cover
        pass

    def set_zoom(self, _delta: int) -> None:  # pragma: no cover
        pass

    def set_time_zoom(self, _multiplier: float) -> None:  # pragma: no cover
        pass

    def set_loop_region(self, start_tick: int, end_tick: int, visible: bool) -> None:
        self.loop_region = (start_tick, end_tick, visible)


@dataclass
class HeadlessStaffView:
    LEFT_PAD: int = 10
    px_per_tick: float = 0.25
    canvas: HeadlessCanvas = field(default_factory=HeadlessCanvas)
    hbar: HeadlessScrollbar = field(default_factory=lambda: HeadlessScrollbar("hbar"))
    vbar: HeadlessScrollbar = field(default_factory=lambda: HeadlessScrollbar("vbar"))
    _cached: Optional[Tuple[Sequence[Event], int, int, int]] = None
    cursor_tick: int = 0
    secondary_cursor_tick: Optional[int] = None
    _cursor_cb: Optional[Callable[[int], None]] = None
    _cursor_drag_state_cb: Optional[Callable[[bool], None]] = None
    auto_scroll_mode: str = "flip"
    loop_region: Optional[Tuple[int, int, bool]] = None
    _layout_mode: str = "horizontal"
    _hbar_grid_defaults: dict[str, object] = field(default_factory=dict, init=False)
    _vbar_grid_defaults: dict[str, object] = field(default_factory=dict, init=False)
    _wrap_pending_rerender: bool = False

    def __post_init__(self) -> None:
        self._hbar_grid_defaults = {"row": 1, "column": 0, "columnspan": 3, "sticky": "ew"}
        self._vbar_grid_defaults = {"row": 0, "column": 2, "sticky": "ns"}
        self.hbar.grid(**self._hbar_grid_defaults)
        self.vbar.grid(**self._vbar_grid_defaults)

    def sync_x_with(self, _target: HeadlessCanvas) -> None:  # pragma: no cover
        pass

    def set_time_zoom(self, multiplier: float) -> None:  # pragma: no cover
        new_px = max(0.1, min(5.0, self.px_per_tick * multiplier))
        if abs(new_px - self.px_per_tick) > 1e-6:
            self.px_per_tick = new_px
            if self._cached:
                events, ppq, beats, beat_type = self._cached
                self.render(events, ppq, beats, beat_type)
        else:
            self.px_per_tick = new_px

    def render(
        self,
        events: Sequence[NoteEvent],
        pulses_per_quarter: int,
        beats: int,
        beat_type: int,
    ) -> None:
        self._cached = (events, pulses_per_quarter, beats, beat_type)

    def set_cursor(self, tick: int, allow_autoscroll: bool = True) -> None:
        self.cursor_tick = max(0, int(tick))
        if self._cursor_cb:
            self._cursor_cb(self.cursor_tick)

    def set_loop_region(self, start_tick: int, end_tick: int, visible: bool) -> None:
        self.loop_region = (start_tick, end_tick, visible)

    def set_cursor_callback(self, callback: Callable[[int], None]) -> None:
        self._cursor_cb = callback

    def set_cursor_drag_state_cb(self, callback: Callable[[bool], None]) -> None:
        self._cursor_drag_state_cb = callback

    def set_secondary_cursor(self, tick: Optional[int]) -> None:
        if tick is None:
            self.secondary_cursor_tick = None
        else:
            self.secondary_cursor_tick = max(0, int(tick))
        return

    def set_auto_scroll_mode(self, mode: object) -> None:
        if isinstance(mode, str):
            self.auto_scroll_mode = mode
        elif hasattr(mode, "value"):
            self.auto_scroll_mode = getattr(mode, "value")

    def set_layout_mode(self, mode: str) -> None:
        normalized = mode.lower()
        if normalized not in {"horizontal", "wrapped"}:
            raise ValueError(f"Unsupported layout mode: {mode}")
        self._layout_mode = normalized
        if normalized == "wrapped":
            self.hbar.grid_remove()
            self.vbar.grid(**self._vbar_grid_defaults)
        else:
            self.hbar.grid(**self._hbar_grid_defaults)
            self.vbar.grid(**self._vbar_grid_defaults)

    def update_idletasks(self) -> None:  # pragma: no cover - compatibility stub
        pass

    def _request_wrapped_rerender(self) -> None:  # pragma: no cover - headless no-op
        self._wrap_pending_rerender = False

class _HeadlessWidget:
    """Common behaviour for headless widget stand-ins."""

    def __init__(self) -> None:
        self._options: dict[str, object] = {}
        self._bindings: dict[str, list[Callable[[SimpleNamespace], object | None]]] = {}
        self._manager: str = ""
        self._grid_options: dict[str, object] = {}
        self._width: int = 24
        self._height: int = 24

    def configure(self, **kwargs: object) -> None:
        if not kwargs:
            return
        image = kwargs.pop("image", None)
        if image is not None:
            if image in ("", None):
                self._options["image"] = ""
            else:
                self._options["image"] = str(image)
        for key, value in kwargs.items():
            self._options[key] = value
        width = self._options.get("width")
        if width is not None:
            try:
                self._width = int(width) if int(width) > 0 else self._width
            except (TypeError, ValueError):
                pass
        length = self._options.get("length")
        if length is not None:
            try:
                length_value = int(length)
            except (TypeError, ValueError):
                length_value = None
            if length_value:
                self._width = max(1, length_value)
        height = self._options.get("height")
        if height is not None:
            try:
                height_value = int(height)
            except (TypeError, ValueError):
                height_value = None
            if height_value:
                self._height = max(1, height_value)

    config = configure

    def cget(self, option: str) -> object:
        if option == "image":
            return self._options.get("image", "")
        return self._options.get(option, "")

    def bind(
        self, sequence: str, func: Callable[[SimpleNamespace], object | None] | None, add: str | None = None
    ) -> None:
        if func is None:
            return
        if add == "+" and sequence in self._bindings:
            self._bindings[sequence].append(func)
        else:
            self._bindings[sequence] = [func]

    def event_generate(self, sequence: str, **kwargs: object) -> None:
        callbacks = list(self._bindings.get(sequence, ()))
        if not callbacks:
            return
        event = SimpleNamespace(widget=self, **kwargs)
        for callback in callbacks:
            callback(event)

    def grid(self, **kwargs: object) -> None:
        if kwargs:
            self._grid_options.update(kwargs)
        self._manager = "grid"

    def grid_configure(self, **kwargs: object) -> None:
        if kwargs:
            self._grid_options.update(kwargs)
        self._manager = "grid"

    def grid_remove(self) -> None:
        self._manager = ""

    def grid_info(self) -> dict[str, object]:
        return dict(self._grid_options)

    def update_idletasks(self) -> None:  # pragma: no cover - compatibility shim
        return None

    def winfo_height(self) -> int:
        return self._height

    def winfo_manager(self) -> str:
        return self._manager

    def winfo_width(self) -> int:
        return self._width


class _HeadlessStateful:
    def __init__(self) -> None:
        self._states: set[str] = set()

    def state(self, states: Optional[Sequence[str]] = None) -> tuple[str, ...]:
        if states is None:
            return tuple(self._states)
        for flag in states:
            if flag.startswith("!"):
                self._states.discard(flag[1:])
            else:
                self._states.add(flag)
        return tuple(self._states)

    def instate(self, states: Sequence[str]) -> bool:
        for flag in states:
            if flag.startswith("!"):
                if flag[1:] in self._states:
                    return False
            elif flag not in self._states:
                return False
        return True


class HeadlessButton(_HeadlessStateful, _HeadlessWidget):
    """Minimal stand-in for ttk.Button in headless tests."""

    def __init__(
        self,
        command: Optional[Callable[[], None]] = None,
        *,
        text: str = "",
        enabled: bool = False,
    ) -> None:
        _HeadlessStateful.__init__(self)
        _HeadlessWidget.__init__(self)
        self._command = command
        self._options.update({
            "text": text,
            "compound": "center",
            "bootstyle": None,
            "width": 24,
        })
        if not enabled:
            self._states.add("disabled")

    def configure(self, **kwargs: object) -> None:
        if "text" in kwargs:
            text_value = kwargs["text"]
            self._options["text"] = "" if text_value is None else str(text_value)
        _HeadlessWidget.configure(self, **kwargs)

    def invoke(self) -> None:
        if "disabled" in self._states:
            return
        if self._command is not None:
            self._command()


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


class HeadlessSpinbox(_HeadlessStateful, _HeadlessWidget):
    def __init__(self) -> None:
        _HeadlessStateful.__init__(self)
        _HeadlessWidget.__init__(self)


class HeadlessCheckbutton(_HeadlessStateful, _HeadlessWidget):
    def __init__(self) -> None:
        _HeadlessStateful.__init__(self)
        _HeadlessWidget.__init__(self)


class HeadlessScale(_HeadlessStateful, _HeadlessWidget):
    """Headless replacement for ``ttk.Scale`` used in GUI tests."""

    def __init__(
        self,
        *,
        variable,
        from_: float = 0.0,
        to: float = 100.0,
        length: int = 120,
    ) -> None:
        _HeadlessStateful.__init__(self)
        _HeadlessWidget.__init__(self)
        self._variable = variable
        self._options.update({"from": float(from_), "to": float(to), "length": length})
        self._width = max(1, int(length))
        self._height = 16
        try:
            initial = float(variable.get())
        except Exception:
            initial = float(from_)
        self._value = float(from_)
        self.set(initial)

    def configure(self, **kwargs: object) -> None:
        if "from_" in kwargs:
            kwargs = dict(kwargs)
            kwargs["from"] = kwargs.pop("from_")
        super().configure(**kwargs)
        for key in ("from", "to"):
            if key in kwargs:
                try:
                    self._options[key] = float(kwargs[key])
                except (TypeError, ValueError):
                    continue

    def cget(self, option: str) -> object:
        if option == "from":
            return self._options.get("from", 0.0)
        if option == "to":
            return self._options.get("to", 100.0)
        return super().cget(option)

    def get(self) -> float:
        return float(self._value)

    def set(self, value: float) -> None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return
        lower = float(self._options.get("from", 0.0))
        upper = float(self._options.get("to", 100.0))
        self._value = max(lower, min(upper, numeric))
        variable = self._variable
        if variable is not None:
            try:
                variable.set(self._value)
            except Exception:
                pass


class HeadlessFrame:
    """Simple frame stub that tracks geometry manager interactions."""

    def __init__(self) -> None:
        self._manager = ""
        self._place_info: dict[str, object] = {}

    def pack(self, **_kwargs) -> None:
        self._manager = "pack"

    def pack_forget(self) -> None:
        self._manager = ""

    def place(self, **kwargs) -> None:
        self._manager = "place"
        self._place_info = kwargs

    def place_forget(self) -> None:
        self._manager = ""
        self._place_info = {}

    def lift(self) -> None:  # pragma: no cover - no-op for tests
        pass

    def lower(self) -> None:  # pragma: no cover - no-op for tests
        pass

    def winfo_manager(self) -> str:
        return self._manager

    def place_info(self) -> dict[str, object]:  # pragma: no cover - debugging helper
        return self._place_info

    def winfo_ismapped(self) -> bool:
        return bool(self._manager)

    def focus_set(self) -> None:  # pragma: no cover - no-op for tests
        pass


def build_headless_ui(app: "App") -> None:
    """Populate minimal widget-like attributes for headless tests."""

    app.fingering_table = None
    preview = HeadlessFingeringView()
    register_preview = getattr(app, "_register_fingering_preview", None)
    if callable(register_preview):
        register_preview(preview)
    else:  # pragma: no cover - legacy path
        app.fingering_preview = preview
    app.fingering_grid = None
    app.roll_orig = HeadlessPianoRoll()
    app.roll_arr = HeadlessPianoRoll()
    if hasattr(app, "_register_auto_scroll_target"):
        app._register_auto_scroll_target(app.roll_orig)
        app._register_auto_scroll_target(app.roll_arr)
    app.staff_orig = HeadlessStaffView()
    app.staff_arr = HeadlessStaffView()
    app.side_fing_orig = HeadlessFingeringView()
    app.side_fing_arr = HeadlessFingeringView()
    if hasattr(app.roll_orig, "set_fingering_cb"):
        app.roll_orig.set_fingering_cb(
            lambda midi, side="original": app._on_preview_roll_hover(side, midi)
        )
    if hasattr(app.roll_arr, "set_fingering_cb"):
        app.roll_arr.set_fingering_cb(
            lambda midi, side="arranged": app._on_preview_roll_hover(side, midi)
        )

    for side in ("original", "arranged"):
        volume_button = HeadlessButton(
            lambda s=side: app._handle_preview_volume_button(s, None),
            enabled=True,
        )
        volume_button.configure(width=3, text="🔈", compound="center")
        volume_button.bind(
            "<ButtonRelease-1>",
            lambda event, s=side: app._handle_preview_volume_button(s, event),
            add="+",
        )
        volume_var = app._preview_volume_vars[side]
        volume_slider = HeadlessScale(
            variable=volume_var,
            from_=0.0,
            to=100.0,
            length=120,
        )
        volume_slider.bind(
            "<ButtonPress-1>",
            lambda event, s=side: app._on_preview_volume_press(s, event),
            add="+",
        )
        volume_slider.bind(
            "<B1-Motion>",
            lambda event, s=side: app._on_preview_volume_drag(s, event),
            add="+",
        )
        volume_slider.bind(
            "<ButtonRelease-1>",
            lambda event, s=side: app._on_preview_volume_release(s, event),
            add="+",
        )
        volume_buttons = getattr(app, "_preview_volume_buttons", None)
        if not isinstance(volume_buttons, dict):
            volume_buttons = {}
            app._preview_volume_buttons = volume_buttons
        volume_buttons[side] = volume_button
        volume_controls = getattr(app, "_preview_volume_controls", None)
        if not isinstance(volume_controls, dict):
            volume_controls = {}
            app._preview_volume_controls = volume_controls
        volume_controls[side] = (volume_button, volume_slider)
        volume_icon_sets = getattr(app, "_preview_volume_icons", None)
        if not isinstance(volume_icon_sets, dict):
            volume_icon_sets = {}
            app._preview_volume_icons = volume_icon_sets
        volume_icon_sets[side] = {"normal": None, "muted": None}
        if hasattr(app, "_update_mute_button_state"):
            try:
                app._update_mute_button_state(side)
            except Exception:
                pass

        tempo_ctrl = HeadlessSpinbox()
        metronome_ctrl = HeadlessCheckbutton()
        app._register_preview_adjust_widgets(side, tempo_ctrl, metronome_ctrl)
        loop_toggle = HeadlessCheckbutton()
        loop_start = HeadlessSpinbox()
        loop_end = HeadlessSpinbox()
        set_range_btn = HeadlessButton(lambda s=side: app._begin_loop_range_selection(s))
        app._register_preview_loop_range_button(side, set_range_btn)
        app._register_preview_loop_widgets(side, loop_toggle, loop_start, loop_end, set_range_btn)
        apply_btn = HeadlessButton(lambda s=side: app._apply_preview_settings(s))
        cancel_btn = HeadlessButton(lambda s=side: app._cancel_preview_settings(s))
        app._register_preview_control_buttons(side, apply_btn, cancel_btn)
        progress_frame = HeadlessFrame()
        app._register_preview_progress_frame(
            side,
            progress_frame,
            place={"relx": 0.0, "rely": 0.0, "relwidth": 1.0, "relheight": 1.0},
        )
    transpose_spin = HeadlessSpinbox()
    transpose_apply = HeadlessButton(app._apply_transpose_offset)
    transpose_cancel = HeadlessButton(app._cancel_transpose_offset)
    app._register_transpose_spinbox(
        transpose_spin, apply_button=transpose_apply, cancel_button=transpose_cancel
    )
    reimport_button = HeadlessButton(app.reimport_and_arrange)
    app._register_reimport_button(reimport_button)


# Avoid circular import at runtime.
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .app import App
