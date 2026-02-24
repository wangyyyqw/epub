# -*- coding: utf-8 -*-
"""Unit tests for split_epub module."""

import os
import sys
import tempfile
import zipfile
import pytest

# Ensure the backend-py directory is in the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from plugins.epub_tool.utils.split_epub import list_split_targets, run


def _make_minimal_epub(path, title="Test Book", version="3.0", chapters=None, extra_files=None, include_nav=True):
    """Create a minimal valid EPUB file for testing.

    Args:
        path: output file path
        title: book title
        version: EPUB version ("2.0" or "3.0")
        chapters: list of (filename, content) tuples for XHTML chapters
        extra_files: list of (bookpath, bytes) for additional files
        include_nav: whether to include a nav document (EPUB3) or NCX (EPUB2)
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
    if version == "3.0" and include_nav:
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
        if version == "3.0" and include_nav:
            zf.writestr(f"{opf_dir}/nav.xhtml", nav_content)
        for fname, content in chapters:
            zf.writestr(fname, content)
        if extra_files:
            for bp, data in extra_files:
                zf.writestr(bp, data)


class TestListSplitTargets:
    """Tests for list_split_targets function."""

    def test_basic_scan_returns_correct_chapters(self):
        """list_split_targets on a known EPUB returns correct chapter list."""
        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
            path = f.name
        try:
            chapters = [
                ("OEBPS/ch01.xhtml", "<html><body><h1>Ch1</h1></body></html>"),
                ("OEBPS/ch02.xhtml", "<html><body><h1>Ch2</h1></body></html>"),
                ("OEBPS/ch03.xhtml", "<html><body><h1>Ch3</h1></body></html>"),
            ]
            _make_minimal_epub(path, chapters=chapters)
            targets = list_split_targets(path)

            assert len(targets) == 3
            for t in targets:
                assert "title" in t
                assert "level" in t
                assert "href" in t
                assert isinstance(t["title"], str)
                assert isinstance(t["level"], int)
                assert t["level"] >= 1
            # Verify titles match nav entries
            assert targets[0]["title"] == "Chapter 1"
            assert targets[1]["title"] == "Chapter 2"
            assert targets[2]["title"] == "Chapter 3"
        finally:
            os.unlink(path)

    def test_no_toc_falls_back_to_spine(self):
        """list_split_targets on an EPUB without TOC falls back to spine list."""
        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
            path = f.name
        try:
            chapters = [
                ("OEBPS/ch01.xhtml", "<html><body><h1>Ch1</h1></body></html>"),
                ("OEBPS/ch02.xhtml", "<html><body><h1>Ch2</h1></body></html>"),
            ]
            # Create EPUB without nav document
            _make_minimal_epub(path, chapters=chapters, include_nav=False)
            targets = list_split_targets(path)

            # Should fall back to spine — returns entries based on filenames
            assert len(targets) == 2
            for t in targets:
                assert "title" in t
                assert "level" in t
                assert "href" in t
                assert t["level"] == 1  # spine fallback uses level 1
        finally:
            os.unlink(path)

    def test_nonexistent_file_returns_empty(self):
        """list_split_targets on nonexistent file returns empty list."""
        targets = list_split_targets("/nonexistent/path/to/book.epub")
        assert targets == []


class TestSplitRun:
    """Tests for split_epub run function."""

    def test_split_point_out_of_range_returns_error(self):
        """run() with split point index out of range returns error (non-zero)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            epub_path = os.path.join(tmpdir, "book.epub")
            outdir = os.path.join(tmpdir, "output")
            os.makedirs(outdir)

            chapters = [
                ("OEBPS/ch01.xhtml", "<html><body><h1>Ch1</h1></body></html>"),
                ("OEBPS/ch02.xhtml", "<html><body><h1>Ch2</h1></body></html>"),
            ]
            _make_minimal_epub(epub_path, chapters=chapters)

            # Index 99 is way out of range for a 2-chapter book
            result = run(epub_path, outdir, [99])
            assert result != 0

    def test_basic_split_produces_correct_output_count(self):
        """run() basic split produces correct number of output files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            epub_path = os.path.join(tmpdir, "book.epub")
            outdir = os.path.join(tmpdir, "output")
            os.makedirs(outdir)

            chapters = [
                ("OEBPS/ch01.xhtml", "<html><body><h1>Ch1</h1></body></html>"),
                ("OEBPS/ch02.xhtml", "<html><body><h1>Ch2</h1></body></html>"),
                ("OEBPS/ch03.xhtml", "<html><body><h1>Ch3</h1></body></html>"),
                ("OEBPS/ch04.xhtml", "<html><body><h1>Ch4</h1></body></html>"),
            ]
            _make_minimal_epub(epub_path, chapters=chapters)

            # Split at chapter 0 and chapter 2 → 2 segments
            result = run(epub_path, outdir, [0, 2])
            assert result == 0

            output_files = [f for f in os.listdir(outdir) if f.endswith(".epub")]
            assert len(output_files) == 2

            # Verify output files are valid EPUBs
            for fname in output_files:
                fpath = os.path.join(outdir, fname)
                assert zipfile.is_zipfile(fpath)
                with zipfile.ZipFile(fpath) as zf:
                    assert "mimetype" in zf.namelist()
