from __future__ import annotations

import math

from ui.main_window.fingering.columns import FingeringColumnLayoutMixin


class _FakeTreeview:
    def __init__(self, widths: dict[str, int], xview_first: float) -> None:
        self._widths = widths
        self._xview = (xview_first, min(xview_first + 0.25, 1.0))

    def column(self, column_id: str, option: str):  # pragma: no cover - passthrough
        assert option == "width"
        return self._widths[column_id]

    def xview(self):  # pragma: no cover - passthrough
        return self._xview


class _MixinUnderTest(FingeringColumnLayoutMixin):
    fingering_table = None
    _fingering_display_columns = ()


class TestFingeringColumnLayoutMixin:
    def test_column_position_accounts_for_horizontal_scroll(self) -> None:
        table = _FakeTreeview({"note": 60, "hole_1": 100, "hole_2": 100}, 0.5)
        mixin = _MixinUnderTest()
        display = ("note", "hole_1", "hole_2")

        left_edge = mixin._column_left_edge(display, "hole_2", table)

        assert math.isclose(left_edge, 30.0)

        should_insert_after = mixin._should_insert_after(85, "hole_2", display, table)
        should_insert_before = mixin._should_insert_after(70, "hole_2", display, table)

        assert should_insert_after is True
        assert should_insert_before is False
