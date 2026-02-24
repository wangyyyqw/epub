# -*- coding: utf-8 -*-
# Feature: epub-merge-split, Property 4: 合并资源冲突解决
"""Property-based tests for merge resource conflict resolution.

**Validates: Requirements 2.5**

Uses hypothesis to generate multiple EPUBs with same-named resources,
merge them, and verify that no duplicate file paths exist in the output.
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

def _make_minimal_epub(path, title="Test", version="3.0", chapters=None, extra_files=None):
    """Create a minimal valid EPUB file for testing."""
    if chapters is None:
        chapters = [("OEBPS/ch01.xhtml", "<html><body><h1>Chapter 1</h1></body></html>")]

    opf_dir = "OEBPS"
    opf_path = f"{opf_dir}/content.opf"

    manifest_items = []
    spine_items = []
    for i, (fname, _content) in enumerate(chapters):
        item_id = f"ch{i+1:02d}"
        href = os.path.basename(fname)
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
        zf.writestr(f"{opf_dir}/nav.xhtml", nav_content)
        for fname, content in chapters:
            zf.writestr(fname, content)
        if extra_files:
            for bp, data in extra_files:
                zf.writestr(bp, data)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_resource_names = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
    min_size=1,
    max_size=8,
)


@st.composite
def shared_resource_names(draw):
    """Generate a list of resource names that will be shared across EPUBs."""
    return draw(st.lists(
        _resource_names,
        min_size=1,
        max_size=4,
        unique=True,
    ))


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

class TestProperty4MergeConflictResolution:
    """Property 4: 合并资源冲突解决 — 无重复文件名"""

    @given(
        shared_resources=shared_resource_names(),
        num_epubs=st.integers(min_value=2, max_value=4),
    )
    @settings(max_examples=100)
    def test_no_duplicate_file_paths_after_merge(self, shared_resources, num_epubs):
        # Feature: epub-merge-split, Property 4: 合并资源冲突解决
        # For any set of EPUBs with same-named resources, merging them
        # should produce an EPUB with no duplicate file paths.

        tmpdir = tempfile.mkdtemp()
        epub_paths = []

        try:
            for vol in range(num_epubs):
                epub_path = os.path.join(tmpdir, f"book{vol+1}.epub")
                # Each EPUB has a unique chapter but shared resource files
                chapters = [(
                    f"OEBPS/ch{vol+1:02d}.xhtml",
                    f"<html><body><h1>Book {vol+1}</h1></body></html>"
                )]
                extra = []
                for res_name in shared_resources:
                    extra.append((
                        f"OEBPS/{res_name}.css",
                        f"/* style from book {vol+1} */".encode()
                    ))
                _make_minimal_epub(epub_path, title=f"Book{vol+1}",
                                   chapters=chapters, extra_files=extra)
                epub_paths.append(epub_path)

            outdir = os.path.join(tmpdir, "output")
            os.makedirs(outdir)

            result = merge_run(epub_paths, outdir)
            assert result == 0, f"Merge failed with code {result}"

            # Find the output file
            output_file = os.path.join(outdir, "merged_book1.epub")
            assert os.path.exists(output_file), "Output file not found"

            # Verify no duplicate file paths
            with zipfile.ZipFile(output_file) as zf:
                names = zf.namelist()
                duplicates = [n for n in names if names.count(n) > 1]
                assert len(duplicates) == 0, (
                    f"Found duplicate file paths in merged EPUB: "
                    f"{set(duplicates)}"
                )
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
