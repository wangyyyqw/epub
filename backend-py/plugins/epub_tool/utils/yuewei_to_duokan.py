import zipfile
import os
from bs4 import BeautifulSoup
import traceback
import re
import shutil

try:
    from ..log import logwriter
except ImportError:
    from .log import logwriter

logger = logwriter()

# note.png path relative to this file
NOTE_PNG_PATH = os.path.join(os.path.dirname(__file__), "note.png")


def _escape_html(text):
    """Escape HTML special characters."""
    if not text:
        return text
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    return text


def _add_epub_namespace(html_content):
    """Add xmlns:epub namespace to <html> tag if missing."""
    epub_ns_pattern = r'xmlns:epub\s*=\s*["\']http://www\.idpf\.org/2007/ops["\']'
    if re.search(epub_ns_pattern, html_content):
        return html_content

    pattern = r'(<html\b[^>]*)(>)'

    def add_namespace(match):
        tag_start = match.group(1)
        tag_end = match.group(2)
        if re.search(epub_ns_pattern, tag_start):
            return match.group(0)

        xmlns_match = re.search(
            r'xmlns\s*=\s*["\']http://www\.w3\.org/1999/xhtml["\']', tag_start
        )
        if xmlns_match:
            end_pos = xmlns_match.end()
            return (
                tag_start[:end_pos]
                + ' xmlns:epub="http://www.idpf.org/2007/ops"'
                + tag_start[end_pos:]
                + tag_end
            )
        return tag_start + ' xmlns:epub="http://www.idpf.org/2007/ops"' + tag_end

    return re.sub(pattern, add_namespace, html_content, count=1, flags=re.IGNORECASE | re.DOTALL)


def _extract_zy_footnote_content(text_content, match_start):
    """Extract zy-footnote or alt content near a match position."""
    # Search within a reasonable window after the match
    search_end = min(match_start + 800, len(text_content))
    window = text_content[match_start:search_end]

    # Try zy-footnote first, then fall back to alt
    m = re.search(r'zy-footnote="([^"]*)"', window)
    if not m:
        m = re.search(r'alt="([^"]*)"', window)
    return m.group(1) if m else ""


def _collect_existing_duokan_footnotes(text_content):
    """Collect footnotes from existing duokan-footnote anchors that lack aside elements."""
    footnotes = []

    # Three patterns for different attribute orderings
    patterns = [
        # href before id
        (r'<a[^>]*class="[^"]*duokan-footnote[^"]*"[^>]*href="#([^"]+)"[^>]*id="([^"]+)"[^>]*>',
         lambda m: (m.group(1), m.group(2))),
        # id before href
        (r'<a[^>]*id="([^"]+)"[^>]*class="[^"]*duokan-footnote[^"]*"[^>]*href="#([^"]+)"[^>]*>',
         lambda m: (m.group(2), m.group(1))),
        # no id attribute
        (r'<a(?![^>]*\bid\s*=)[^>]*class="[^"]*duokan-footnote[^"]*"[^>]*href="#([^"]+)"[^>]*>',
         lambda m: (m.group(1), m.group(1) + "_ref")),
    ]

    seen_ids = set()
    for pattern, extract_ids in patterns:
        for match in re.finditer(pattern, text_content):
            note_id, note_ref_id = extract_ids(match)
            if note_id in seen_ids:
                continue

            # Skip if aside already exists
            if re.search(rf'<aside[^>]*id="{re.escape(note_id)}"[^>]*>', text_content):
                continue

            note_content = _extract_zy_footnote_content(text_content, match.start())
            seen_ids.add(note_id)
            footnotes.append({
                'id': note_id,
                'ref_id': note_ref_id,
                'content': _escape_html(note_content),
            })

    return footnotes


def _convert_yuewei_spans(text_content):
    """Convert yuewei reader footnote spans to duokan format. Returns (modified_content, footnotes)."""
    # Match yuewei footnote spans (both class orderings)
    span_pattern1 = r'<span[^>]*class="[^"]*reader[^"]*js_readerFooterNote[^"]*"[^>]*data-wr-footernote="([^"]*)"[^>]*>\s*</span>'
    span_pattern2 = r'<span[^>]*class="[^"]*js_readerFooterNote[^"]*reader[^"]*"[^>]*data-wr-footernote="([^"]*)"[^>]*>\s*</span>'

    matches = list(re.finditer(span_pattern1, text_content))
    seen_spans = {m.group(0) for m in matches}
    for m in re.finditer(span_pattern2, text_content):
        if m.group(0) not in seen_spans:
            matches.append(m)
    matches.sort(key=lambda m: m.start())

    if not matches:
        return text_content, []

    # Assign sequential numbers by position
    position_numbers = {m.start(): i for i, m in enumerate(matches, 1)}
    footnotes = []

    # Replace in reverse to preserve positions
    for match in reversed(matches):
        note_number = position_numbers[match.start()]
        note_id = f"note{note_number}"
        note_ref_id = f"note_ref{note_number}"
        note_content = _escape_html(match.group(1))

        replacement = (
            f'      <sup>\n'
            f'         <a class="duokan-footnote" epub:type="noteref" href="#{note_id}" id="{note_ref_id}">\n'
            f'           <img alt="note" class="zhangyue-footnote" src="../Images/note.png" zy-footnote="{note_content}"/>\n'
            f'         </a>\n'
            f'       </sup>'
        )

        start, end = match.span()
        text_content = text_content[:start] + replacement + text_content[end:]

        footnotes.append({
            'id': note_id,
            'ref_id': note_ref_id,
            'content': note_content,
        })

    return text_content, footnotes


def _build_footnote_section(footnotes):
    """Build the aside footnote HTML section from a list of footnotes."""
    if not footnotes:
        return ""

    # Deduplicate by id
    seen = set()
    unique = []
    for note in footnotes:
        if note['id'] not in seen:
            seen.add(note['id'])
            unique.append(note)

    # Sort by numeric suffix
    def sort_key(note):
        m = re.search(r'(\d+)', note['id'])
        return int(m.group(1)) if m else 0

    unique.sort(key=sort_key)

    parts = ["\n\n"]
    for note in unique:
        parts.append(
            f'  <aside epub:type="footnote" id="{note["id"]}">\n'
            f'   <ol class="duokan-footnote-content" style="list-style:none">\n'
            f'   <li class="duokan-footnote-item" id="{note["id"]}">\n'
            f'   <p><a href="#{note["ref_id"]}">{note["content"]}</a></p>\n'
            f'   </li>\n'
            f'   </ol>\n'
            f'   </aside>\n'
        )
    return "".join(parts)


def _inject_footnotes_before_body_close(text_content, footnote_section):
    """Insert footnote section before </body>."""
    if not footnote_section:
        return text_content
    if '</body>' in text_content:
        parts = text_content.rsplit('</body>', 1)
        return parts[0] + footnote_section + '</body>' + (parts[1] if len(parts) > 1 else '')
    return text_content + footnote_section




class YueweiToDuokan:
    def __init__(self, epub_path, output_path):
        if not os.path.exists(epub_path):
            raise Exception("EPUB文件不存在")

        self.epub_path = os.path.normpath(epub_path)
        self.epub = zipfile.ZipFile(epub_path)

        if output_path and os.path.exists(output_path):
            if os.path.isfile(output_path):
                raise Exception("输出路径不能是文件")
        else:
            output_path = os.path.dirname(epub_path)

        self.output_path = os.path.normpath(output_path)
        self.file_write_path = os.path.join(
            self.output_path,
            os.path.basename(self.epub_path).replace(".epub", "_duokan.epub"),
        )

        if os.path.exists(self.file_write_path):
            os.remove(self.file_write_path)

        self.target_epub = zipfile.ZipFile(
            self.file_write_path, "w", zipfile.ZIP_DEFLATED,
        )
        self._has_note_png = False
        self._note_png_injected = False
        self._images_dir = "Images"

    def _check_note_png_exists(self):
        """Check if note.png already exists in the source EPUB."""
        for name in self.epub.namelist():
            if name.lower().endswith('note.png'):
                return True
        return False

    def _inject_note_png(self):
        """Inject note.png into the EPUB if it doesn't exist and we have a local copy."""
        if self._note_png_injected or self._has_note_png:
            return
        if os.path.exists(NOTE_PNG_PATH):
            target_path = f"{self._images_dir}/note.png"
            with open(NOTE_PNG_PATH, 'rb') as f:
                self.target_epub.writestr(target_path, f.read())
            self._note_png_injected = True
            logger.write(f"注入 note.png 到 {target_path}")

    def _detect_images_dir(self):
        """从 EPUB 文件列表中检测实际的图片目录名。"""
        for name in self.epub.namelist():
            lower = name.lower()
            if '/images/' in lower or lower.startswith('images/'):
                parts = name.split('/')
                for p in parts:
                    if p.lower() == 'images':
                        self._images_dir = name[:name.index(p) + len(p)]
                        return
                break
            elif '/image/' in lower or lower.startswith('image/'):
                idx = lower.find('image/')
                self._images_dir = name[:idx + len('image')].rstrip('/')
                return

    def _process_opf(self, filename, content):
        """Process OPF file: remove duplicate manifest items."""
        try:
            import posixpath
            text = content.decode('utf-8')
            soup = BeautifulSoup(text, 'xml')
            manifest = soup.find('manifest')
            if manifest:
                seen_hrefs = set()
                for item_tag in manifest.find_all('item'):
                    href = item_tag.get('href')
                    if href:
                        if href in seen_hrefs:
                            logger.write(f"移除OPF中重复项: {href}")
                            item_tag.decompose()
                        else:
                            seen_hrefs.add(href)

                # Add note.png to manifest if we injected it
                if self._note_png_injected and not any(
                    item_tag.get('href', '').endswith('note.png')
                    for item_tag in manifest.find_all('item')
                ):
                    note_png_full = f"{self._images_dir}/note.png"
                    opf_dir = posixpath.dirname(filename)
                    if opf_dir:
                        rel_href = posixpath.relpath(note_png_full, opf_dir)
                    else:
                        rel_href = note_png_full

                    new_item = soup.new_tag('item')
                    new_item['id'] = 'note-png'
                    new_item['href'] = rel_href
                    new_item['media-type'] = 'image/png'
                    manifest.append(new_item)
                    logger.write(f"OPF manifest 添加 note.png: {rel_href}")

            return str(soup).encode('utf-8')
        except Exception as e:
            logger.write(f"处理OPF文件 {filename} 失败: {e}")
            traceback.print_exc()
            return content

    def _process_html(self, filename, content):
        """Process HTML/XHTML file: convert yuewei footnotes to duokan format."""
        try:
            text = content.decode('utf-8')
            text = _add_epub_namespace(text)

            # Convert yuewei spans to duokan format
            text, footnotes = _convert_yuewei_spans(text)

            # Collect existing duokan footnotes that need aside elements
            existing_footnotes = _collect_existing_duokan_footnotes(text)
            footnotes.extend(existing_footnotes)

            # If we found any footnotes, inject note.png and build footnote section
            if footnotes:
                self._inject_note_png()
                footnote_section = _build_footnote_section(footnotes)
                text = _inject_footnotes_before_body_close(text, footnote_section)

            return text.encode('utf-8')
        except Exception as e:
            logger.write(f"处理文件 {filename} 失败: {e}")
            traceback.print_exc()
            return content

    def process(self):
        try:
            self._has_note_png = self._check_note_png_exists()
            self._detect_images_dir()
            written_files = set()

            # Process all files, saving OPF for last so we can update manifest
            opf_items = []

            for item in self.epub.infolist():
                if item.filename in written_files:
                    logger.write(f"跳过重复文件: {item.filename}")
                    continue

                content = self.epub.read(item.filename)

                # mimetype must be stored uncompressed per EPUB spec
                if item.filename == 'mimetype':
                    self.target_epub.writestr(item.filename, content, compress_type=zipfile.ZIP_STORED)
                    written_files.add(item.filename)
                elif item.filename.lower().endswith('.opf'):
                    opf_items.append((item, content))
                    written_files.add(item.filename)
                elif item.filename.lower().endswith(('.html', '.xhtml', '.htm')):
                    new_content = self._process_html(item.filename, content)
                    self.target_epub.writestr(item.filename, new_content)
                    written_files.add(item.filename)
                else:
                    self.target_epub.writestr(item, content)
                    written_files.add(item.filename)

            # Process OPF files last (after note.png injection decision)
            for item, content in opf_items:
                new_content = self._process_opf(item.filename, content)
                self.target_epub.writestr(item.filename, new_content)

            self.close_file()
            return 0, self.file_write_path

        except Exception as e:
            logger.write(f"处理EPUB失败: {e}")
            traceback.print_exc()
            self.close_file()
            self.fail_del_target()
            return 1, str(e)

    def close_file(self):
        if self.epub:
            self.epub.close()
        if self.target_epub:
            self.target_epub.close()

    def fail_del_target(self):
        if self.file_write_path and os.path.exists(self.file_write_path):
            os.remove(self.file_write_path)


def run(epub_path, output_path=None):
    logger.write(f"\\n正在执行阅微转多看: {epub_path}")
    tool = YueweiToDuokan(epub_path, output_path)
    return tool.process()
