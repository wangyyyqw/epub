# -*- coding: utf-8 -*-
"""Unit tests for check_zhangyue_drm function."""

import io
import zipfile
import sys
import os
import types
import importlib
import importlib.util
import pytest

_utils_dir = os.path.dirname(os.path.abspath(__file__))
_plugin_dir = os.path.dirname(_utils_dir)


class _FakeLogWriter:
    def write(self, *a, **kw):
        pass


# Set up a minimal package structure in sys.modules so relative imports work
_pkg = types.ModuleType("epub_tool")
_pkg.__path__ = [_plugin_dir]
_pkg.__package__ = "epub_tool"
sys.modules["epub_tool"] = _pkg

_log_mod = types.ModuleType("epub_tool.log")
_log_mod.logwriter = _FakeLogWriter
sys.modules["epub_tool.log"] = _log_mod

_utils_pkg = types.ModuleType("epub_tool.utils")
_utils_pkg.__path__ = [_utils_dir]
_utils_pkg.__package__ = "epub_tool.utils"
sys.modules["epub_tool.utils"] = _utils_pkg

_utils_log = types.ModuleType("epub_tool.utils.log")
_utils_log.logwriter = _FakeLogWriter
sys.modules["epub_tool.utils.log"] = _utils_log

# Now load decrypt_epub as part of the epub_tool.utils package
_spec = importlib.util.spec_from_file_location(
    "epub_tool.utils.decrypt_epub",
    os.path.join(_utils_dir, "decrypt_epub.py"),
    submodule_search_locations=[]
)
_mod = importlib.util.module_from_spec(_spec)
_mod.__package__ = "epub_tool.utils"
sys.modules["epub_tool.utils.decrypt_epub"] = _mod
_spec.loader.exec_module(_mod)

check_zhangyue_drm = _mod.check_zhangyue_drm


def _make_epub_zip(files: dict) -> zipfile.ZipFile:
    """Create an in-memory ZipFile with the given files dict {name: content_bytes}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    buf.seek(0)
    return zipfile.ZipFile(buf, "r")


class TestCheckZhangYueDrm:
    def test_returns_true_when_encryption_xml_contains_zhangyue(self):
        epub_zip = _make_epub_zip({
            "META-INF/encryption.xml": '<Encryption><EncryptedData zhangyue="true"/></Encryption>'
        })
        assert check_zhangyue_drm(epub_zip) is True

    def test_returns_true_case_insensitive_uppercase(self):
        epub_zip = _make_epub_zip({
            "META-INF/encryption.xml": '<Encryption><EncryptedData ZHANGYUE="true"/></Encryption>'
        })
        assert check_zhangyue_drm(epub_zip) is True

    def test_returns_true_case_insensitive_mixed(self):
        epub_zip = _make_epub_zip({
            "META-INF/encryption.xml": '<Encryption><EncryptedData ZhangYue="true"/></Encryption>'
        })
        assert check_zhangyue_drm(epub_zip) is True

    def test_returns_false_when_no_encryption_xml(self):
        epub_zip = _make_epub_zip({
            "META-INF/container.xml": '<container/>'
        })
        assert check_zhangyue_drm(epub_zip) is False

    def test_returns_false_when_encryption_xml_has_no_zhangyue(self):
        epub_zip = _make_epub_zip({
            "META-INF/encryption.xml": '<Encryption><EncryptedData algorithm="aes"/></Encryption>'
        })
        assert check_zhangyue_drm(epub_zip) is False

    def test_returns_false_for_empty_epub(self):
        epub_zip = _make_epub_zip({})
        assert check_zhangyue_drm(epub_zip) is False
