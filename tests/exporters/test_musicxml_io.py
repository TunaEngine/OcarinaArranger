from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile

from ocarina_tools import analyze_key, export_mxl, load_score

from ..helpers import make_chord_score, make_linear_score


def test_export_mxl_and_load_score_roundtrip(tmp_path):
    tree, _ = make_chord_score()
    out_path = tmp_path / "score.mxl"
    export_mxl(tree, out_path)
    with zipfile.ZipFile(out_path) as archive:
        assert "score.xml" in archive.namelist()
        payload = archive.read("score.xml")
        assert b"<score-partwise" in payload
    tree2, root2 = load_score(str(out_path))
    assert len(root2.findall("part")) == 2
    assert analyze_key(root2)["tonic"] == "D"


def test_load_score_reads_zipped_musicxml(tmp_path):
    tree, _ = make_linear_score()
    xml_payload = ET.tostring(tree.getroot(), encoding="utf-8", xml_declaration=True)
    zipped_path = tmp_path / "compressed.musicxml"

    with zipfile.ZipFile(zipped_path, "w") as archive:
        archive.writestr("score.musicxml", xml_payload)

    loaded_tree, loaded_root = load_score(str(zipped_path))

    assert loaded_tree.getroot() is loaded_root
    assert loaded_root.tag.endswith("score-partwise")
    assert loaded_root.find("part") is not None


def test_load_score_reads_mxl_zip_double_extension(tmp_path):
    tree, _ = make_linear_score()
    xml_payload = ET.tostring(tree.getroot(), encoding="utf-8", xml_declaration=True)
    zipped_path = tmp_path / "score.mxl.zip"

    with zipfile.ZipFile(zipped_path, "w") as archive:
        archive.writestr("score.xml", xml_payload)

    loaded_tree, loaded_root = load_score(str(zipped_path))

    assert loaded_tree.getroot() is loaded_root
    assert loaded_root.tag.endswith("score-partwise")
    assert loaded_root.find("part") is not None
