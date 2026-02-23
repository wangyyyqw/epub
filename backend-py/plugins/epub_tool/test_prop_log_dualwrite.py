# -*- coding: utf-8 -*-
# Feature: epub-tool-enhancements, Property 3: 日志双写一致性
"""Property-based tests for log dual-write consistency.

**Validates: Requirements 2.1, 2.2**

Uses hypothesis to generate random log message sequences, write them
through logwriter.write(), and verify all messages appear in both
log.txt file and stderr output. Also verifies the first line of
log.txt contains a timestamp.
"""

import os
import sys
import re
import tempfile
import importlib.util

from hypothesis import given, settings, assume
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Module loading
# ---------------------------------------------------------------------------
_utils_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "utils")

_spec = importlib.util.spec_from_file_location(
    "log",
    os.path.join(_utils_dir, "log.py"),
)
_mod = importlib.util.module_from_spec(_spec)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Generate printable log messages (no newlines to keep line-based parsing simple)
_log_message = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Z"),
        blacklist_characters="\n\r",
    ),
    min_size=1,
    max_size=80,
)

_log_message_list = st.lists(_log_message, min_size=1, max_size=20)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_logwriter_in_tmpdir(tmpdir: str):
    """Create a logwriter instance that writes log.txt into tmpdir.

    We achieve this by temporarily overriding sys.argv[0] so that
    logwriter.__init__ resolves the log path to tmpdir.
    """
    # Reload the module fresh each time to avoid stale state
    fresh_spec = importlib.util.spec_from_file_location(
        "log_fresh",
        os.path.join(_utils_dir, "log.py"),
    )
    fresh_mod = importlib.util.module_from_spec(fresh_spec)

    old_argv0 = sys.argv[0]
    # Point argv[0] to a dummy file inside tmpdir so dirname resolves to tmpdir
    sys.argv[0] = os.path.join(tmpdir, "dummy_binary")
    try:
        fresh_spec.loader.exec_module(fresh_mod)
        lw = fresh_mod.logwriter()
    finally:
        sys.argv[0] = old_argv0
    return lw


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

class TestProperty3LogDualWriteConsistency:
    """Property 3: 日志双写一致性"""

    @given(messages=_log_message_list)
    @settings(max_examples=100)
    def test_all_messages_in_file_and_stderr(self, messages):
        # Feature: epub-tool-enhancements, Property 3: 日志双写一致性
        # For any sequence of log messages, every message written via
        # logwriter.write() must appear in both log.txt and stderr,
        # and the first line of log.txt must contain a timestamp.

        import io

        with tempfile.TemporaryDirectory() as tmpdir:
            # Capture stderr
            old_stderr = sys.stderr
            captured_stderr = io.StringIO()
            sys.stderr = captured_stderr
            try:
                lw = _create_logwriter_in_tmpdir(tmpdir)

                for msg in messages:
                    lw.write(msg)

                lw.close()
            finally:
                sys.stderr = old_stderr

            # Read log.txt
            log_path = os.path.join(tmpdir, "log.txt")
            assert os.path.exists(log_path), "log.txt should exist"

            with open(log_path, "r", encoding="utf-8") as f:
                file_content = f.read()

            stderr_content = captured_stderr.getvalue()

            # Verify first line contains timestamp (format: time: YYYY-MM-DD HH:MM:SS)
            first_line = file_content.split("\n")[0]
            assert re.match(
                r"^time: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", first_line
            ), f"First line should be a timestamp, got: {first_line!r}"

            # Verify all messages appear in log.txt
            for msg in messages:
                assert msg in file_content, (
                    f"Message {msg!r} not found in log.txt"
                )

            # Verify all messages appear in stderr
            for msg in messages:
                assert msg in stderr_content, (
                    f"Message {msg!r} not found in stderr"
                )
