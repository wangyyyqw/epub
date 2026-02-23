# -*- coding: utf-8 -*-
# Feature: epub-tool-enhancements, Property 4: OPF 查看 XML 格式化保真性
"""Property-based tests for _format_xml function in view_opf module.

**Validates: Requirements 3.2, 3.3**

Uses hypothesis to generate random valid XML content, format it using
_format_xml, parse the result back, and verify the DOM tree is
semantically equivalent to the original.
"""

import os
import importlib.util
import xml.dom.minidom

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

_format_xml = _mod._format_xml


# ---------------------------------------------------------------------------
# Strategies for generating random valid XML
# ---------------------------------------------------------------------------

# Tag names: alphabetic, 1-10 chars (valid XML tag names)
_tag_names = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz",
    min_size=1,
    max_size=10,
)

# Attribute names: alphabetic, 1-8 chars
_attr_names = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz",
    min_size=1,
    max_size=8,
)

# Attribute values: printable ASCII without XML-special chars
_attr_values = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789 _-.",
    min_size=0,
    max_size=20,
)

# Text content: safe characters that won't break XML
_text_content = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789 ,._-",
    min_size=0,
    max_size=30,
)


def _build_xml_element(tag, attrs, text, children_xml):
    """Build an XML element string from components."""
    attr_str = ""
    if attrs:
        # Deduplicate attribute names (XML doesn't allow duplicate attrs)
        seen = set()
        unique_attrs = []
        for name, value in attrs:
            if name not in seen:
                seen.add(name)
                unique_attrs.append((name, value))
        attr_str = " " + " ".join(
            f'{name}="{value}"' for name, value in unique_attrs
        )

    inner = ""
    if text:
        # Escape XML special chars in text
        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        inner += escaped
    if children_xml:
        inner += children_xml

    if inner:
        return f"<{tag}{attr_str}>{inner}</{tag}>"
    else:
        return f"<{tag}{attr_str}/>"


@st.composite
def xml_elements(draw, max_depth=3):
    """Generate a random valid XML element (possibly with children)."""
    tag = draw(_tag_names)
    num_attrs = draw(st.integers(min_value=0, max_value=3))
    attrs = draw(
        st.lists(
            st.tuples(_attr_names, _attr_values),
            min_size=num_attrs,
            max_size=num_attrs,
        )
    )
    text = draw(_text_content)

    children_xml = ""
    if max_depth > 0:
        num_children = draw(st.integers(min_value=0, max_value=2))
        children = draw(
            st.lists(
                xml_elements(max_depth=max_depth - 1),
                min_size=num_children,
                max_size=num_children,
            )
        )
        children_xml = "".join(children)

    return _build_xml_element(tag, attrs, text, children_xml)


@st.composite
def valid_xml_documents(draw):
    """Generate a complete valid XML document with a root element."""
    root_element = draw(xml_elements(max_depth=3))
    return f'<?xml version="1.0" encoding="UTF-8"?>{root_element}'


# ---------------------------------------------------------------------------
# DOM comparison helpers
# ---------------------------------------------------------------------------

def _normalize_text(text):
    """Normalize whitespace in text for comparison."""
    if text is None:
        return ""
    return " ".join(text.split())


def _dom_trees_equivalent(node1, node2):
    """Check if two DOM nodes are semantically equivalent.

    Compares element names, attributes, text content, and child structure,
    ignoring whitespace-only text nodes introduced by pretty-printing.
    """
    if node1.nodeType != node2.nodeType:
        return False

    if node1.nodeType == node1.ELEMENT_NODE:
        # Compare tag names
        if node1.tagName != node2.tagName:
            return False

        # Compare attributes
        attrs1 = {}
        if node1.attributes:
            for i in range(node1.attributes.length):
                attr = node1.attributes.item(i)
                attrs1[attr.name] = attr.value
        attrs2 = {}
        if node2.attributes:
            for i in range(node2.attributes.length):
                attr = node2.attributes.item(i)
                attrs2[attr.name] = attr.value
        if attrs1 != attrs2:
            return False

        # Get significant children (skip whitespace-only text nodes)
        children1 = _significant_children(node1)
        children2 = _significant_children(node2)

        if len(children1) != len(children2):
            return False

        for c1, c2 in zip(children1, children2):
            if not _dom_trees_equivalent(c1, c2):
                return False

        return True

    elif node1.nodeType == node1.TEXT_NODE:
        return _normalize_text(node1.data) == _normalize_text(node2.data)

    elif node1.nodeType == node1.DOCUMENT_NODE:
        # Compare document element (root)
        return _dom_trees_equivalent(node1.documentElement, node2.documentElement)

    # For other node types, just check node value
    return node1.nodeValue == node2.nodeValue


def _significant_children(node):
    """Return child nodes, filtering out whitespace-only text nodes."""
    result = []
    for child in node.childNodes:
        if child.nodeType == child.TEXT_NODE:
            if child.data.strip():
                result.append(child)
        else:
            result.append(child)
    return result


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

class TestProperty4OPFFormatFidelity:
    """Property 4: OPF 查看 XML 格式化保真性"""

    @given(xml_doc=valid_xml_documents())
    @settings(max_examples=100)
    def test_format_xml_preserves_dom_structure(self, xml_doc):
        # Feature: epub-tool-enhancements, Property 4: OPF 查看 XML 格式化保真性
        # For any valid XML, formatting it and parsing back should produce
        # a semantically equivalent DOM tree.

        # Parse the original XML
        original_dom = xml.dom.minidom.parseString(xml_doc)

        # Format using the function under test
        formatted = _format_xml(xml_doc)

        # Parse the formatted result
        formatted_dom = xml.dom.minidom.parseString(formatted)

        # Verify DOM trees are semantically equivalent
        assert _dom_trees_equivalent(original_dom, formatted_dom), (
            f"DOM trees not equivalent.\n"
            f"Original XML: {xml_doc!r}\n"
            f"Formatted XML: {formatted!r}"
        )

        # Clean up
        original_dom.unlink()
        formatted_dom.unlink()
