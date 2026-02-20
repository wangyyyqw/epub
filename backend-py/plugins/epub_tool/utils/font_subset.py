import zipfile
import os
from bs4 import BeautifulSoup
from tinycss2 import parse_stylesheet, serialize, parse_declaration_list
import re
from fontTools import subset
from fontTools.ttLib import TTFont
from io import BytesIO
import traceback
import logging

try:
    from ..log import logwriter
except ImportError:
    from .log import logwriter

logger = logwriter()

class FontSubset:
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
            logger.write(f"输出路径不存在，使用默认路径: {output_path}")
            
        self.output_path = os.path.normpath(output_path)
        self.file_write_path = os.path.join(
            self.output_path,
            os.path.basename(self.epub_path).replace(".epub", "_subset.epub"),
        )
        
        if os.path.exists(self.file_write_path):
            os.remove(self.file_write_path)
            
        self.htmls = []
        self.css = []
        self.fonts = []
        self.ori_files = []
        self.font_to_font_family_mapping = {}
        self.css_selector_to_font_mapping = {}
        self.font_to_char_mapping = {}
        self.target_epub = None
        
        for file in self.epub.namelist():
            if file.lower().endswith((".html", ".xhtml")):
                self.htmls.append(file)
            elif file.lower().endswith(".css"):
                self.ori_files.append(file)
                self.css.append(file)
            elif file.lower().endswith((".ttf", ".otf", ".woff")):
                self.fonts.append(file)
            else:
                self.ori_files.append(file)

    def create_target_epub(self):
        self.target_epub = zipfile.ZipFile(
            self.file_write_path,
            "w",
            zipfile.ZIP_STORED,
        )

    def find_local_fonts_mapping(self):
        mapping = {}
        for css in self.css:
            with self.epub.open(css) as f:
                content = f.read().decode("utf-8")
                rules = parse_stylesheet(content)
                for rule in rules:
                    if rule.type == "at-rule" and rule.lower_at_keyword == "font-face":
                        declarations = parse_declaration_list(rule.content)
                        font_family = None
                        src_urls = []
                        
                        for decl in declarations:
                            if decl.type == "declaration":
                                if decl.lower_name == "font-family":
                                    font_family = serialize(decl.value).strip().strip('"\'')
                                elif decl.lower_name == "src":
                                    for token in decl.value:
                                        if token.type == 'url':
                                            src_urls.append(token.value)
                                        elif token.type == 'function' and token.lower_name == 'url':
                                            val = serialize(token.arguments).strip().strip('"\'')
                                            src_urls.append(val)
                        
                        if font_family and src_urls:
                            for url in src_urls:
                                # 尝试匹配文件名
                                url_basename = os.path.basename(url).split('?')[0].split('#')[0]
                                for font_path in self.fonts:
                                    if os.path.basename(font_path) == url_basename:
                                        mapping[font_family] = font_path
                                        
        self.font_to_font_family_mapping = mapping

    def find_selector_to_font_mapping(self):
        mapping = {}
        for css in self.css:
            with self.epub.open(css) as f:
                content = f.read().decode("utf-8")
                rules = parse_stylesheet(content)
                for rule in rules:
                    if rule.type == "qualified-rule":
                        selector = serialize(rule.prelude).strip()
                        declarations = parse_declaration_list(rule.content)
                        for declaration in declarations:
                            if declaration.type == "declaration" and declaration.lower_name == "font-family":
                                font_family_values = [
                                    token.value
                                    for token in declaration.value
                                    if token.type == "string" or token.type == "ident"
                                ]
                                if font_family_values:
                                    primary_font = font_family_values[0].strip("'\"")
                                    if primary_font in self.font_to_font_family_mapping:
                                        if primary_font not in mapping:
                                            mapping[selector] = self.font_to_font_family_mapping[primary_font]
        self.css_selector_to_font_mapping = dict(sorted(mapping.items(), reverse=True))

    def find_char_mapping(self):
        mapping = {}
        # 初始化所有字体文件的字符集为空字符串
        for font in self.fonts:
            mapping[font] = set()

        for one_html in self.htmls:
            with self.epub.open(one_html) as f:
                content = f.read().decode("utf-8")
                soup = BeautifulSoup(content, "html.parser")
                
                # 1. 按照 CSS 选择器查找
                for css_selector, font_file in self.css_selector_to_font_mapping.items():
                    elements = soup.select(css_selector)
                    for element in elements:
                        text = element.get_text(strip=True)
                        mapping[font_file].update(text)
                
                # TODO: 这里可能漏掉没有特定 class 但继承了 font-family 的文本
                # 或者直接定义在 style 属性里的 font-family
                # 为了保险起见，如果字体被全局应用（如 body），应该包含所有文本
                # 目前逻辑仅处理 explicit selector mapping，类似 encrypt_font 的逻辑

        self.font_to_char_mapping = mapping

    def get_mapping(self):
        self.find_local_fonts_mapping()
        self.find_selector_to_font_mapping()
        self.find_char_mapping()
        logger.write(f"字体文件映射: {self.font_to_font_family_mapping}")
        logger.write(f"CSS选择器映射: {self.css_selector_to_font_mapping}")
        # logger.write(f"字体文件到字符映射: {self.font_to_char_mapping}") # 可能太大，不打印
        return self.font_to_char_mapping

    def subset_fonts(self):
        self.create_target_epub()
        
        removed_fonts = set()
        
        # 处理字体文件
        for font_path in self.fonts:
            if font_path in self.font_to_char_mapping and self.font_to_char_mapping[font_path]:
                text = "".join(self.font_to_char_mapping[font_path])
                logger.write(f"正在处理字体: {font_path}, 字符数: {len(text)}")
                
                try:
                    # 读取原始字体
                    font_data = self.epub.read(font_path)
                    font = TTFont(BytesIO(font_data))
                    
                    # 配置 subsetter
                    options = subset.Options()
                    options.flavor = None # 保持原有 flavor (ttf/otf)
                    # 保留常用表，去除不需要的
                    # options.drop_tables = [] 
                    
                    subsetter = subset.Subsetter(options=options)
                    subsetter.populate(text=text)
                    subsetter.subset(font)
                    
                    # 保存 subset 后的字体
                    font_stream = BytesIO()
                    font.save(font_stream)
                    self.target_epub.writestr(font_path, font_stream.getvalue(), zipfile.ZIP_DEFLATED)
                    logger.write(f"字体 {font_path} 子集化完成")
                    
                except Exception as e:
                    logger.write(f"字体 {font_path} 子集化失败: {e}")
                    traceback.print_exc()
                    # 失败则写入原文件
                    self.target_epub.writestr(font_path, self.epub.read(font_path), zipfile.ZIP_DEFLATED)
            else:
                logger.write(f"字体 {font_path} 未检测到使用文本，从EPUB中移除")
                removed_fonts.add(font_path)
                # 不写入 target_epub，即删除

        # 复制其他文件
        for file in self.ori_files:
            # 如果是 OPF 文件，需要移除被删除的字体 manifest item
            if file.lower().endswith(".opf") and removed_fonts:
                content = self.epub.read(file).decode('utf-8')
                try:
                    soup = BeautifulSoup(content, 'xml')
                    manifest = soup.find('manifest')
                    if manifest:
                        items_to_remove = []
                        for item in manifest.find_all('item'):
                            href = item.get('href')
                            if href:
                                # 解析相对路径。OPF 中的 href 是相对于 OPF 文件所在目录的
                                opf_dir = os.path.dirname(file)
                                # 注意：EPUB 路径分隔符为 /，需要确保处理正确
                                abs_href = opf_dir + '/' + href if opf_dir else href
                                # 简单规范化路径（处理 .. 等）
                                # 这里我们简单模拟，因为 zipfile 里的路径通常是规范的
                                # 如果 abs_href 匹配 removed_fonts 中的某一项
                                # 考虑到路径可能包含 ..，我们尝试匹配文件名或者使用更复杂的解析
                                # 这里为了健壮性，我们尝试多种匹配
                                
                                # 1. 直接匹配
                                if abs_href in removed_fonts:
                                    items_to_remove.append(item)
                                    continue
                                    
                                # 2. 处理规范化路径 (Python os.path.normpath 在 Windows 下用 \，所以要小心)
                                # 我们可以自己写个简单的 normpath for url
                                def simple_normpath(path):
                                    parts = path.split('/')
                                    stack = []
                                    for part in parts:
                                        if part == '..':
                                            if stack: stack.pop()
                                        elif part == '.':
                                            continue
                                        else:
                                            stack.append(part)
                                    return '/'.join(stack)
                                    
                                norm_abs_href = simple_normpath(abs_href)
                                if norm_abs_href in removed_fonts:
                                    items_to_remove.append(item)
                                    continue
                                    
                                # 3. 尝试匹配文件名（如果结构简单）
                                # 如果字体文件名唯一，这通常有效
                                font_name = os.path.basename(href)
                                for rm_font in removed_fonts:
                                    if os.path.basename(rm_font) == font_name:
                                        # 再次确认路径后缀匹配，防止误删同名文件
                                        if rm_font.endswith(href):
                                            items_to_remove.append(item)
                                            break
                        
                        if items_to_remove:
                            logger.write(f"从OPF中移除 {len(items_to_remove)} 个无效字体引用")
                            for item in items_to_remove:
                                item.decompose()
                            
                            # 写入修改后的 OPF
                            self.target_epub.writestr(file, str(soup).encode('utf-8'), zipfile.ZIP_DEFLATED)
                            continue

                except Exception as e:
                    logger.write(f"清理OPF失败: {e}，将写入原始OPF")
                    traceback.print_exc()
            
            # 默认情况：直接复制
            self.target_epub.writestr(file, self.epub.read(file), zipfile.ZIP_DEFLATED)
            
        # 复制 HTML 文件 (无需修改内容)
        for file in self.htmls:
            self.target_epub.writestr(file, self.epub.read(file), zipfile.ZIP_DEFLATED)
            
        self.close_file()
        logger.write(f"EPUB字体子集化完成，输出路径: {self.file_write_path}")

    def close_file(self):
        if self.epub:
            self.epub.close()
        if self.target_epub:
            self.target_epub.close()

    def fail_del_target(self):
        if self.file_write_path and os.path.exists(self.file_write_path):
            os.remove(self.file_write_path)
            logger.write(f"删除临时文件: {self.file_write_path}")

def run_epub_font_subset(epub_path, output_path=None):
    logger.write(f"\n正在尝试对EPUB进行字体子集化: {epub_path}")
    fs = FontSubset(epub_path, output_path)
    if len(fs.fonts) == 0:
        logger.write("没有找到字体文件，退出")
        return "skip"
    
    logger.write(f"包含字体文件: {', '.join(fs.fonts)}")
    
    try:
        fs.get_mapping()
        fs.subset_fonts()
        
        # Summary Log
        kept_fonts = [f for f in fs.fonts if f in fs.font_to_char_mapping and fs.font_to_char_mapping[f]]
        removed_fonts = [f for f in fs.fonts if f not in kept_fonts]
        
        logger.write("\n" + "="*30)
        logger.write("【字体子集化结果统计】")
        logger.write(f"处理前字体数: {len(fs.fonts)}")
        logger.write(f"保留字体数: {len(kept_fonts)}")
        logger.write(f"移除字体数: {len(removed_fonts)}")
        
        if kept_fonts:
            logger.write("\n[保留并压缩的字体]:")
            for f in kept_fonts:
                count = len(fs.font_to_char_mapping[f])
                logger.write(f"  - {f} (包含 {count} 个字符)")
                
        if removed_fonts:
            logger.write("\n[未使用并移除的字体]:")
            for f in removed_fonts:
                logger.write(f"  - {f}")
        logger.write("="*30 + "\n")
        
        return 0
    except Exception as e:
        logger.write(f"字体子集化失败: {e}")
        traceback.print_exc()
        fs.close_file()
        fs.fail_del_target()
        return e

if __name__ == "__main__":
    epub_read_path = input("请输入EPUB文件路径: ")
    run_epub_font_subset(epub_read_path)
