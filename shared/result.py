"""Simple result helpers shared across layers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Optional, TypeVar


T = TypeVar("T")
E = TypeVar("E")


@dataclass(slots=True)
class Result(Generic[T, E]):
    """Discriminated union capturing either a success value or an error."""

    value: Optional[T] = None
    error: Optional[E] = None

    @classmethod
    def ok(cls, value: T) -> "Result[T, E]":
        return cls(value=value)

    @classmethod
    def err(cls, error: E) -> "Result[T, E]":
        return cls(error=error)

    def is_ok(self) -> bool:
        return self.error is None

    def is_err(self) -> bool:
        return self.error is not None

    def unwrap(self) -> T:
        if self.error is not None:
            raise RuntimeError(f"Tried to unwrap error result: {self.error}")
        assert self.value is not None
        return self.value


__all__ = ["Result"]
