import argparse
import sys
import os
import json
import re
from typing import Tuple, List, Dict, Any
from core.plugin_base import BasePlugin
from core.utils import detect_encoding
from .chapter_splitter import DefaultChapterSplitter
from .epub_creator import create_epub
from .text_cleaner import TextCleaner, BLANK_CHARS
from .douban_cover import search_books, download_cover

class TxtToEpubPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "txt2epub"

    @property
    def description(self) -> str:
        return "Convert TXT file to EPUB"

    def register_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("--txt-path", required=True)
        parser.add_argument("--epub-path", required=True)
        parser.add_argument("--title", required=True)
        parser.add_argument("--author", default="Unknown")
        parser.add_argument("--cover-path", default=None)
        
        # Pattern arguments
        parser.add_argument("--custom-regex", default=None, help="Single regex (flat mode)")
        parser.add_argument("--patterns", default=None, help="Multiple patterns: 'regex:level:split' separated by |||")
        parser.add_argument("--patterns-file", default=None, help="Path to UTF-8 file containing patterns string (avoids CLI encoding issues)")
        
        # Text cleaning
        parser.add_argument("--remove-empty-line", action='store_true')
        parser.add_argument("--fix-indent", action='store_true')
        
        # Title formatting
        parser.add_argument("--split-title", action='store_true', help="Split chapter title into number and text")
        
        # Header image
        parser.add_argument("--header-image", default=None, help="Path to header image for each chapter")
        
        # File naming
        parser.add_argument("--naming-rule", default="Chapter{0000}", help="File naming rule, e.g. 'Chapter{0000}' or 'Vol{00}-Ch{0000}'")
        
        # Template
        parser.add_argument("--template", default=None, help="Custom XHTML template path")
        
        # Scan mode
        parser.add_argument("--scan", action='store_true', help="Scan only mode, returns JSON")
        
        # Douban cover search
        parser.add_argument("--search-cover", default=None, help="Search Douban for book cover by title")
        parser.add_argument("--download-cover", default=None, help="Download cover from URL, returns local path")

    def _parse_pattern(self, p: str) -> Tuple[str, int, bool]:
        """
        Parse 'pattern:level:split' format.
        Returns: (pattern, level, should_split)
        """
        parts = p.rsplit(':', maxsplit=2)

        if len(parts) == 3:
            pattern = parts[0]
            try:
                level = int(parts[1])
            except ValueError:
                # parts[1] is not a number, ':' belongs to the regex
                # Fallback: try rsplit(':', 1)
                fallback_parts = p.rsplit(':', maxsplit=1)
                try:
                    level = int(fallback_parts[1])
                except ValueError:
                    return p, 1, True  # entire string is regex
                return fallback_parts[0], level, True
            should_split = parts[2].lower() in ('true', '1', 'yes', 'y')
            return pattern, level, should_split

        elif len(parts) == 2:
            try:
                level = int(parts[1])
            except ValueError:
                return p, 1, True  # entire string is regex
            return parts[0], level, True

        else:
            return p, 1, True

    def run(self, args: argparse.Namespace):
        # Douban cover search mode (no file needed)
        if args.search_cover:
            try:
                results = search_books(args.search_cover)
                print(json.dumps(results, ensure_ascii=False))
            except Exception as e:
                print(f"ERROR: 搜索失败: {e}", file=sys.stderr)
                sys.exit(1)
            return

        # Douban cover download mode
        if args.download_cover:
            try:
                local_path = download_cover(args.download_cover)
                print(json.dumps({"path": local_path}, ensure_ascii=False))
            except Exception as e:
                print(f"ERROR: 下载封面失败: {e}", file=sys.stderr)
                sys.exit(1)
            return

        if not os.path.exists(args.txt_path):
            print(f"ERROR: Input file not found: {args.txt_path}", file=sys.stderr)
            sys.exit(1)
            
        try:
            # 1. Detect Encoding
            encoding = detect_encoding(args.txt_path, verbose=not args.scan)
            if not encoding:
                encoding = 'utf-8'
                
            # 2. Read Content
            try:
                with open(args.txt_path, 'r', encoding=encoding, errors='replace') as f:
                    content = f.read()
            except Exception as e:
                print(f"ERROR: Failed to read file with encoding {encoding}: {e}", file=sys.stderr)
                sys.exit(1)
                
            if not args.scan:
                print("PROGRESS: 30% (File read)", file=sys.stderr)

            # 3. Scan Mode
            if args.scan:
                splitter = DefaultChapterSplitter()
                results = splitter.scan(content)
                suggested = splitter.suggest_hierarchy(results)
                
                # Calculate word counts for each pattern and each chapter
                for r in results:
                    pattern = re.compile(r["pattern"], re.M)
                    matches = list(pattern.finditer(content))
                    chapter_details = []
                    word_counts = []
                    for i, m in enumerate(matches):
                        start = m.end()
                        end = matches[i+1].start() if i+1 < len(matches) else len(content)
                        section = content[start:end]
                        word_count = len(section.strip(BLANK_CHARS))
                        word_counts.append(word_count)
                        chapter_details.append({
                            "title": m.group().strip(BLANK_CHARS),
                            "word_count": word_count
                        })
                    r["word_counts"] = word_counts
                    r["avg_words"] = sum(word_counts) // len(word_counts) if word_counts else 0
                    r["chapter_details"] = chapter_details
                
                output = {
                    "patterns": results,
                    "suggested_hierarchy": [
                        {
                            "level": r.get("assigned_level", i), 
                            "name": r["name"], 
                            "pattern": r["pattern"], 
                            "count": r["count"],
                            "avg_words": r.get("avg_words", 0),
                            "chapters": r.get("chapters", []),
                            "chapter_details": r.get("chapter_details", [])
                        }
                        for i, r in enumerate(suggested)
                    ]
                }
                print(json.dumps(output, ensure_ascii=False))
                return

            # 4. Clean Text
            if args.remove_empty_line or args.fix_indent:
                print("Cleaning text...", file=sys.stderr)
                cleaner = TextCleaner(
                    remove_empty_lines=args.remove_empty_line,
                    fix_indent=args.fix_indent
                )
                content = cleaner.clean(content)
                print("PROGRESS: 40% (Text Cleaned)", file=sys.stderr)

            # 5. Split Chapters
            print("Splitting chapters...", file=sys.stderr)
            splitter = DefaultChapterSplitter()
            
            # Support --patterns-file to avoid Windows CLI encoding issues
            patterns_str = args.patterns
            if not patterns_str and args.patterns_file:
                try:
                    with open(args.patterns_file, 'r', encoding='utf-8') as f:
                        patterns_str = f.read().strip()
                except Exception as e:
                    print(f"WARNING: Failed to read patterns file: {e}", file=sys.stderr)
            
            chapters = []
            if patterns_str:
                pattern_list = []
                level_list = []
                split_list = []
                
                for p in patterns_str.split("|||"):
                    p = p.strip()
                    if not p:
                        continue
                    pattern, level, should_split = self._parse_pattern(p)
                    pattern_list.append(pattern)
                    level_list.append(level)
                    split_list.append(should_split)
                
                if pattern_list:
                    print(f"Using {len(pattern_list)} patterns with levels: {list(zip(pattern_list, level_list, split_list))}", file=sys.stderr)
                    chapters = splitter.split_hierarchical(content, pattern_list, level_list, split_list)
                    
                    def count_nodes(nodes):
                        total = len(nodes)
                        for n in nodes:
                            total += count_nodes(n.get("children", []))
                        return total
                    total = count_nodes(chapters)
                    print(f"Found {total} sections in {len(chapters)} top-level chapters.", file=sys.stderr)
                else:
                    chapters = splitter.split(content, custom_pattern=args.custom_regex)
                    print(f"Found {len(chapters)} chapters.", file=sys.stderr)
            else:
                chapters = splitter.split(content, custom_pattern=args.custom_regex)
                print(f"Found {len(chapters)} chapters.", file=sys.stderr)

            print("PROGRESS: 60% (Chapters Split)", file=sys.stderr)
            
            # 6. Create EPUB
            print("Generating EPUB...", file=sys.stderr)
            
            # Load custom template if provided
            template_content = None
            if args.template and os.path.exists(args.template):
                try:
                    with open(args.template, 'r', encoding='utf-8') as f:
                        template_content = f.read()
                except Exception as e:
                    print(f"WARNING: Failed to load template: {e}", file=sys.stderr)
            
            create_epub(
                output_path=args.epub_path,
                title=args.title,
                author=args.author,
                chapters=chapters,
                cover_path=args.cover_path,
                header_image_path=args.header_image,
                split_title=args.split_title,
                naming_rule=args.naming_rule,
                template_content=template_content
            )
            print("PROGRESS: 100% (Done)", file=sys.stderr)
            
        except Exception as e:
            print(f"CRITICAL ERROR: {str(e)}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)
