"""
阅微转多看：将阅微格式的脚注转换为标准多看格式。
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


def _extract_zy_footnote_content(text_content, match_start):
    """Extract zy-footnote or alt content near a match position."""
    search_end = min(match_start + 800, len(text_content))
    window = text_content[match_start:search_end]

    m = re.search(r'zy-footnote="([^"]*)"', window)
    if not m:
        m = re.search(r'alt="([^"]*)"', window)
    return m.group(1) if m else ""


def _collect_existing_duokan_footnotes(text_content):
    """Collect footnotes from existing duokan-footnote anchors that lack aside elements."""
    footnotes = []

    patterns = [
        (r'<a[^>]*class="[^"]*duokan-footnote[^"]*"[^>]*href="#([^"]+)"[^>]*id="([^"]+)"[^>]*>',
         lambda m: (m.group(1), m.group(2))),
        (r'<a[^>]*id="([^"]+)"[^>]*class="[^"]*duokan-footnote[^"]*"[^>]*href="#([^"]+)"[^>]*>',
         lambda m: (m.group(2), m.group(1))),
        (r'<a(?![^>]*\bid\s*=)[^>]*class="[^"]*duokan-footnote[^"]*"[^>]*href="#([^"]+)"[^>]*>',
         lambda m: (m.group(1), m.group(1) + "_ref")),
    ]

    seen_ids = set()
    for pattern, extract_ids in patterns:
        for match in re.finditer(pattern, text_content):
            note_id, note_ref_id = extract_ids(match)
            if note_id in seen_ids:
                continue
            if re.search(rf'<aside[^>]*id="{re.escape(note_id)}"[^>]*>', text_content):
                continue

            note_content = _extract_zy_footnote_content(text_content, match.start())
            seen_ids.add(note_id)
            footnotes.append({
                'id': note_id,
                'ref_id': note_ref_id,
                'content': escape_html(note_content),
            })

    return footnotes


def _convert_yuewei_spans(text_content):
    """Convert yuewei reader footnote spans to duokan format. Returns (modified_content, footnotes)."""
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

    position_numbers = {m.start(): i for i, m in enumerate(matches, 1)}
    footnotes = []

    for match in reversed(matches):
        note_number = position_numbers[match.start()]
        note_id = f"note{note_number}"
        note_ref_id = f"note_ref{note_number}"
        note_content = escape_html(match.group(1))

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


class YueweiToDuokan(DuokanConverterBase):
    def _process_html(self, filename, content):
        try:
            text = content.decode('utf-8')
            text = add_epub_namespace(text)

            text, footnotes = _convert_yuewei_spans(text)
            existing_footnotes = _collect_existing_duokan_footnotes(text)
            footnotes.extend(existing_footnotes)

            if footnotes:
                self._inject_note_png()
                footnote_section = build_footnote_section(footnotes)
                text = inject_footnotes_before_body_close(text, footnote_section)

            return text.encode('utf-8')
        except Exception as e:
            logger.write(f"处理文件 {filename} 失败: {e}")
            traceback.print_exc()
            return content


def run(epub_path, output_path=None):
    logger.write(f"\n正在执行阅微转多看: {epub_path}")
    tool = YueweiToDuokan(epub_path, output_path)
    return tool.process()
