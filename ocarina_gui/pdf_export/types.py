"""Common type declarations for the PDF exporter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


DEFAULT_COLUMNS = {
    ("A4", "portrait"): 4,
    ("A4", "landscape"): 4,
    ("A6", "portrait"): 2,
    ("A6", "landscape"): 4,
}


@dataclass(frozen=True)
class PdfExportOptions:
    """Normalized options describing how to render an arranged PDF."""

    page_size: str
    orientation: str
    columns: Optional[int] = None
    include_piano_roll: bool = True
    include_staff: bool = True
    include_text: bool = False
    include_fingerings: bool = True

    def __post_init__(self) -> None:  # type: ignore[override]
        size = self.page_size.strip().upper()
        orientation = self.orientation.strip().lower()
        object.__setattr__(self, "page_size", size)
        object.__setattr__(self, "orientation", orientation)

        default = self.default_columns_for(size, orientation)
        if self.columns is None:
            columns = default
        else:
            columns = int(self.columns)
            if columns <= 0:
                raise ValueError("PDF fingering columns must be greater than zero")
        object.__setattr__(self, "columns", columns)
        object.__setattr__(self, "include_piano_roll", bool(self.include_piano_roll))
        object.__setattr__(self, "include_staff", bool(self.include_staff))
        object.__setattr__(self, "include_text", bool(self.include_text))
        object.__setattr__(self, "include_fingerings", bool(self.include_fingerings))

    def normalized_size(self) -> str:
        return self.page_size

    def normalized_orientation(self) -> str:
        return self.orientation

    def normalized_columns(self) -> int:
        return self.columns

    def label(self) -> str:
        orient = self.normalized_orientation()
        return f"{self.normalized_size()} {orient.capitalize()}"

    def filename_suffix(self) -> str:
        return f"{self.normalized_size()}-{self.normalized_orientation()}"

    @classmethod
    def with_defaults(
        cls,
        page_size: str = "A4",
        orientation: str = "portrait",
        *,
        include_piano_roll: bool = True,
        include_staff: bool = True,
        include_text: bool = False,
        include_fingerings: bool = True,
    ) -> "PdfExportOptions":
        return cls(
            page_size=page_size,
            orientation=orientation,
            include_piano_roll=include_piano_roll,
            include_staff=include_staff,
            include_text=include_text,
            include_fingerings=include_fingerings,
        )

    @staticmethod
    def default_columns_for(page_size: str, orientation: str) -> int:
        size = page_size.strip().upper()
        orient = orientation.strip().lower()
        default = DEFAULT_COLUMNS.get((size, orient))
        if default is not None:
            return default
        return 2 if size == "A6" else 4


from ocarina_tools import NoteEvent

__all__ = ["DEFAULT_COLUMNS", "NoteEvent", "PdfExportOptions"]
