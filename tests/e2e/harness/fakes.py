from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ocarina_gui.fingering import InstrumentChoice


@dataclass(slots=True)
class FakeInstrumentSpec:
    instrument_id: str
    name: str
    note_names: tuple[str, ...]
    preferred_range: tuple[str, str]
    note_map: dict[str, list[int]] = field(default_factory=dict)
    preferred_range_min: str = field(init=False)
    preferred_range_max: str = field(init=False)
    candidate_range_min: str = field(init=False)
    candidate_range_max: str = field(init=False)
    note_order: tuple[str, ...] = field(init=False)
    candidate_notes: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "preferred_range_min", self.preferred_range[0])
        object.__setattr__(self, "preferred_range_max", self.preferred_range[1])
        object.__setattr__(self, "candidate_range_min", self.note_names[0])
        object.__setattr__(self, "candidate_range_max", self.note_names[-1])
        object.__setattr__(self, "note_order", self.note_names)
        object.__setattr__(self, "candidate_notes", self.note_names)


class FakeFingeringView:
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN001 - tkinter protocol
        self._hole_handler = None
        self._windway_handler = None
        self.displayed_fingerings: list[tuple[str, int]] = []

    def clear(self) -> None:
        self.displayed_fingerings.clear()

    def show_fingering(self, note_name: str, midi: int) -> None:
        self.displayed_fingerings.append((note_name, midi))

    def set_hole_click_handler(self, handler) -> None:  # noqa: ANN001 - tkinter protocol
        self._hole_handler = handler

    def set_windway_click_handler(self, handler) -> None:  # noqa: ANN001 - tkinter protocol
        self._windway_handler = handler


class FakeFingeringGridView:
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN001 - tkinter protocol
        self.notes: tuple[str, ...] = ()

    def set_notes(self, notes, *_args) -> None:  # noqa: ANN001 - tkinter protocol
        self.notes = tuple(notes)


class FakeFingeringLibrary:
    def __init__(self) -> None:
        alto_spec = FakeInstrumentSpec(
            instrument_id="alto_c_12",
            name="Alto C (12-hole)",
            note_names=("C4", "D4", "E4", "F4", "G4"),
            preferred_range=("C4", "G4"),
            note_map={
                "C4": [2, 2, 2, 2],
                "D4": [2, 2, 2, 0],
                "E4": [2, 2, 0, 0],
                "F4": [2, 0, 0, 0],
                "G4": [0, 0, 0, 0],
            },
        )
        tenor_spec = FakeInstrumentSpec(
            instrument_id="alto_c_6",
            name="Alto C (6-hole)",
            note_names=("C4", "D4", "E4", "F4", "G4"),
            preferred_range=("C4", "F4"),
            note_map={
                "C4": [2, 2, 2, 2],
                "D4": [2, 2, 2, 0],
                "E4": [2, 2, 0, 0],
                "F4": [2, 0, 0, 0],
                "G4": [0, 0, 0, 0],
            },
        )
        self._instruments: dict[str, FakeInstrumentSpec] = {
            alto_spec.instrument_id: alto_spec,
            tenor_spec.instrument_id: tenor_spec,
        }
        self._current_id = alto_spec.instrument_id
        self._listeners: list[Callable[[FakeInstrumentSpec], None]] = []

    def get_available_instruments(self) -> list[InstrumentChoice]:
        return [
            InstrumentChoice(instrument_id=spec.instrument_id, name=spec.name)
            for spec in self._instruments.values()
        ]

    def get_instrument(self, instrument_id: str) -> FakeInstrumentSpec:
        if instrument_id not in self._instruments:
            raise ValueError(f"Unknown instrument: {instrument_id}")
        return self._instruments[instrument_id]

    def get_current_instrument_id(self) -> str:
        return self._current_id

    def set_active_instrument(self, instrument_id: str) -> None:
        spec = self.get_instrument(instrument_id)
        if instrument_id == self._current_id:
            return
        self._current_id = instrument_id
        for listener in list(self._listeners):
            listener(spec)

    def register_listener(self, listener: Callable[[FakeInstrumentSpec], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def _unsubscribe() -> None:
            try:
                self._listeners.remove(listener)
            except ValueError:  # pragma: no cover - defensive cleanup
                pass

        return _unsubscribe

    def collect_note_names(self, instrument: FakeInstrumentSpec) -> list[str]:
        return list(instrument.note_names)

    def preferred_window(self, instrument: FakeInstrumentSpec) -> tuple[str, str]:
        return instrument.preferred_range


class ImmediateThread:
    def __init__(self, target=None, args=(), kwargs=None, **_unused) -> None:  # noqa: ANN001
        self._target = target or (lambda: None)
        self._args = args
        self._kwargs = kwargs or {}

    def start(self) -> None:
        self._target(*self._args, **self._kwargs)

    def join(self, timeout: float | None = None) -> None:  # noqa: D401 - compatibility no-op
        return None


__all__ = [
    "FakeInstrumentSpec",
    "FakeFingeringView",
    "FakeFingeringGridView",
    "FakeFingeringLibrary",
    "ImmediateThread",
]
