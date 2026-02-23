# -*- coding: utf-8 -*-
# Feature: epub-tool-enhancements, Property 5: OPF 查看文件列表完整性
"""Property-based tests for file list completeness in view_opf module.

**Validates: Requirements 3.6**

Uses hypothesis to generate EPUBs with random file lists, call run(),
parse the "=== File List ===" section from stdout, and verify the file
list matches the zip namelist exactly.
"""

import os
import sys
import zipfile
import tempfile
import importlib.util

from hypothesis import given, settings, assume
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Module loading (same pattern as test_view_opf.py)
# ---------------------------------------------------------------------------
_utils_dir = os.path.dirname(os.path.abspath(__file__))

_spec = importlib.util.spec_from_file_location(
    "view_opf",
    os.path.join(_utils_dir, "view_opf.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

run = _mod.run


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


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Path segments: lowercase letters, 1-10 chars
_path_segments = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
    min_size=1,
    max_size=10,
)

# File extensions
_extensions = st.sampled_from([".xhtml", ".html", ".css", ".xml", ".ncx", ".png", ".jpg", ".ttf", ".otf", ".js"])


@st.composite
def file_paths(draw):
    """Generate a random file path like 'OEBPS/text/chapter1.xhtml'."""
    depth = draw(st.integers(min_value=1, max_value=3))
    segments = [draw(_path_segments) for _ in range(depth)]
    ext = draw(_extensions)
    filename = segments[-1] + ext
    if depth > 1:
        return "/".join(segments[:-1]) + "/" + filename
    return filename


@st.composite
def random_file_lists(draw):
    """Generate a list of unique random file paths for EPUB content."""
    paths = draw(
        st.lists(
            file_paths(),
            min_size=0,
            max_size=10,
            unique=True,
        )
    )
    # Filter out paths that would collide with required EPUB structure files
    reserved = {"META-INF/container.xml", "OEBPS/content.opf", "mimetype"}
    return [p for p in paths if p not in reserved and not p.startswith("META-INF/")]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_epub_with_files(extra_files: list[str]) -> str:
    """Create a temporary EPUB with required structure + extra files."""
    tmp = tempfile.NamedTemporaryFile(suffix=".epub", delete=False)
    opf_path = "OEBPS/content.opf"
    container_xml = CONTAINER_XML_TEMPLATE.format(opf_path=opf_path)

    with zipfile.ZipFile(tmp, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr(opf_path, MINIMAL_OPF)
        for fpath in extra_files:
            zf.writestr(fpath, "placeholder content")
    tmp.close()
    return tmp.name


def _parse_file_list_section(stdout: str) -> list[str]:
    """Extract file names from the '=== File List ===' section of stdout."""
    marker = "=== File List ==="
    parts = stdout.split(marker)
    if len(parts) < 2:
        return []
    section = parts[1]
    return [line.strip() for line in section.strip().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

class TestProperty5OPFFileListCompleteness:
    """Property 5: OPF 查看文件列表完整性"""

    @given(extra_files=random_file_lists())
    @settings(max_examples=100)
    def test_file_list_matches_zip_namelist(self, extra_files):
        # Feature: epub-tool-enhancements, Property 5: OPF 查看文件列表完整性
        # For any valid EPUB with random files, the output file list
        # should match the zip namelist exactly.

        import io

        epub_path = _make_epub_with_files(extra_files)
        try:
            # Get the actual zip namelist for comparison
            with zipfile.ZipFile(epub_path, "r") as zf:
                expected_names = set(zf.namelist())

            # Capture stdout by temporarily replacing sys.stdout
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
            try:
                result = run(epub_path)
                stdout_output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

            assert result == 0, "run() should return 0 for a valid EPUB"

            # Parse the file list from stdout
            output_names = set(_parse_file_list_section(stdout_output))

            # Verify completeness: every file in the zip appears in output
            assert expected_names == output_names, (
                f"File list mismatch.\n"
                f"Expected (zip namelist): {sorted(expected_names)}\n"
                f"Got (output): {sorted(output_names)}"
            )
        finally:
            os.unlink(epub_path)
