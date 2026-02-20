import uuid
import os
import sys
import html
import re
from ebooklib import epub
from typing import List, Dict, Any, Tuple, Union, Optional

def create_epub(
    output_path: str,
    title: str,
    author: str,
    chapters: Union[List[Tuple[str, str]], List[Dict[str, Any]]],
    cover_path: Optional[str] = None,
    lang: str = 'zh-CN',
    book_id: Optional[str] = None,
    header_image_path: Optional[str] = None,
    split_title: bool = False,
    naming_rule: str = "Chapter{0000}",
    template_content: Optional[str] = None
) -> None:
    """
    Create EPUB from chapters.
    
    Args:
        chapters: Either flat [(title, content), ...] or hierarchical [{"title", "content", "children"}]
        header_image_path: Optional path to an image to be placed at the beginning of each chapter
        split_title: Whether to split chapter title "第X章 标题" into two lines
        naming_rule: File naming rule like 'Chapter{0000}'
        template_content: Custom XHTML template with [TITLE] and [MAIN] placeholders
    """
    if not chapters:
        raise ValueError("Cannot create EPUB: chapters list is empty or None")
    
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    book = epub.EpubBook()
    
    if book_id is None:
        book_id = str(uuid.uuid4())
    book.set_identifier(f'urn:uuid:{book_id}')
    book.set_title(title)
    book.set_language(lang)
    book.add_author(author)

    style = '''
    p { margin-bottom: 1em; text-indent: 2em; }
    h1, h2, h3, h4, h5, h6 { text-align: center; margin-top: 1em; margin-bottom: 1em; }
    
    div.logo {
        margin: 0;
        text-align: center;
        text-indent: 0;
    }
    .logo img.responsive-image {
        width: 100%;
        max-width: 100%;
        height: auto;
    }
    .logo {
        duokan-text-indent: 0;
        duokan-bleed: lefttopright;
    }
    
    .number {
        display: inline-block;
    }
    .title {
        display: inline-block;
    }
    '''
    css_item = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
    book.add_item(css_item)

    if cover_path and os.path.exists(cover_path):
        try:
            with open(cover_path, 'rb') as f:
                book.set_cover(os.path.basename(cover_path), f.read(), create_page=True)
        except Exception as e:
            print(f"WARNING: Failed to load cover image: {e}", file=sys.stderr)

    header_image_filename = None
    if header_image_path and os.path.exists(header_image_path):
        try:
            header_image_filename = "logo" + os.path.splitext(header_image_path)[1]
            with open(header_image_path, 'rb') as f:
                img_item = epub.EpubItem(
                    uid="header_image",
                    file_name=f"Images/{header_image_filename}",
                    media_type="image/jpeg" if header_image_path.lower().endswith(('.jpg', '.jpeg')) else "image/png",
                    content=f.read()
                )
                book.add_item(img_item)
        except Exception as e:
            print(f"WARNING: Failed to load header image: {e}", file=sys.stderr)
            header_image_filename = None

    epub_chapters = []
    toc = []
    counter = [0]
    level_counters = {}
    
    def is_hierarchical(data):
        return data and isinstance(data[0], dict) and "children" in data[0]
    
    def create_chapter_html(chapter_title: str, content: str, level: int = 1) -> str:
        level = max(1, min(6, level))
        
        display_title = html.escape(chapter_title)
        
        if split_title:
            match = re.match(r'^(第.+?章)\s*(.*)$', chapter_title)
            if match:
                number_part = html.escape(match.group(1))
                title_part = html.escape(match.group(2))
                display_title = f'<span class="number">{number_part}</span><br/><span class="title">{title_part}</span>'
        
        html_parts = []
        
        if header_image_filename:
            html_parts.append(f'''
            <div class="logo">
                <img class="responsive-image" alt="logo" src="Images/{header_image_filename}"/>
            </div>
            ''')
            
        html_parts.append(f'<h{level}>{display_title}</h{level}>')
        
        lines = [f'<p>{html.escape(line)}</p>' for line in content.split('\n') if line.strip()]
        html_parts.append('\n'.join(lines))
        
        return '\n'.join(html_parts)
    
    def get_next_filename(level: int) -> str:
        if level not in level_counters:
            level_counters[level] = 0
        level_counters[level] += 1
        
        prefix = "Chapter" if level == 1 else f"Section{level}"
        num = level_counters[level]
        
        return f"{prefix}{num:04d}"
    
    def process_hierarchical(nodes: List[Dict], depth: int = 1) -> Tuple[List, List]:
        items = []
        toc_entries = []
        
        for node in nodes:
            chapter_title = node.get("title", "Untitled")
            content = node.get("content", "")
            children = node.get("children", [])
            level = node.get("level", depth)
            
            counter[0] += 1
            
            filename = get_next_filename(level)
            
            html_content = create_chapter_html(chapter_title, content, level)
            c_item = epub.EpubHtml(title=chapter_title, file_name=f'{filename}.xhtml', lang=lang)
            c_item.content = html_content
            c_item.add_item(css_item)
            book.add_item(c_item)
            items.append(c_item)

            if children:
                child_items, child_toc = process_hierarchical(children, depth + 1)
                items.extend(child_items)
                toc_entries.append((epub.Section(chapter_title), [c_item] + child_toc))
            else:
                toc_entries.append(c_item)
        
        return items, toc_entries
    
    if is_hierarchical(chapters):
        epub_chapters, toc = process_hierarchical(chapters)
    else:
        for i, (t, c) in enumerate(chapters):
            html_content = create_chapter_html(t, c, 1)
            filename = get_next_filename(1)
            
            c_item = epub.EpubHtml(title=t, file_name=f'{filename}.xhtml', lang=lang)
            c_item.content = html_content
            c_item.add_item(css_item)
            book.add_item(c_item)
            epub_chapters.append(c_item)
        toc = epub_chapters

    book.toc = toc

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    
    spine = ['nav']
    if book.get_item_with_href('cover.xhtml'):
        spine.insert(0, 'cover')
    spine.extend(epub_chapters)
    book.spine = spine
    
    try:
        epub.write_epub(output_path, book)
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"SUCCESS: {output_path} ({file_size} bytes)", file=sys.stderr)
        else:
            print(f"ERROR: File was not created at {output_path}", file=sys.stderr)
            raise RuntimeError(f"EPUB file was not created at {output_path}")
    except Exception as e:
        print(f"ERROR: Failed to write EPUB: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        raise e
