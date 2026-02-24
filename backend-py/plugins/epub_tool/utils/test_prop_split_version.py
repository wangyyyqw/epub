# -*- coding: utf-8 -*-
# Feature: epub-merge-split, Property 13: 拆分保持原始 EPUB 版本
"""Property-based tests for split preserving original EPUB version.

**Validates: Requirements 7.3, 7.4**

Uses hypothesis to generate EPUBs with random version (2.0 or 3.0),
split them, and verify all output EPUBs have the same version as input.
"""

import os
import sys
import types
import zipfile
import tempfile
import importlib.util
import re

from hypothesis import given, settings
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

# Load merge_epub first (dependency)
_merge_spec = importlib.util.spec_from_file_location(
    "epub_tool.utils.merge_epub",
    os.path.join(_utils_dir, "merge_epub.py"),
    submodule_search_locations=[],
)
_merge_mod = importlib.util.module_from_spec(_merge_spec)
_merge_mod.__package__ = "epub_tool.utils"
sys.modules["epub_tool.utils.merge_epub"] = _merge_mod
_merge_spec.loader.exec_module(_merge_mod)

_find_opf_path = _merge_mod._find_opf_path

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

split_run = _split_mod.run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_epub_for_split(path, version="3.0", num_chapters=3):
    """Create a minimal EPUB with multiple chapters suitable for splitting."""
    opf_dir = "OEBPS"
    opf_path = f"{opf_dir}/content.opf"

    chapters = []
    manifest_items = []
    spine_items = []
    for i in range(num_chapters):
        fname = f"OEBPS/ch{i+1:02d}.xhtml"
        content = (
            f'<html xmlns="http://www.w3.org/1999/xhtml">'
            f'<head><title>Chapter {i+1}</title></head>'
            f'<body><h1>Chapter {i+1}</h1><p>Content</p></body></html>'
        )
        chapters.append((fname, content))
        item_id = f"ch{i+1:02d}"
        href = f"ch{i+1:02d}.xhtml"
        manifest_items.append(
            f'    <item id="{item_id}" href="{href}" '
            f'media-type="application/xhtml+xml"/>'
        )
        spine_items.append(f'    <itemref idref="{item_id}"/>')

    if version.startswith("3"):
        manifest_items.append(
            '    <item id="nav" href="nav.xhtml" '
            'media-type="application/xhtml+xml" properties="nav"/>'
        )

        nav_content = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:epub="http://www.idpf.org/2007/ops">'
            '<head><title>TOC</title></head><body>'
            '<nav epub:type="toc" id="toc"><h1>TOC</h1><ol>'
        )
        for i in range(num_chapters):
            nav_content += (
                f'<li><a href="ch{i+1:02d}.xhtml">Chapter {i+1}</a></li>'
            )
        nav_content += '</ol></nav></body></html>'
    else:
        # EPUB2: use NCX
        manifest_items.append(
            '    <item id="ncx" href="toc.ncx" '
            'media-type="application/x-dtbncx+xml"/>'
        )
        ncx_content = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
            '<head><meta name="dtb:uid" content="test"/></head>'
            '<docTitle><text>Test</text></docTitle><navMap>'
        )
        for i in range(num_chapters):
            ncx_content += (
                f'<navPoint id="np{i+1}" playOrder="{i+1}">'
                f'<navLabel><text>Chapter {i+1}</text></navLabel>'
                f'<content src="ch{i+1:02d}.xhtml"/></navPoint>'
            )
        ncx_content += '</navMap></ncx>'

    toc_attr = ' toc="ncx"' if not version.startswith("3") else ""

    opf_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="{version}" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">test-split-version</dc:identifier>
    <dc:title>Test Split</dc:title>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
{chr(10).join(manifest_items)}
  </manifest>
  <spine{toc_attr}>
{chr(10).join(spine_items)}
  </spine>
</package>"""

    container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr(opf_path, opf_content)
        if version.startswith("3"):
            zf.writestr(f"{opf_dir}/nav.xhtml", nav_content)
        else:
            zf.writestr(f"{opf_dir}/toc.ncx", ncx_content)
        for fname, content in chapters:
            zf.writestr(fname, content)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

class TestProperty13SplitPreservesVersion:
    """Property 13: 拆分保持原始 EPUB 版本"""

    @given(
        version=st.sampled_from(["2.0", "3.0"]),
        num_chapters=st.integers(min_value=2, max_value=6),
    )
    @settings(max_examples=100)
    def test_split_preserves_epub_version(self, version, num_chapters):
        # Feature: epub-merge-split, Property 13: 拆分保持原始 EPUB 版本
        # For any EPUB (2.0 or 3.0), splitting it should produce output
        # EPUBs with the same OPF version as the input.

        tmpdir = tempfile.mkdtemp()
        try:
            epub_path = os.path.join(tmpdir, "test.epub")
            _make_epub_for_split(epub_path, version=version,
                                 num_chapters=num_chapters)

            outdir = os.path.join(tmpdir, "output")
            os.makedirs(outdir)

            # Split at index 0 and midpoint to get 2 segments
            mid = num_chapters // 2
            split_points = [0, mid]

            result = split_run(epub_path, outdir, split_points)
            assert result == 0, f"Split failed with code {result}"

            # Check all output EPUBs
            output_files = sorted([
                f for f in os.listdir(outdir) if f.endswith(".epub")
            ])
            assert len(output_files) > 0, "No output files generated"

            for out_fname in output_files:
                out_path = os.path.join(outdir, out_fname)
                with zipfile.ZipFile(out_path) as zf:
                    opf_path = _find_opf_path(zf)
                    assert opf_path, f"No OPF in {out_fname}"
                    opf_content = zf.read(opf_path).decode("utf-8")
                    assert f'version="{version}"' in opf_content, (
                        f"Expected version='{version}' in {out_fname}, "
                        f"got:\n{opf_content[:200]}"
                    )
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
