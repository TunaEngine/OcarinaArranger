"""Compatibility layer re-exporting headless widget stand-ins."""

from .widgets_base import (
    HeadlessButton,
    HeadlessCheckbutton,
    HeadlessCombobox,
    HeadlessFrame,
    HeadlessLabel,
    HeadlessNotebook,
    HeadlessProgressbar,
    HeadlessRadiobutton,
    HeadlessScale,
    HeadlessSpinbox,
    _HeadlessContainer,
    _HeadlessStateful,
    _HeadlessWidget,
)
from .widgets_tree import HeadlessTreeview

__all__ = [
    "_HeadlessWidget",
    "_HeadlessContainer",
    "_HeadlessStateful",
    "HeadlessButton",
    "HeadlessSpinbox",
    "HeadlessCheckbutton",
    "HeadlessScale",
    "HeadlessLabel",
    "HeadlessRadiobutton",
    "HeadlessCombobox",
    "HeadlessProgressbar",
    "HeadlessNotebook",
    "HeadlessFrame",
    "HeadlessTreeview",
]
