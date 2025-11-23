"""Shared helpers for rendering consistent PDF headers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from services.update.constants import GITHUB_REPO

from .layouts import PdfLayout
from .writer import PageBuilder


HEADER_FONT = "F1"
_HEADER_GAP_MULTIPLIER = 0.5
_LINK_COLOR = (0.0, 0.2, 0.8)


@dataclass(frozen=True)
class HeaderLine:
    """Represents a logical line within the document header."""

    text: str
    font: str = HEADER_FONT
    link: str | None = None
    color_rgb: Tuple[float, float, float] | None = None


def build_header_lines(title: str | None = None) -> Tuple[HeaderLine, ...]:
    """Create the header lines to render on the first page."""

    account, app = _split_github_repo(GITHUB_REPO)
    link_label = f"{account} {app}".strip() or GITHUB_REPO

    lines: List[HeaderLine] = []
    title = title.strip() if title else ""
    if title:
        lines.append(HeaderLine(text=title))

    link_url = f"https://github.com/{GITHUB_REPO}"
    lines.append(
        HeaderLine(
            text=link_label,
            link=link_url,
            color_rgb=_LINK_COLOR,
        )
    )
    return tuple(lines)


def draw_document_header(
    page: PageBuilder, layout: PdfLayout, header_lines: Sequence[HeaderLine]
) -> float:
    """Render the common document header and return its height."""

    if not header_lines:
        return 0.0

    y = layout.margin_top
    for line in header_lines:
        color = line.color_rgb
        page.draw_text(
            layout.margin_left,
            y,
            line.text,
            font=line.font,
            fill_rgb=color,
        )
        if line.link:
            width = page.estimate_text_width(line.text, font=line.font)
            page.add_link_annotation(
                layout.margin_left,
                y,
                width,
                layout.line_height,
                line.link,
            )
        y += layout.line_height
    return header_height(layout, header_lines)


def header_height(layout: PdfLayout, header_lines: Sequence[HeaderLine]) -> float:
    """Calculate the rendered height of the header block."""

    return len(header_lines) * layout.line_height if header_lines else 0.0


def header_gap(layout: PdfLayout, header_lines: Sequence[HeaderLine]) -> float:
    """Return the vertical gap inserted after the header block."""

    return layout.line_height * _HEADER_GAP_MULTIPLIER if header_lines else 0.0


def _split_github_repo(repo: str) -> Tuple[str, str]:
    if "/" not in repo:
        return repo, ""
    account, app = repo.split("/", 1)
    return account.strip(), app.strip()


__all__ = [
    "HEADER_FONT",
    "HeaderLine",
    "build_header_lines",
    "draw_document_header",
    "header_gap",
    "header_height",
]

