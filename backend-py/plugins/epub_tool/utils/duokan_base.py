"""
多看脚注转换共享基础模块。

提供阅微→多看和掌阅→多看共用的：
- HTML 工具函数（escape、namespace 注入）
- 脚注区域构建和注入
- EPUB 处理基类（note.png 注入、图片目录检测、OPF 处理、文件遍历）
"""
import zipfile
import os
import traceback
import re
import posixpath

try:
    from ..log import logwriter
except ImportError:
    from .log import logwriter

logger = logwriter()

NOTE_PNG_PATH = os.path.join(os.path.dirname(__file__), "note.png")


# ── 共享工具函数 ──────────────────────────────────────────────

def escape_html(text):
    """Escape HTML special characters."""
    if not text:
        return text
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    return text


def add_epub_namespace(html_content):
    """Add xmlns:epub namespace to <html> tag if missing."""
    epub_ns_pattern = r'xmlns:epub\s*=\s*["\']http://www\.idpf\.org/2007/ops["\']'
    if re.search(epub_ns_pattern, html_content):
        return html_content

    pattern = r'(<html\b[^>]*)(>)'

    def _add_ns(match):
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

    return re.sub(pattern, _add_ns, html_content, count=1, flags=re.IGNORECASE | re.DOTALL)


def build_footnote_section(footnotes):
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
        nums = re.findall(r'(\d+)', note['id'])
        return [int(n) for n in nums] if nums else [0]

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


def inject_footnotes_before_body_close(text_content, footnote_section):
    """Insert footnote section before </body>."""
    if not footnote_section:
        return text_content
    if '</body>' in text_content:
        parts = text_content.rsplit('</body>', 1)
        return parts[0] + footnote_section + '</body>' + (parts[1] if len(parts) > 1 else '')
    return text_content + footnote_section


# ── EPUB 处理基类 ─────────────────────────────────────────────

class DuokanConverterBase:
    """阅微/掌阅→多看转换器的共享基类。"""

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
        for name in self.epub.namelist():
            if name.lower().endswith('note.png'):
                return True
        return False

    def _inject_note_png(self):
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
        try:
            from bs4 import BeautifulSoup
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

                if self._note_png_injected and not any(
                    item_tag.get('href', '').endswith('note.png')
                    for item_tag in manifest.find_all('item')
                ):
                    note_png_full = f"{self._images_dir}/note.png"
                    opf_dir = posixpath.dirname(filename)
                    rel_href = posixpath.relpath(note_png_full, opf_dir) if opf_dir else note_png_full

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
        """子类必须实现：处理 HTML/XHTML 文件中的脚注转换。"""
        raise NotImplementedError

    def process(self):
        try:
            self._has_note_png = self._check_note_png_exists()
            self._detect_images_dir()
            written_files = set()
            opf_items = []

            for item in self.epub.infolist():
                if item.filename in written_files:
                    logger.write(f"跳过重复文件: {item.filename}")
                    continue

                content = self.epub.read(item.filename)

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
