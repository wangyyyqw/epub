# -*- coding: utf-8 -*-
"""Unit tests for view_opf module."""

import io
import os
import sys
import zipfile
import tempfile
import importlib.util
import pytest

_utils_dir = os.path.dirname(os.path.abspath(__file__))

_spec = importlib.util.spec_from_file_location(
    "view_opf",
    os.path.join(_utils_dir, "view_opf.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

run = _mod.run
_find_opf_path = _mod._find_opf_path
_format_xml = _mod._format_xml


SAMPLE_CONTAINER_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

SAMPLE_OPF = """\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata><dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">Test Book</dc:title></metadata>
  <manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml"/></manifest>
  <spine><itemref idref="nav"/></spine>
</package>"""


def _make_epub_file(files: dict) -> str:
    """Create a temporary EPUB file with the given files dict {name: content_str}."""
    tmp = tempfile.NamedTemporaryFile(suffix=".epub", delete=False)
    with zipfile.ZipFile(tmp, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    tmp.close()
    return tmp.name


class TestFindOpfPath:
    def test_finds_opf_from_container_xml(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("META-INF/container.xml", SAMPLE_CONTAINER_XML)
        buf.seek(0)
        with zipfile.ZipFile(buf, "r") as zf:
            assert _find_opf_path(zf) == "OEBPS/content.opf"

    def test_returns_none_when_no_container_xml(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("mimetype", "application/epub+zip")
        buf.seek(0)
        with zipfile.ZipFile(buf, "r") as zf:
            assert _find_opf_path(zf) is None

    def test_returns_none_when_container_has_no_opf(self):
        container = '<container><rootfiles></rootfiles></container>'
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("META-INF/container.xml", container)
        buf.seek(0)
        with zipfile.ZipFile(buf, "r") as zf:
            assert _find_opf_path(zf) is None


class TestFormatXml:
    def test_formats_valid_xml(self):
        raw = '<root><child attr="val"/></root>'
        result = _format_xml(raw)
        assert "<root>" in result
        assert "<child" in result

    def test_returns_raw_on_invalid_xml(self, capsys):
        raw = "this is not xml <<<"
        result = _format_xml(raw)
        assert result == raw
        captured = capsys.readouterr()
        assert "WARNING" in captured.err


class TestRun:
    def test_valid_epub_outputs_opf_and_file_list(self, capsys):
        epub_path = _make_epub_file({
            "mimetype": "application/epub+zip",
            "META-INF/container.xml": SAMPLE_CONTAINER_XML,
            "OEBPS/content.opf": SAMPLE_OPF,
            "OEBPS/nav.xhtml": "<html/>",
        })
        try:
            result = run(epub_path)
            assert result == 0
            captured = capsys.readouterr()
            assert "=== OPF Content ===" in captured.out
            assert "=== File List ===" in captured.out
            assert "Test Book" in captured.out
            assert "OEBPS/content.opf" in captured.out
            assert "OEBPS/nav.xhtml" in captured.out
        finally:
            os.unlink(epub_path)

    def test_missing_container_xml_returns_error(self, capsys):
        epub_path = _make_epub_file({
            "mimetype": "application/epub+zip",
        })
        try:
            result = run(epub_path)
            assert result == 1
            captured = capsys.readouterr()
            assert "ERROR" in captured.err
        finally:
            os.unlink(epub_path)

    def test_missing_opf_file_returns_error(self, capsys):
        epub_path = _make_epub_file({
            "mimetype": "application/epub+zip",
            "META-INF/container.xml": SAMPLE_CONTAINER_XML,
            # OPF file referenced but not present
        })
        try:
            result = run(epub_path)
            assert result == 1
            captured = capsys.readouterr()
            assert "ERROR" in captured.err
        finally:
            os.unlink(epub_path)

    def test_nonexistent_file_returns_error(self, capsys):
        result = run("/nonexistent/path/to/file.epub")
        assert result == 1
        captured = capsys.readouterr()
        assert "ERROR" in captured.err

    def test_file_list_contains_all_entries(self, capsys):
        files = {
            "mimetype": "application/epub+zip",
            "META-INF/container.xml": SAMPLE_CONTAINER_XML,
            "OEBPS/content.opf": SAMPLE_OPF,
            "OEBPS/nav.xhtml": "<html/>",
            "OEBPS/style.css": "body {}",
        }
        epub_path = _make_epub_file(files)
        try:
            run(epub_path)
            captured = capsys.readouterr()
            file_list_section = captured.out.split("=== File List ===")[1]
            for name in files:
                assert name in file_list_section
        finally:
            os.unlink(epub_path)
