from __future__ import annotations

from importlib import resources
from importlib.abc import Traversable

MAIN_WINDOW_RESOURCE_PACKAGE = "ui.main_window.resources"


def get_main_window_resource(resource_name: str) -> Traversable | None:
    """Return a traversable handle for a bundled main-window resource."""

    try:
        resource = resources.files(MAIN_WINDOW_RESOURCE_PACKAGE).joinpath(resource_name)
    except (FileNotFoundError, ModuleNotFoundError):
        return None

    is_file = getattr(resource, "is_file", None)
    if callable(is_file) and is_file():
        return resource
    return None


__all__ = ["MAIN_WINDOW_RESOURCE_PACKAGE", "get_main_window_resource"]
