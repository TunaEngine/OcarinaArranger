from __future__ import annotations

from ..input_reset import PreviewInputResetMixin
from .loop import PreviewLoopHandlersMixin
from .playback import PreviewPlaybackHandlersMixin
from .tempo import PreviewTempoHandlersMixin
from .volume import PreviewVolumeHandlersMixin


class PreviewInputHandlersMixin(
    PreviewInputResetMixin,
    PreviewPlaybackHandlersMixin,
    PreviewTempoHandlersMixin,
    PreviewLoopHandlersMixin,
    PreviewVolumeHandlersMixin,
):
    """Tkinter callbacks that respond to preview UI input."""


__all__ = ["PreviewInputHandlersMixin"]
