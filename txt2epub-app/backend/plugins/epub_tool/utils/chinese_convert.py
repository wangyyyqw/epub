import zipfile
import os
from bs4 import BeautifulSoup, NavigableString, Comment, Doctype, ProcessingInstruction, Declaration
import traceback
from opencc import OpenCC
import io

try:
    from ..log import logwriter
except ImportError:
    from .log import logwriter

logger = logwriter()

class ChineseConvert:
    def __init__(self, epub_path, output_path, mode='s2t'):
        if not os.path.exists(epub_path):
            raise Exception("EPUB文件不存在")

        self.epub_path = os.path.normpath(epub_path)
        self.epub = zipfile.ZipFile(epub_path)
        self.mode = mode  # 's2t' (Simplified to Traditional) or 't2s' (Traditional to Simplified)
        self.cc = OpenCC(mode)
        
        if output_path and os.path.exists(output_path):
            if os.path.isfile(output_path):
                raise Exception("输出路径不能是文件")
        else:
            output_path = os.path.dirname(epub_path)
            
        self.output_path = os.path.normpath(output_path)
        suffix = "_traditional" if mode == 's2t' else "_simplified"
        self.file_write_path = os.path.join(
            self.output_path,
            os.path.basename(self.epub_path).replace(".epub", f"{suffix}.epub"),
        )
        
        if os.path.exists(self.file_write_path):
            os.remove(self.file_write_path)
            
        self.target_epub = zipfile.ZipFile(
            self.file_write_path,
            "w",
            zipfile.ZIP_DEFLATED,
        )

    def convert_text(self, text):
        if not text:
            return text
        return self.cc.convert(text)

    def process_file(self):
        for item in self.epub.infolist():
            content = self.epub.read(item.filename)
            
            # Process HTML/XHTML/NCX/OPF files
            if item.filename.lower().endswith(('.html', '.xhtml', '.htm', '.ncx', '.opf')):
                try:
                    # Try to detect encoding, usually utf-8 for epub
                    text_content = content.decode('utf-8')
                    
                    # Use BeautifulSoup for HTML files to avoid breaking tags
                    if item.filename.lower().endswith(('.html', '.xhtml', '.htm')):
                        soup = BeautifulSoup(text_content, 'html.parser')
                        
                        # Convert text nodes
                        for string in soup.find_all(string=True):
                            # Skip special tags (Comment, Doctype, ProcessingInstruction, etc.)
                            if isinstance(string, (Comment, Doctype, ProcessingInstruction, Declaration)):
                                continue
                                
                            # Skip special tags if necessary, but usually text nodes are safe
                            if string.parent.name not in ['style', 'script']:
                                new_string = self.convert_text(string)
                                string.replace_with(new_string)
                                
                        # Convert title attribute in tags if any
                        for tag in soup.find_all(True):
                            if tag.has_attr('title'):
                                tag['title'] = self.convert_text(tag['title'])
                            if tag.has_attr('alt'):
                                tag['alt'] = self.convert_text(tag['alt'])
                                
                        # Return processed HTML
                        # Use formatter='html' to prevent escaping issues if needed, but utf-8 encode handles it
                        new_content = str(soup).encode('utf-8')
                        
                    else:
                        # For NCX/OPF
                        soup = BeautifulSoup(text_content, 'xml')
                        
                        # Convert text in tags
                        for string in soup.find_all(string=True):
                            # Skip special tags
                            if isinstance(string, (Comment, Doctype, ProcessingInstruction, Declaration)):
                                continue
                                
                            new_string = self.convert_text(string)
                            string.replace_with(new_string)
                            
                        new_content = str(soup).encode('utf-8')

                    self.target_epub.writestr(item.filename, new_content)
                    
                except Exception as e:
                    logger.write(f"文件 {item.filename} 转换失败，使用原内容: {e}")
                    self.target_epub.writestr(item, content)
            else:
                # Copy other files (images, css, fonts) as is
                self.target_epub.writestr(item, content)

        self.close_file()
        logger.write(f"EPUB简繁转换完成 ({self.mode})，输出路径: {self.file_write_path}")

    def close_file(self):
        if self.epub:
            self.epub.close()
        if self.target_epub:
            self.target_epub.close()

    def fail_del_target(self):
        if self.file_write_path and os.path.exists(self.file_write_path):
            os.remove(self.file_write_path)
            logger.write(f"删除临时文件: {self.file_write_path}")

def run_s2t(epub_path, output_path=None):
    logger.write(f"\n正在尝试将EPUB转换为繁体: {epub_path}")
    return _run_convert(epub_path, output_path, 's2t')

def run_t2s(epub_path, output_path=None):
    logger.write(f"\n正在尝试将EPUB转换为简体: {epub_path}")
    return _run_convert(epub_path, output_path, 't2s')

def _run_convert(epub_path, output_path, mode):
    cc_tool = None
    try:
        cc_tool = ChineseConvert(epub_path, output_path, mode)
        cc_tool.process_file()
        return 0
    except Exception as e:
        logger.write(f"简繁转换失败: {e}")
        traceback.print_exc()
        if cc_tool:
            cc_tool.close_file()
            cc_tool.fail_del_target()
        return e

if __name__ == "__main__":
    epub_read_path = input("请输入EPUB文件路径: ")
    mode = input("请输入模式 (s2t/t2s): ")
    if mode == 's2t':
        run_s2t(epub_read_path)
    else:
        run_t2s(epub_read_path)
