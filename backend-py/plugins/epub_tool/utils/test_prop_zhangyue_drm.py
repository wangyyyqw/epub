# -*- coding: utf-8 -*-
# Feature: epub-tool-enhancements, Property 6: 掌阅 DRM 检测正确性（大小写不敏感）
"""Property-based tests for check_zhangyue_drm function.

**Validates: Requirements 4.1, 4.2, 4.6**

Uses hypothesis to generate random encryption.xml content and verify that
check_zhangyue_drm correctly detects "zhangyue" in a case-insensitive manner.
"""

import io
import zipfile
import sys
import os
import types
import importlib
import importlib.util

from hypothesis import given, settings, assume
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Module loading setup (same pattern as test_check_zhangyue_drm.py)
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

check_zhangyue_drm = sys.modules["epub_tool.utils.decrypt_epub"].check_zhangyue_drm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_epub_zip(files: dict) -> zipfile.ZipFile:
    """Create an in-memory ZipFile with the given files dict {name: content_bytes}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    buf.seek(0)
    return zipfile.ZipFile(buf, "r")


# Strategy: generate a random case variant of "zhangyue"
def _random_case_zhangyue():
    """Generate a random case variant of 'zhangyue'."""
    base = "zhangyue"
    return st.tuples(*[st.sampled_from([c.lower(), c.upper()]) for c in base]).map(
        lambda chars: "".join(chars)
    )


# Strategy: generate XML-safe text that does NOT contain "zhangyue" (case-insensitive)
def _safe_text():
    """Generate text guaranteed not to contain 'zhangyue' in any case."""
    # Use a restricted alphabet that excludes characters from "zhangyue"
    # to make it impossible to accidentally form the word
    safe_chars = "bcdfiklmopqrstvwx0123456789 _-=+<>/\n"
    return st.text(alphabet=safe_chars, min_size=0, max_size=200)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

class TestProperty6ZhangYueDrmDetection:
    """Property 6: 掌阅 DRM 检测正确性（大小写不敏感）"""

    @given(
        zhangyue_variant=_random_case_zhangyue(),
        prefix=_safe_text(),
        suffix=_safe_text(),
    )
    @settings(max_examples=100)
    def test_returns_true_when_encryption_xml_contains_zhangyue(
        self, zhangyue_variant, prefix, suffix
    ):
        # Feature: epub-tool-enhancements, Property 6: 掌阅 DRM 检测正确性（大小写不敏感）
        # When encryption.xml contains any case variant of "zhangyue", detection should return True
        content = f"<Encryption>{prefix}{zhangyue_variant}{suffix}</Encryption>"
        epub_zip = _make_epub_zip({"META-INF/encryption.xml": content})
        assert check_zhangyue_drm(epub_zip) is True

    @given(content_body=_safe_text())
    @settings(max_examples=100)
    def test_returns_false_when_encryption_xml_has_no_zhangyue(self, content_body):
        # Feature: epub-tool-enhancements, Property 6: 掌阅 DRM 检测正确性（大小写不敏感）
        # When encryption.xml does NOT contain "zhangyue" in any case, detection should return False
        content = f"<Encryption>{content_body}</Encryption>"
        # Double-check our safe text strategy
        assume("zhangyue" not in content.lower())
        epub_zip = _make_epub_zip({"META-INF/encryption.xml": content})
        assert check_zhangyue_drm(epub_zip) is False

    @given(other_files=st.dictionaries(
        keys=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz/._",
            min_size=1,
            max_size=30,
        ).filter(lambda s: not s.startswith("/") and "META-INF/encryption.xml" != s),
        values=st.binary(min_size=0, max_size=50),
        min_size=0,
        max_size=5,
    ))
    @settings(max_examples=100)
    def test_returns_false_when_no_encryption_xml(self, other_files):
        # Feature: epub-tool-enhancements, Property 6: 掌阅 DRM 检测正确性（大小写不敏感）
        # When there is no META-INF/encryption.xml file at all, detection should return False
        epub_zip = _make_epub_zip(other_files)
        assert check_zhangyue_drm(epub_zip) is False
