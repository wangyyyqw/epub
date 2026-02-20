import zipfile
import os
import re
import traceback

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:
    BeautifulSoup = None

try:
    from ..log import logwriter
except ImportError:
    from .log import logwriter

logger = logwriter()

class FootnoteToComment:
    def __init__(self, epub_path, output_path, regex_pattern=None):
        if not os.path.exists(epub_path):
            raise Exception("EPUB文件不存在")
        if not BeautifulSoup:
            raise Exception("需要安装 beautifulsoup4 库")

        self.epub_path = os.path.normpath(epub_path)
        self.output_path = output_path
        self.regex_pattern = regex_pattern if regex_pattern else r'^#+'
        self.epub = zipfile.ZipFile(epub_path)
        
        if output_path and os.path.exists(output_path):
            if os.path.isfile(output_path):
                raise Exception("输出路径不能是文件")
        else:
            output_path = os.path.dirname(epub_path)
            
        self.output_path = os.path.normpath(output_path)
        self.file_write_path = os.path.join(
            self.output_path,
            os.path.basename(self.epub_path).replace(".epub", "_ftc.epub"), # ftc = footnote to comment
        )
        
        if os.path.exists(self.file_write_path):
            os.remove(self.file_write_path)
            
        self.target_epub = zipfile.ZipFile(
            self.file_write_path,
            "w",
            zipfile.ZIP_DEFLATED,
        )

    def process_file(self):
        for item in self.epub.infolist():
            content = self.epub.read(item.filename)
            
            # 处理 HTML 文件
            if item.filename.lower().endswith(('.html', '.xhtml', '.htm')):
                try:
                    try:
                        text_content = content.decode('utf-8')
                    except UnicodeDecodeError:
                        text_content = content.decode('gbk', errors='ignore')
                    
                    soup = BeautifulSoup(text_content, 'html.parser')
                    
                    # 查找所有指向内部 ID 的链接
                    # 使用正则匹配 href
                    try:
                        links = soup.find_all('a', href=re.compile(self.regex_pattern))
                    except Exception as e:
                        logger.write(f"正则匹配出错: {e}")
                        links = []
                    
                    targets_to_remove = set()
                    modified = False
                    
                    for link in links:
                        href = link.get('href')
                        target_id = href[1:] # 去掉 #
                        
                        # 在当前 soup 中查找 target
                        target_element = soup.find(id=target_id)
                        if target_element:
                            content_node = target_element
                            should_remove_node = target_element
                            
                            # 策略优化：如果 target 是 a 标签（通常是回跳链接），则获取其父元素作为内容容器
                            if target_element.name == 'a' and target_element.parent and target_element.parent.name in ['p', 'li', 'div', 'dd']:
                                content_node = target_element.parent
                                should_remove_node = target_element.parent

                            # 提取纯文本内容
                            note_text = content_node.get_text(strip=True)
                            
                            # 尝试去除回跳链接的文本（假设回跳链接文本与源链接文本一致）
                            link_text = link.get_text(strip=True)
                            if link_text and note_text.startswith(link_text):
                                note_text = note_text[len(link_text):].strip()
                            
                            if note_text:
                                # 创建新的 span 元素
                                new_span = soup.new_tag('span')
                                new_span['class'] = 'reader js_readerFooterNote'
                                new_span['data-wr-footernote'] = note_text
                                
                                # 替换 a 标签
                                link.replace_with(new_span)
                                
                                # 记录待删除的 target
                                targets_to_remove.add(should_remove_node)
                                modified = True
                    
                    # 删除原脚注元素
                    for target in targets_to_remove:
                        # 检查 target 是否还在 DOM 中 (可能包含多个引用指向同一 target)
                        # 如果是多对一，第一次删除后，后续引用处理时 target 已经不在 DOM 树中吗？
                        # BeautifulSoup 的 replace_with 是移除节点。
                        # 这里我们只读取 text，不移动节点。只有在这里才真正移除。
                        # 但如果多个 link 指向同一个 target，targets_to_remove 是 set，只会存一个。
                        # 所以直接 safe remove。
                        if target.parent:
                             target.decompose()
                             
                    if modified:
                        # 修正 html 结构（BeautifulSoup 可能会处理不当）
                        # 确保 epub namespace 存在 (如果原始就有，bs4 通常会保留，但有时需要检查)
                        # 这里简单处理，直接转 string
                        new_html = str(soup)
                        self.target_epub.writestr(item.filename, new_html.encode('utf-8'))
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
                    # 复用 regex_comment 的样式
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
                    if "span.reader" not in css_content:
                        css_content += comment_css
                        self.target_epub.writestr(item.filename, css_content.encode('utf-8'))
                    else:
                         self.target_epub.writestr(item, content)
                         
                except Exception as e:
                    logger.write(f"样式文件 {item.filename} 处理失败: {e}")
                    self.target_epub.writestr(item, content)

            # 处理 OPF 文件，添加 note.png 资源
            elif item.filename.lower().endswith('.opf'):
                try:
                    # 读取 note.png
                    note_png_path = os.path.join(os.path.dirname(__file__), 'note.png')
                    if os.path.exists(note_png_path):
                        # 解析 OPF
                        soup_opf = BeautifulSoup(content, 'xml')
                        manifest = soup_opf.find('manifest')
                        
                        if manifest:
                            # 检查 manifest 中是否已有 note.png
                            # 我们假设路径固定为 Images/note.png (相对于 OPF)
                            # 对应的 href 应该是 "Images/note.png"
                            
                            # 获取 OPF所在目录
                            opf_dir = os.path.dirname(item.filename)
                            # 图片在 epub 中的路径
                            image_path_in_epub = os.path.join(opf_dir, 'Images/note.png').replace('\\', '/')
                            # 在 manifest 中的 href
                            image_href = 'Images/note.png'
                            
                            item_exists = manifest.find('item', href=image_href)
                            if not item_exists:
                                # 创建 item
                                new_item = soup_opf.new_tag('item')
                                new_item['id'] = 'note_png_res'
                                new_item['href'] = image_href
                                new_item['media-type'] = 'image/png'
                                manifest.append(new_item)
                                logger.write(f"在 manifest 中添加 note.png: {image_href}")
                            
                            # 写入修改后的 OPF
                            new_opf_content = str(soup_opf)
                            self.target_epub.writestr(item.filename, new_opf_content.encode('utf-8'))
                            
                            # 写入 note.png 文件
                            with open(note_png_path, 'rb') as f:
                                png_data = f.read()
                                self.target_epub.writestr(image_path_in_epub, png_data)
                                logger.write(f"写入图片文件: {image_path_in_epub}")
                        else:
                            self.target_epub.writestr(item, content)
                    else:
                        logger.write("未找到 note.png 源文件，跳过注入")
                        self.target_epub.writestr(item, content)
                        
                except Exception as e:
                    logger.write(f"OPF 文件 {item.filename} 处理失败: {e}")
                    traceback.print_exc()
                    self.target_epub.writestr(item, content)

            else:
                self.target_epub.writestr(item, content)

        self.close_file()
        logger.write(f"脚注链接转换完成，输出路径: {self.file_write_path}")

    def close_file(self):
        if self.epub:
            self.epub.close()
        if self.target_epub:
            self.target_epub.close()

    def fail_del_target(self):
        if self.file_write_path and os.path.exists(self.file_write_path):
            os.remove(self.file_write_path)
            logger.write(f"删除临时文件: {self.file_write_path}")

def run(epub_path, output_path=None, regex_pattern=None):
    logger.write(f"\n正在进行脚注链接转换: {epub_path}")
    tool = None
    try:
        tool = FootnoteToComment(epub_path, output_path, regex_pattern)
        tool.process_file()
        return 0
    except Exception as e:
        logger.write(f"脚注链接转换失败: {e}")
        traceback.print_exc()
        if tool:
            tool.close_file()
            tool.fail_del_target()
        return e
