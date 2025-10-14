from __future__ import annotations

from types import SimpleNamespace

from ocarina_tools.parts import MusicXmlPartInfo
from shared.melody_part import select_melody_candidate

from ui.main_window.preview.commands import PreviewCommandsMixin


class _FakeViewModel:
    def __init__(
        self,
        *,
        parts: tuple[MusicXmlPartInfo, ...],
        selected: tuple[str, ...],
        dialog_result: tuple[str, ...] | None,
    ) -> None:
        self.state = SimpleNamespace(
            input_path="/tmp/example.musicxml",
            available_parts=parts,
            selected_part_ids=selected,
        )
        self._parts = parts
        self._dialog_result = dialog_result
        self.ask_calls: list[tuple[tuple[MusicXmlPartInfo, ...], tuple[str, ...]]] = []
        self.apply_calls: list[tuple[str, ...]] = []
        self.load_calls = 0

    def load_part_metadata(self) -> tuple[MusicXmlPartInfo, ...]:
        self.load_calls += 1
        self.state.available_parts = self._parts
        return self._parts

    def ask_select_parts(
        self, parts: tuple[MusicXmlPartInfo, ...], preselected: tuple[str, ...]
    ) -> tuple[str, ...] | None:
        self.ask_calls.append((parts, preselected))
        return self._dialog_result

    def apply_part_selection(self, part_ids: tuple[str, ...]) -> tuple[str, ...]:
        self.apply_calls.append(part_ids)
        self.state.selected_part_ids = part_ids
        return part_ids


class _PreviewHarness(PreviewCommandsMixin):
    def __init__(self, viewmodel: _FakeViewModel) -> None:
        self._viewmodel = viewmodel
        self.selected_tab: str | None = None
        self.render_calls = 0

    def _require_input_path(self, error_message: str) -> str:
        return self._viewmodel.state.input_path

    def _select_preview_tab(self, tab: str) -> None:
        self.selected_tab = tab

    def render_previews(self):  # type: ignore[override]
        self.render_calls += 1


def _make_part(part_id: str, name: str) -> MusicXmlPartInfo:
    return MusicXmlPartInfo(part_id, name, None, 0, None, None, None, None)


def test_reimport_prompts_for_part_selection_again() -> None:
    parts = (_make_part("P1", "Flute"), _make_part("P2", "Oboe"))
    viewmodel = _FakeViewModel(parts=parts, selected=("P1",), dialog_result=("P2",))
    harness = _PreviewHarness(viewmodel)

    initial_selection = viewmodel.state.selected_part_ids
    harness.reimport_and_arrange()

    assert viewmodel.ask_calls == [(parts, initial_selection)]
    assert viewmodel.apply_calls[-1] == ("P2",)
    assert viewmodel.state.selected_part_ids == ("P2",)
    assert harness.selected_tab == "arranged"
    assert harness.render_calls == 1


def test_reimport_loads_parts_when_none_cached() -> None:
    parts = (_make_part("P1", "Flute"), _make_part("P2", "Oboe"))
    viewmodel = _FakeViewModel(parts=parts, selected=(), dialog_result=("P2",))
    viewmodel.state.available_parts = ()
    harness = _PreviewHarness(viewmodel)

    harness.reimport_and_arrange()

    assert viewmodel.load_calls == 1
    expected_default = select_melody_candidate(parts) or parts[0].part_id
    assert viewmodel.ask_calls == [(parts, (expected_default,))]
    assert viewmodel.apply_calls[-1] == ("P2",)


def test_reimport_cancel_skips_apply_and_render() -> None:
    parts = (_make_part("P1", "Flute"), _make_part("P2", "Oboe"))
    viewmodel = _FakeViewModel(parts=parts, selected=("P1",), dialog_result=None)
    harness = _PreviewHarness(viewmodel)

    initial_selection = viewmodel.state.selected_part_ids
    harness.reimport_and_arrange()

    assert viewmodel.ask_calls == [(parts, initial_selection)]
    assert viewmodel.apply_calls == []
    assert harness.selected_tab is None
    assert harness.render_calls == 0
