# -*- coding: utf-8 -*-
# Feature: epub-merge-split, Property 12: 合并混合版本输出 EPUB3
"""Property-based tests for merge mixed version output.

**Validates: Requirements 7.1, 7.2**

Uses hypothesis to generate EPUBs with mixed versions (some 2.0, some 3.0),
merge them, and verify the output OPF has version="3.0".
"""

import os
import sys
import types
import zipfile
import tempfile
import importlib.util

from hypothesis import given, settings, assume
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Module loading
# ---------------------------------------------------------------------------
_utils_dir = os.path.dirname(os.path.abspath(__file__))
_plugin_dir = os.path.dirname(_utils_dir)


class _FakeLogWriter:
    def write(self, *a, **kw):
        pass


_pkg = types.ModuleType("epub_tool")
_pkg.__path__ = [_plugin_dir]
_pkg.__package__ = "epub_tool"
sys.modules.setdefault("epub_tool", _pkg)

_log_mod = types.ModuleType("epub_tool.log")
_log_mod.logwriter = _FakeLogWriter
sys.modules.setdefault("epub_tool.log", _log_mod)

_utils_pkg = types.ModuleType("epub_tool.utils")
_utils_pkg.__path__ = [_utils_dir]
_utils_pkg.__package__ = "epub_tool.utils"
sys.modules.setdefault("epub_tool.utils", _utils_pkg)

_utils_log = types.ModuleType("epub_tool.utils.log")
_utils_log.logwriter = _FakeLogWriter
sys.modules.setdefault("epub_tool.utils.log", _utils_log)

# Load merge_epub
_merge_spec = importlib.util.spec_from_file_location(
    "epub_tool.utils.merge_epub",
    os.path.join(_utils_dir, "merge_epub.py"),
    submodule_search_locations=[],
)
_merge_mod = importlib.util.module_from_spec(_merge_spec)
_merge_mod.__package__ = "epub_tool.utils"
sys.modules["epub_tool.utils.merge_epub"] = _merge_mod
_merge_spec.loader.exec_module(_merge_mod)

merge_run = _merge_mod.run
_find_opf_path = _merge_mod._find_opf_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_epub(path, title="Test", version="3.0", chapters=None):
    """Create a minimal valid EPUB file for testing."""
    if chapters is None:
        chapters = [("OEBPS/ch01.xhtml", "<html><body><h1>Ch1</h1></body></html>")]

    opf_dir = "OEBPS"
    opf_path = f"{opf_dir}/content.opf"

    manifest_items = []
    spine_items = []
    for i, (fname, _) in enumerate(chapters):
        item_id = f"ch{i+1:02d}"
        href = os.path.basename(fname)
        manifest_items.append(
            f'    <item id="{item_id}" href="{href}" '
            f'media-type="application/xhtml+xml"/>'
        )
        spine_items.append(f'    <itemref idref="{item_id}"/>')

    if version == "3.0":
        manifest_items.append(
            '    <item id="nav" href="nav.xhtml" '
            'media-type="application/xhtml+xml" properties="nav"/>'
        )

    opf_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="{version}" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">test-{title}</dc:identifier>
    <dc:title>{title}</dc:title>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
{chr(10).join(manifest_items)}
  </manifest>
  <spine>
{chr(10).join(spine_items)}
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
<nav epub:type="toc" id="toc"><h1>TOC</h1><ol>
"""
    for i, (fname, _) in enumerate(chapters):
        href = os.path.basename(fname)
        nav_content += f'    <li><a href="{href}">Ch {i+1}</a></li>\n'
    nav_content += "</ol></nav></body></html>"

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr(opf_path, opf_content)
        if version == "3.0":
            zf.writestr(f"{opf_dir}/nav.xhtml", nav_content)
        for fname, content in chapters:
            zf.writestr(fname, content)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

@st.composite
def mixed_version_lists(draw):
    """Generate a list of EPUB versions with at least one 2.0 and one 3.0."""
    n = draw(st.integers(min_value=2, max_value=5))
    versions = draw(st.lists(
        st.sampled_from(["2.0", "3.0"]),
        min_size=n,
        max_size=n,
    ))
    # Ensure at least one of each version for a true mixed scenario
    assume("2.0" in versions and "3.0" in versions)
    return versions


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

class TestProperty12MergeMixedVersionOutputEPUB3:
    """Property 12: 合并混合版本输出 EPUB3"""

    @given(versions=mixed_version_lists())
    @settings(max_examples=100)
    def test_mixed_version_merge_outputs_epub3(self, versions):
        # Feature: epub-merge-split, Property 12: 合并混合版本输出 EPUB3
        # For any set of EPUBs with mixed versions (some 2.0, some 3.0),
        # merging them should produce an output with OPF version="3.0".

        tmpdir = tempfile.mkdtemp()
        epub_paths = []

        try:
            for i, ver in enumerate(versions):
                epub_path = os.path.join(tmpdir, f"book{i+1}.epub")
                chapters = [(
                    f"OEBPS/ch{i+1:02d}.xhtml",
                    f"<html><body><h1>Book {i+1}</h1></body></html>"
                )]
                _make_minimal_epub(epub_path, title=f"Book{i+1}",
                                   version=ver, chapters=chapters)
                epub_paths.append(epub_path)

            outdir = os.path.join(tmpdir, "output")
            os.makedirs(outdir)

            result = merge_run(epub_paths, outdir)
            assert result == 0, f"Merge failed with code {result}"

            output_file = os.path.join(outdir, "merged_book1.epub")
            assert os.path.exists(output_file), "Output file not found"

            with zipfile.ZipFile(output_file) as zf:
                opf_path = _find_opf_path(zf)
                assert opf_path, "No OPF found in merged EPUB"
                opf_content = zf.read(opf_path).decode("utf-8")
                assert 'version="3.0"' in opf_content, (
                    f"Expected version='3.0' in OPF, got:\n{opf_content[:200]}"
                )
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
