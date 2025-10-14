"""Instrument-level management mixin for the layout editor view-model."""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence

from ocarina_tools.pitch import midi_to_name as pitch_midi_to_name

from ocarina_gui.fingering import InstrumentSpec, parse_note_name_safe

from .models import InstrumentLayoutState, clone_state, state_from_spec, state_to_dict
from .note_patterns import normalize_pattern, sort_note_order


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
            copy_fingerings=False,
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

    def set_half_hole_support(self, enabled: bool) -> None:
        state = self.state
        value = bool(enabled)
        if state.allow_half_holes == value:
            return
        state.allow_half_holes = value
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
                        data["candidate_notes"] = list(
                            dict.fromkeys(existing_candidates)
                        )
                    else:
                        data["candidate_notes"] = list(fallback_candidates)

                if fallback_state:
                    fallback_min = parse_note_name_safe(fallback_state.candidate_range_min)
                    fallback_max = parse_note_name_safe(fallback_state.candidate_range_max)
                else:
                    fallback_min = None
                    fallback_max = None

                range_data = data.get("candidate_range") or {}
                current_min_name = str(range_data.get("min", "")).strip()
                current_max_name = str(range_data.get("max", "")).strip()
                current_min = (
                    parse_note_name_safe(current_min_name) if current_min_name else None
                )
                current_max = (
                    parse_note_name_safe(current_max_name) if current_max_name else None
                )

                combined_min = current_min if current_min is not None else fallback_min
                combined_max = current_max if current_max is not None else fallback_max

                if combined_min is not None and combined_max is not None:
                    data["candidate_range"] = {
                        "min": pitch_midi_to_name(combined_min, flats=False),
                        "max": pitch_midi_to_name(combined_max, flats=False),
                    }

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
    def copyable_instrument_choices(self) -> List[tuple[str, str]]:
        """Return instruments that match the current layout geometry."""

        target = self.state
        hole_count = len(target.holes)
        windway_count = len(target.windways)

        compatible: List[tuple[str, str]] = []
        for identifier in self._order:
            if identifier == target.instrument_id:
                continue
            state = self._states[identifier]
            if len(state.holes) != hole_count or len(state.windways) != windway_count:
                continue
            compatible.append((identifier, state.name))

        compatible.sort(key=lambda choice: choice[1].lower())
        return compatible

    def copy_fingerings_from(self, instrument_id: str) -> None:
        """Copy fingering patterns from ``instrument_id`` into the current state."""

        if instrument_id not in self._states:
            raise ValueError(f"Instrument '{instrument_id}' is not available")

        source = self._states[instrument_id]
        target = self.state

        if len(source.holes) != len(target.holes) or len(source.windways) != len(target.windways):
            raise ValueError(
                "Fingerings can only be copied from instruments with the same number of holes "
                "and windways"
            )

        hole_count = len(target.holes)
        windway_count = len(target.windways)

        range_min = self._safe_parse(target.candidate_range_min)
        range_max = self._safe_parse(target.candidate_range_max)

        source_range_min = self._safe_parse(source.candidate_range_min)
        source_range_max = self._safe_parse(source.candidate_range_max)

        def _note_bounds(names: Sequence[str]) -> tuple[Optional[int], Optional[int]]:
            values = [self._safe_parse(name) for name in names]
            filtered = [value for value in values if value is not None]
            if not filtered:
                return (None, None)
            return (min(filtered), max(filtered))

        note_range_min, note_range_max = _note_bounds(tuple(source.note_map.keys()))

        if source_range_min is None or source_range_max is None:
            inferred_min, inferred_max = _note_bounds(
                tuple(source.note_map.keys()) + tuple(source.candidate_notes)
            )
            if source_range_min is None:
                source_range_min = inferred_min
            if source_range_max is None:
                source_range_max = inferred_max

        candidate_offsets: List[int] = []

        def _add_offset(value: Optional[int]) -> None:
            if value is None:
                return
            candidate_offsets.append(int(value))

        _add_offset(0)
        if range_min is not None:
            if source_range_min is not None:
                _add_offset(range_min - source_range_min)
            if note_range_min is not None:
                _add_offset(range_min - note_range_min)
        if range_max is not None:
            if source_range_max is not None:
                _add_offset(range_max - source_range_max)
            if note_range_max is not None:
                _add_offset(range_max - note_range_max)

        candidate_offsets = list(dict.fromkeys(candidate_offsets))

        def _score_offset(offset: int) -> tuple[int, int, int, int, int]:
            included: List[int] = []
            hits_min = False
            hits_max = False

            for name in source.note_map.keys():
                midi = self._safe_parse(name)
                if midi is None:
                    continue
                midi += offset
                if range_min is not None and midi < range_min:
                    continue
                if range_max is not None and midi > range_max:
                    continue
                included.append(midi)
                if range_min is not None and midi == range_min:
                    hits_min = True
                if range_max is not None and midi == range_max:
                    hits_max = True

            if not included:
                return (0, 1 if range_min is None else 0, 1 if range_max is None else 0, -10**6, -abs(offset))

            included.sort()
            span = included[-1] - included[0] if len(included) > 1 else 0
            min_score = 1 if range_min is None else int(hits_min)
            max_score = 1 if range_max is None else int(hits_max)
            return (len(included), min_score, max_score, span, -abs(offset))

        transpose: Optional[int]
        if candidate_offsets:
            transpose = max(candidate_offsets, key=_score_offset)
        else:
            transpose = None

        def _within_range(note: str) -> bool:
            midi = self._safe_parse(note)
            if midi is None:
                return True
            if range_min is not None and midi < range_min:
                return False
            if range_max is not None and midi > range_max:
                return False
            return True

        new_map: Dict[str, List[int]] = {}
        for note, pattern in source.note_map.items():
            midi = self._safe_parse(note)
            if transpose is not None:
                if midi is None:
                    continue
                note = pitch_midi_to_name(midi + transpose, flats=False)
            if not _within_range(note):
                continue
            new_map[note] = normalize_pattern(pattern, hole_count, windway_count)

        new_order: List[str] = []
        seen_order: set[str] = set()
        for note in source.note_order:
            midi = self._safe_parse(note)
            if transpose is not None:
                if midi is None:
                    continue
                note = pitch_midi_to_name(midi + transpose, flats=False)
            if note in new_map and note not in seen_order:
                new_order.append(note)
                seen_order.add(note)
        for note in new_map:
            if note not in new_order:
                new_order.append(note)

        candidate_notes: List[str] = []
        seen: set[str] = set()

        def _add_candidate(name: str) -> None:
            normalized = str(name).strip()
            if not normalized or normalized in seen:
                return
            if not _within_range(normalized):
                return
            candidate_notes.append(normalized)
            seen.add(normalized)

        if range_min is not None and range_max is not None and range_min <= range_max:
            for generated in self._generate_range_names(range_min, range_max):
                _add_candidate(generated)
        else:
            for existing in target.candidate_notes:
                _add_candidate(existing)

        for existing in target.candidate_notes:
            _add_candidate(existing)
        for existing in source.candidate_notes:
            _add_candidate(existing)
        for note in new_order:
            _add_candidate(note)

        changed = (
            target.note_map != new_map
            or target.note_order != new_order
            or list(target.candidate_notes) != candidate_notes
        )

        target.note_map = new_map
        target.note_order = new_order
        target.candidate_notes = candidate_notes

        sort_note_order(target)
        self._normalize_preferred_range(target)

        if changed:
            target.dirty = True

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
