from __future__ import annotations

from .commands import PreviewCommandsMixin
from .handlers import PreviewInputHandlersMixin
from .loop_controls import PreviewLoopControlsMixin
from .playback import PreviewPlaybackControlMixin
from .registration import PreviewRegistrationMixin
from .layout import PreviewLayoutMixin
from .rendering import PreviewRenderingMixin
from .transpose import PreviewTransposeMixin
from .utilities import PreviewUtilitiesMixin


class PreviewPlaybackMixin(
    PreviewCommandsMixin,
    PreviewInputHandlersMixin,
    PreviewLoopControlsMixin,
    PreviewTransposeMixin,
    PreviewRegistrationMixin,
    PreviewRenderingMixin,
    PreviewPlaybackControlMixin,
    PreviewUtilitiesMixin,
    PreviewLayoutMixin,
):
    """Preview rendering and playback helpers for :class:`MainWindow`."""


__all__ = ["PreviewPlaybackMixin"]
