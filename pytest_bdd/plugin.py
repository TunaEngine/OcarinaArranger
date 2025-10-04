"""Lightweight pytest-bdd shim plugin.

When the optional dependency is available we delegate to the genuine plugin so
contributors keep the full behaviour. Otherwise we register the marker pytest
expects and remain inert.
"""

from __future__ import annotations

from ._shim import load_real_module

_REAL_PLUGIN = load_real_module(__name__)

if _REAL_PLUGIN is not None:
    for name in dir(_REAL_PLUGIN):
        if name.startswith("__"):
            continue
        globals()[name] = getattr(_REAL_PLUGIN, name)

else:

    def pytest_configure(config):  # pragma: no cover - trivial registration
        """Register a ``bdd`` marker so pytest does not warn about it."""

        config.addinivalue_line(
            "markers",
            "bdd: marks tests that rely on pytest-bdd; provided by optional shim",
        )

    __all__ = ("pytest_configure",)

