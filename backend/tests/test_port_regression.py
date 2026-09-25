"""The port must write the same document as the original builder, track for track,
apart from two deliberate fixes, both found by the Word vs LibreOffice parity test:
the table grid carries the real column widths, and the document ends with a 1pt
paragraph so Word never adds a blank page 2 after the table.

Runs the original build_resume.py from the git-ignored reference/ copy (never from
TARGET) against the copied data, then builds the same track with the new engine from
the v2 -> v3 conversion, and compares the document XML and its relationships.
"""
import importlib.util
import re
import zipfile

import pytest

from resume_engine.builder import L_CELL_W, R_CELL_W, build
from resume_engine.schema import BuildOptions

from .conftest import requires_reference

TRACKS = ["A", "B", "C", "D"]
GRID_COL = re.compile(r'<w:gridCol w:w="(\d+)"/>')


TAIL = re.compile(r"</w:tbl>(<w:p>.*?</w:p>)<w:sectPr")


def _without_grid(xml):
    """Normalise the two deliberate fixes away, leaving everything else to compare."""
    xml = TAIL.sub("</w:tbl><w:sectPr", xml)
    return GRID_COL.sub('<w:gridCol w:w="*"/>', xml)


def _load_original(reference_dir):
    spec = importlib.util.spec_from_file_location(
        "original_build_resume", reference_dir / "templates" / "build_resume.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _parts(path):
    with zipfile.ZipFile(path) as z:
        return (z.read("word/document.xml").decode("utf-8"),
                z.read("word/_rels/document.xml.rels").decode("utf-8"))


@requires_reference
@pytest.mark.parametrize("track", TRACKS)
def test_same_document_as_original(track, reference_dir, v2_data, reference_resume, tmp_path):
    original = _load_original(reference_dir)
    old_path = tmp_path / "old.docx"
    new_path = tmp_path / "new.docx"
    original.build(v2_data, track, str(old_path))
    result = build(reference_resume, BuildOptions(track=track), str(new_path))

    old_xml, old_rels = _parts(old_path)
    new_xml, new_rels = _parts(new_path)
    assert _without_grid(new_xml) == _without_grid(old_xml)
    # The fix: grid columns equal the cell widths (in twips), not two equal halves.
    assert GRID_COL.findall(new_xml) == [str(int(L_CELL_W * 20)), str(int(R_CELL_W * 20))]
    # The fix: a 1pt tail paragraph (exact 1pt line, 1pt paragraph mark) after the table.
    tail = TAIL.search(new_xml).group(1)
    assert 'w:lineRule="exact"' in tail and 'w:line="20"' in tail and '<w:sz w:val="2"/>' in tail
    # Relationship order is not guaranteed; compare the set of relationships.
    rel = re.compile(r"<Relationship [^>]+/>")
    assert sorted(rel.findall(new_rels)) == sorted(rel.findall(old_rels))
    assert result.scale == v2_data["scale"][track]


@requires_reference
def test_tailoring_matches_original(reference_dir, v2_data, reference_resume, tmp_path):
    """Original --projects/--drop flags map onto left_sections and drop."""
    from resume_engine.schema import LeftSection

    original = _load_original(reference_dir)
    old_path, new_path = tmp_path / "old.docx", tmp_path / "new.docx"
    original.build(v2_data, "C", str(old_path), only_projects=["stationwatch", "newsletter_ai"],
                   drop={"R4"})
    opts = BuildOptions(track="C", drop={"R4"},
                        left_sections=[LeftSection(heading="Projects",
                                                   item_ids=["stationwatch", "newsletter_ai"])])
    result = build(reference_resume, opts, str(new_path))
    assert _without_grid(_parts(new_path)[0]) == _without_grid(_parts(old_path)[0])
    assert "R4" not in result.entry_ids
    assert result.item_ids == ["stationwatch", "newsletter_ai"]
