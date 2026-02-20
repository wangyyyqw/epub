import os
import sys
import traceback
from ebooklib import epub

try:
    from ..log import logwriter
except ImportError:
    from .log import logwriter

logger = logwriter()

class EpubVersionConverter:
    def __init__(self, epub_path, output_path, target_version):
        if not os.path.exists(epub_path):
            raise Exception("EPUB文件不存在")

        self.epub_path = epub_path
        self.target_version = target_version # '2.0' or '3.0'
        
        if output_path and os.path.exists(output_path):
            if os.path.isfile(output_path):
                raise Exception("输出路径不能是文件")
        else:
            output_path = os.path.dirname(epub_path)
            
        self.output_path = output_path
        suffix = "_v3" if target_version == '3.0' else "_v2"
        self.file_write_path = os.path.join(
            self.output_path,
            os.path.basename(self.epub_path).replace(".epub", f"{suffix}.epub"),
        )

    def process(self):
        try:
            logger.write(f"正在读取 EPUB: {self.epub_path}")
            book = epub.read_epub(self.epub_path)
            
            # Check current version
            # Ebooklib might not parse version perfectly from all files, but we can try setting it.
            logger.write(f"当前版本 (检测): {book.version}")
            
            # Set new version (ebooklib uses strict typing for some fields, be careful)
            # Actually ebooklib doesn't have a simple 'version' setter that does everything.
            # But write_epub handles some of it if items are correct.
            
            # For EPUB 3, we need Nav file. For EPUB 2, we need NCX.
            # Ebooklib usually adds NCX by default. 
            # If converting to EPUB 3, we should ensure Nav exists.
            
            has_nav = any(isinstance(x, epub.EpubNav) for x in book.items)
            has_ncx = any(isinstance(x, epub.EpubNcx) for x in book.items)
            
            if self.target_version == '3.0':
                book.version = '3.0' # Set internal version
                if not has_nav:
                    logger.write("生成 EPUB3 导航文件 (Nav)...")
                    book.add_item(epub.EpubNav())
                # Should we remove NCX? EPUB 3 can have NCX for backward compatibility.
                # Let's keep it.
            
            elif self.target_version == '2.0':
                book.version = '2.0'
                if not has_ncx:
                    logger.write("生成 EPUB2 目录文件 (NCX)...")
                    book.add_item(epub.EpubNcx())
                # Remove Nav if exists? EPUB 2 readers might choke on it or just ignore it.
                # Ebooklib handles writing based on book items. 
                # Let's remove Nav items to be safe for strict EPUB 2
                nav_items = [x for x in book.items if isinstance(x, epub.EpubNav)]
                for item in nav_items:
                    book.items.remove(item)
                    
            logger.write(f"正在写入新版本 EPUB ({self.target_version})...")
            epub.write_epub(self.file_write_path, book, {})
            
            logger.write(f"转换成功: {self.file_write_path}")
            return 0, self.file_write_path
            
        except Exception as e:
            logger.write(f"转换失败: {e}")
            traceback.print_exc()
            return 1, str(e)

def run(epub_path, output_path=None, target_version='3.0'):
    converter = EpubVersionConverter(epub_path, output_path, target_version)
    return converter.process()
