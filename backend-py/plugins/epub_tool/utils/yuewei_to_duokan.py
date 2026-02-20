import zipfile
import os
from bs4 import BeautifulSoup
import traceback
import re

try:
    from ..log import logwriter
except ImportError:
    from .log import logwriter

logger = logwriter()

class YueweiToDuokan:
    def __init__(self, epub_path, output_path):
        if not os.path.exists(epub_path):
            raise Exception("EPUB文件不存在")

        self.epub_path = os.path.normpath(epub_path)
        self.epub = zipfile.ZipFile(epub_path)
        
        if output_path and os.path.exists(output_path):
            if os.path.isfile(output_path):
                raise Exception("输出路径不能是文件")
        else:
            output_path = os.path.dirname(epub_path)
            
        self.output_path = os.path.normpath(output_path)
        self.file_write_path = os.path.join(
            self.output_path,
            os.path.basename(self.epub_path).replace(".epub", "_duokan.epub"),
        )
        
        if os.path.exists(self.file_write_path):
            os.remove(self.file_write_path)
            
        self.target_epub = zipfile.ZipFile(
            self.file_write_path,
            "w",
            zipfile.ZIP_DEFLATED,
        )

    def process(self):
        try:
            for item in self.epub.infolist():
                content = self.epub.read(item.filename)
                
                if item.filename.lower().endswith(('.html', '.xhtml', '.htm')):
                    try:
                        text_content = content.decode('utf-8')
                        
                        # 使用正则表达式查找所有阅微脚注span标签
                        import re
                        
                        # HTML转义函数
                        def escape_html(text):
                            """转义HTML特殊字符"""
                            if not text:
                                return text
                            # 必须按顺序转义：& 最先
                            text = text.replace('&', '&amp;')
                            text = text.replace('<', '&lt;')
                            text = text.replace('>', '&gt;')
                            text = text.replace('"', '&quot;')
                            return text
                        
                        # 添加epub命名空间函数
                        def add_epub_namespace(html_content):
                            """在html标签中添加epub命名空间"""
                            # 检查是否已经包含epub命名空间（使用正则表达式检查各种格式）
                            import re
                            epub_ns_pattern = r'xmlns:epub\s*=\s*["\']http://www\.idpf\.org/2007/ops["\']'
                            if re.search(epub_ns_pattern, html_content):
                                return html_content
                            
                            # 匹配html标签，添加epub命名空间
                            # 处理多种格式的html标签，包括跨行
                            # 匹配 <html 开头，后面跟任意字符（包括换行）直到>
                            # 使用re.DOTALL使.匹配换行符
                            pattern = r'(<html\b[^>]*)(>)'
                            
                            def add_namespace(match):
                                tag_start = match.group(1)
                                tag_end = match.group(2)
                                # 如果已经有xmlns:epub属性，直接返回（再次检查，以防万一）
                                if re.search(epub_ns_pattern, tag_start):
                                    return match.group(0)
                                
                                # 检查xmlns属性（可能使用单引号或双引号）
                                xmlns_pattern = r'xmlns\s*=\s*["\']http://www\.w3\.org/1999/xhtml["\']'
                                xmlns_match = re.search(xmlns_pattern, tag_start)
                                
                                if xmlns_match:
                                    # 在xmlns属性后添加epub命名空间
                                    xmlns_attr = xmlns_match.group(0)
                                    # 在xmlns属性值后添加epub命名空间
                                    # 找到xmlns属性的结束位置
                                    start_pos = xmlns_match.start()
                                    end_pos = xmlns_match.end()
                                    # 在xmlns属性后添加epub命名空间
                                    new_tag_start = (tag_start[:end_pos] + 
                                                   ' xmlns:epub="http://www.idpf.org/2007/ops"' + 
                                                   tag_start[end_pos:])
                                    return new_tag_start + tag_end
                                else:
                                    # 如果没有找到xmlns属性，在html标签后直接添加
                                    return tag_start + ' xmlns:epub="http://www.idpf.org/2007/ops"' + tag_end
                            
                            # 替换第一个匹配的html标签（应该只有一个）
                            # 使用re.DOTALL处理跨行标签
                            new_html = re.sub(pattern, add_namespace, html_content, count=1, flags=re.IGNORECASE|re.DOTALL)
                            return new_html
                        
                        # 匹配阅微脚注span标签的正则表达式
                        # 匹配格式: <span class="reader js_readerFooterNote" data-wr-footernote="..."></span>
                        # 允许class属性的任意顺序、额外的空格和其他属性
                        # 使用更灵活的模式，避免\b可能的问题
                        span_pattern1 = r'<span[^>]*class="[^"]*reader[^"]*js_readerFooterNote[^"]*"[^>]*data-wr-footernote="([^"]*)"[^>]*>\s*</span>'
                        span_pattern2 = r'<span[^>]*class="[^"]*js_readerFooterNote[^"]*reader[^"]*"[^>]*data-wr-footernote="([^"]*)"[^>]*>\s*</span>'
                        
                        # 添加epub命名空间（如果不存在）
                        text_content = add_epub_namespace(text_content)
                        
                        footnotes = []
                        
                        # 查找所有匹配的span标签（使用两个模式）
                        matches = []
                        # 使用第一个模式查找
                        for match in re.finditer(span_pattern1, text_content):
                            matches.append(match)
                        # 使用第二个模式查找
                        for match in re.finditer(span_pattern2, text_content):
                            # 检查是否已经匹配过（避免重复）
                            span_text = match.group(0)
                            if not any(span_text == m.group(0) for m in matches):
                                matches.append(match)
                        
                        # 按位置排序
                        matches.sort(key=lambda m: m.start())
                        
                        # 首先，为所有匹配分配正确的编号（按原始顺序）
                        # 创建编号映射：匹配位置 -> 编号
                        position_number_map = {}
                        for i, match in enumerate(matches, 1):
                            position_number_map[match.start()] = i
                        
                        # 从后向前替换，避免索引变化问题
                        for match in reversed(matches):
                            note_content_raw = match.group(1)
                            # 转义HTML特殊字符
                            note_content_escaped = escape_html(note_content_raw)
                            # 根据匹配位置获取正确的编号
                            note_number = position_number_map[match.start()]
                            note_id = f"note{note_number}"
                            note_ref_id = f"note_ref{note_number}"
                            
                            # 按照用户提供的精确格式生成替换内容
                            # 注意：保留用户格式中的换行和缩进，但移除可能破坏HTML结构的额外闭合标签
                            replacement = f'''      <sup> 
         <a class="duokan-footnote" epub:type="noteref" href="#{note_id}" id="{note_ref_id}"> 
           <img alt="note" class="zhangyue-footnote" src="../Images/note.png" zy-footnote="{note_content_escaped}"/> 
         </a> 
       </sup>'''
                            
                            # 替换匹配的span标签
                            start, end = match.span()
                            text_content = text_content[:start] + replacement + text_content[end:]
                            
                            # 收集脚注信息，用于在文件末尾添加
                            footnotes.append({
                                'id': note_id,
                                'ref_id': note_ref_id,
                                'content': note_content_escaped,
                                'position': start  # 保存原始位置信息
                            })
                        
                        # 在文件末尾添加脚注
                        if footnotes:
                            # 按编号排序脚注（note1, note2, note3...）
                            def get_note_number(note):
                                # 从id中提取数字，如"note1" -> 1
                                import re
                                match = re.search(r'note(\d+)', note['id'])
                                return int(match.group(1)) if match else 0
                            
                            footnotes_sorted = sorted(footnotes, key=get_note_number)
                            
                            footnote_section = "\n\n"
                            for note in footnotes_sorted:
                                footnote = f'''  <aside epub:type="footnote" id="{note['id']}"> 
   <ol class="duokan-footnote-content" style="list-style:none"> 
   <li class="duokan-footnote-item"> 
   <p><a href="#{note['ref_id']}">{note['content']}</a></p> 
   </li> 
   </ol> 
   </aside>'''
                                footnote_section += footnote + "\n"
                            
                            # 找到body结束标签的位置，在之前插入脚注
                            # 只替换最后一个</body>标签，避免破坏文档结构
                            if '</body>' in text_content:
                                # 分割字符串，只替换最后一个</body>
                                parts = text_content.rsplit('</body>', 1)
                                if len(parts) == 2:
                                    text_content = parts[0] + footnote_section + '</body>' + parts[1]
                                else:
                                    # 回退到简单替换
                                    text_content = text_content.replace('</body>', footnote_section + '</body>')
                            else:
                                # 如果没有body标签，在文件末尾添加
                                text_content += footnote_section
                        
                        new_content = text_content.encode('utf-8')
                        self.target_epub.writestr(item.filename, new_content)
                        
                    except Exception as e:
                        logger.write(f"处理文件 {item.filename} 失败: {e}")
                        traceback.print_exc()
                        self.target_epub.writestr(item, content)
                else:
                    self.target_epub.writestr(item, content)
            
            self.close_file()
            # Return tuple compatible with cli.py handling
            return 0, self.file_write_path
            
        except Exception as e:
            logger.write(f"处理EPUB失败: {e}")
            traceback.print_exc()
            self.close_file()
            self.fail_del_target()
            return 1, str(e)

    def close_file(self):
        if self.epub:
            self.epub.close()
        if self.target_epub:
            self.target_epub.close()

    def fail_del_target(self):
        if self.file_write_path and os.path.exists(self.file_write_path):
            os.remove(self.file_write_path)

def run(epub_path, output_path=None):
    logger.write(f"\\n正在执行阅微转多看: {epub_path}")
    tool = YueweiToDuokan(epub_path, output_path)
    return tool.process()

