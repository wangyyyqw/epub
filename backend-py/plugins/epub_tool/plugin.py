import argparse
import sys
import os
import json
from core.plugin_base import BasePlugin

from .utils import encrypt_epub, decrypt_epub, reformat_epub, \
    chinese_convert, font_subset, img_compress, img_to_webp, \
    webp_to_img, phonetic_notation, pinyin_annotate, \
    yuewei_to_duokan, zhangyue_to_duokan, encrypt_font, download_web_images, regex_comment, \
    footnote_to_comment, convert_version, view_opf, merge_epub, split_epub

class EpubToolPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "epub_tool"

    @property
    def description(self) -> str:
        return "Advanced EPUB Tools: Encrypt, Decrypt, Reformat"

    def register_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("--operation", choices=[
            "encrypt", "encrypt_font", "list_font_targets", "decrypt", "reformat", "s2t", "t2s", 
            "font_subset", "img_compress", "img_to_webp", 
            "webp_to_img", "phonetic", "yuewei", "zhangyue", "download_images", "comment", "footnote_conv",
            "convert_version", "view_opf",
            "merge", "split", "list_split_targets"
        ], required=True, help="Operation to perform")
        parser.add_argument("--target-version", choices=["2.0", "3.0"], default="3.0", help="Target EPUB version")
        parser.add_argument("--input-path", help="Path to input EPUB file")
        parser.add_argument("--font-path", help="Path to font file for encryption")
        parser.add_argument("--regex-pattern", help="Regex pattern for footnote processing")
        parser.add_argument("--output-path", help="Path to output EPUB file or directory")
        parser.add_argument("--target-font-families", nargs='*', help="Target font families to encrypt")
        parser.add_argument("--target-xhtml-files", nargs='*', help="Target XHTML files to process")
        parser.add_argument("--input-paths", nargs='*', help="Multiple input EPUB file paths (for merge)")
        parser.add_argument("--split-points", help="Comma-separated split point indices")

    def run(self, args: argparse.Namespace):
        # merge uses --input-paths, other operations use --input-path
        if args.operation == "merge":
            if not args.input_paths or len(args.input_paths) < 2:
                print("ERROR: merge requires at least 2 input files via --input-paths", file=sys.stderr)
                sys.exit(1)
            print(f"Running epub_tool operation: {args.operation} on {len(args.input_paths)} files", file=sys.stderr)
        else:
            if not args.input_path:
                print("ERROR: --input-path is required", file=sys.stderr)
                sys.exit(1)
            print(f"Running epub_tool operation: {args.operation} on {args.input_path}", file=sys.stderr)
            if not os.path.exists(args.input_path):
                print(f"ERROR: Input file not found: {args.input_path}", file=sys.stderr)
                sys.exit(1)

        result = 0
        try:
            if args.output_path:
                output_dir = args.output_path
            elif args.operation == "merge" and args.input_paths:
                output_dir = os.path.dirname(args.input_paths[0])
            elif args.input_path:
                output_dir = os.path.dirname(args.input_path)
            else:
                output_dir = os.getcwd()
            
            if args.operation == "encrypt":
                result = encrypt_epub.run(args.input_path, output_dir)
            elif args.operation == "encrypt_font":
                result = encrypt_font.run_epub_font_encrypt(
                    args.input_path, 
                    output_dir,
                    target_font_families=args.target_font_families if args.target_font_families else None,
                    target_xhtml_files=args.target_xhtml_files if args.target_xhtml_files else None
                )
            elif args.operation == "list_font_targets":
                targets = encrypt_font.list_epub_font_encrypt_targets(args.input_path)
                print(json.dumps(targets, ensure_ascii=False, indent=2))
            elif args.operation == "decrypt":
                result = decrypt_epub.run(args.input_path, output_dir)
            elif args.operation == "view_opf":
                result = view_opf.run(args.input_path)
            elif args.operation == "reformat":
                result = reformat_epub.run(args.input_path, output_dir)
            elif args.operation == "s2t":
                result = chinese_convert.run_s2t(args.input_path, output_dir)
            elif args.operation == "t2s":
                result = chinese_convert.run_t2s(args.input_path, output_dir)
            elif args.operation == "font_subset":
                result = font_subset.run_epub_font_subset(args.input_path, output_dir)
            elif args.operation == "img_compress":
                result = img_compress.run(args.input_path, output_dir)
            elif args.operation == "img_to_webp":
                result = img_to_webp.run(args.input_path, output_dir)
            elif args.operation == "webp_to_img":
                result = webp_to_img.run(args.input_path, output_dir)
            elif args.operation == "phonetic":
                res = phonetic_notation.run_add_pinyin(args.input_path, output_dir)
                result = res[0] if isinstance(res, (tuple, list)) else res
            elif args.operation == "yuewei":
                res = yuewei_to_duokan.run(args.input_path, output_dir)
                result = res[0] if isinstance(res, (tuple, list)) else res
            elif args.operation == "zhangyue":
                res = zhangyue_to_duokan.run(args.input_path, output_dir)
                result = res[0] if isinstance(res, (tuple, list)) else res
            elif args.operation == "download_images":
                result = download_web_images.run(args.input_path, output_dir)
            elif args.operation == "comment":
                regex = args.regex_pattern or r'\[(.*?)\]'
                result = regex_comment.run(args.input_path, output_dir, regex)
            elif args.operation == "footnote_conv":
                regex = args.regex_pattern or r'^.+'
                result = footnote_to_comment.run(args.input_path, output_dir, regex)
            elif args.operation == "convert_version":
                target_ver = args.target_version or '3.0'
                result = convert_version.run(args.input_path, output_dir, target_ver)
            elif args.operation == "merge":
                result = merge_epub.run(args.input_paths, output_dir)
            elif args.operation == "list_split_targets":
                targets = split_epub.list_split_targets(args.input_path)
                print(json.dumps(targets, ensure_ascii=False, indent=2))
            elif args.operation == "split":
                points = [int(x) for x in args.split_points.split(",")]
                result = split_epub.run(args.input_path, output_dir, points)
            
            if result == 0:
                print("SUCCESS", file=sys.stderr)
            elif result == "skip":
                print("SKIP", file=sys.stderr)
            elif result == "zhangyue_drm":
                print("ZHANGYUE_DRM", file=sys.stderr)
                sys.exit(2)
            else:
                print(f"FAILURE: Code {result}", file=sys.stderr)
                sys.exit(1)

        except Exception as e:
            print(f"CRITICAL ERROR: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)
