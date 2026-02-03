import uuid
import os
import sys
import html
from ebooklib import epub
from typing import List, Dict, Any, Tuple, Union, Optional

def create_epub(
    output_path: str,
    title: str,
    author: str,
    chapters: Union[List[Tuple[str, str]], List[Dict[str, Any]]],
    cover_path: Optional[str] = None,
    lang: str = 'zh-CN',
    book_id: Optional[str] = None
) -> None:
    """
    Create EPUB from chapters.
    
    Args:
        chapters: Either flat [(title, content), ...] or hierarchical [{"title", "content", "children"}]
    
    Raises:
        ValueError: If chapters is empty or None
    """
    # Validate chapters
    if not chapters:
        raise ValueError("Cannot create EPUB: chapters list is empty or None")
    
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    book = epub.EpubBook()
    
    # Set Metadata
    if book_id is None:
        book_id = str(uuid.uuid4())
    book.set_identifier(f'urn:uuid:{book_id}')
    book.set_title(title)
    book.set_language(lang)
    book.add_author(author)

    # Add Cover
    if cover_path and os.path.exists(cover_path):
        try:
            with open(cover_path, 'rb') as f:
                book.set_cover(os.path.basename(cover_path), f.read(), create_page=True)
        except Exception as e:
            print(f"WARNING: Failed to load cover image: {e}", file=sys.stderr)

    # Detect format and create chapters
    epub_chapters = []
    toc = []
    counter = [0]  # Mutable counter for unique IDs
    
    def is_hierarchical(data):
        """Check if chapters are in hierarchical format."""
        return data and isinstance(data[0], dict) and "children" in data[0]
    
    def create_chapter_html(title: str, content: str, level: int = 1) -> str:
        """Convert content to HTML with appropriate heading level."""
        level = max(1, min(6, level))  # Clamp to h1-h6
        escaped_title = html.escape(title)
        lines = [f'<p>{html.escape(line)}</p>' for line in content.split('\n') if line.strip()]
        return f'<h{level}>{escaped_title}</h{level}>\n' + '\n'.join(lines)
    
    def process_hierarchical(nodes: List[Dict], depth: int = 1) -> Tuple[List, List]:

        """
        Recursively process hierarchical chapters.
        Returns (epub_items, toc_entries)
        """
        items = []
        toc_entries = []
        
        for node in nodes:
            title = node.get("title", "Untitled")
            content = node.get("content", "")
            children = node.get("children", [])
            level = node.get("level", depth)  # Use stored level or fall back to depth
            
            # Create this chapter
            chapter_id = counter[0]
            counter[0] += 1
            
            html_content = create_chapter_html(title, content, level)
            c_item = epub.EpubHtml(title=title, file_name=f'chap_{chapter_id}.xhtml', lang=lang)
            c_item.content = html_content
            book.add_item(c_item)
            items.append(c_item)

            
            # Process children
            if children:
                child_items, child_toc = process_hierarchical(children, depth + 1)
                items.extend(child_items)
                # Create nested TOC entry
                toc_entries.append((epub.Section(title), [c_item] + child_toc))
            else:
                # Leaf node
                toc_entries.append(c_item)
        
        return items, toc_entries
    
    if is_hierarchical(chapters):
        # Hierarchical format
        epub_chapters, toc = process_hierarchical(chapters)
    else:
        # Flat format (backward compatible)
        for i, (t, c) in enumerate(chapters):
            escaped_title = html.escape(t)
            lines = [f'<p>{html.escape(line)}</p>' for line in c.split('\n') if line.strip()]
            html_content = f'<h1>{escaped_title}</h1>\n' + '\n'.join(lines)
            
            c_item = epub.EpubHtml(title=t, file_name=f'chap_{i}.xhtml', lang=lang)
            c_item.content = html_content
            book.add_item(c_item)
            epub_chapters.append(c_item)
        toc = epub_chapters

    # Define Spine
    spine_items = []
    book.spine = spine_items + epub_chapters
    
    if book.get_item_with_href('cover.xhtml'):
        book.spine.insert(0, book.get_item_with_href('cover.xhtml'))

    # Define TOC (nested or flat)
    book.toc = toc

    # Add Structure files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    
    # Write EPUB
    try:
        epub.write_epub(output_path, book)
        print(f"SUCCESS: {output_path}", file=sys.stderr)
    except Exception as e:
        print(f"ERROR: Failed to write EPUB: {e}", file=sys.stderr)
        raise e
