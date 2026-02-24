# -*- coding: utf-8 -*-
# Feature: epub-merge-split, Property 6: 拆分目标扫描返回有效结构化 JSON
"""Property-based tests for list_split_targets function.

**Validates: Requirements 3.1, 3.2, 6.3**

Uses hypothesis to generate random EPUB files with random TOC structures,
then verifies that list_split_targets() returns a valid JSON array where
each element has `title` (non-empty string), `level` (positive int),
and `href` (non-empty string).
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
# Module loading – stub out logwriter so the module can be loaded standalone.
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

# Load merge_epub first (dependency of split_epub)
_merge_spec = importlib.util.spec_from_file_location(
    "epub_tool.utils.merge_epub",
    os.path.join(_utils_dir, "merge_epub.py"),
    submodule_search_locations=[],
)
_merge_mod = importlib.util.module_from_spec(_merge_spec)
_merge_mod.__package__ = "epub_tool.utils"
sys.modules["epub_tool.utils.merge_epub"] = _merge_mod
_merge_spec.loader.exec_module(_merge_mod)

# Load split_epub
_split_spec = importlib.util.spec_from_file_location(
    "epub_tool.utils.split_epub",
    os.path.join(_utils_dir, "split_epub.py"),
    submodule_search_locations=[],
)
_split_mod = importlib.util.module_from_spec(_split_spec)
_split_mod.__package__ = "epub_tool.utils"
sys.modules["epub_tool.utils.split_epub"] = _split_mod
_split_spec.loader.exec_module(_split_mod)

list_split_targets = _split_mod.list_split_targets


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_chapter_titles = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 ",
    min_size=1,
    max_size=20,
).filter(lambda s: s.strip())

_chapter_filenames = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
    min_size=1,
    max_size=10,
)


@st.composite
def chapter_lists(draw):
    """Generate a list of (title, filename) pairs for EPUB chapters."""
    n = draw(st.integers(min_value=1, max_value=8))
    chapters = []
    used_names = set()
    for i in range(n):
        title = draw(_chapter_titles)
        name = draw(_chapter_filenames)
        # Ensure unique filenames
        while name in used_names:
            name = name + str(i)
        used_names.add(name)
        chapters.append((title.strip(), name))
    return chapters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_epub_with_toc(chapters):
    """Create a minimal EPUB with a nav TOC from chapter list.

    Args:
        chapters: list of (title, filename) tuples

    Returns:
        path to temporary EPUB file
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".epub", delete=False)
    opf_dir = "OEBPS"
    opf_path = f"{opf_dir}/content.opf"

    # Build manifest and spine
    manifest_items = []
    spine_items = []
    for i, (title, fname) in enumerate(chapters):
        item_id = f"ch{i+1:02d}"
        href = f"{fname}.xhtml"
        manifest_items.append(
            f'    <item id="{item_id}" href="{href}" '
            f'media-type="application/xhtml+xml"/>'
        )
        spine_items.append(f'    <itemref idref="{item_id}"/>')

    manifest_items.append(
        '    <item id="nav" href="nav.xhtml" '
        'media-type="application/xhtml+xml" properties="nav"/>'
    )

    opf_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">test-split-targets</dc:identifier>
    <dc:title>Test</dc:title>
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

    # Build nav
    nav_items = []
    for i, (title, fname) in enumerate(chapters):
        nav_items.append(f'    <li><a href="{fname}.xhtml">{title}</a></li>')

    nav_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>TOC</title></head>
<body>
<nav epub:type="toc" id="toc">
  <h1>Table of Contents</h1>
  <ol>
{chr(10).join(nav_items)}
  </ol>
</nav>
</body>
</html>"""

    with zipfile.ZipFile(tmp, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr(opf_path, opf_content)
        zf.writestr(f"{opf_dir}/nav.xhtml", nav_content)
        for i, (title, fname) in enumerate(chapters):
            xhtml = (
                f'<html xmlns="http://www.w3.org/1999/xhtml">'
                f'<head><title>{title}</title></head>'
                f'<body><h1>{title}</h1></body></html>'
            )
            zf.writestr(f"{opf_dir}/{fname}.xhtml", xhtml)

    tmp.close()
    return tmp.name


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

class TestProperty6SplitTargetsValidJSON:
    """Property 6: 拆分目标扫描返回有效结构化 JSON"""

    @given(chapters=chapter_lists())
    @settings(max_examples=100)
    def test_list_split_targets_returns_valid_structure(self, chapters):
        # Feature: epub-merge-split, Property 6: 拆分目标扫描返回有效结构化 JSON
        # For any valid EPUB with random TOC structure,
        # list_split_targets() should return a list of dicts each with
        # title (non-empty str), level (positive int), href (non-empty str).

        epub_path = _make_epub_with_toc(chapters)
        try:
            result = list_split_targets(epub_path)

            assert isinstance(result, list), f"Expected list, got {type(result)}"
            assert len(result) > 0, "Expected non-empty result for EPUB with chapters"

            for i, entry in enumerate(result):
                assert isinstance(entry, dict), (
                    f"Entry {i} should be dict, got {type(entry)}"
                )

                # title: non-empty string
                assert "title" in entry, f"Entry {i} missing 'title'"
                assert isinstance(entry["title"], str), (
                    f"Entry {i} title should be str, got {type(entry['title'])}"
                )
                assert len(entry["title"].strip()) > 0, (
                    f"Entry {i} title should be non-empty"
                )

                # level: positive integer
                assert "level" in entry, f"Entry {i} missing 'level'"
                assert isinstance(entry["level"], int), (
                    f"Entry {i} level should be int, got {type(entry['level'])}"
                )
                assert entry["level"] > 0, (
                    f"Entry {i} level should be positive, got {entry['level']}"
                )

                # href: non-empty string
                assert "href" in entry, f"Entry {i} missing 'href'"
                assert isinstance(entry["href"], str), (
                    f"Entry {i} href should be str, got {type(entry['href'])}"
                )
                assert len(entry["href"].strip()) > 0, (
                    f"Entry {i} href should be non-empty"
                )
        finally:
            os.unlink(epub_path)
