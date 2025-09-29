from __future__ import annotations

from pathlib import Path
from xml.etree.ElementTree import ElementTree


def write_score(tmp_path: Path, tree: ElementTree, *, name: str = "sample.musicxml") -> Path:
    path = tmp_path / name
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path
