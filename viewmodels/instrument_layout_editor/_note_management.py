"""Note-related operations for the instrument layout editor view-model."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from ocarina_tools.pitch import midi_to_name as pitch_midi_to_name
from ocarina_tools.pitch import parse_note_name

from .models import InstrumentLayoutState
from .note_patterns import ensure_candidate_name, normalize_pattern, sort_note_order


class NoteManagementMixin:
    """Provide note-range and fingering pattern helpers."""

    state: InstrumentLayoutState

    # ------------------------------------------------------------------
    @staticmethod
    def _safe_parse(note: str) -> Optional[int]:
        try:
            return parse_note_name(note)
        except ValueError:
            return None

    def _generate_range_names(self, minimum: int, maximum: int) -> List[str]:
        return [pitch_midi_to_name(midi, flats=False) for midi in range(minimum, maximum + 1)]

    def _candidate_note_names_for_state(
        self, state: InstrumentLayoutState
    ) -> List[str]:
        range_min = self._safe_parse(state.candidate_range_min)
        range_max = self._safe_parse(state.candidate_range_max)

        midi_min: Optional[int] = range_min
        midi_max: Optional[int] = range_max

        extra_sources = list(
            dict.fromkeys(list(state.candidate_notes) + list(state.note_map.keys()))
        )
        invalid: List[str] = []
        for name in extra_sources:
            midi = self._safe_parse(name)
            if midi is None:
                invalid.append(name)
                continue
            if midi_min is None or midi < midi_min:
                midi_min = midi
            if midi_max is None or midi > midi_max:
                midi_max = midi

        if midi_min is None or midi_max is None:
            return list(state.candidate_notes)

        candidates = self._generate_range_names(midi_min, midi_max)
        seen = set(candidates)
        for name in extra_sources:
            if name not in seen and name not in invalid:
                candidates.append(name)
                seen.add(name)
        for name in invalid:
            if name not in seen:
                candidates.append(name)
                seen.add(name)
        return candidates

    def _normalize_preferred_range(self, state: InstrumentLayoutState) -> None:
        options = self._candidate_note_names_for_state(state)
        if not options:
            if state.preferred_range_min or state.preferred_range_max:
                state.preferred_range_min = ""
                state.preferred_range_max = ""
                state.dirty = True
            return

        changed = False
        min_name = state.preferred_range_min or options[0]
        max_name = state.preferred_range_max or options[-1]

        if min_name not in options:
            min_name = options[0]
            changed = True
        if max_name not in options:
            max_name = options[-1]
            changed = True

        min_midi = self._safe_parse(min_name)
        max_midi = self._safe_parse(max_name)
        if min_midi is not None and max_midi is not None and min_midi > max_midi:
            min_name = options[0]
            max_name = options[-1]
            changed = True

        if state.preferred_range_min != min_name:
            state.preferred_range_min = min_name
            changed = True
        if state.preferred_range_max != max_name:
            state.preferred_range_max = max_name
            changed = True

        if changed:
            state.dirty = True

    # ------------------------------------------------------------------
    def note_patterns(self) -> Dict[str, List[int]]:
        state = self.state
        return {note: list(pattern) for note, pattern in state.note_map.items()}

    def candidate_note_names(self) -> List[str]:
        """Return ordered note names within the instrument's current range."""

        state = self.state
        self._normalize_preferred_range(state)
        return self._candidate_note_names_for_state(state)

    def set_candidate_range(self, minimum: str, maximum: str) -> None:
        state = self.state
        min_name = str(minimum).strip()
        max_name = str(maximum).strip()
        if not min_name or not max_name:
            raise ValueError("Candidate range requires both minimum and maximum notes")

        min_midi = self._safe_parse(min_name)
        max_midi = self._safe_parse(max_name)
        if min_midi is None or max_midi is None:
            raise ValueError("Candidate range notes must be valid pitch names")
        if min_midi > max_midi:
            raise ValueError("Candidate range minimum must be lower than maximum")

        canonical_min = pitch_midi_to_name(min_midi, flats=False)
        canonical_max = pitch_midi_to_name(max_midi, flats=False)

        invalid_names = [
            name
            for name in dict.fromkeys(
                list(state.candidate_notes) + list(state.note_map.keys())
            )
            if self._safe_parse(name) is None
        ]

        changed = False
        removed_notes: List[str] = []
        for name in list(state.note_map.keys()):
            midi = self._safe_parse(name)
            if midi is None:
                continue
            if midi < min_midi or midi > max_midi:
                del state.note_map[name]
                removed_notes.append(name)
                changed = True

        if removed_notes:
            filtered_order = [
                note for note in state.note_order if note not in removed_notes
            ]
            if len(filtered_order) != len(state.note_order):
                state.note_order = filtered_order
                changed = True
        generated = self._generate_range_names(min_midi, max_midi)
        seen = set(generated)
        for name in invalid_names:
            if name not in seen:
                generated.append(name)
                seen.add(name)

        hole_count = len(state.holes)
        windway_count = len(state.windways)
        total_count = hole_count + windway_count
        for name in generated:
            if name not in state.note_map:
                state.note_map[name] = [0] * total_count
                changed = True

        added_notes = [name for name in generated if name not in state.note_order]
        if added_notes:
            state.note_order.extend(added_notes)
            sort_note_order(state)
            changed = True

        if list(state.candidate_notes) != list(generated):
            state.candidate_notes = generated
            changed = True

        if state.candidate_range_min != canonical_min:
            state.candidate_range_min = canonical_min
            changed = True
        if state.candidate_range_max != canonical_max:
            state.candidate_range_max = canonical_max
            changed = True

        if not state.has_explicit_candidate_range:
            state.has_explicit_candidate_range = True
            changed = True

        if changed:
            state.dirty = True
            self._normalize_preferred_range(state)

    def set_preferred_range(self, minimum: str, maximum: str) -> None:
        state = self.state
        min_name = str(minimum).strip()
        max_name = str(maximum).strip()
        if not min_name or not max_name:
            raise ValueError("Preferred range requires both minimum and maximum notes")

        min_midi = self._safe_parse(min_name)
        max_midi = self._safe_parse(max_name)
        if min_midi is None or max_midi is None:
            raise ValueError("Preferred range notes must be valid pitch names")
        if min_midi > max_midi:
            raise ValueError("Preferred range minimum must be lower than maximum")

        options = self._candidate_note_names_for_state(state)
        if options and (min_name not in options or max_name not in options):
            raise ValueError("Preferred range notes must be within the instrument's range")

        if (
            state.preferred_range_min == min_name
            and state.preferred_range_max == max_name
        ):
            return

        state.preferred_range_min = min_name
        state.preferred_range_max = max_name
        state.dirty = True

    def initial_pattern_for_note(self, note: str) -> List[int]:
        """Return a starting fingering pattern for a newly added note."""

        state = self.state
        hole_count = len(state.holes)
        windway_count = len(state.windways)
        total_count = hole_count + windway_count
        normalized_note = str(note).strip()
        if not normalized_note:
            return [0] * total_count

        try:
            target_midi = parse_note_name(normalized_note)
        except ValueError:
            return [0] * total_count

        best_higher: Optional[Tuple[int, List[int]]] = None
        best_lower: Optional[Tuple[int, List[int]]] = None
        exact_match: Optional[List[int]] = None

        for existing, pattern in state.note_map.items():
            candidate = normalize_pattern(pattern, hole_count, windway_count)
            try:
                midi = parse_note_name(existing)
            except ValueError:
                continue

            difference = midi - target_midi
            if difference == 0:
                exact_match = candidate
                continue
            if difference > 0:
                if best_higher is None or difference < best_higher[0]:
                    best_higher = (difference, candidate)
            else:
                distance = -difference
                if best_lower is None or distance < best_lower[0]:
                    best_lower = (distance, candidate)

        if best_higher is not None:
            return list(best_higher[1])
        if best_lower is not None:
            return list(best_lower[1])
        if exact_match is not None:
            return list(exact_match)
        return [0] * total_count

    def set_note_pattern(self, note: str, pattern: Iterable[int]) -> None:
        state = self.state
        normalized_note = str(note).strip()
        if not normalized_note:
            raise ValueError("Note name cannot be empty")

        is_new_note = normalized_note not in state.note_map
        midi_value = self._safe_parse(normalized_note)
        if is_new_note and midi_value is not None:
            min_midi = self._safe_parse(state.candidate_range_min)
            max_midi = self._safe_parse(state.candidate_range_max)
            if min_midi is not None and midi_value < min_midi:
                raise ValueError("Note is below the instrument's available range")
            if max_midi is not None and midi_value > max_midi:
                raise ValueError("Note is above the instrument's available range")

        normalized_pattern = normalize_pattern(
            pattern,
            len(state.holes),
            len(state.windways),
        )
        current = state.note_map.get(normalized_note)
        if current == normalized_pattern:
            return

        state.note_map[normalized_note] = normalized_pattern
        ensure_candidate_name(state, normalized_note)
        if normalized_note not in state.note_order:
            state.note_order.append(normalized_note)
        sort_note_order(state)
        self._normalize_preferred_range(state)
        state.dirty = True

    def remove_note(self, note: str) -> None:
        state = self.state
        normalized_note = str(note).strip()
        if not normalized_note:
            raise ValueError("Note name cannot be empty")

        removed = False
        if normalized_note in state.note_map:
            del state.note_map[normalized_note]
            removed = True

        try:
            state.note_order.remove(normalized_note)
            removed = True
        except ValueError:
            pass

        if not removed:
            raise ValueError(f"Note '{normalized_note}' does not exist")

        sort_note_order(state)
        self._normalize_preferred_range(state)
        state.dirty = True

