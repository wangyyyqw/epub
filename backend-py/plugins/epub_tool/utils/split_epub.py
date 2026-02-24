# -*- coding: utf-8 -*-
# EPUB 拆分模块：将单个 EPUB 按章节/卷拆分为多个独立文件

import os
import sys
import re
import zipfile
import posixpath
from xml.etree import ElementTree
from urllib.parse import unquote

from .merge_epub import (
    _strip_ns,
    _find_opf_path,
    _parse_opf,
    _parse_toc_nav,
    _parse_toc_ncx,
    NS_OPF,
    NS_DC,
    NS_XHTML,
    NS_NCX,
    NS_EPUB,
)

try:
    from ..log import logwriter
except ImportError:
    from .log import logwriter

logger = logwriter()

# Register namespaces
ElementTree.register_namespace("", NS_OPF)
ElementTree.register_namespace("dc", NS_DC)
ElementTree.register_namespace("xhtml", NS_XHTML)
ElementTree.register_namespace("ncx", NS_NCX)
ElementTree.register_namespace("epub", NS_EPUB)


def _parse_toc_nav_with_levels(epub_zip, nav_path):
    """Parse EPUB3 nav document, return list of {"title", "level", "href"} dicts.

    Unlike merge_epub._parse_toc_nav which returns flat (title, href) tuples,
    this version tracks nesting level for split target display.
    """
    try:
        nav_content = epub_zip.read(nav_path).decode("utf-8")
    except KeyError:
        return []
    root = ElementTree.fromstring(nav_content)
    nav_dir = posixpath.dirname(nav_path)
    entries = []

    def _find_toc_nav(elem):
        for child in elem:
            tag = _strip_ns(child.tag)
            if tag == "nav":
                epub_type = child.get(f"{{{NS_EPUB}}}type", "") or child.get("epub:type", "")
                if "toc" in epub_type:
                    return child
            result = _find_toc_nav(child)
            if result is not None:
                return result
        return None

    def _walk_nav_list(ol_elem, level):
        for li in ol_elem:
            if _strip_ns(li.tag) != "li":
                continue
            for child in li:
                child_tag = _strip_ns(child.tag)
                if child_tag == "a":
                    title = "".join(child.itertext()).strip()
                    href_attr = child.get("href", "")
                    # Strip fragment
                    href_no_frag = href_attr.split("#")[0] if href_attr else ""
                    href = posixpath.normpath(posixpath.join(nav_dir, unquote(href_no_frag))) if href_no_frag else ""
                    entries.append({"title": title, "level": level, "href": href})
                elif child_tag == "span":
                    title = "".join(child.itertext()).strip()
                    entries.append({"title": title, "level": level, "href": ""})
                elif child_tag == "ol":
                    _walk_nav_list(child, level + 1)

    nav_elem = _find_toc_nav(root)
    if nav_elem is not None:
        for child in nav_elem:
            if _strip_ns(child.tag) == "ol":
                _walk_nav_list(child, 1)
    return entries


def _parse_toc_ncx_with_levels(epub_zip, ncx_path):
    """Parse EPUB2 NCX TOC, return list of {"title", "level", "href"} dicts."""
    try:
        ncx_content = epub_zip.read(ncx_path).decode("utf-8")
    except KeyError:
        return []
    root = ElementTree.fromstring(ncx_content)
    ncx_dir = posixpath.dirname(ncx_path)
    entries = []

    def _walk_navpoints(parent, level):
        for child in parent:
            tag = _strip_ns(child.tag)
            if tag == "navPoint":
                title = ""
                href = ""
                for sub in child:
                    sub_tag = _strip_ns(sub.tag)
                    if sub_tag == "navLabel":
                        for t in sub:
                            if _strip_ns(t.tag) == "text":
                                title = (t.text or "").strip()
                    elif sub_tag == "content":
                        src = sub.get("src", "")
                        src_no_frag = src.split("#")[0] if src else ""
                        href = posixpath.normpath(posixpath.join(ncx_dir, src_no_frag)) if src_no_frag else ""
                if title or href:
                    entries.append({"title": title, "level": level, "href": href})
                _walk_navpoints(child, level + 1)

    for child in root:
        if _strip_ns(child.tag) == "navMap":
            _walk_navpoints(child, 1)
            break
    return entries


def _spine_as_targets(manifest, spine, opf_dir):
    """Fallback: use spine content documents as split targets when no valid TOC."""
    targets = []
    for idx, (idref, linear, props) in enumerate(spine):
        if idref in manifest:
            href, media_type, _ = manifest[idref]
            if media_type == "application/xhtml+xml" or href.lower().endswith((".xhtml", ".html")):
                bookpath = posixpath.normpath(posixpath.join(opf_dir, href)) if opf_dir else href
                title = os.path.basename(href)
                targets.append({"title": title, "level": 1, "href": bookpath})
    return targets


def list_split_targets(epub_path):
    """Scan EPUB chapter structure, return list of split target dicts.

    Each dict: {"title": str, "level": int, "href": str}

    Args:
        epub_path: path to the EPUB file

    Returns:
        list of split target dicts
    """
    if not os.path.exists(epub_path):
        logger.write(f"ERROR: 文件不存在: {epub_path}")
        return []
    if not zipfile.is_zipfile(epub_path):
        logger.write(f"ERROR: 不是有效的 EPUB/ZIP 文件: {epub_path}")
        return []

    with zipfile.ZipFile(epub_path, "r") as zf:
        opf_path = _find_opf_path(zf)
        if not opf_path:
            logger.write(f"ERROR: 无法找到 OPF 文件: {epub_path}")
            return []

        version, metadata_elem, manifest, spine, opf_dir, toc_id = _parse_opf(zf, opf_path)

        targets = []

        # Try EPUB3 nav first
        for item_id, (href, media_type, props) in manifest.items():
            if "nav" in props:
                nav_path = posixpath.normpath(posixpath.join(opf_dir, href)) if opf_dir else href
                targets = _parse_toc_nav_with_levels(zf, nav_path)
                break

        # Fallback to NCX
        if not targets and toc_id and toc_id in manifest:
            ncx_href = manifest[toc_id][0]
            ncx_path = posixpath.normpath(posixpath.join(opf_dir, ncx_href)) if opf_dir else ncx_href
            targets = _parse_toc_ncx_with_levels(zf, ncx_path)

        # Fallback to spine
        if not targets:
            targets = _spine_as_targets(manifest, spine, opf_dir)

    return targets


def _collect_referenced_resources(epub_zip, content_bookpaths, manifest, opf_dir):
    """Collect resource bookpaths referenced by a set of content documents.

    Scans href and src attributes in XHTML content docs to find referenced
    resources (CSS, images, fonts, etc.).

    Args:
        epub_zip: open ZipFile
        content_bookpaths: set of content document bookpaths in this segment
        manifest: parsed manifest dict {id: (href, media_type, properties)}
        opf_dir: OPF directory

    Returns:
        set of referenced resource bookpaths
    """
    # Build a set of all known bookpaths from manifest
    all_bookpaths = {}
    for item_id, (href, media_type, props) in manifest.items():
        bp = posixpath.normpath(posixpath.join(opf_dir, href)) if opf_dir else href
        all_bookpaths[bp] = (item_id, href, media_type, props)

    referenced = set()

    for content_bp in content_bookpaths:
        try:
            data = epub_zip.read(content_bp).decode("utf-8")
        except (KeyError, UnicodeDecodeError):
            continue

        content_dir = posixpath.dirname(content_bp)

        # Find all href="..." and src="..." references
        for match in re.finditer(r'(?:href|src)\s*=\s*["\']([^"\']*)["\']', data):
            ref = match.group(1)
            if not ref or ref.startswith("http://") or ref.startswith("https://") or ref.startswith("data:") or ref.startswith("#"):
                continue
            # Strip fragment
            ref_no_frag = ref.split("#")[0]
            if not ref_no_frag:
                continue
            resolved = posixpath.normpath(posixpath.join(content_dir, unquote(ref_no_frag)))
            if resolved in all_bookpaths:
                referenced.add(resolved)

    # Also scan CSS files for url() references (fonts, images)
    css_to_scan = set()
    for bp in referenced:
        if bp in all_bookpaths:
            _, _, mt, _ = all_bookpaths[bp]
            if mt == "text/css" or bp.lower().endswith(".css"):
                css_to_scan.add(bp)

    for css_bp in css_to_scan:
        try:
            css_data = epub_zip.read(css_bp).decode("utf-8")
        except (KeyError, UnicodeDecodeError):
            continue
        css_dir = posixpath.dirname(css_bp)
        for match in re.finditer(r'url\(["\']?([^)]*?)["\']?\)', css_data):
            ref = match.group(1)
            if not ref or ref.startswith("data:"):
                continue
            resolved = posixpath.normpath(posixpath.join(css_dir, unquote(ref)))
            if resolved in all_bookpaths:
                referenced.add(resolved)

    return referenced


def _generate_split_opf(metadata_elem, manifest_items, spine_items, version, nav_id=None):
    """Generate an OPF XML string for a split segment.

    Args:
        metadata_elem: original metadata ElementTree element
        manifest_items: list of (id, href, media_type, properties)
        spine_items: list of (idref, linear, properties)
        version: OPF version string (preserve original)
        nav_id: id of nav item if EPUB3

    Returns:
        OPF XML string
    """
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(f'<package xmlns="http://www.idpf.org/2007/opf" version="{version}" unique-identifier="split-id">')

    # Metadata
    lines.append('  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">')
    if metadata_elem is not None:
        for child in metadata_elem:
            tag = _strip_ns(child.tag)
            if tag == "identifier":
                lines.append(f'    <dc:identifier id="split-id">{child.text or "split-epub"}</dc:identifier>')
            elif tag in ("title", "creator", "language", "subject", "source", "publisher", "date", "description"):
                text = child.text or ""
                lines.append(f'    <dc:{tag}>{text}</dc:{tag}>')
            elif tag == "meta":
                name = child.get("name", "")
                content = child.get("content", "")
                prop = child.get("property", "")
                if name and content:
                    lines.append(f'    <meta name="{name}" content="{content}"/>')
                elif prop:
                    text = child.text or ""
                    lines.append(f'    <meta property="{prop}">{text}</meta>')
    else:
        lines.append('    <dc:identifier id="split-id">split-epub</dc:identifier>')
        lines.append('    <dc:title>Split EPUB</dc:title>')
        lines.append('    <dc:language>en</dc:language>')

    if version.startswith("3"):
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        lines.append(f'    <meta property="dcterms:modified">{now}</meta>')

    lines.append('  </metadata>')

    # Manifest
    lines.append('  <manifest>')
    for item_id, href, media_type, properties in manifest_items:
        props_attr = f' properties="{properties}"' if properties else ""
        href_escaped = href.replace("&", "&amp;")
        lines.append(f'    <item id="{item_id}" href="{href_escaped}" media-type="{media_type}"{props_attr}/>')
    lines.append('  </manifest>')

    # Spine
    toc_attr = ""
    # For EPUB2, find NCX id for spine toc attribute
    if not version.startswith("3"):
        for item_id, href, media_type, properties in manifest_items:
            if media_type == "application/x-dtbncx+xml":
                toc_attr = f' toc="{item_id}"'
                break
    lines.append(f'  <spine{toc_attr}>')
    for idref, linear, properties in spine_items:
        attrs = f'idref="{idref}"'
        if linear:
            attrs += f' linear="{linear}"'
        if properties:
            attrs += f' properties="{properties}"'
        lines.append(f'    <itemref {attrs}/>')
    lines.append('  </spine>')

    lines.append('</package>')
    return "\n".join(lines)


def _generate_split_nav(toc_entries, nav_bookpath):
    """Generate EPUB3 nav document for a split segment.

    Args:
        toc_entries: list of {"title", "level", "href"} for this segment
        nav_bookpath: bookpath where the nav will be placed

    Returns:
        Nav XHTML content as string
    """
    nav_dir = posixpath.dirname(nav_bookpath)
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<!DOCTYPE html>')
    lines.append('<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">')
    lines.append('<head><title>Table of Contents</title></head>')
    lines.append('<body>')
    lines.append('<nav epub:type="toc" id="toc">')
    lines.append('  <h1>Table of Contents</h1>')
    lines.append('  <ol>')

    for entry in toc_entries:
        title = entry["title"]
        href = entry["href"]
        if href:
            rel_href = posixpath.relpath(href, nav_dir).replace("\\", "/")
            lines.append(f'    <li><a href="{rel_href}">{title}</a></li>')
        else:
            lines.append(f'    <li><span>{title}</span></li>')

    lines.append('  </ol>')
    lines.append('</nav>')
    lines.append('</body>')
    lines.append('</html>')
    return "\n".join(lines)


def _generate_split_ncx(toc_entries, ncx_bookpath):
    """Generate EPUB2 NCX TOC for a split segment.

    Args:
        toc_entries: list of {"title", "level", "href"} for this segment
        ncx_bookpath: bookpath where the NCX will be placed

    Returns:
        NCX XML content as string
    """
    ncx_dir = posixpath.dirname(ncx_bookpath)
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">')
    lines.append('<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">')
    lines.append('  <head>')
    lines.append('    <meta name="dtb:uid" content="split-epub"/>')
    lines.append('    <meta name="dtb:depth" content="1"/>')
    lines.append('    <meta name="dtb:totalPageCount" content="0"/>')
    lines.append('    <meta name="dtb:maxPageNumber" content="0"/>')
    lines.append('  </head>')
    lines.append('  <docTitle><text>Split EPUB</text></docTitle>')
    lines.append('  <navMap>')

    for idx, entry in enumerate(toc_entries):
        title = entry["title"]
        href = entry["href"]
        if href:
            rel_href = posixpath.relpath(href, ncx_dir).replace("\\", "/")
            lines.append(f'    <navPoint id="navPoint-{idx + 1}" playOrder="{idx + 1}">')
            lines.append(f'      <navLabel><text>{title}</text></navLabel>')
            lines.append(f'      <content src="{rel_href}"/>')
            lines.append(f'    </navPoint>')

    lines.append('  </navMap>')
    lines.append('</ncx>')
    return "\n".join(lines)


def _write_split_epub(output_path, opf_path, opf_content, toc_path, toc_content, files_data):
    """Write a split EPUB file.

    Args:
        output_path: output file path
        opf_path: path to OPF inside EPUB
        opf_content: OPF XML string
        toc_path: path to TOC (nav or NCX) inside EPUB
        toc_content: TOC content string
        files_data: list of (bookpath, bytes_data) for content files
    """
    container_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    container_xml += '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
    container_xml += '  <rootfiles>\n'
    container_xml += f'    <rootfile full-path="{opf_path}" media-type="application/oebps-package+xml"/>\n'
    container_xml += '  </rootfiles>\n'
    container_xml += '</container>'

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr(opf_path, opf_content)
        if toc_path and toc_content:
            zf.writestr(toc_path, toc_content)

        written = {"mimetype", "META-INF/container.xml", opf_path}
        if toc_path:
            written.add(toc_path)

        for bookpath, data in files_data:
            if bookpath not in written:
                zf.writestr(bookpath, data)
                written.add(bookpath)


def run(epub_path, output_dir, split_points):
    """Split EPUB by split points.

    Args:
        epub_path: path to the EPUB file
        output_dir: output directory
        split_points: list of split point indices (into the targets list)

    Returns:
        0 on success, non-zero on failure
    """
    if not os.path.exists(epub_path):
        logger.write(f"ERROR: 文件不存在: {epub_path}")
        return 1
    if not zipfile.is_zipfile(epub_path):
        logger.write(f"ERROR: 不是有效的 EPUB/ZIP 文件: {epub_path}")
        return 1

    try:
        return _do_split(epub_path, output_dir, split_points)
    except Exception as e:
        logger.write(f"ERROR: 拆分失败: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


def _do_split(epub_path, output_dir, split_points):
    """Core split logic."""
    with zipfile.ZipFile(epub_path, "r") as zf:
        opf_path = _find_opf_path(zf)
        if not opf_path:
            logger.write(f"ERROR: 无法找到 OPF 文件: {epub_path}")
            return 1

        version, metadata_elem, manifest, spine, opf_dir, toc_id = _parse_opf(zf, opf_path)
        is_epub3 = version.startswith("3")

        # --- Get TOC targets (with levels) for filtering segment TOC entries ---
        toc_targets = []
        nav_item_path = None

        # Try EPUB3 nav
        for item_id, (href, media_type, props) in manifest.items():
            if "nav" in props:
                nav_item_path = posixpath.normpath(posixpath.join(opf_dir, href)) if opf_dir else href
                toc_targets = _parse_toc_nav_with_levels(zf, nav_item_path)
                break

        # Fallback to NCX
        ncx_item_path = None
        if not toc_targets and toc_id and toc_id in manifest:
            ncx_href = manifest[toc_id][0]
            ncx_item_path = posixpath.normpath(posixpath.join(opf_dir, ncx_href)) if opf_dir else ncx_href
            toc_targets = _parse_toc_ncx_with_levels(zf, ncx_item_path)

        # Fallback to spine
        used_spine_fallback = False
        if not toc_targets:
            toc_targets = _spine_as_targets(manifest, spine, opf_dir)
            used_spine_fallback = True

        if not toc_targets:
            logger.write("ERROR: EPUB 中没有可拆分的内容")
            return 1

        # --- Validate split points ---
        sorted_points = sorted(set(split_points))
        for pt in sorted_points:
            if pt < 0 or pt >= len(toc_targets):
                logger.write(f"ERROR: 拆分点索引超出范围: {pt} (有效范围: 0-{len(toc_targets) - 1})")
                return 1

        # --- Build spine bookpath list and id mapping ---
        spine_bookpaths = []  # ordered list of content doc bookpaths in spine
        spine_id_map = {}  # bookpath -> (idref, linear, props)
        for idref, linear, props in spine:
            if idref in manifest:
                href, media_type, _ = manifest[idref]
                if media_type == "application/xhtml+xml" or href.lower().endswith((".xhtml", ".html")):
                    bp = posixpath.normpath(posixpath.join(opf_dir, href)) if opf_dir else href
                    if bp not in spine_id_map:
                        spine_bookpaths.append(bp)
                    spine_id_map[bp] = (idref, linear, props)

        # --- Map TOC targets to spine positions ---
        # Each target's href maps to a position in the spine
        target_spine_indices = []
        for t in toc_targets:
            href = t["href"]
            if href in spine_bookpaths:
                target_spine_indices.append(spine_bookpaths.index(href))
            else:
                # Target href not in spine; use -1 as placeholder
                target_spine_indices.append(-1)

        # --- Divide spine into segments based on split points ---
        # Split points are indices into toc_targets. Each split point starts a new segment.
        # Segments are defined by the spine range between consecutive split point hrefs.
        segment_ranges = []  # list of (start_spine_idx, end_spine_idx) — inclusive start, exclusive end
        for i, pt in enumerate(sorted_points):
            start_spine = target_spine_indices[pt]
            if start_spine < 0:
                # If target not in spine, try to find next valid spine position
                for j in range(pt, len(toc_targets)):
                    if target_spine_indices[j] >= 0:
                        start_spine = target_spine_indices[j]
                        break
            if start_spine < 0:
                start_spine = 0

            # End is the start of the next segment, or end of spine
            if i + 1 < len(sorted_points):
                next_pt = sorted_points[i + 1]
                end_spine = target_spine_indices[next_pt]
                if end_spine < 0:
                    for j in range(next_pt, len(toc_targets)):
                        if target_spine_indices[j] >= 0:
                            end_spine = target_spine_indices[j]
                            break
                if end_spine < 0:
                    end_spine = len(spine_bookpaths)
            else:
                end_spine = len(spine_bookpaths)

            segment_ranges.append((start_spine, end_spine))

        # --- Track shared content docs: assign to first referencing segment ---
        assigned_docs = set()  # bookpaths already assigned to a segment

        # --- Build bookpath->manifest-id mapping ---
        bp_to_manifest = {}  # bookpath -> (item_id, href, media_type, properties)
        for item_id, (href, media_type, props) in manifest.items():
            bp = posixpath.normpath(posixpath.join(opf_dir, href)) if opf_dir else href
            bp_to_manifest[bp] = (item_id, href, media_type, props)

        # --- Generate each segment EPUB ---
        basename = os.path.splitext(os.path.basename(epub_path))[0]
        num_segments = len(segment_ranges)
        os.makedirs(output_dir, exist_ok=True)

        for seg_idx, (start_sp, end_sp) in enumerate(segment_ranges):
            seg_num = seg_idx + 1
            logger.write(f"正在生成第 {seg_num}/{num_segments} 段...")

            # Content docs for this segment (from spine)
            seg_content_bps = []
            for sp_idx in range(start_sp, end_sp):
                bp = spine_bookpaths[sp_idx]
                if bp not in assigned_docs:
                    seg_content_bps.append(bp)
                    assigned_docs.add(bp)

            if not seg_content_bps:
                logger.write(f"WARNING: 第 {seg_num} 段没有内容文档，跳过")
                continue

            # Collect referenced resources
            seg_resource_bps = _collect_referenced_resources(
                zf, set(seg_content_bps), manifest, opf_dir
            )

            # Remove content docs from resources (they're tracked separately)
            seg_resource_bps -= set(seg_content_bps)
            # Also remove nav and NCX from resources (we generate our own)
            if nav_item_path:
                seg_resource_bps.discard(nav_item_path)
            if ncx_item_path:
                seg_resource_bps.discard(ncx_item_path)

            # --- Build manifest for this segment ---
            seg_manifest_items = []
            seg_spine_items = []

            # Add content docs
            for bp in seg_content_bps:
                if bp in bp_to_manifest:
                    item_id, href, media_type, props = bp_to_manifest[bp]
                    # Strip nav property
                    clean_props = props.replace("nav", "").strip() if props else ""
                    rel_href = posixpath.relpath(bp, opf_dir)
                    seg_manifest_items.append((item_id, rel_href, media_type, clean_props))
                    # Add to spine
                    if bp in spine_id_map:
                        idref, linear, sp_props = spine_id_map[bp]
                        seg_spine_items.append((idref, linear, sp_props))

            # Add resource files
            for bp in sorted(seg_resource_bps):
                if bp in bp_to_manifest:
                    item_id, href, media_type, props = bp_to_manifest[bp]
                    clean_props = props.replace("nav", "").strip() if props else ""
                    rel_href = posixpath.relpath(bp, opf_dir)
                    seg_manifest_items.append((item_id, rel_href, media_type, clean_props))

            # --- Generate TOC for this segment ---
            # Filter toc_targets to only include entries whose href is in this segment
            seg_content_set = set(seg_content_bps)
            seg_toc_entries = []
            for t_idx, t in enumerate(toc_targets):
                # Check if this TOC entry's href belongs to this segment's content
                if t["href"] in seg_content_set:
                    seg_toc_entries.append(t)
                elif not t["href"]:
                    # Entries without href (like span-only): include if between segment boundaries
                    # Check if surrounding entries belong to this segment
                    # Simple heuristic: include if the next entry with href is in this segment
                    for next_idx in range(t_idx + 1, len(toc_targets)):
                        if toc_targets[next_idx]["href"]:
                            if toc_targets[next_idx]["href"] in seg_content_set:
                                seg_toc_entries.append(t)
                            break

            # --- Generate TOC file ---
            toc_path = None
            toc_content = None

            if is_epub3:
                toc_bookpath = posixpath.join(opf_dir, "nav_split.xhtml")
                toc_content = _generate_split_nav(seg_toc_entries, toc_bookpath)
                toc_path = toc_bookpath
                nav_id = "split-nav"
                rel_toc = posixpath.relpath(toc_bookpath, opf_dir)
                seg_manifest_items.append((nav_id, rel_toc, "application/xhtml+xml", "nav"))
            else:
                toc_bookpath = posixpath.join(opf_dir, "toc_split.ncx")
                toc_content = _generate_split_ncx(seg_toc_entries, toc_bookpath)
                toc_path = toc_bookpath
                ncx_id = "split-ncx"
                rel_toc = posixpath.relpath(toc_bookpath, opf_dir)
                seg_manifest_items.append((ncx_id, rel_toc, "application/x-dtbncx+xml", ""))

            # --- Generate OPF ---
            nav_id_for_opf = "split-nav" if is_epub3 else None
            opf_content = _generate_split_opf(
                metadata_elem, seg_manifest_items, seg_spine_items,
                version=version, nav_id=nav_id_for_opf
            )

            # --- Collect file data ---
            files_data = []
            all_seg_bps = set(seg_content_bps) | seg_resource_bps
            for bp in all_seg_bps:
                try:
                    data = zf.read(bp)
                    files_data.append((bp, data))
                except KeyError:
                    logger.write(f"WARNING: 文件不存在于 EPUB 中: {bp}")

            # --- Write EPUB ---
            seg_filename = f"{basename}_{seg_num:02d}.epub"
            seg_output_path = os.path.join(output_dir, seg_filename)

            _write_split_epub(
                seg_output_path,
                opf_path,  # Keep original OPF path
                opf_content,
                toc_path,
                toc_content,
                files_data,
            )
            logger.write(f"已生成: {seg_filename}")

    logger.write(f"拆分完成，共生成 {num_segments} 个文件")
    return 0
