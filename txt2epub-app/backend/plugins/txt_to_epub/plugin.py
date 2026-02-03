import argparse
import sys
import os
import json
import re
from typing import Tuple, List, Dict, Any
from core.plugin_base import BasePlugin
from core.utils import detect_encoding
# Use relative imports since they are in the same package
from .chapter_splitter import DefaultChapterSplitter
from .epub_creator import create_epub
from .text_cleaner import TextCleaner

class TxtToEpubPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "txt2epub"

    @property
    def description(self) -> str:
        return "Convert TXT file to EPUB"

    def register_arguments(self, parser: argparse.ArgumentParser):
        """Register arguments specific to this plugin."""
        parser.add_argument("--txt-path", required=True)
        parser.add_argument("--epub-path", required=True)
        parser.add_argument("--title", required=True)
        parser.add_argument("--author", default="Unknown")
        parser.add_argument("--cover-path", default=None)
        # Pattern arguments
        parser.add_argument("--custom-regex", default=None, help="Single regex (flat mode)")
        parser.add_argument("--patterns", default=None, help="Multiple patterns separated by ||| for hierarchical mode")
        parser.add_argument("--remove-empty-line", action='store_true')
        parser.add_argument("--fix-indent", action='store_true')
        parser.add_argument("--scan", action='store_true', help="Scan only mode, returns JSON")

    def _parse_pattern_with_level(self, p: str) -> Tuple[str, int]:
        """
        Parse 'pattern:level' format safely.
        """
        match = re.match(r'^(.+):(\d+)$', p)
        if match:
            pattern = match.group(1)
            try:
                level = int(match.group(2))
                return pattern, level
            except ValueError:
                pass
        return p, 1

    def run(self, args: argparse.Namespace):
        # Logic from main.py
        
        if not os.path.exists(args.txt_path):
            print(f"ERROR: Input file not found: {args.txt_path}", file=sys.stderr)
            sys.exit(1)
            
        try:
            # 1. Detect Encoding
            # Always verbose=False if scan is True to prevent stdout pollution, 
            # though detect_encoding now prints to stderr anyway.
            encoding = detect_encoding(args.txt_path, verbose=not args.scan)
            if not encoding:
                encoding = 'utf-8' # Fallback
                
            # 2. Read Content
            try:
                with open(args.txt_path, 'r', encoding=encoding, errors='replace') as f:
                    content = f.read()
            except Exception as e:
                print(f"ERROR: Failed to read file with encoding {encoding}: {e}", file=sys.stderr)
                sys.exit(1)
                
            if not args.scan:
                 print("PROGRESS: 30% (File read)", file=sys.stderr)

            # 3. Scan Mode Check
            if args.scan:
                splitter = DefaultChapterSplitter()
                results = splitter.scan(content)
                suggested = splitter.suggest_hierarchy(results)
                output = {
                    "patterns": results,
                    "suggested_hierarchy": [
                        {"level": r.get("assigned_level", i), "name": r["name"], "pattern": r["pattern"], "count": r["count"]}
                        for i, r in enumerate(suggested)
                    ]
                }
                # ONLY this print goes to stdout
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
            
            chapters = []
            if args.patterns:
                pattern_list = []
                level_list = []
                for p in args.patterns.split("|||"):
                    p = p.strip()
                    if not p:
                        continue
                    pattern, level = self._parse_pattern_with_level(p)
                    pattern_list.append(pattern)
                    level_list.append(level)
                
                if pattern_list:
                    print(f"Using {len(pattern_list)} patterns with levels: {list(zip(pattern_list, level_list))}", file=sys.stderr)
                    chapters = splitter.split_hierarchical(content, pattern_list, level_list)
                    
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
            create_epub(
                output_path=args.epub_path,
                title=args.title,
                author=args.author,
                chapters=chapters,
                cover_path=args.cover_path
            )
            print("PROGRESS: 100% (Done)", file=sys.stderr)
            
        except Exception as e:
            print(f"CRITICAL ERROR: {str(e)}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)
