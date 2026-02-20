import zipfile
import os
from bs4 import BeautifulSoup, NavigableString
import traceback
import re
import logging

try:
    from ..log import logwriter
except ImportError:
    from .log import logwriter

logger = logwriter()

class RegexFootnote:
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
            os.path.basename(self.epub_path).replace(".epub", "_note.epub"),
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
            # 强制使用非贪婪匹配，即使用户输入了 (.*)，我们也尝试优化它
            # 但最好的方式是让用户输入正确的正则
            # 这里我们假设用户输入的正则可能包含 greedy matching，
            # 如果我们检测到标签结构，我们可以尝试优化
            
            # 不过，既然是通用工具，最好不要随意修改用户的正则
            # 除非我们明确知道用户想要非贪婪匹配
            # 针对用户反馈的问题：(.*) 匹配了太多。
            # 我们可以在文档中提示，或者在这里做一个简单的替换
            # 如果正则包含 (.*)，我们将其替换为 (.*?)
            # 这是一个比较激进的假设，但对于处理 HTML 标签内的内容通常是正确的
            
            optimized_pattern = self.regex_pattern.replace("(.*)", "(.*?)")
            if optimized_pattern != self.regex_pattern:
                logger.write(f"自动优化正则: {self.regex_pattern} -> {optimized_pattern}")
            
            pattern = re.compile(optimized_pattern, re.DOTALL) # 增加 DOTALL 以支持跨行匹配
        except re.error as e:
            raise Exception(f"无效的正则表达式: {e}")

        for item in self.epub.infolist():
            content = self.epub.read(item.filename)
            
            # 仅处理 HTML 文件
            if item.filename.lower().endswith(('.html', '.xhtml', '.htm')):
                try:
                    # 尝试 decode，如果失败则尝试其他编码
                    try:
                        text_content = content.decode('utf-8')
                    except UnicodeDecodeError:
                        text_content = content.decode('gbk', errors='ignore')
                    
                    footnotes_to_add = []
                    note_index = 1
                    
                    # 查找匹配
                    matches = list(pattern.finditer(text_content))
                    
                    if matches:
                        new_content = ""
                        last_idx = 0
                        
                        # 倒序处理或者正序拼接
                        for match in matches:
                            start, end = match.span()
                            # 优先获取捕获组1，如果没有则使用整体匹配
                            if match.groups():
                                matched_text = match.group(1)
                            else:
                                matched_text = match.group()
                                
                            # 添加匹配前的文本
                            new_content += text_content[last_idx:start]
                            
                            # 构建替换 HTML 字符串
                            # <sup> 
                            #   <a class="duokan-footnote" epub:type="noteref" href="#note1" id="note_ref1"> 
                            #     <img alt="note" class="zhangyue-footnote" src="../Images/note.png" zy-footnote="匹配到的内容"/> 
                            #   </a> 
                            # </sup>
                            
                            replacement = (
                                f'<sup>'
                                f'<a class="duokan-footnote" epub:type="noteref" href="#note{note_index}" id="note_ref{note_index}">'
                                f'<img alt="note" class="zhangyue-footnote" src="../Images/note.png" zy-footnote="{matched_text}"/>'
                                f'</a>'
                                f'</sup>'
                            )
                            new_content += replacement
                            
                            # 准备对应的 aside 内容
                            # <aside epub:type="footnote" id="note1"> 
                            #   <ol class="duokan-footnote-content" style="list-style:none"> 
                            #   <li class="duokan-footnote-item" id="note1"> 
                            #   <p><a href="#note_ref1">匹配到的内容</a></p> 
                            #   </li> 
                            #   </ol> 
                            # </aside>
                            
                            aside_html = (
                                f'<aside epub:type="footnote" id="note{note_index}">'
                                f'<ol class="duokan-footnote-content" style="list-style:none">'
                                f'<li class="duokan-footnote-item" id="note{note_index}">'
                                f'<p><a href="#note_ref{note_index}">{matched_text}</a></p>'
                                f'</li>'
                                f'</ol>'
                                f'</aside>'
                            )
                            
                            footnotes_to_add.append(aside_html)
                            
                            note_index += 1
                            last_idx = end
                            
                        # 添加剩余文本
                        new_content += text_content[last_idx:]
                        
                        # 检查并添加 epub 命名空间
                        if 'xmlns:epub="http://www.idpf.org/2007/ops"' not in new_content:
                            new_content = new_content.replace(
                                '<html', 
                                '<html xmlns:epub="http://www.idpf.org/2007/ops"', 
                                1
                            )

                        # 在 body 结束标签前插入 footnotes
                        # 如果没有 body 结束标签，则追加到文件末尾（虽然不太规范）
                        if footnotes_to_add:
                            footnotes_str = "\n".join(footnotes_to_add)
                            if "</body>" in new_content:
                                new_content = new_content.replace("</body>", f"{footnotes_str}\n</body>")
                            else:
                                new_content += f"\n{footnotes_str}"
                        
                        self.target_epub.writestr(item.filename, new_content.encode('utf-8'))
                    else:
                        self.target_epub.writestr(item, content)
                        
                except Exception as e:
                    logger.write(f"文件 {item.filename} 处理失败: {e}")
                    traceback.print_exc()
                    self.target_epub.writestr(item, content)
            
            # 处理 CSS 文件，追加脚注样式
            elif item.filename.lower().endswith('.css'):
                try:
                    # 尝试 decode
                    try:
                        css_content = content.decode('utf-8')
                    except UnicodeDecodeError:
                        css_content = content.decode('gbk', errors='ignore')
                        
                    # 检查是否已包含通用样式
                    footnote_css = """
/* ========== 脚注通用样式 ========== */ 
 
 /* 脚注标记：上标图标 */ 
 .zhangyue-footnote, 
 .duokan-footnote img { 
   width: 1.3em ; 
   height: 1.3em ; 
   vertical-align: 0.1em; 
   margin-left: 0.2em; 
 } 
 
 /* 防止图片被拉伸（保持比例） */ 
 .zhangyue-footnote { 
   object-fit: contain; 
 } 
 
 /* 脚注容器（文末） */ 
 .duokan-footnote-content { 
   list-style: none; 
   padding-left: 0; 
   margin: 0.8em 0; 
   font-size: 0.9em; 
   line-height: 1.4; 
 } 
 
 /* 脚注项段落 */ 
 .duokan-footnote-item p { 
   margin: 0; 
   text-indent: 0; 
   display: inline; 
 } 
 
 /* 脚注返回链接 */ 
 .duokan-footnote-item a { 
   text-decoration: none; 
   color: inherit; 
 } 
 
 /* 去除脚注标记的链接下划线 */ 
 a.duokan-footnote, 
 .sup a.duokan-footnote, 
 span a.duokan-footnote { 
   text-decoration: none !important; 
 }
"""
                    if "/* ========== 脚注通用样式 ========== */" not in css_content:
                        css_content += footnote_css
                        self.target_epub.writestr(item.filename, css_content.encode('utf-8'))
                    else:
                         self.target_epub.writestr(item, content)
                         
                except Exception as e:
                    logger.write(f"样式文件 {item.filename} 处理失败: {e}")
                    self.target_epub.writestr(item, content)

            else:
                self.target_epub.writestr(item, content)

        self.close_file()
        logger.write(f"EPUB正则注释替换完成，输出路径: {self.file_write_path}")

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
        
    logger.write(f"\n正在进行正则注释替换: {epub_path}, 正则: {regex_pattern}")
    tool = None
    try:
        tool = RegexFootnote(epub_path, output_path, regex_pattern)
        tool.process_file()
        return 0
    except Exception as e:
        logger.write(f"正则注释替换失败: {e}")
        traceback.print_exc()
        if tool:
            tool.close_file()
            tool.fail_del_target()
        return e
