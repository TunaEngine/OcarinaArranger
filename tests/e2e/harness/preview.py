from __future__ import annotations

from ocarina_gui.preview import PreviewData
from ocarina_tools import NoteEvent

def default_preview_data() -> PreviewData:
    return PreviewData(
        original_events=[NoteEvent(0, 480, 60, 1)],
        arranged_events=[NoteEvent(0, 480, 72, 1)],
        pulses_per_quarter=480,
        beats=4,
        beat_type=4,
        original_range=(60, 60),
        arranged_range=(72, 72),
        tempo_bpm=96,
    )


__all__ = ["default_preview_data"]
