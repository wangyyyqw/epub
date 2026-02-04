import zipfile
import os
import re
import time
from copy import deepcopy
from bs4 import BeautifulSoup, NavigableString, Comment, Doctype, ProcessingInstruction, Declaration
import traceback

try:
    from ..log import logwriter
except ImportError:
    from .log import logwriter

try:
    # Attempt relative import first
    from .dict import ShengPiZi
    from .dict import Phrases
    from .dict import 完整拼音字典 as FullPinyin
except ImportError:
    # Fallback to absolute import if running from root
    try:
        from ..dict import Phrases
        from ..dict import 完整拼音字典 as FullPinyin
    except ImportError:
        # Last resort for direct execution
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), 'dict'))
        import Phrases
        import 完整拼音字典 as FullPinyin

logger = logwriter()

# Global Constants
UEMPTY = ''
# states
(START, END, FAIL, WAIT_TAIL) = list(range(4))
# conditions
(TAIL, ERROR, MATCHED_SWITCH, UNMATCHED_SWITCH, CONNECTOR) = list(range(5))

MAPS = None
LOG = {}

class Node(object):
    def __init__(self, from_word, to_phonetic=None, is_tail=True,
            have_child=False):
        self.from_word = from_word
        if to_phonetic is None: #字典中没有该键
            self.to_phonetic = from_word
            self.is_original = True #需返回原值
        else: #字典中存在该键
            self.to_phonetic = to_phonetic or from_word 
            self.is_original = False

        self.is_tail = is_tail 
        self.have_child = have_child

    def is_original_long_word(self): # 在字典中找不到键的短语
        return self.is_original and len(self.from_word)>1

    def is_follow(self, chars): #查询传入字符串是否该节点键值前缀部分
        return chars != self.from_word[:-1]

    def add_phonetic(self):
        if type(self.to_phonetic) == str:
            return self.to_phonetic
        elif type(self.to_phonetic) == list:
            if len(self.from_word) == 1:
                return '<ruby>' + self.from_word+'<rt>'+self.to_phonetic[0] +'</rt></ruby>'
            elif len(self.from_word) > 1 and len(self.from_word) == len(self.to_phonetic):
                index,result = 0,''
                for char in self.from_word:
                    result = result + char if not self.to_phonetic[index]\
                           else result + '<ruby>' + char + '<rt>' + self.to_phonetic[index] +'</rt></ruby>'
                    index += 1
                return result
        return self.from_word

class ConvertMap(object):
    def __init__(self, mapping=None):
        self._map = {}
        if mapping:
            self.set_convert_map(mapping)

    def set_convert_map(self, mapping):
        convert_map = {}
        have_child = {}
        max_key_length = 0
        for key in sorted(mapping.keys()):
            if len(key)>1:
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
            is_tail, have_child, to_phonetic  = self._map[k]
            return Node(k, to_phonetic, is_tail, have_child)
        except:
            return Node(k)

    def __contains__(self, k):
        return k in self._map

class StatesMachineException(Exception): pass

class StatesMachine(object):
    def __init__(self):
        self.state = START
        self.final = UEMPTY
        self.len = 0
        self.pool = UEMPTY
        self.last_matched = None 

    def clone(self, pool):
        new = deepcopy(self)
        new.state = WAIT_TAIL
        new.pool = pool
        new.last_matched = self.last_matched
        return new

    def feed(self, char, map):
        self.node = node = map[self.pool+char]
        if node.have_child:
            if node.is_tail:
                if node.is_original: 
                    cond = UNMATCHED_SWITCH
                else: 
                    cond = MATCHED_SWITCH
            else: 
                cond = CONNECTOR
        else: 
            if node.is_tail: 
                cond = TAIL
            else: 
                cond = ERROR

        new = None
        if cond == ERROR:
            self.state = FAIL
        elif cond == TAIL:
            if self.state == WAIT_TAIL and node.is_original_long_word():
                self.state = FAIL
            else:
                self.final += node.add_phonetic()
                self.len += 1
                self.pool = UEMPTY
                self.state = END
                if not node.is_original:
                    LOG[node.from_word] = node.to_phonetic
        elif self.state == START or self.state == WAIT_TAIL:
            if cond == MATCHED_SWITCH:
                self.last_matched = [node.from_word,node.to_phonetic]
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
            self.state = START
            new = self.feed(char, map)
        elif self.state == FAIL:
            raise StatesMachineException('Translate States Machine Error')
        return new

    def __len__(self):
        return self.len + 1

class Converter(object):
    def __init__(self):
        global MAPS
        if MAPS is None:
            initMaps()
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
        self.start()
        for char in string:
            self.feed(char)
        self.end()
        return self.get_result()

    def get_result(self):
        return self.final

def initMaps():
    mapping = {}
    # Load Full Pinyin dict for Full Text Annotation
    for code in FullPinyin.pinyin_dict:
        mapping[code] = FullPinyin.pinyin_dict[code]
    
    # Load Phrases dict
    for key in Phrases.phrases_dict:
        mapping[key] = Phrases.phrases_dict[key]

    global MAPS
    MAPS = ConvertMap(mapping)

def log_result():
    text = ''
    text += '-'*13+'\n生僻字注音统计：\n'+'-'*13 +'\n'
    text += '【共注音生僻字%d个】'%len(LOG) + '\n'
    text += ''.join(LOG.keys())+ '\n\n'
    return text

class PinyinAnnotate:
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
            os.path.basename(self.epub_path).replace(".epub", "_pinyin.epub"),
        )
        
        if os.path.exists(self.file_write_path):
            os.remove(self.file_write_path)
            
        self.target_epub = zipfile.ZipFile(
            self.file_write_path,
            "w",
            zipfile.ZIP_DEFLATED,
        )
        # Initialize dictionary maps
        initMaps()
        # Initialize Converter
        self.converter = Converter()

    def process_file(self):
        """处理EPUB文件中的所有HTML/XML文件"""
        LOG.clear()
        
        opf_filename = None
        opf_content = None
        
        for item in self.epub.infolist():
            content = self.epub.read(item.filename)
            
            # 记录OPF文件，稍后处理
            if item.filename.lower().endswith('.opf'):
                opf_filename = item.filename
                opf_content = content
                continue

            # 处理HTML/XHTML文件
            if item.filename.lower().endswith(('.html', '.xhtml', '.htm')):
                try:
                    text_content = content.decode('utf-8')
                    
                    # Use regex to find text blocks to avoid parsing huge HTML with BS4 if possible
                    # But keeping BS4 logic for safety and correctness with tags
                    soup = BeautifulSoup(text_content, 'html.parser')
                    
                    for string in soup.find_all(string=True):
                        if isinstance(string, (Comment, Doctype, ProcessingInstruction, Declaration)):
                            continue
                        if string.parent.name in ['style', 'script', 'ruby', 'rt', 'rp']:
                            continue
                            
                        original_text = str(string)
                        
                        def replace_func(match):
                            return self.converter.convert(match.group())

                        new_text = re.sub(r'(?<!<ruby>)[^\x20-\x7E\r\n]+', replace_func, original_text)
                        
                        if new_text != original_text:
                            new_fragment = BeautifulSoup(new_text, 'html.parser')
                            string.replace_with(new_fragment)

                    new_content = str(soup).encode('utf-8')
                    self.target_epub.writestr(item.filename, new_content)
                    
                except Exception as e:
                    logger.write(f"文件 {item.filename} 处理失败，使用原内容: {e}")
                    self.target_epub.writestr(item, content)
            else:
                self.target_epub.writestr(item, content)

        # Generate Log Content for system log
        log_content = log_result()
        logger.write(log_content)
        
        # Write original OPF if found (we skipped it in the loop)
        if opf_filename and opf_content:
            self.target_epub.writestr(opf_filename, opf_content)

        self.close_file()
        return 0, self.file_write_path

    def close_file(self):
        if self.epub:
            self.epub.close()
        if self.target_epub:
            self.target_epub.close()

    def fail_del_target(self):
        if self.file_write_path and os.path.exists(self.file_write_path):
            os.remove(self.file_write_path)
            logger.write(f"删除临时文件: {self.file_write_path}")

def run_add_pinyin(epub_path, output_path=None):
    logger.write(f"\n正在尝试给EPUB添加生僻字注音: {epub_path}")
    
    pinyin_tool = None
    try:
        pinyin_tool = PinyinAnnotate(epub_path, output_path)
        result = pinyin_tool.process_file()
        return result
    except Exception as e:
        error_msg = f"生僻字注音失败: {e}"
        logger.write(error_msg)
        traceback.print_exc()
        if pinyin_tool:
            pinyin_tool.close_file()
            pinyin_tool.fail_del_target()
        return (1, error_msg)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        epub_read_path = sys.argv[1]
        run_add_pinyin(epub_read_path)
