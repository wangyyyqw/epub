"""
掌阅转多看：将掌阅格式的脚注转换为标准多看格式。

掌阅格式特点：
- <aside> 元素散落在正文中，紧跟 <sup> 标签
- <li> 内容没有 <p> 包裹，没有返回链接
- <img> 使用 class="epub-footnote zhangyue-footnote qqreader-footnote"

转换后：
- 移除正文中散落的 <aside> 元素
- 在 </body> 前集中生成标准多看格式的脚注区域
- 每个脚注有 <p> 包裹和返回链接
"""
import zipfile
import os
import traceback
import re

try:
    from ..log import logwriter
except ImportError:
    from .log import logwriter

logger = logwriter()

NOTE_PNG_PATH = os.path.join(os.path.dirname(__file__), "note.png")


def _escape_html(text):
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


def _convert_zhangyue_inline_asides(text_content):
    """
    提取正文中散落的掌阅 <aside> 脚注，移除原位置，收集脚注内容。
    
    掌阅格式：
    <aside epub:type="footnote" id="footnote-X-Y">
      <ol class="duokan-footnote-content" ...>
        <li class="duokan-footnote-item" id="footnote-X-Y">脚注内容</li>
      </ol>
    </aside>
    <sup><a class="duokan-footnote" epub:type="noteref" href="#footnote-X-Y">
      <img ... class="epub-footnote zhangyue-footnote qqreader-footnote"/>
    </a></sup>
    
    Returns: (modified_content, footnotes_list)
    """
    # 匹配散落在正文中的 <aside> 元素
    aside_pattern = re.compile(
        r'<aside[^>]*epub:type="footnote"[^>]*id="([^"]+)"[^>]*>'
        r'(.*?)</aside>',
        re.DOTALL | re.IGNORECASE
    )

    footnotes = []
    seen_ids = set()

    for match in aside_pattern.finditer(text_content):
        note_id = match.group(1)
        aside_inner = match.group(2)

        if note_id in seen_ids:
            continue
        seen_ids.add(note_id)

        # 从 <li> 中提取脚注文本内容
        li_match = re.search(
            r'<li[^>]*class="duokan-footnote-item"[^>]*>(.*?)</li>',
            aside_inner, re.DOTALL | re.IGNORECASE
        )
        note_content = ""
        if li_match:
            # 去除内部 HTML 标签，只保留纯文本
            raw = li_match.group(1).strip()
            note_content = re.sub(r'<[^>]+>', '', raw).strip()

        # 查找对应的 <a> 引用，提取 ref id
        ref_pattern = re.compile(
            r'<a[^>]*class="[^"]*duokan-footnote[^"]*"[^>]*href="#'
            + re.escape(note_id) + r'"[^>]*id="([^"]+)"',
            re.IGNORECASE
        )
        ref_match = ref_pattern.search(text_content)
        if not ref_match:
            # 尝试 id 在 href 前面的情况
            ref_pattern2 = re.compile(
                r'<a[^>]*id="([^"]+)"[^>]*class="[^"]*duokan-footnote[^"]*"[^>]*href="#'
                + re.escape(note_id) + r'"',
                re.IGNORECASE
            )
            ref_match = ref_pattern2.search(text_content)

        note_ref_id = ref_match.group(1) if ref_match else note_id + "_ref"

        footnotes.append({
            'id': note_id,
            'ref_id': note_ref_id,
            'content': _escape_html(note_content),
        })

    # 移除正文中所有散落的 <aside> 脚注元素
    text_content = aside_pattern.sub('', text_content)

    # 清理移除 aside 后可能留下的空白行
    text_content = re.sub(r'\n\s*\n\s*\n', '\n\n', text_content)

    return text_content, footnotes


def _build_footnote_section(footnotes):
    """构建标准多看格式的脚注区域 HTML。"""
    if not footnotes:
        return ""

    # 去重
    seen = set()
    unique = []
    for note in footnotes:
        if note['id'] not in seen:
            seen.add(note['id'])
            unique.append(note)

    # 按数字排序
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


def _inject_footnotes_before_body_close(text_content, footnote_section):
    """在 </body> 前插入脚注区域。"""
    if not footnote_section:
        return text_content
    if '</body>' in text_content:
        parts = text_content.rsplit('</body>', 1)
        return parts[0] + footnote_section + '</body>' + (parts[1] if len(parts) > 1 else '')
    return text_content + footnote_section


class ZhangyueToDuokan:
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

    def _check_note_png_exists(self):
        for name in self.epub.namelist():
            if name.lower().endswith('note.png'):
                return True
        return False

    def _inject_note_png(self):
        if self._note_png_injected or self._has_note_png:
            return
        if os.path.exists(NOTE_PNG_PATH):
            images_dir = "Images"
            for name in self.epub.namelist():
                lower = name.lower()
                if '/images/' in lower or lower.startswith('images/'):
                    parts = name.split('/')
                    for p in parts:
                        if p.lower() == 'images':
                            images_dir = name[:name.index(p) + len(p)]
                            break
                    break
                elif '/image/' in lower or lower.startswith('image/'):
                    idx = lower.find('image/')
                    images_dir = name[:idx + len('image')].rstrip('/')
                    break

            target_path = f"{images_dir}/note.png"
            with open(NOTE_PNG_PATH, 'rb') as f:
                self.target_epub.writestr(target_path, f.read())
            self._note_png_injected = True
            logger.write(f"注入 note.png 到 {target_path}")

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
                    new_item = soup.new_tag('item')
                    new_item['id'] = 'note-png'
                    new_item['href'] = 'Images/note.png'
                    new_item['media-type'] = 'image/png'
                    manifest.append(new_item)

            return str(soup).encode('utf-8')
        except Exception as e:
            logger.write(f"处理OPF文件 {filename} 失败: {e}")
            traceback.print_exc()
            return content

    def _process_html(self, filename, content):
        try:
            text = content.decode('utf-8')
            text = _add_epub_namespace(text)

            # 提取并移除散落的掌阅 aside 脚注
            text, footnotes = _convert_zhangyue_inline_asides(text)

            if footnotes:
                self._inject_note_png()
                footnote_section = _build_footnote_section(footnotes)
                text = _inject_footnotes_before_body_close(text, footnote_section)
                logger.write(f"  {filename}: 转换 {len(footnotes)} 个掌阅脚注")

            return text.encode('utf-8')
        except Exception as e:
            logger.write(f"处理文件 {filename} 失败: {e}")
            traceback.print_exc()
            return content

    def process(self):
        try:
            self._has_note_png = self._check_note_png_exists()
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


def run(epub_path, output_path=None):
    logger.write(f"\n正在执行掌阅转多看: {epub_path}")
    tool = ZhangyueToDuokan(epub_path, output_path)
    return tool.process()
