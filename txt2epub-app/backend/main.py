import argparse
import sys
import os
import json
import chardet
from chapter_splitter import DefaultChapterSplitter
from epub_creator import create_epub
from text_cleaner import TextCleaner

def detect_encoding(file_path, verbose=True):
    # Read first 50KB to guess encoding
    with open(file_path, 'rb') as f:
        rawdata = f.read(50000)
    result = chardet.detect(rawdata)
    encoding = result['encoding']
    confidence = result['confidence']
    if verbose:
        print(f"PROGRESS: 10% (Detected encoding: {encoding}, confidence: {confidence})")
    return encoding

def main():
    parser = argparse.ArgumentParser(description="TXT to EPUB Converter Backend")
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
    
    args = parser.parse_args()
    
    if not os.path.exists(args.txt_path):
        print(f"ERROR: Input file not found: {args.txt_path}")
        sys.exit(1)
        
    try:
        # 1. Detect Encoding
        encoding = detect_encoding(args.txt_path, verbose=not args.scan)
        if not encoding:
            encoding = 'utf-8' # Fallback
            
        # 2. Read Content
        try:
            with open(args.txt_path, 'r', encoding=encoding, errors='replace') as f:
                content = f.read()
        except Exception as e:
            print(f"ERROR: Failed to read file with encoding {encoding}: {e}")
            sys.exit(1)
            
        if not args.scan:
             print("PROGRESS: 30% (File read)")

        # 3. Scan Mode Check
        if args.scan:
            splitter = DefaultChapterSplitter()
            results = splitter.scan(content)
            # Add hierarchy suggestion
            suggested = splitter.suggest_hierarchy(results)
            output = {
                "patterns": results,
                "suggested_hierarchy": [
                    {"level": r.get("assigned_level", i), "name": r["name"], "pattern": r["pattern"], "count": r["count"]}
                    for i, r in enumerate(suggested)
                ]
            }
            print(json.dumps(output, ensure_ascii=False))
            sys.exit(0)

        # 4. Clean Text (Only for conversion)
        if args.remove_empty_line or args.fix_indent:
            print("Cleaning text...")
            cleaner = TextCleaner(
                remove_empty_lines=args.remove_empty_line,
                fix_indent=args.fix_indent
            )
            content = cleaner.clean(content)
            print("PROGRESS: 40% (Text Cleaned)")

        # 5. Split Chapters
        print("Splitting chapters...")
        splitter = DefaultChapterSplitter()
        
        # Check if hierarchical mode
        if args.patterns:
            # Parse patterns with levels (format: pattern:level|||pattern:level)
            pattern_list = []
            level_list = []
            for p in args.patterns.split("|||"):
                p = p.strip()
                if not p:
                    continue
                # Check if has level suffix (e.g., ^第.+章:1)
                if ':' in p:
                    # Split from the last colon (pattern might contain :)
                    last_colon = p.rfind(':')
                    pattern = p[:last_colon]
                    try:
                        level = int(p[last_colon+1:])
                    except ValueError:
                        pattern = p
                        level = 1
                else:
                    pattern = p
                    level = 1
                pattern_list.append(pattern)
                level_list.append(level)
            
            if pattern_list:
                print(f"Using {len(pattern_list)} patterns with levels: {list(zip(pattern_list, level_list))}")
                chapters = splitter.split_hierarchical(content, pattern_list, level_list)
                chapter_count = len(chapters)
                # Count total including children
                def count_nodes(nodes):
                    total = len(nodes)
                    for n in nodes:
                        total += count_nodes(n.get("children", []))
                    return total
                total = count_nodes(chapters)
                print(f"Found {total} sections in {len(chapters)} top-level chapters.")
            else:
                chapters = splitter.split(content, custom_pattern=args.custom_regex)
                print(f"Found {len(chapters)} chapters.")
        else:
            # Flat mode
            chapters = splitter.split(content, custom_pattern=args.custom_regex)
            print(f"Found {len(chapters)} chapters.")

            
        print("PROGRESS: 60% (Chapters Split)")
        
        # 6. Create EPUB
        print("Generating EPUB...")
        create_epub(
            output_path=args.epub_path,
            title=args.title,
            author=args.author,
            chapters=chapters,
            cover_path=args.cover_path
        )
        print("PROGRESS: 100% (Done)")
        
    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
