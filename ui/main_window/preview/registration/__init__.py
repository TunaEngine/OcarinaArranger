from __future__ import annotations

from .progress import PreviewProgressMixin
from .settings import PreviewSettingsMixin
from .tabs import PreviewTabManagementMixin
from .widgets import PreviewWidgetRegistrationMixin


class PreviewRegistrationMixin(
    PreviewWidgetRegistrationMixin,
    PreviewTabManagementMixin,
    PreviewSettingsMixin,
    PreviewProgressMixin,
):
    """Composite mixin for preview widget registration and state sync."""


__all__ = ["PreviewRegistrationMixin"]
