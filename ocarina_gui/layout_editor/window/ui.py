"""UI construction helpers for the instrument layout editor window."""

from __future__ import annotations

from .ui_footer import _LayoutEditorFooterMixin
from .ui_header import _LayoutEditorHeaderMixin
from .ui_selection import _LayoutEditorSelectionMixin

__all__ = ["_LayoutEditorUIMixin"]


class _LayoutEditorUIMixin(
    _LayoutEditorHeaderMixin,
    _LayoutEditorSelectionMixin,
    _LayoutEditorFooterMixin,
):
    """Composite mixin bundling the layout editor UI building helpers."""

    pass
