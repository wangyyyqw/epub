import argparse
import sys
import os
from core.plugin_base import BasePlugin

# Import utils relative to this file
# Note: Since the utils folder is inside this package, imports in utils might need adjustment 
# or we need to ensure this folder is a package.
from .utils import encrypt_epub, decrypt_epub, reformat_epub, \
    chinese_convert, font_subset, img_compress, img_to_webp, \
    webp_to_img, phonetic_notation, pinyin_annotate, regex_footnote, \
    yuewei_to_duokan, encrypt_font, download_web_images, regex_comment, \
    footnote_to_comment

class EpubToolPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "epub_tool"

    @property
    def description(self) -> str:
        return "Advanced EPUB Tools: Encrypt, Decrypt, Reformat"

    def register_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("--operation", choices=[
            "encrypt", "encrypt_font", "decrypt", "reformat", "s2t", "t2s", 
            "font_subset", "img_compress", "img_to_webp", 
            "webp_to_img", "phonetic", "footnote", "yuewei", "download_images", "comment", "footnote_conv"
        ], required=True, help="Operation to perform")
        parser.add_argument("--input-path", required=True, help="Path to input EPUB file")
        parser.add_argument("--font-path", help="Path to font file for encryption")
        parser.add_argument("--regex-pattern", help="Regex pattern for footnote processing")

    def run(self, args: argparse.Namespace):
        print(f"Running epub_tool operation: {args.operation} on {args.input_path}", file=sys.stderr)
        
        if not os.path.exists(args.input_path):
            print(f"ERROR: Input file not found: {args.input_path}", file=sys.stderr)
            sys.exit(1)

        result = 0
        try:
            if args.operation == "encrypt":
                result = encrypt_epub.run(args.input_path)  # Removed args.font_path as it handles general obfuscation
            elif args.operation == "encrypt_font":
                 # Use the separate font encryptor
                 result = encrypt_font.run_epub_font_encrypt(args.input_path)
            elif args.operation == "decrypt":
                result = decrypt_epub.run(args.input_path)
            elif args.operation == "reformat":
                result = reformat_epub.run(args.input_path)
            elif args.operation == "s2t":
                result = chinese_convert.run_s2t(args.input_path)
            elif args.operation == "t2s":
                result = chinese_convert.run_t2s(args.input_path)
            elif args.operation == "font_subset":
                result = font_subset.run_epub_font_subset(args.input_path)
            elif args.operation == "img_compress":
                result = img_compress.run(args.input_path)
            elif args.operation == "img_to_webp":
                result = img_to_webp.run(args.input_path, os.path.dirname(args.input_path))
            elif args.operation == "webp_to_img":
                result = webp_to_img.run(args.input_path, os.path.dirname(args.input_path))
            elif args.operation == "phonetic":
                res = phonetic_notation.run_add_pinyin(args.input_path)
                result = res[0] if isinstance(res, (tuple, list)) else res
            elif args.operation == "footnote":
                regex = args.regex_pattern or r'\[(\d+)\]'
                result = regex_footnote.run(args.input_path, os.path.dirname(args.input_path), regex)
            elif args.operation == "yuewei":
                result = yuewei_to_duokan.run(args.input_path)
            elif args.operation == "download_images":
                result = download_web_images.run(args.input_path)
            elif args.operation == "comment":
                regex = args.regex_pattern or r'\[(.*?)\]'
                result = regex_comment.run(args.input_path, os.path.dirname(args.input_path), regex)
            elif args.operation == "footnote_conv":
                result = footnote_to_comment.run(args.input_path, os.path.dirname(args.input_path))
            
            if result == 0:
                print("SUCCESS", file=sys.stderr)
            else:
                print(f"FAILURE: Code {result}", file=sys.stderr)
                sys.exit(1)

        except Exception as e:
            print(f"CRITICAL ERROR: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)
