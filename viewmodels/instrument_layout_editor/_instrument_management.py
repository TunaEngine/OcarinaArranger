"""Instrument-level management mixin for the layout editor view-model."""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence

from ocarina_gui.fingering import InstrumentSpec

from .models import InstrumentLayoutState, clone_state, state_from_spec, state_to_dict
from .note_patterns import sort_note_order


class InstrumentManagementMixin:
    """Create, update, and persist instrument layout states."""

    _states: Dict[str, InstrumentLayoutState]
    _order: List[str]
    _current_id: str
    state: InstrumentLayoutState

    # ------------------------------------------------------------------
    def _build_state(self, instrument: InstrumentSpec) -> InstrumentLayoutState:
        state = state_from_spec(instrument)
        sort_note_order(state)
        self._normalize_preferred_range(state)
        return state

    # ------------------------------------------------------------------
    def add_instrument(
        self,
        instrument_id: str,
        name: str,
        *,
        title: Optional[str] = None,
    ) -> InstrumentLayoutState:
        instrument_id = str(instrument_id).strip()
        if not instrument_id:
            raise ValueError("Instrument identifier cannot be empty")
        if instrument_id in self._states:
            raise ValueError(f"Instrument '{instrument_id}' already exists")

        name = str(name).strip() or instrument_id
        template = self.state
        state = clone_state(
            instrument_id,
            name,
            template=template,
            title=title,
        )
        sort_note_order(state)
        self._normalize_preferred_range(state)

        self._states[instrument_id] = state
        self._order.append(instrument_id)
        self._current_id = instrument_id
        self.state = state
        return state

    def remove_current_instrument(self) -> InstrumentLayoutState:
        if len(self._states) <= 1:
            raise ValueError("At least one instrument must remain")

        current_id = self._current_id
        index = self._order.index(current_id)
        self._order.pop(index)
        del self._states[current_id]

        if index >= len(self._order):
            index = len(self._order) - 1
        self._current_id = self._order[index]
        self.state = self._states[self._current_id]
        self.state.dirty = True
        return self.state

    def update_instrument_metadata(
        self,
        *,
        instrument_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        state = self.state
        changed = False

        if name is not None:
            new_name = str(name).strip()
            if not new_name:
                raise ValueError("Instrument name cannot be empty")
            if new_name != state.name:
                state.name = new_name
                changed = True

        if instrument_id is not None:
            new_id = str(instrument_id).strip()
            if not new_id:
                raise ValueError("Instrument identifier cannot be empty")
            if new_id != state.instrument_id:
                if new_id in self._states:
                    raise ValueError(f"Instrument '{new_id}' already exists")
                old_id = state.instrument_id
                state.instrument_id = new_id
                self._states[new_id] = state
                del self._states[old_id]
                index = self._order.index(old_id)
                self._order[index] = new_id
                self._current_id = new_id
                changed = True

        if changed:
            state.dirty = True

    def select_instrument(self, instrument_id: str) -> None:
        if instrument_id not in self._states:
            raise ValueError(f"Unknown instrument: {instrument_id}")
        self._current_id = instrument_id
        self.state = self._states[instrument_id]

    # ------------------------------------------------------------------
    def current_instrument_dict(self) -> Dict[str, object]:
        return state_to_dict(self.state)

    def build_config(self) -> Dict[str, object]:
        return {"instruments": [state_to_dict(self._states[identifier]) for identifier in self._order]}

    def import_instrument(
        self,
        data: Mapping[str, object],
        *,
        conflict_strategy: str = "error",
    ) -> InstrumentLayoutState:
        if not isinstance(data, Mapping):
            raise ValueError("Instrument configuration must be a mapping")

        try:
            spec = InstrumentSpec.from_dict(dict(data))
        except Exception as exc:  # pragma: no cover - delegated validation
            raise ValueError(f"Invalid instrument specification: {exc}") from exc

        identifier = spec.instrument_id
        state = self._build_state(spec)
        state.dirty = True

        if conflict_strategy == "replace" and identifier in self._states:
            self._states[identifier] = state
            if identifier not in self._order:
                self._order.append(identifier)
        else:
            if identifier in self._states:
                if conflict_strategy != "copy":
                    raise ValueError(f"Instrument '{identifier}' already exists")
                identifier = self._generate_unique_instrument_id(identifier)
                state.instrument_id = identifier
                state.name = self._generate_copy_name(state.name)

            self._states[identifier] = state
            if identifier not in self._order:
                self._order.append(identifier)

        self._current_id = identifier
        self.state = state
        return state

    def load_config(
        self,
        config: Mapping[str, object],
        *,
        current_instrument_id: Optional[str] = None,
    ) -> None:
        entries = config.get("instruments")
        if entries is None:
            raise ValueError("Configuration must define at least one instrument")
        if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
            raise ValueError("Configuration must define at least one instrument")

        new_states: Dict[str, InstrumentLayoutState] = {}
        new_order: List[str] = []
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise ValueError("Instrument entries must be mappings")
            try:
                data = dict(entry)
                instrument_id = str(data.get("id", ""))
                fallback_state = self._states.get(instrument_id)
                fallback_candidates: Sequence[str] = ()
                if fallback_state and fallback_state.candidate_notes:
                    fallback_candidates = tuple(
                        str(note) for note in fallback_state.candidate_notes
                    )

                if fallback_candidates:
                    existing_candidates = [
                        str(note) for note in data.get("candidate_notes", [])
                    ]
                    if existing_candidates:
                        combined = list(
                            dict.fromkeys(existing_candidates + list(fallback_candidates))
                        )
                        if len(combined) > len(existing_candidates):
                            data["candidate_notes"] = combined
                    else:
                        data["candidate_notes"] = list(fallback_candidates)

                spec = InstrumentSpec.from_dict(data)
            except Exception as exc:  # pragma: no cover - delegated validation
                raise ValueError(f"Invalid instrument specification: {exc}") from exc
            if spec.instrument_id in new_states:
                raise ValueError(f"Instrument '{spec.instrument_id}' defined multiple times")
            new_states[spec.instrument_id] = self._build_state(spec)
            new_order.append(spec.instrument_id)

        if not new_order:
            raise ValueError("Configuration must define at least one instrument")

        self._states = new_states
        self._order = new_order

        preferred_id = current_instrument_id or self._current_id
        if preferred_id not in self._states:
            preferred_id = self._order[0]

        self._current_id = preferred_id
        self.state = self._states[self._current_id]
        self.mark_clean()

    def is_dirty(self) -> bool:
        return any(state.dirty for state in self._states.values())

    def mark_clean(self) -> None:
        for state in self._states.values():
            state.dirty = False

    def choices(self) -> List[tuple[str, str]]:
        return [(identifier, self._states[identifier].name) for identifier in self._order]

    def get_state(self, instrument_id: str) -> InstrumentLayoutState:
        return self._states[instrument_id]

    # ------------------------------------------------------------------
    def _generate_unique_instrument_id(self, base: str) -> str:
        candidate = base
        suffix = 2
        while candidate in self._states:
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    def _generate_copy_name(self, name: str) -> str:
        base = name or "Instrument"
        candidate = f"{base} (copy)"
        suffix = 2
        existing = {state.name for state in self._states.values()}
        while candidate in existing:
            candidate = f"{base} (copy {suffix})"
            suffix += 1
        return candidate
