#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import zipfile
import traceback
from copy import deepcopy
from typing import Sized

try:
    from ..log import logwriter
except ImportError:
    from .log import logwriter

logger = logwriter()

# 全局开关配置
BOOK_NOREPEAT_SWITCH = False  # 整本书不重复注音开关
PAGE_NOREPEAT_SWITCH = False  # 页面内不重复注音开关
READ_PHRASES = True          # 是否使用短语词典校准多音字

UEMPTY = ''
# 状态定义
(START, END, FAIL, WAIT_TAIL) = list(range(4))
# 条件定义
(TAIL, ERROR, MATCHED_SWITCH, UNMATCHED_SWITCH, CONNECTOR) = list(range(5))

# 全局变量
MAPS = {}
LOG = {}
LOG_PER_PAGE = {}

# 导入字典 - 尝试多种导入方式
try:
    # 首先尝试相对导入（作为模块使用时）
    from .dict.ShengPiZi import shengpizi_dict
    from .dict.Phrases import phrases_dict
    from .dict.国标一二级汉字 import GB_lev_1
    from .dict.完整拼音字典 import pinyin_dict
except ImportError:
    try:
        # 尝试绝对导入（直接运行时）
        from dict.ShengPiZi import shengpizi_dict
        from dict.Phrases import phrases_dict
        from dict.国标一二级汉字 import GB_lev_1
        from dict.完整拼音字典 import pinyin_dict
    except ImportError as e:
        logger.write(f"导入字典失败: {e}")
        # 尝试从PhoneticNotation目录导入
        import sys
        phonetic_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'PhoneticNotation', 'Dict')
        sys.path.insert(0, phonetic_path)
        try:
            from ShengPiZi import shengpizi_dict
            from Phrases import phrases_dict
            from 国标一二级汉字 import GB_lev_1
            from 完整拼音字典 import pinyin_dict
        except ImportError as e2:
            logger.write(f"所有字典导入尝试均失败: {e2}")
            raise ImportError("无法导入生僻字字典，请检查字典文件是否存在")




class Node(object):
    """转换节点"""
    def __init__(self, from_word, to_phonetic=None, is_tail=True, have_child=False):
        self.from_word = from_word
        if to_phonetic is None:  # 字典中没有该键
            self.to_phonetic = from_word
            self.is_original = True  # 需返回原值
        else:  # 字典中存在该键
            if BOOK_NOREPEAT_SWITCH and from_word in LOG:
                self.to_phonetic = from_word
                self.is_original = True
            elif PAGE_NOREPEAT_SWITCH and from_word in LOG_PER_PAGE:
                self.to_phonetic = from_word
                self.is_original = True
            else:
                self.to_phonetic = to_phonetic or from_word  # 如果字典中存在该键但对应值为空，则返回原值
                self.is_original = False

        self.is_tail = is_tail  # 是否尾节点
        self.have_child = have_child

    def is_original_long_word(self):  # 在字典中找不到键的短语
        return self.is_original and len(self.from_word) > 1

    def is_follow(self, chars):  # 查询传入字符串是否该节点键值前缀部分
        return chars != self.from_word[:-1]

    def add_phonetic(self):
        if isinstance(self.to_phonetic, str):
            return self.to_phonetic
        elif isinstance(self.to_phonetic, list):
            if len(self.from_word) == 1:
                return '<ruby>' + self.from_word + '<rt>' + self.to_phonetic[0] + '</rt></ruby>'
            elif len(self.from_word) > 1 and len(self.from_word) == len(self.to_phonetic):
                index, result = 0, ''
                for char in self.from_word:
                    if not self.to_phonetic[index]:
                        result += char
                    else:
                        result += '<ruby>' + char + '<rt>' + self.to_phonetic[index] + '</rt></ruby>'
                    index += 1
                return result
        return self.from_word

    def __str__(self):
        return '<Node, %s, %s, %s, %s>' % (repr(self.from_word),
                repr(self.to_phonetic), self.is_tail, self.have_child)

    __repr__ = __str__


class ConvertMap(object):
    """转换映射表"""
    def __init__(self, mapping=None):
        self._map = {}
        if mapping:
            self.set_convert_map(mapping)

    def set_convert_map(self, mapping):
        convert_map = {}
        have_child = {}
        max_key_length = 0
        for key in sorted(mapping.keys()):
            if len(key) > 1:
                for i in range(1, len(key)):
                    parent_key = key[:i]
                    have_child[parent_key] = True
            have_child[key] = False
            max_key_length = max(max_key_length, len(key))
        for key in sorted(have_child.keys()):
            convert_map[key] = (key in mapping, have_child[key],
                    mapping.get(key, UEMPTY))
        self._map = convert_map
        self.max_key_length = max_key_length

    def __getitem__(self, k):
        try:
            is_tail, have_child, to_phonetic = self._map[k]
            return Node(k, to_phonetic, is_tail, have_child)
        except:
            return Node(k)

    def __contains__(self, k):
        return k in self._map

    def __len__(self):
        return len(self._map)


def init_maps():
    """初始化转换映射表"""
    global MAPS
    
    mapping = {}
    
    # 合并生僻字字典
    for code in shengpizi_dict:
        mapping[code] = shengpizi_dict[code]
    
    # 合并短语词典
    for key in phrases_dict:
        mapping[key] = phrases_dict[key]
    
    MAPS = ConvertMap(mapping)


class StatesMachineException(Exception):
    pass


class StatesMachine(object):
    """状态机"""
    def __init__(self):
        self.state = START
        self.final = UEMPTY
        self.len = 0
        self.pool = UEMPTY
        self.last_matched = None  # 用于记录，不参与转化过程

    def clone(self, pool):
        new = deepcopy(self)
        new.state = WAIT_TAIL
        new.pool = pool
        new.last_matched = self.last_matched
        return new

    def feed(self, char, map):
        self.node = node = map[self.pool + char]
        if node.have_child:
            if node.is_tail:
                if node.is_original:
                    # 该字符串属于字典中的键值，也属于某键前缀，但该键值对应值为None
                    cond = UNMATCHED_SWITCH
                else:  # 该字符串属于字典中的键，又属于某键前缀
                    cond = MATCHED_SWITCH
            else:  # 该字符串不属于字典中的键，但属于某键前缀
                cond = CONNECTOR
        else:  # 该字符串不属于某键前缀
            if node.is_tail:  # 该字符串属于字典中的键或者非键
                cond = TAIL
            else:  # 未知错误状态
                cond = ERROR

        new = None
        if cond == ERROR:
            self.state = FAIL
        elif cond == TAIL:
            if self.state == WAIT_TAIL and node.is_original_long_word():
                self.state = FAIL
                # 录入LOG
                if self.last_matched is not None:
                    key, value = self.last_matched
                    LOG[key] = value
                    LOG_PER_PAGE[key] = value
            else:
                self.final += node.add_phonetic()
                self.len += 1
                self.pool = UEMPTY
                self.state = END
                # 录入LOG
                if not node.is_original:
                    LOG[node.from_word] = node.to_phonetic
                    LOG_PER_PAGE[node.from_word] = node.to_phonetic
        elif self.state == START or self.state == WAIT_TAIL:
            if cond == MATCHED_SWITCH:
                self.last_matched = [node.from_word, node.to_phonetic]
                new = self.clone(node.from_word)
                self.final += node.add_phonetic()
                self.len += 1
                self.state = END
                self.pool = UEMPTY
            elif cond == UNMATCHED_SWITCH or cond == CONNECTOR:
                if self.state == START:
                    new = self.clone(node.from_word)
                    self.final += node.add_phonetic()
                    self.len += 1
                    self.state = END
                else:
                    if node.is_follow(self.pool):
                        self.state = FAIL
                    else:
                        self.pool = node.from_word
        elif self.state == END:
            # END is a new START
            self.state = START
            new = self.feed(char, map)
        elif self.state == FAIL:
            raise StatesMachineException('Translate States Machine '
                    'have error with input data %s' % node)
        return new

    def __len__(self):
        return self.len + 1

    def __str__(self):
        return '<StatesMachine %s, pool: "%s", state: %s, final: %s>' % (
                id(self), self.pool, self.state, self.final)
    __repr__ = __str__


class Converter(object):
    """转换器"""
    def __init__(self):
        self.map = MAPS
        self.start()

    def feed(self, char):
        branches = []
        for fsm in self.machines:
            new = fsm.feed(char, self.map)
            if new:
                branches.append(new)
        if branches:
            self.machines.extend(branches)
        self.machines = [fsm for fsm in self.machines if fsm.state != FAIL]
        all_ok = True
        for fsm in self.machines:
            if fsm.state != END:
                all_ok = False
        if all_ok:
            self._clean()
        return self.get_result()

    def _clean(self):
        if len(self.machines):
            self.machines.sort(key=lambda x: len(x))
            self.final += self.machines[0].final
            
        self.machines = [StatesMachine()]

    def start(self):
        self.machines = [StatesMachine()]
        self.final = UEMPTY

    def end(self):
        self.machines = [fsm for fsm in self.machines
                if fsm.state == FAIL or fsm.state == END]
        self._clean()

    def convert(self, string):
        """转换字符串"""
        self.start()
        for char in string:
            self.feed(char)
        self.end()
        return self.get_result()

    def get_result(self):
        return self.final


def convert_chars(match):
    """简单的字符转换函数（不使用短语词典）"""
    text = ''
    for char in match.group():
        try:
            MAPS[char]
            if BOOK_NOREPEAT_SWITCH and char in LOG.keys():
                text += char
            elif PAGE_NOREPEAT_SWITCH and char in LOG_PER_PAGE.keys():
                text += char
            else:
                text += '<ruby>' + char + '<rt>' + shengpizi_dict[char][0] + '</rt></ruby>'
                LOG[char] = shengpizi_dict[char]
                LOG_PER_PAGE[char] = shengpizi_dict[char]
        except:
            text += char
    return text


def generate_log(output_file=None):
    """生成处理日志"""
    text = ''
    if output_file:
        text += '-' * 13 + '\n输出文件信息：\n' + '-' * 13 + '\n'
        text += f'输出文件: {output_file}\n\n'
    text += '-' * 13 + '\n执行结果统计：\n' + '-' * 13 + '\n'
    text += '【共注音生僻字%d个】' % len(LOG) + '\n'
    text += ''.join(LOG.keys()) + '\n\n'
    
    monophonic_chars = list(filter(lambda key: len(LOG[key]) == 1, LOG.keys()))
    text += '【包含单音生僻字%d个】' % len(monophonic_chars) + '\n'
    text += ''.join(monophonic_chars) + '\n\n'
    
    polyphonic_chars = list(filter(lambda key: len(LOG[key]) > 1, LOG.keys()))
    text += '【含多音生僻字%d个】' % len(polyphonic_chars) + '\n'
    text += ''.join(polyphonic_chars) + '\n\n'
    
    text += '-' * 13 + '\n已注音的生僻字：\n' + '-' * 13 + '\n'
    multitone = ''
    for key in LOG:
        phonetic = ','.join(LOG[key])
        text += '%s : %s\n' % (key, phonetic)
        if len(LOG[key]) > 1:
            multitone += '%s : %s\n' % (key, phonetic)
    
    text += '\n' + '-' * 13 + '\n多音生僻字：\n' + '-' * 13 + '\n'
    text += multitone
    return text


class PhoneticAnnotate:
    """EPUB生僻字注音处理器"""
    def __init__(self, epub_path, output_path=None):
        if not os.path.exists(epub_path):
            raise Exception("EPUB文件不存在")

        self.epub_path = os.path.normpath(epub_path)
        self.epub = zipfile.ZipFile(epub_path)
        
        if output_path is None:
            # 未指定输出路径，使用原始EPUB文件所在目录
            output_path = os.path.dirname(self.epub_path)
            # 如果目录为空（例如文件在当前目录），则使用当前目录
            if not output_path:
                output_path = os.getcwd()
        elif os.path.exists(output_path):
            # 输出路径存在
            if os.path.isfile(output_path):
                raise Exception("输出路径不能是文件")
            # 如果是目录，直接使用
        else:
            # 输出路径不存在，将其视为目录路径，后续会创建
            pass
            
        self.output_path = os.path.normpath(output_path)
        # 确保输出目录存在
        os.makedirs(self.output_path, exist_ok=True)
        self.file_write_path = os.path.join(
            self.output_path,
            os.path.basename(self.epub_path).replace(".epub", "_phonetic.epub"),
        )
        
        if os.path.exists(self.file_write_path):
            os.remove(self.file_write_path)
        
        self.target_epub = None
        
        # 初始化全局变量
        global LOG, LOG_PER_PAGE
        LOG.clear()
        LOG_PER_PAGE.clear()

    def process_file(self):
        """处理EPUB文件"""
        try:
            # 创建目标EPUB文件
            self.target_epub = zipfile.ZipFile(self.file_write_path, 'w', zipfile.ZIP_DEFLATED)
            
            # 遍历EPUB中的所有文件
            for file_info in self.epub.infolist():
                file_name = file_info.filename
                
                # 跳过不需要处理的文件
                if file_name.startswith('__MACOSX') or file_name.startswith('.DS_Store'):
                    continue
                
                # 读取文件内容
                content = self.epub.read(file_name)
                
                # 处理HTML/XHTML文件
                if file_name.lower().endswith(('.html', '.xhtml', '.htm')):
                    processed_content = self.process_html_content(content.decode('utf-8'))
                    self.target_epub.writestr(file_name, processed_content.encode('utf-8'))
                else:
                    # 非HTML文件直接复制
                    self.target_epub.writestr(file_info, content)
            
            logger.write(f"生僻字注音完成，输出文件: {self.file_write_path}")
            return self.file_write_path
            
        except Exception as e:
            self.fail_del_target()
            raise e
        finally:
            self.close_file()

    def process_html_content(self, html_content):
        """处理HTML内容"""
        # 查找body标签
        body_match = re.search(r'<body[^>]*>.*</body>', html_content, re.S)
        if body_match is None:
            return html_content
        
        body_text = body_match.group()
        
        # 清空当前页面的日志
        global LOG_PER_PAGE
        LOG_PER_PAGE.clear()
        
        # 根据开关选择转换方式
        if READ_PHRASES:
            # 使用完整的转换器（支持短语词典）
            conv_text = re.sub(
                r'(?<!<ruby>)[^\x20-\x7E\r\n]+',
                lambda x: Converter().convert(x.group()),
                body_text
            )
        else:
            # 使用简单的字符转换
            conv_text = re.sub(
                r'(?<!<ruby>)[^\x20-\x7E\r\n]+',
                convert_chars,
                body_text
            )
        
        # 替换原body内容
        new_html = html_content[:body_match.start()] + conv_text + html_content[body_match.end():]
        return new_html

    def close_file(self):
        """关闭ZIP文件"""
        if self.epub:
            self.epub.close()
        if self.target_epub:
            self.target_epub.close()

    def fail_del_target(self):
        """失败时删除目标文件"""
        if self.file_write_path and os.path.exists(self.file_write_path):
            os.remove(self.file_write_path)
            logger.write(f"删除临时文件: {self.file_write_path}")


def run_add_pinyin(epub_path, output_path=None):
    """运行生僻字注音功能的主函数"""
    logger.write(f"\n正在尝试给EPUB添加生僻字注音: {epub_path}")
    
    # 确保字典已初始化
    if not MAPS:
        init_maps()
    
    phonetic_tool = None
    try:
        phonetic_tool = PhoneticAnnotate(epub_path, output_path)
        output_file = phonetic_tool.process_file()
        
        # 生成日志
        log_text = generate_log(output_file)
        logger.write("\n" + log_text)
        
        return (0, output_file)
    except Exception as e:
        error_msg = f"生僻字注音失败: {e}"
        logger.write(error_msg)
        traceback.print_exc()
        if phonetic_tool:
            phonetic_tool.close_file()
            phonetic_tool.fail_del_target()
        return (1, error_msg)


# 初始化映射表
init_maps()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        epub_path = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) > 2 else None
        run_add_pinyin(epub_path, output_path)
    else:
        print("用法: python phonetic_notation.py <epub文件路径> [输出目录]")