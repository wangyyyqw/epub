# -*- coding: utf-8 -*-
"""Unit tests for merge_epub module."""

import os
import sys
import tempfile
import zipfile
import pytest

# Ensure the backend-py directory is in the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from plugins.epub_tool.utils.merge_epub import (
    _find_opf_path,
    _parse_opf,
    _detect_conflicts,
    _update_references_in_content,
    _update_references_in_css,
    run,
)


def _make_minimal_epub(path, title="Test Book", version="3.0", chapters=None, extra_files=None):
    """Create a minimal valid EPUB file for testing.

    Args:
        path: output file path
        title: book title
        version: EPUB version ("2.0" or "3.0")
        chapters: list of (filename, content) tuples for XHTML chapters
        extra_files: list of (bookpath, bytes) for additional files
    """
    if chapters is None:
        chapters = [("OEBPS/ch01.xhtml", "<html><body><h1>Chapter 1</h1></body></html>")]

    opf_dir = "OEBPS"
    opf_path = f"{opf_dir}/content.opf"

    manifest_items = []
    spine_items = []
    for i, (fname, _content) in enumerate(chapters):
        item_id = f"ch{i+1:02d}"
        href = os.path.basename(fname)
        manifest_items.append(f'    <item id="{item_id}" href="{href}" media-type="application/xhtml+xml"/>')
        spine_items.append(f'    <itemref idref="{item_id}"/>')

    # Add nav for EPUB3
    if version == "3.0":
        manifest_items.append('    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>')

    manifest_str = "\n".join(manifest_items)
    spine_str = "\n".join(spine_items)

    opf_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="{version}" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">test-{title}</dc:identifier>
    <dc:title>{title}</dc:title>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
{manifest_str}
  </manifest>
  <spine>
{spine_str}
  </spine>
</package>"""

    container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

    nav_content = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>TOC</title></head>
<body>
<nav epub:type="toc" id="toc">
  <h1>Table of Contents</h1>
  <ol>
"""
    for i, (fname, _) in enumerate(chapters):
        href = os.path.basename(fname)
        nav_content += f'    <li><a href="{href}">Chapter {i+1}</a></li>\n'
    nav_content += """  </ol>
</nav>
</body>
</html>"""

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr(opf_path, opf_content)
        if version == "3.0":
            zf.writestr(f"{opf_dir}/nav.xhtml", nav_content)
        for fname, content in chapters:
            zf.writestr(fname, content)
        if extra_files:
            for bp, data in extra_files:
                zf.writestr(bp, data)


class TestFindOpfPath:
    def test_finds_opf_from_container(self):
        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
            path = f.name
        try:
            _make_minimal_epub(path)
            with zipfile.ZipFile(path) as zf:
                opf = _find_opf_path(zf)
                assert opf == "OEBPS/content.opf"
        finally:
            os.unlink(path)


class TestParseOpf:
    def test_parses_manifest_and_spine(self):
        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
            path = f.name
        try:
            chapters = [
                ("OEBPS/ch01.xhtml", "<html><body>Ch1</body></html>"),
                ("OEBPS/ch02.xhtml", "<html><body>Ch2</body></html>"),
            ]
            _make_minimal_epub(path, chapters=chapters)
            with zipfile.ZipFile(path) as zf:
                version, meta, manifest, spine, opf_dir, toc_id = _parse_opf(zf, "OEBPS/content.opf")
                assert version == "3.0"
                assert "ch01" in manifest
                assert "ch02" in manifest
                assert len(spine) == 2
                assert opf_dir == "OEBPS"
        finally:
            os.unlink(path)


class TestDetectConflicts:
    def test_no_conflicts(self):
        sets = [{"OEBPS/a.xhtml"}, {"OEBPS/b.xhtml"}]
        maps = _detect_conflicts(sets)
        assert maps[0] == {}
        assert maps[1] == {}

    def test_conflict_adds_prefix(self):
        sets = [{"OEBPS/ch01.xhtml", "OEBPS/style.css"},
                {"OEBPS/ch01.xhtml", "OEBPS/img.png"}]
        maps = _detect_conflicts(sets)
        assert maps[0] == {}
        assert "OEBPS/ch01.xhtml" in maps[1]
        assert maps[1]["OEBPS/ch01.xhtml"] == "OEBPS/vol2_ch01.xhtml"

    def test_three_way_conflict(self):
        sets = [{"a.css"}, {"a.css"}, {"a.css"}]
        maps = _detect_conflicts(sets)
        assert maps[0] == {}
        assert maps[1]["a.css"] == "vol2_a.css"
        assert maps[2]["a.css"] == "vol3_a.css"


class TestUpdateReferences:
    def test_updates_href_in_xhtml(self):
        content = b'<html><body><a href="style.css">link</a><img src="img.png"/></body></html>'
        rename_map = {"OEBPS/style.css": "OEBPS/vol2_style.css"}
        result = _update_references_in_content(content, rename_map, "OEBPS/ch01.xhtml")
        assert b"vol2_style.css" in result

    def test_updates_url_in_css(self):
        css = b'body { background: url("img.png"); }'
        rename_map = {"OEBPS/img.png": "OEBPS/vol2_img.png"}
        result = _update_references_in_css(css, rename_map, "OEBPS/style.css")
        assert b"vol2_img.png" in result

    def test_no_change_when_no_conflict(self):
        content = b'<html><body><a href="other.css">link</a></body></html>'
        rename_map = {"OEBPS/style.css": "OEBPS/vol2_style.css"}
        result = _update_references_in_content(content, rename_map, "OEBPS/ch01.xhtml")
        assert result == content


class TestMergeRun:
    def test_merge_two_epubs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            epub1 = os.path.join(tmpdir, "book1.epub")
            epub2 = os.path.join(tmpdir, "book2.epub")
            outdir = os.path.join(tmpdir, "output")
            os.makedirs(outdir)

            _make_minimal_epub(epub1, title="Book One", chapters=[
                ("OEBPS/ch01.xhtml", "<html><body><h1>Book1 Ch1</h1></body></html>"),
            ])
            _make_minimal_epub(epub2, title="Book Two", chapters=[
                ("OEBPS/ch01.xhtml", "<html><body><h1>Book2 Ch1</h1></body></html>"),
            ])

            result = run([epub1, epub2], outdir)
            assert result == 0

            output_file = os.path.join(outdir, "merged_book1.epub")
            assert os.path.exists(output_file)

            # Verify it's a valid EPUB
            with zipfile.ZipFile(output_file) as zf:
                names = zf.namelist()
                assert "mimetype" in names
                assert "META-INF/container.xml" in names
                # Should have OPF
                opf_files = [n for n in names if n.endswith(".opf")]
                assert len(opf_files) == 1

    def test_merge_less_than_two_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            epub1 = os.path.join(tmpdir, "book1.epub")
            _make_minimal_epub(epub1)
            result = run([epub1], tmpdir)
            assert result == 1

    def test_merge_nonexistent_file_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run(["/nonexistent/file.epub", "/another/file.epub"], tmpdir)
            assert result == 1

    def test_merge_mixed_versions_outputs_epub3(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            epub2 = os.path.join(tmpdir, "v2.epub")
            epub3 = os.path.join(tmpdir, "v3.epub")
            outdir = os.path.join(tmpdir, "output")
            os.makedirs(outdir)

            _make_minimal_epub(epub2, title="V2 Book", version="2.0", chapters=[
                ("OEBPS/ch01.xhtml", "<html><body>V2</body></html>"),
            ])
            _make_minimal_epub(epub3, title="V3 Book", version="3.0", chapters=[
                ("OEBPS/ch02.xhtml", "<html><body>V3</body></html>"),
            ])

            result = run([epub2, epub3], outdir)
            assert result == 0

            output_file = os.path.join(outdir, "merged_v2.epub")
            with zipfile.ZipFile(output_file) as zf:
                opf_path = _find_opf_path(zf)
                opf_content = zf.read(opf_path).decode("utf-8")
                assert 'version="3.0"' in opf_content

    def test_merge_corrupted_file_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            epub1 = os.path.join(tmpdir, "good.epub")
            bad = os.path.join(tmpdir, "bad.epub")
            _make_minimal_epub(epub1)
            with open(bad, "wb") as f:
                f.write(b"not a zip file")

            result = run([epub1, bad], tmpdir)
            assert result == 1
