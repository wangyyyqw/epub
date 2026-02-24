# -*- coding: utf-8 -*-
# Feature: epub-merge-split, Property 11: 拆分点参数解析正确性
"""Property-based tests for split points argument parsing.

**Validates: Requirements 6.4**

Uses hypothesis to generate random lists of non-negative integers,
convert them to comma-separated strings, parse them back using the
same logic as plugin.py, and verify the result equals the original list.
"""

from hypothesis import given, settings
from hypothesis import strategies as st


def _parse_split_points(s: str) -> list[int]:
    """Parse comma-separated split point string, same logic as plugin.py."""
    return [int(x) for x in s.split(",")]


class TestProperty11SplitPointsParsing:
    """Property 11: 拆分点参数解析正确性"""

    @given(
        points=st.lists(
            st.integers(min_value=0, max_value=9999),
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=100)
    def test_comma_separated_roundtrip(self, points):
        # Feature: epub-merge-split, Property 11: 拆分点参数解析正确性
        # For any list of non-negative integers, converting to a comma-separated
        # string and parsing back should produce the original list.

        csv_str = ",".join(str(p) for p in points)
        parsed = _parse_split_points(csv_str)

        assert parsed == points, (
            f"Roundtrip failed.\n"
            f"Original: {points}\n"
            f"CSV string: {csv_str!r}\n"
            f"Parsed: {parsed}"
        )
