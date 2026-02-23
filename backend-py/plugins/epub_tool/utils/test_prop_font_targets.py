# -*- coding: utf-8 -*-
# Feature: epub-tool-enhancements, Property 1: 字体加密目标扫描返回有效结构化 JSON
"""Property-based tests for list_epub_font_encrypt_targets function.

**Validates: Requirements 1.1, 1.5**

Uses hypothesis to generate random EPUB files with random font families
and XHTML files, then verifies that list_epub_font_encrypt_targets()
returns a valid structured dict with correct types and constraints.
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
# Module loading – mirror the pattern used by other tests in this directory.
# encrypt_font.py uses a relative import for logwriter; we stub it out so
# the module can be loaded without the full package hierarchy.
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

_spec = importlib.util.spec_from_file_location(
    "epub_tool.utils.encrypt_font",
    os.path.join(_utils_dir, "encrypt_font.py"),
    submodule_search_locations=[],
)
_mod = importlib.util.module_from_spec(_spec)
_mod.__package__ = "epub_tool.utils"
sys.modules["epub_tool.utils.encrypt_font"] = _mod
_spec.loader.exec_module(_mod)

list_epub_font_encrypt_targets = _mod.list_epub_font_encrypt_targets


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONTAINER_XML_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="{opf_path}" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

MINIMAL_OPF = """\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata/>
  <manifest/>
  <spine/>
</package>"""

CSS_FONT_FACE_TEMPLATE = """\
@font-face {{
  font-family: "{family}";
  src: url("{font_file}");
}}
"""

MINIMAL_XHTML = """\
<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>test</title></head>
<body><p>content</p></body>
</html>"""


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Font family names: letters and spaces, 1-15 chars
_font_family_names = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz ",
    min_size=1,
    max_size=15,
).filter(lambda s: s.strip())  # must have non-space content

# XHTML file name segments
_name_segments = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
    min_size=1,
    max_size=8,
)

_xhtml_extensions = st.sampled_from([".xhtml", ".html"])


@st.composite
def xhtml_file_paths(draw):
    """Generate a path like 'OEBPS/text/chapter1.xhtml'."""
    name = draw(_name_segments)
    ext = draw(_xhtml_extensions)
    return f"OEBPS/text/{name}{ext}"


@st.composite
def font_family_sets(draw):
    """Generate a list of unique font family names with matching font files."""
    families = draw(
        st.lists(
            _font_family_names,
            min_size=0,
            max_size=5,
            unique_by=lambda s: s.strip().lower(),
        )
    )
    return [f.strip() for f in families if f.strip()]


@st.composite
def xhtml_file_sets(draw):
    """Generate a list of unique XHTML file paths."""
    return draw(
        st.lists(
            xhtml_file_paths(),
            min_size=0,
            max_size=5,
            unique=True,
        )
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_epub(font_families: list[str], xhtml_files: list[str]) -> str:
    """Create a temporary EPUB with given font families and XHTML files.

    For each font family, creates a .ttf font file and a CSS @font-face rule
    referencing it. XHTML files are created with minimal valid content.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".epub", delete=False)
    opf_path = "OEBPS/content.opf"
    container_xml = CONTAINER_XML_TEMPLATE.format(opf_path=opf_path)

    with zipfile.ZipFile(tmp, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr(opf_path, MINIMAL_OPF)

        # Create font files and CSS with @font-face declarations
        css_content = ""
        for i, family in enumerate(font_families):
            font_filename = f"font{i}.ttf"
            font_path = f"OEBPS/fonts/{font_filename}"
            zf.writestr(font_path, b"\x00\x01\x00\x00" + b"\x00" * 20)  # dummy font
            css_content += CSS_FONT_FACE_TEMPLATE.format(
                family=family,
                font_file=f"../fonts/{font_filename}",
            )

        if css_content:
            zf.writestr("OEBPS/styles/style.css", css_content)

        # Create XHTML files
        for xhtml_path in xhtml_files:
            zf.writestr(xhtml_path, MINIMAL_XHTML)

    tmp.close()
    return tmp.name


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

class TestProperty1FontTargetsScanReturnsValidJSON:
    """Property 1: 字体加密目标扫描返回有效结构化 JSON"""

    @given(
        font_families=font_family_sets(),
        xhtml_files=xhtml_file_sets(),
    )
    @settings(max_examples=100)
    def test_returns_valid_structured_dict(self, font_families, xhtml_files):
        # Feature: epub-tool-enhancements, Property 1: 字体加密目标扫描返回有效结构化 JSON
        # For any valid EPUB with random font families and XHTML files,
        # list_epub_font_encrypt_targets() should return a dict with
        # correct structure and types.

        epub_path = _make_epub(font_families, xhtml_files)
        try:
            result = list_epub_font_encrypt_targets(epub_path)

            # Must be a dict
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"

            # Must have exactly the two required keys
            assert "font_families" in result, "Missing 'font_families' key"
            assert "xhtml_files" in result, "Missing 'xhtml_files' key"

            # font_families must be a list of strings
            ff = result["font_families"]
            assert isinstance(ff, list), f"font_families should be list, got {type(ff)}"
            for item in ff:
                assert isinstance(item, str), f"font_families item should be str, got {type(item)}"
                assert len(item.strip()) > 0, "font_families item should be non-empty"

            # xhtml_files must be a list of strings ending with .xhtml or .html
            xf = result["xhtml_files"]
            assert isinstance(xf, list), f"xhtml_files should be list, got {type(xf)}"
            for item in xf:
                assert isinstance(item, str), f"xhtml_files item should be str, got {type(item)}"
                assert item.lower().endswith(".xhtml") or item.lower().endswith(".html"), (
                    f"xhtml_files item should end with .xhtml or .html, got: {item}"
                )
        finally:
            os.unlink(epub_path)
