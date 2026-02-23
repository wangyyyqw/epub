# -*- coding: utf-8 -*-
# Feature: epub-tool-enhancements, Property 7: 掌阅 DRM 检测后正确终止并返回错误标识
"""Property-based tests for run() termination on ZhangYue DRM detection.

**Validates: Requirements 4.3, 4.4**

Uses hypothesis to generate EPUBs marked as ZhangYue DRM encrypted,
then verifies that run() returns "zhangyue_drm" and stderr contains
a warning about ZhangYue encryption.
"""

import io
import zipfile
import sys
import os
import types
import importlib
import importlib.util
import tempfile

from hypothesis import given, settings, assume
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Module loading setup (same pattern as test_prop_zhangyue_drm.py)
# ---------------------------------------------------------------------------
_utils_dir = os.path.dirname(os.path.abspath(__file__))
_plugin_dir = os.path.dirname(_utils_dir)


class _CaptureLogWriter:
    """A fake logwriter that captures messages for assertion."""

    def __init__(self):
        self.messages = []

    def write(self, text):
        self.messages.append(text)
        print(text, file=sys.stderr)
        sys.stderr.flush()


_pkg = types.ModuleType("epub_tool")
_pkg.__path__ = [_plugin_dir]
_pkg.__package__ = "epub_tool"
sys.modules.setdefault("epub_tool", _pkg)

_log_mod = types.ModuleType("epub_tool.log")
_log_mod.logwriter = _CaptureLogWriter
sys.modules.setdefault("epub_tool.log", _log_mod)

_utils_pkg = types.ModuleType("epub_tool.utils")
_utils_pkg.__path__ = [_utils_dir]
_utils_pkg.__package__ = "epub_tool.utils"
sys.modules.setdefault("epub_tool.utils", _utils_pkg)

_utils_log = types.ModuleType("epub_tool.utils.log")
_utils_log.logwriter = _CaptureLogWriter
sys.modules.setdefault("epub_tool.utils.log", _utils_log)

if "epub_tool.utils.decrypt_epub" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "epub_tool.utils.decrypt_epub",
        os.path.join(_utils_dir, "decrypt_epub.py"),
        submodule_search_locations=[],
    )
    _mod = importlib.util.module_from_spec(_spec)
    _mod.__package__ = "epub_tool.utils"
    sys.modules["epub_tool.utils.decrypt_epub"] = _mod
    _spec.loader.exec_module(_mod)

_decrypt_mod = sys.modules["epub_tool.utils.decrypt_epub"]
run = _decrypt_mod.run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Minimal OPF template for a valid EPUB 2.0 with an encrypted-looking manifest item.
# The href "encrypted:file.xhtml" contains ":" which triggers encrypted = True.
_CONTAINER_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

_OPF_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Test</dc:title>
    <dc:language>en</dc:language>
    <dc:identifier id="uid">test-id</dc:identifier>
  </metadata>
  <manifest>
    <item id="ch1" href="encrypted:ch1.xhtml" media-type="application/xhtml+xml"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="ch1"/>
  </spine>
</package>"""

_XHTML_CONTENT = """\
<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>T</title></head><body><p>test</p></body></html>"""

_NCX_CONTENT = """\
<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
<head><meta name="dtb:uid" content="test-id"/></head>
<docTitle><text>Test</text></docTitle>
<navMap><navPoint id="np1" playOrder="1"><navLabel><text>Ch1</text></navLabel><content src="encrypted:ch1.xhtml"/></navPoint></navMap>
</ncx>"""


def _random_case_zhangyue():
    """Generate a random case variant of 'zhangyue'."""
    base = "zhangyue"
    return st.tuples(*[st.sampled_from([c.lower(), c.upper()]) for c in base]).map(
        lambda chars: "".join(chars)
    )


def _safe_xml_text():
    """Generate XML-safe text that does NOT contain 'zhangyue'."""
    safe_chars = "bcdfiklmopqrstvwx0123456789 _-=+\n"
    return st.text(alphabet=safe_chars, min_size=0, max_size=80)


def _make_zhangyue_epub(zhangyue_variant: str, prefix: str, suffix: str) -> str:
    """Create a temporary EPUB file on disk that is ZhangYue DRM encrypted.

    Returns the path to the temporary file.
    """
    encryption_xml = f"<Encryption>{prefix}{zhangyue_variant}{suffix}</Encryption>"

    fd, epub_path = tempfile.mkstemp(suffix=".epub")
    os.close(fd)

    with zipfile.ZipFile(epub_path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", _CONTAINER_XML)
        zf.writestr("META-INF/encryption.xml", encryption_xml)
        zf.writestr("OEBPS/content.opf", _OPF_TEMPLATE)
        zf.writestr("OEBPS/encrypted:ch1.xhtml", _XHTML_CONTENT)
        zf.writestr("OEBPS/toc.ncx", _NCX_CONTENT)

    return epub_path


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

class TestProperty7ZhangYueDrmTermination:
    """Property 7: 掌阅 DRM 检测后正确终止并返回错误标识"""

    @given(
        zhangyue_variant=_random_case_zhangyue(),
        prefix=_safe_xml_text(),
        suffix=_safe_xml_text(),
    )
    @settings(max_examples=100)
    def test_run_returns_zhangyue_drm_and_warns(
        self, zhangyue_variant, prefix, suffix
    ):
        # Feature: epub-tool-enhancements, Property 7: 掌阅 DRM 检测后正确终止并返回错误标识
        # For any EPUB detected as ZhangYue DRM encrypted, run() should return
        # "zhangyue_drm" and stderr should contain a warning about ZhangYue encryption.
        epub_path = _make_zhangyue_epub(zhangyue_variant, prefix, suffix)
        try:
            # Reset the module-level logger to capture messages for this run
            original_logger = _decrypt_mod.logger
            capture_logger = _CaptureLogWriter()
            _decrypt_mod.logger = capture_logger

            result = run(epub_path)

            # Property: run() must return "zhangyue_drm"
            assert result == "zhangyue_drm", (
                f"Expected 'zhangyue_drm' but got {result!r} "
                f"for zhangyue variant: {zhangyue_variant!r}"
            )

            # Property: logger output must contain ZhangYue warning
            all_messages = "\n".join(capture_logger.messages)
            assert "zhangyue" in all_messages.lower() or "掌阅" in all_messages, (
                f"Expected ZhangYue/掌阅 warning in logger output but got: {all_messages!r}"
            )

            _decrypt_mod.logger = original_logger
        finally:
            # Clean up temp files
            if os.path.exists(epub_path):
                os.unlink(epub_path)
            # Also clean up any _decrypt.epub that run() might have created
            decrypt_path = epub_path.replace(".epub", "_decrypt.epub")
            if os.path.exists(decrypt_path):
                os.unlink(decrypt_path)
