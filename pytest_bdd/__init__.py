from __future__ import annotations

from typing import Any, Callable, TypeVar

import pytest

from ._shim import load_real_module

F = TypeVar("F", bound=Callable[..., object])

_REAL_PYTEST_BDD = load_real_module(__name__)

if _REAL_PYTEST_BDD is not None:
    # Mirror the real module's public surface so contributors with
    # ``pytest-bdd`` installed retain full functionality.
    __doc__ = getattr(_REAL_PYTEST_BDD, "__doc__")
    __all__ = getattr(_REAL_PYTEST_BDD, "__all__", None)
    __path__ = getattr(_REAL_PYTEST_BDD, "__path__", [])
    __spec__ = getattr(_REAL_PYTEST_BDD, "__spec__", None)

    for name in dir(_REAL_PYTEST_BDD):
        if name.startswith("__") and name not in {"__getattr__", "__all__"}:
            continue
        globals()[name] = getattr(_REAL_PYTEST_BDD, name)

    def __getattr__(name: str) -> Any:  # pragma: no cover - thin delegation
        return getattr(_REAL_PYTEST_BDD, name)

else:

    def _identity_decorator(*_args: Any, **_kwargs: Any) -> Callable[[F], F]:
        def _decorator(func: F) -> F:
            return func

        return _decorator

    given = _identity_decorator
    when = _identity_decorator
    then = _identity_decorator

    class _Parsers:
        @staticmethod
        def parse(pattern: str) -> str:
            return pattern

        @staticmethod
        def re(pattern: str) -> str:
            return pattern

    parsers = _Parsers()

    def scenarios(*_args: Any, **_kwargs: Any) -> None:
        pytest.skip(
            "pytest-bdd scenarios require the optional dependency",
            allow_module_level=True,
        )

    __all__ = tuple(sorted({"given", "when", "then", "parsers", "scenarios"}))

