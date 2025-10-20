"""File loading utilities for plain MusicXML, zipped MXL, and MIDI files."""
from __future__ import annotations

from dataclasses import dataclass
import re
import zipfile
import xml.etree.ElementTree as ET

from .midi_import import read_midi
from .midi_import.models import MidiImportReport


@dataclass(frozen=True)
class ScoreLoadResult:
    """Container exposing the parsed tree, root, and MIDI import report."""

    tree: ET.ElementTree
    root: ET.Element
    midi_report: MidiImportReport | None = None

    def __iter__(self):  # type: ignore[override]
        yield self.tree
        yield self.root


def load_score(path: str, *, midi_mode: str = "auto") -> ScoreLoadResult:
    lower = path.lower()
    is_zip = zipfile.is_zipfile(path)
    expects_mxl_archive = lower.endswith((".mxl", ".mxl.zip"))
    if expects_mxl_archive or (is_zip and lower.endswith((".xml", ".musicxml"))):
        with zipfile.ZipFile(path, "r") as archive:
            candidate: str | None = None
            if "score.xml" in archive.namelist():
                candidate = "score.xml"
            else:
                try:
                    with archive.open("META-INF/container.xml") as handle:
                        data = handle.read().decode("utf-8", errors="ignore")
                    match = re.search(r"full-path=\"([^\"]+)\"", data)
                    if match and match.group(1) in archive.namelist():
                        candidate = match.group(1)
                except KeyError:
                    pass
            if not candidate:
                for name in archive.namelist():
                    if name.lower().endswith((".xml", ".musicxml")):
                        candidate = name
                        break
            if not candidate:
                raise ValueError("No XML found inside MXL.")
            with archive.open(candidate) as handle:
                data = handle.read()
        tree = ET.ElementTree(ET.fromstring(data))
        root = tree.getroot()
        return ScoreLoadResult(tree=tree, root=root, midi_report=None)
    if lower.endswith((".mid", ".midi")):
        song, report = read_midi(path, mode=midi_mode)
        return ScoreLoadResult(tree=song.tree, root=song.root, midi_report=report)
    tree = ET.parse(path)
    root = tree.getroot()
    return ScoreLoadResult(tree=tree, root=root, midi_report=None)


__all__ = ["ScoreLoadResult", "load_score"]

