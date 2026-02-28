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
import re
import traceback

try:
    from .duokan_base import (
        escape_html, add_epub_namespace,
        build_footnote_section, inject_footnotes_before_body_close,
        DuokanConverterBase, logger,
    )
except ImportError:
    from duokan_base import (
        escape_html, add_epub_namespace,
        build_footnote_section, inject_footnotes_before_body_close,
        DuokanConverterBase, logger,
    )


def _convert_zhangyue_inline_asides(text_content, images_dir="Images"):
    """
    提取正文中散落的掌阅 <aside> 脚注，移除原位置，收集脚注内容。
    同时将脚注 <img> 的 src 替换为 note.png 路径。
    
    Returns: (modified_content, footnotes_list)
    """
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

        li_match = re.search(
            r'<li[^>]*class="duokan-footnote-item"[^>]*>(.*?)</li>',
            aside_inner, re.DOTALL | re.IGNORECASE
        )
        note_content = ""
        if li_match:
            raw = li_match.group(1).strip()
            note_content = re.sub(r'<[^>]+>', '', raw).strip()

        ref_pattern = re.compile(
            r'<a[^>]*class="[^"]*duokan-footnote[^"]*"[^>]*href="#'
            + re.escape(note_id) + r'"[^>]*id="([^"]+)"',
            re.IGNORECASE
        )
        ref_match = ref_pattern.search(text_content)
        if not ref_match:
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
            'content': escape_html(note_content),
        })

    # 移除正文中所有散落的 <aside> 脚注元素
    text_content = aside_pattern.sub('', text_content)

    # 将掌阅脚注 <img> 的 src 统一替换为 note.png
    images_basename = images_dir.split('/')[-1] if '/' in images_dir else images_dir
    note_png_src = f"../{images_basename}/note.png"

    def _replace_img_src(m):
        tag = m.group(0)
        tag = re.sub(r'src="[^"]*"', f'src="{note_png_src}"', tag)
        return tag

    text_content = re.sub(
        r'<img[^>]*class="[^"]*(?:zhangyue-footnote|epub-footnote)[^"]*"[^>]*/?>',
        _replace_img_src,
        text_content,
        flags=re.IGNORECASE
    )

    # 清理移除 aside 后可能留下的空白行
    text_content = re.sub(r'\n\s*\n\s*\n', '\n\n', text_content)

    return text_content, footnotes


class ZhangyueToDuokan(DuokanConverterBase):
    def _process_html(self, filename, content):
        try:
            text = content.decode('utf-8')
            text = add_epub_namespace(text)

            text, footnotes = _convert_zhangyue_inline_asides(text, self._images_dir)

            if footnotes:
                self._inject_note_png()
                footnote_section = build_footnote_section(footnotes)
                text = inject_footnotes_before_body_close(text, footnote_section)
                logger.write(f"  {filename}: 转换 {len(footnotes)} 个掌阅脚注")

            return text.encode('utf-8')
        except Exception as e:
            logger.write(f"处理文件 {filename} 失败: {e}")
            traceback.print_exc()
            return content


def run(epub_path, output_path=None):
    logger.write(f"\n正在执行掌阅转多看: {epub_path}")
    tool = ZhangyueToDuokan(epub_path, output_path)
    return tool.process()
