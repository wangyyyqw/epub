# -*- coding: utf-8 -*-
# Feature: epub-merge-split, Property 9: 拆分文件命名规则
"""Property-based tests for split output file naming.

**Validates: Requirements 4.5**

Uses hypothesis to generate random basenames and split point counts,
then verifies that the output filenames match the `{basename}_{NN}.epub`
pattern with zero-padded two-digit sequence numbers starting from 01.
"""

import re

from hypothesis import given, settings
from hypothesis import strategies as st


def _generate_split_filenames(basename: str, num_segments: int) -> list[str]:
    """Generate split output filenames, same logic as split_epub.py."""
    return [f"{basename}_{i+1:02d}.epub" for i in range(num_segments)]


# Basenames: alphanumeric + common chars, non-empty
_basenames = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
    min_size=1,
    max_size=30,
)


class TestProperty9SplitFileNaming:
    """Property 9: 拆分文件命名规则"""

    @given(
        basename=_basenames,
        num_segments=st.integers(min_value=1, max_value=99),
    )
    @settings(max_examples=100)
    def test_split_filenames_match_pattern(self, basename, num_segments):
        # Feature: epub-merge-split, Property 9: 拆分文件命名规则
        # For any basename and number of segments, output filenames should
        # match {basename}_{NN}.epub with zero-padded two-digit numbers
        # starting from 01.

        filenames = _generate_split_filenames(basename, num_segments)

        assert len(filenames) == num_segments, (
            f"Expected {num_segments} filenames, got {len(filenames)}"
        )

        pattern = re.compile(rf"^{re.escape(basename)}_(\d{{2}})\.epub$")

        for i, fname in enumerate(filenames):
            match = pattern.match(fname)
            assert match is not None, (
                f"Filename {fname!r} does not match pattern "
                f"'{basename}_NN.epub'"
            )
            seq_num = int(match.group(1))
            expected_num = i + 1
            assert seq_num == expected_num, (
                f"Sequence number mismatch: expected {expected_num:02d}, "
                f"got {seq_num:02d} in {fname!r}"
            )
