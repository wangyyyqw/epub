# -*- coding: utf-8 -*-
# EPUB 合并模块：将多个 EPUB 文件合并为一个

import os
import sys
import re
import zipfile
import copy
import posixpath
from xml.etree import ElementTree
from urllib.parse import unquote, quote

try:
    from ..log import logwriter
except ImportError:
    from .log import logwriter

logger = logwriter()

# XML namespaces
NS_CONTAINER = "urn:oasis:names:tc:opendocument:xmlns:container"
NS_OPF = "http://www.idpf.org/2007/opf"
NS_DC = "http://purl.org/dc/elements/1.1/"
NS_XHTML = "http://www.w3.org/1999/xhtml"
NS_NCX = "http://www.daisy.org/z3986/2005/ncx/"
NS_EPUB = "http://www.idpf.org/2007/ops"

# Register namespaces to preserve prefixes during serialization
ElementTree.register_namespace("", NS_OPF)
ElementTree.register_namespace("dc", NS_DC)
ElementTree.register_namespace("opf", NS_OPF)
ElementTree.register_namespace("xhtml", NS_XHTML)
ElementTree.register_namespace("ncx", NS_NCX)
ElementTree.register_namespace("epub", NS_EPUB)


def _strip_ns(tag):
    """Remove namespace from an XML tag."""
    m = re.match(r"\{.*?\}(.*)", tag)
    return m.group(1) if m else tag


def _find_opf_path(epub_zip):
    """Find the OPF file path from container.xml or by scanning."""
    try:
        container = epub_zip.read("META-INF/container.xml").decode("utf-8")
        m = re.search(r'full-path="([^"]*\.opf)"', container, re.IGNORECASE)
        if m:
            return m.group(1)
    except KeyError:
        pass
    # Fallback: find first .opf in namelist
    for name in epub_zip.namelist():
        if name.lower().endswith(".opf"):
            return name
    return None


def _parse_opf(epub_zip, opf_path):
    """Parse OPF and return (version, metadata_elem, manifest_dict, spine_list, opf_dir, opf_tree).

    manifest_dict: {id: (href, media_type, properties)}
    spine_list: [(idref, linear, properties)]
    """
    opf_content = epub_zip.read(opf_path).decode("utf-8")
    root = ElementTree.fromstring(opf_content)
    version = root.get("version", "3.0")
    opf_dir = posixpath.dirname(opf_path)

    metadata_elem = None
    manifest_elem = None
    spine_elem = None
    for child in root:
        tag = _strip_ns(child.tag)
        if tag == "metadata":
            metadata_elem = child
        elif tag == "manifest":
            manifest_elem = child
        elif tag == "spine":
            spine_elem = child

    # Parse manifest
    manifest = {}
    if manifest_elem is not None:
        for item in manifest_elem:
            item_id = item.get("id")
            href = unquote(item.get("href", ""))
            media_type = item.get("media-type", "")
            properties = item.get("properties", "")
            if item_id and href:
                manifest[item_id] = (href, media_type, properties)

    # Parse spine
    spine = []
    toc_id = ""
    if spine_elem is not None:
        toc_id = spine_elem.get("toc", "")
        for itemref in spine_elem:
            idref = itemref.get("idref", "")
            linear = itemref.get("linear", "")
            props = itemref.get("properties", "")
            if idref:
                spine.append((idref, linear, props))

    return version, metadata_elem, manifest, spine, opf_dir, toc_id


def _parse_toc_ncx(epub_zip, ncx_path):
    """Parse EPUB2 NCX TOC, return list of (title, href) tuples."""
    try:
        ncx_content = epub_zip.read(ncx_path).decode("utf-8")
    except KeyError:
        return []
    root = ElementTree.fromstring(ncx_content)
    ncx_dir = posixpath.dirname(ncx_path)
    entries = []

    def _walk_navpoints(parent):
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
                        href = posixpath.normpath(posixpath.join(ncx_dir, src)) if src else ""
                if title or href:
                    entries.append((title, href))
                _walk_navpoints(child)

    # Find navMap
    for child in root:
        if _strip_ns(child.tag) == "navMap":
            _walk_navpoints(child)
            break
    return entries


def _parse_toc_nav(epub_zip, nav_path):
    """Parse EPUB3 nav document, return list of (title, href) tuples."""
    try:
        nav_content = epub_zip.read(nav_path).decode("utf-8")
    except KeyError:
        return []
    root = ElementTree.fromstring(nav_content)
    nav_dir = posixpath.dirname(nav_path)
    entries = []

    def _find_toc_nav(elem):
        """Find the nav element with epub:type='toc'."""
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

    def _walk_nav_list(ol_elem):
        for li in ol_elem:
            if _strip_ns(li.tag) != "li":
                continue
            for child in li:
                child_tag = _strip_ns(child.tag)
                if child_tag == "a":
                    title = "".join(child.itertext()).strip()
                    href_attr = child.get("href", "")
                    href = posixpath.normpath(posixpath.join(nav_dir, href_attr)) if href_attr else ""
                    entries.append((title, href))
                elif child_tag == "span":
                    title = "".join(child.itertext()).strip()
                    entries.append((title, ""))
                elif child_tag == "ol":
                    _walk_nav_list(child)

    # Search for body > nav[epub:type=toc] > ol
    nav_elem = _find_toc_nav(root)
    if nav_elem is not None:
        for child in nav_elem:
            if _strip_ns(child.tag) == "ol":
                _walk_nav_list(child)
    return entries


def _detect_conflicts(all_book_files):
    """Detect filename conflicts across multiple EPUBs.

    Args:
        all_book_files: list of sets, each set contains bookpaths for one EPUB

    Returns:
        rename_map: list of dicts, one per EPUB. Each dict maps old_bookpath -> new_bookpath
    """
    # Collect all paths from all books
    seen = set()
    conflict_paths = set()
    for book_files in all_book_files:
        for fp in book_files:
            if fp in seen:
                conflict_paths.add(fp)
            seen.add(fp)

    rename_maps = []
    for vol_idx, book_files in enumerate(all_book_files):
        rmap = {}
        if vol_idx == 0:
            # First EPUB keeps original names
            rename_maps.append(rmap)
            continue
        for fp in book_files:
            if fp in conflict_paths:
                dirname = posixpath.dirname(fp)
                basename = posixpath.basename(fp)
                new_name = f"vol{vol_idx + 1}_{basename}"
                new_path = posixpath.join(dirname, new_name) if dirname else new_name
                rmap[fp] = new_path
        rename_maps.append(rmap)
    return rename_maps


def _update_references_in_content(content_bytes, rename_map, content_bookpath):
    """Update href and src references in an XHTML/HTML content document.

    Args:
        content_bytes: bytes of the content document
        rename_map: dict mapping old_bookpath -> new_bookpath
        content_bookpath: bookpath of this content document (for resolving relative refs)

    Returns:
        Updated content as bytes
    """
    if not rename_map:
        return content_bytes

    try:
        text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return content_bytes

    content_dir = posixpath.dirname(content_bookpath)

    def _replace_attr(match):
        attr_name = match.group(1)
        quote_char = match.group(2)
        value = match.group(3)

        # Split off fragment
        frag = ""
        if "#" in value:
            value, frag = value.split("#", 1)
            frag = "#" + frag

        if not value:
            return match.group(0)

        # Resolve to bookpath
        resolved = posixpath.normpath(posixpath.join(content_dir, unquote(value)))

        if resolved in rename_map:
            new_resolved = rename_map[resolved]
            # Compute new relative path
            new_rel = posixpath.relpath(new_resolved, content_dir)
            safe_chars = "/:@!$&'()*+,;="
            quoted_rel = quote(new_rel, safe=safe_chars)
            return f'{attr_name}={quote_char}{quoted_rel}{frag}{quote_char}'
        return match.group(0)

    # Match href="..." and src="..."
    pattern = r'((?:href|src))\s*=\s*(["\'])(.*?)\2'
    text = re.sub(pattern, _replace_attr, text)
    return text.encode("utf-8")


def _update_references_in_css(css_bytes, rename_map, css_bookpath):
    """Update url() references in CSS files."""
    if not rename_map:
        return css_bytes

    try:
        text = css_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return css_bytes

    css_dir = posixpath.dirname(css_bookpath)

    def _replace_url(match):
        quote_char = match.group(1) or ""
        value = match.group(2)

        if not value or value.startswith("data:"):
            return match.group(0)

        resolved = posixpath.normpath(posixpath.join(css_dir, unquote(value)))
        if resolved in rename_map:
            new_resolved = rename_map[resolved]
            new_rel = posixpath.relpath(new_resolved, css_dir)
            return f'url({quote_char}{new_rel}{quote_char})'
        return match.group(0)

    pattern = r'url\((["\']?)([^)]*?)\1\)'
    text = re.sub(pattern, _replace_url, text)
    return text.encode("utf-8")


def _generate_merged_opf(metadata_elem, all_manifest_items, all_spine_items, version="3.0", nav_id=None):
    """Generate a merged OPF XML string.

    Args:
        metadata_elem: ElementTree element for metadata (from first EPUB)
        all_manifest_items: list of (id, href, media_type, properties)
        all_spine_items: list of (idref, linear, properties)
        version: OPF version string
        nav_id: id of the nav document item (for EPUB3)

    Returns:
        OPF XML string
    """
    # Build OPF manually for clean output
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(f'<package xmlns="http://www.idpf.org/2007/opf" version="{version}" unique-identifier="merged-id">')

    # Metadata
    lines.append('  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">')
    if metadata_elem is not None:
        for child in metadata_elem:
            tag = _strip_ns(child.tag)
            if tag == "identifier":
                lines.append(f'    <dc:identifier id="merged-id">{child.text or "merged-epub"}</dc:identifier>')
            elif tag in ("title", "creator", "language", "subject", "source", "publisher", "date", "description"):
                text = child.text or ""
                lines.append(f'    <dc:{tag}>{text}</dc:{tag}>')
            elif tag == "meta":
                # Preserve meta elements
                name = child.get("name", "")
                content = child.get("content", "")
                prop = child.get("property", "")
                if name and content:
                    lines.append(f'    <meta name="{name}" content="{content}"/>')
                elif prop:
                    text = child.text or ""
                    lines.append(f'    <meta property="{prop}">{text}</meta>')
    else:
        lines.append('    <dc:identifier id="merged-id">merged-epub</dc:identifier>')
        lines.append('    <dc:title>Merged EPUB</dc:title>')
        lines.append('    <dc:language>en</dc:language>')

    # Ensure required EPUB3 modified meta
    if version == "3.0":
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        lines.append(f'    <meta property="dcterms:modified">{now}</meta>')

    lines.append('  </metadata>')

    # Manifest
    lines.append('  <manifest>')
    for item_id, href, media_type, properties in all_manifest_items:
        props_attr = f' properties="{properties}"' if properties else ""
        href_escaped = href.replace("&", "&amp;")
        lines.append(f'    <item id="{item_id}" href="{href_escaped}" media-type="{media_type}"{props_attr}/>')
    lines.append('  </manifest>')

    # Spine
    lines.append('  <spine>')
    for idref, linear, properties in all_spine_items:
        attrs = f'idref="{idref}"'
        if linear:
            attrs += f' linear="{linear}"'
        if properties:
            attrs += f' properties="{properties}"'
        lines.append(f'    <itemref {attrs}/>')
    lines.append('  </spine>')

    lines.append('</package>')
    return "\n".join(lines)


def _generate_merged_nav(all_toc_entries, nav_bookpath):
    """Generate a merged EPUB3 nav document.

    Args:
        all_toc_entries: list of (epub_title, [(title, href), ...]) per input EPUB
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

    for epub_title, entries in all_toc_entries:
        lines.append(f'    <li>')
        lines.append(f'      <span>{epub_title}</span>')
        if entries:
            lines.append(f'      <ol>')
            for title, href in entries:
                if href:
                    rel_href = posixpath.relpath(href, nav_dir)
                    rel_href = rel_href.replace("\\", "/")
                    lines.append(f'        <li><a href="{rel_href}">{title}</a></li>')
                else:
                    lines.append(f'        <li><span>{title}</span></li>')
            lines.append(f'      </ol>')
        lines.append(f'    </li>')

    lines.append('  </ol>')
    lines.append('</nav>')
    lines.append('</body>')
    lines.append('</html>')
    return "\n".join(lines)


def _write_epub(output_path, mimetype_bytes, container_xml, opf_path, opf_content, nav_path, nav_content, all_files):
    """Write a valid EPUB file.

    Args:
        output_path: output file path
        mimetype_bytes: mimetype file content
        container_xml: META-INF/container.xml content
        opf_path: path to OPF inside EPUB
        opf_content: OPF XML string
        nav_path: path to nav document inside EPUB (or None)
        nav_content: nav XHTML string (or None)
        all_files: list of (bookpath, bytes_data) for all content files
    """
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # mimetype must be first and stored (not compressed)
        zf.writestr("mimetype", mimetype_bytes, compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr(opf_path, opf_content)
        if nav_path and nav_content:
            zf.writestr(nav_path, nav_content)

        written = {"mimetype", "META-INF/container.xml", opf_path}
        if nav_path:
            written.add(nav_path)

        for bookpath, data in all_files:
            if bookpath not in written:
                zf.writestr(bookpath, data)
                written.add(bookpath)


def run(input_paths, output_dir):
    """Merge multiple EPUB files into one.

    Args:
        input_paths: list of EPUB file paths, in merge order
        output_dir: output directory

    Returns:
        0 on success, non-zero on failure
    """
    if not input_paths or len(input_paths) < 2:
        logger.write("ERROR: 至少需要 2 个 EPUB 文件进行合并")
        return 1

    # Validate all input files
    for p in input_paths:
        if not os.path.exists(p):
            logger.write(f"ERROR: 文件不存在: {p}")
            return 1
        if not zipfile.is_zipfile(p):
            logger.write(f"ERROR: 不是有效的 EPUB/ZIP 文件: {p}")
            return 1

    try:
        return _do_merge(input_paths, output_dir)
    except Exception as e:
        logger.write(f"ERROR: 合并失败: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


def _do_merge(input_paths, output_dir):
    """Core merge logic."""
    epub_data = []  # list of parsed EPUB data dicts
    all_book_file_sets = []  # for conflict detection

    # Phase 1: Parse all EPUBs
    for idx, epub_path in enumerate(input_paths):
        logger.write(f"正在解析第 {idx + 1} 个 EPUB: {os.path.basename(epub_path)}")
        zf = zipfile.ZipFile(epub_path, "r")

        opf_path = _find_opf_path(zf)
        if not opf_path:
            logger.write(f"ERROR: 无法找到 OPF 文件: {epub_path}")
            zf.close()
            return 1

        version, metadata_elem, manifest, spine, opf_dir, toc_id = _parse_opf(zf, opf_path)

        # Collect all bookpaths (relative to EPUB root)
        book_files = set()
        for item_id, (href, media_type, props) in manifest.items():
            bookpath = posixpath.normpath(posixpath.join(opf_dir, href)) if opf_dir else href
            book_files.add(bookpath)

        all_book_file_sets.append(book_files)

        # Parse TOC
        toc_entries = []
        nav_path = None
        # Try EPUB3 nav first
        for item_id, (href, media_type, props) in manifest.items():
            if "nav" in props:
                nav_path = posixpath.normpath(posixpath.join(opf_dir, href)) if opf_dir else href
                toc_entries = _parse_toc_nav(zf, nav_path)
                break
        # Fallback to NCX
        if not toc_entries and toc_id and toc_id in manifest:
            ncx_href = manifest[toc_id][0]
            ncx_path = posixpath.normpath(posixpath.join(opf_dir, ncx_href)) if opf_dir else ncx_href
            toc_entries = _parse_toc_ncx(zf, ncx_path)

        epub_data.append({
            "path": epub_path,
            "zip": zf,
            "opf_path": opf_path,
            "opf_dir": opf_dir,
            "version": version,
            "metadata": metadata_elem,
            "manifest": manifest,
            "spine": spine,
            "toc_id": toc_id,
            "toc_entries": toc_entries,
            "book_files": book_files,
        })

    # Phase 2: Detect conflicts and build rename maps
    rename_maps = _detect_conflicts(all_book_file_sets)

    # Phase 3: Build merged content
    merged_opf_dir = "OEBPS"
    merged_opf_path = "OEBPS/content.opf"
    merged_nav_bookpath = "OEBPS/nav.xhtml"

    all_manifest_items = []
    all_spine_items = []
    all_toc_for_nav = []
    all_content_files = []  # (bookpath, bytes)
    used_ids = set()

    # Determine output version: if any version differs, use 3.0
    versions = [d["version"] for d in epub_data]
    output_version = "3.0" if len(set(versions)) > 1 else versions[0]
    # If mixed or any is not 3.0 but we have mixed, force 3.0
    if any(v != versions[0] for v in versions):
        output_version = "3.0"

    for vol_idx, data in enumerate(epub_data):
        zf = data["zip"]
        manifest = data["manifest"]
        spine = data["spine"]
        opf_dir = data["opf_dir"]
        rename_map = rename_maps[vol_idx]
        epub_title = os.path.splitext(os.path.basename(data["path"]))[0]

        # Build bookpath rename map (old bookpath -> new bookpath)
        bookpath_rename = {}
        for old_bp, new_bp in rename_map.items():
            bookpath_rename[old_bp] = new_bp

        # Process manifest items
        id_remap = {}  # old_id -> new_id
        for item_id, (href, media_type, props) in manifest.items():
            bookpath = posixpath.normpath(posixpath.join(opf_dir, href)) if opf_dir else href

            # Skip NCX and nav for individual EPUBs (we generate our own)
            if media_type == "application/x-dtbncx+xml":
                continue
            if "nav" in props:
                continue

            # Apply rename if conflicting
            final_bookpath = bookpath_rename.get(bookpath, bookpath)

            # Compute href relative to merged OPF dir
            merged_href = posixpath.relpath(final_bookpath, merged_opf_dir)

            # Ensure unique ID
            new_id = item_id
            if new_id in used_ids:
                new_id = f"vol{vol_idx + 1}_{item_id}"
            while new_id in used_ids:
                new_id = f"vol{vol_idx + 1}_{item_id}_{len(used_ids)}"
            used_ids.add(new_id)
            id_remap[item_id] = new_id

            # Strip nav properties from non-nav items
            merged_props = props.replace("nav", "").strip() if props else ""

            all_manifest_items.append((new_id, merged_href, media_type, merged_props))

            # Read and process file content
            try:
                file_data = zf.read(bookpath)
            except KeyError:
                logger.write(f"WARNING: 文件不存在于 EPUB 中: {bookpath}")
                continue

            # Update references in content documents and CSS
            if media_type == "application/xhtml+xml" or bookpath.lower().endswith((".xhtml", ".html")):
                file_data = _update_references_in_content(file_data, bookpath_rename, bookpath)
            elif media_type == "text/css" or bookpath.lower().endswith(".css"):
                file_data = _update_references_in_css(file_data, bookpath_rename, bookpath)

            all_content_files.append((final_bookpath, file_data))

        # Process spine items
        for idref, linear, props in spine:
            new_idref = id_remap.get(idref, idref)
            if new_idref in used_ids:  # Only add if the item exists in manifest
                all_spine_items.append((new_idref, linear, props))

        # Collect TOC entries with updated paths
        updated_toc = []
        for title, href in data["toc_entries"]:
            new_href = bookpath_rename.get(href, href)
            updated_toc.append((title, new_href))
        all_toc_for_nav.append((epub_title, updated_toc))

    # Add nav document to manifest
    nav_id = "merged-nav"
    all_manifest_items.append((nav_id, posixpath.relpath(merged_nav_bookpath, merged_opf_dir),
                               "application/xhtml+xml", "nav"))
    used_ids.add(nav_id)

    # Phase 4: Generate merged OPF
    first_metadata = epub_data[0]["metadata"]
    opf_content = _generate_merged_opf(
        first_metadata, all_manifest_items, all_spine_items,
        version=output_version, nav_id=nav_id
    )

    # Phase 5: Generate merged TOC (nav document)
    nav_content = _generate_merged_nav(all_toc_for_nav, merged_nav_bookpath)

    # Phase 6: Write output EPUB
    first_name = os.path.splitext(os.path.basename(input_paths[0]))[0]
    output_filename = f"merged_{first_name}.epub"
    output_path = os.path.join(output_dir, output_filename)

    container_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    container_xml += '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
    container_xml += '  <rootfiles>\n'
    container_xml += f'    <rootfile full-path="{merged_opf_path}" media-type="application/oebps-package+xml"/>\n'
    container_xml += '  </rootfiles>\n'
    container_xml += '</container>'

    _write_epub(
        output_path,
        b"application/epub+zip",
        container_xml,
        merged_opf_path,
        opf_content,
        merged_nav_bookpath,
        nav_content,
        all_content_files,
    )

    # Close all zip files
    for data in epub_data:
        data["zip"].close()

    logger.write(f"合并完成: {output_path}")
    return 0
