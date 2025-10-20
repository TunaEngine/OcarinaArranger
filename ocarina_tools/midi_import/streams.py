"""Byte stream helpers shared by MIDI decoders."""
from __future__ import annotations


class SafeStream:
    """Utility to read bytes with bound checks and a stateful cursor."""

    __slots__ = ("_data", "_length", "_position")

    def __init__(self, data: bytes):
        self._data = memoryview(data)
        self._length = len(self._data)
        self._position = 0

    @property
    def remaining(self) -> int:
        return self._length - self._position

    def tell(self) -> int:
        return self._position

    def read_exact(self, size: int) -> bytes:
        if size < 0:
            raise ValueError("Size must be non-negative.")
        if self.remaining < size:
            raise ValueError("Unexpected end of MIDI track data.")
        start = self._position
        self._position += size
        return bytes(self._data[start : start + size])

    def read_up_to(self, size: int) -> bytes:
        if size < 0:
            raise ValueError("Size must be non-negative.")
        available = min(size, self.remaining)
        start = self._position
        self._position += available
        return bytes(self._data[start : start + available])

    def read_byte(self) -> int:
        return self.read_exact(1)[0]

    def peek_byte(self) -> int:
        if self.remaining <= 0:
            raise ValueError("Unexpected end of MIDI track data.")
        return self._data[self._position]

    def skip(self, size: int) -> None:
        self.read_exact(size)

    def read_varlen(self, *, allow_partial: bool = False, max_bytes: int = 4) -> int:
        value = 0
        consumed = 0
        while True:
            if self.remaining <= 0:
                if allow_partial and consumed:
                    return value
                raise ValueError("Malformed variable-length quantity in MIDI track.")
            byte = self.read_byte()
            value = (value << 7) | (byte & 0x7F)
            consumed += 1
            if byte & 0x80 == 0:
                return value
            if max_bytes and consumed >= max_bytes:
                if allow_partial:
                    return value
                raise ValueError("Variable-length quantity exceeds maximum length.")

    def consume_all(self) -> None:
        self._position = self._length


__all__ = ["SafeStream"]
