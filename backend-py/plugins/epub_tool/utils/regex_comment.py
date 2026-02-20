import zipfile
import os
import re
import traceback

try:
    from ..log import logwriter
except ImportError:
    from .log import logwriter

logger = logwriter()

class RegexComment:
    def __init__(self, epub_path, output_path, regex_pattern):
        if not os.path.exists(epub_path):
            raise Exception("EPUB文件不存在")

        self.epub_path = os.path.normpath(epub_path)
        self.output_path = output_path
        self.regex_pattern = regex_pattern
        self.epub = zipfile.ZipFile(epub_path)
        
        if output_path and os.path.exists(output_path):
            if os.path.isfile(output_path):
                raise Exception("输出路径不能是文件")
        else:
            output_path = os.path.dirname(epub_path)
            
        self.output_path = os.path.normpath(output_path)
        self.file_write_path = os.path.join(
            self.output_path,
            os.path.basename(self.epub_path).replace(".epub", "_comment.epub"),
        )
        
        if os.path.exists(self.file_write_path):
            os.remove(self.file_write_path)
            
        self.target_epub = zipfile.ZipFile(
            self.file_write_path,
            "w",
            zipfile.ZIP_DEFLATED,
        )

    def process_file(self):
        try:
            # 优化正则
            optimized_pattern = self.regex_pattern.replace("(.*)", "(.*?)")
            if optimized_pattern != self.regex_pattern:
                logger.write(f"自动优化正则: {self.regex_pattern} -> {optimized_pattern}")
            
            pattern = re.compile(optimized_pattern, re.DOTALL)
        except re.error as e:
            raise Exception(f"无效的正则表达式: {e}")

        for item in self.epub.infolist():
            content = self.epub.read(item.filename)
            
            # 处理 HTML 文件
            if item.filename.lower().endswith(('.html', '.xhtml', '.htm')):
                try:
                    try:
                        text_content = content.decode('utf-8')
                    except UnicodeDecodeError:
                        text_content = content.decode('gbk', errors='ignore')
                    
                    matches = list(pattern.finditer(text_content))
                    
                    if matches:
                        new_content = ""
                        last_idx = 0
                        
                        for match in matches:
                            start, end = match.span()
                            if match.groups():
                                matched_text = match.group(1)
                            else:
                                matched_text = match.group()
                                
                            # 添加匹配前的文本
                            new_content += text_content[last_idx:start]
                            
                            # 构建替换 HTML 字符串
                            # <span class="reader js_readerFooterNote" data-wr-footernote="注释内容"></span>
                            replacement = f'<span class="reader js_readerFooterNote" data-wr-footernote="{matched_text}"></span>'
                            
                            new_content += replacement
                            last_idx = end
                            
                        # 添加剩余文本
                        new_content += text_content[last_idx:]
                        
                        self.target_epub.writestr(item.filename, new_content.encode('utf-8'))
                    else:
                        self.target_epub.writestr(item, content)
                        
                except Exception as e:
                    logger.write(f"文件 {item.filename} 处理失败: {e}")
                    traceback.print_exc()
                    self.target_epub.writestr(item, content)
            
            # 处理 CSS 文件，追加注释样式
            elif item.filename.lower().endswith('.css'):
                try:
                    try:
                        css_content = content.decode('utf-8')
                    except UnicodeDecodeError:
                        css_content = content.decode('gbk', errors='ignore')
                        
                    # 检查是否已包含样式
                    comment_css = """
/* ========== 正则注释样式 ========== */
span.reader {
    position: relative;
    display: inline-block;
    width: 19px;
    height: 19px;
    vertical-align: sub;
    cursor: pointer;
    margin: 0 3px;
    background-image: url("../Images/note.png");
    background-size: 100%;
    background-repeat: no-repeat;
}

span.reader:hover:after {
    content: attr(data-wr-footernote);
    position: fixed;
    left: 0;
    bottom: 0;
    margin: 1em;
    background: black;
    border-radius: 0.25em;
    color: white;
    padding: 0.5em;
    font-size: 1em;
    font-family: "南构明史稿鉴", sans-serif;
    z-index: 10;
    text-indent: 0em;
}
"""
                    if "/* ========== 正则注释样式 ========== */" not in css_content:
                        css_content += comment_css
                        self.target_epub.writestr(item.filename, css_content.encode('utf-8'))
                    else:
                         self.target_epub.writestr(item, content)
                         
                except Exception as e:
                    logger.write(f"样式文件 {item.filename} 处理失败: {e}")
                    self.target_epub.writestr(item, content)

            else:
                self.target_epub.writestr(item, content)

        self.close_file()
        logger.write(f"正则注释转换完成，输出路径: {self.file_write_path}")

    def close_file(self):
        if self.epub:
            self.epub.close()
        if self.target_epub:
            self.target_epub.close()

    def fail_del_target(self):
        if self.file_write_path and os.path.exists(self.file_write_path):
            os.remove(self.file_write_path)
            logger.write(f"删除临时文件: {self.file_write_path}")

def run(epub_path, output_path, regex_pattern):
    if not regex_pattern:
        logger.write("错误：正则表达式为空")
        return "regex_empty"
        
    logger.write(f"\n正在进行正则注释转换: {epub_path}, 正则: {regex_pattern}")
    tool = None
    try:
        tool = RegexComment(epub_path, output_path, regex_pattern)
        tool.process_file()
        return 0
    except Exception as e:
        logger.write(f"正则注释转换失败: {e}")
        traceback.print_exc()
        if tool:
            tool.close_file()
            tool.fail_del_target()
        return e
