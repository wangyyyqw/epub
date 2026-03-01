import re


# 全面的空白字符集（参考 SplitChapter BLANK_CHARS）
# 包含各种 Unicode 空白：NBSP、全角空格、零宽字符、BOM 等
BLANK_CHARS = (
    "\r\n\t\x20\xa0"           # 基本空白 + NBSP
    "\u2000\u2001\u2002\u2003"  # En/Em Quad, En/Em Space
    "\u2004\u2005\u2006\u2007"  # Three/Four/Six-Per-Em Space, Figure Space
    "\u2008\u2009\u200a"        # Punctuation/Thin/Hair Space
    "\u200b\u200c\u200d"        # Zero-Width Space/Non-Joiner/Joiner
    "\u202f\u2060"              # Narrow No-Break Space, Word Joiner
    "\u3000"                    # 全角空格（中文常见）
    "\ufeff"                    # BOM / Zero-Width No-Break Space
)

# 用于 regex 的空白字符类
BLANK_CHARS_PATTERN = '[' + re.escape(BLANK_CHARS) + ']'


class TextCleaner:
    """Text cleaner for Chinese novel content."""
    
    def __init__(self, remove_empty_lines: bool = True, fix_indent: bool = True):
        self.remove_empty_lines = remove_empty_lines
        self.fix_indent = fix_indent
        
        # Pre-compile regex patterns for performance
        self._multiple_newlines = re.compile(r'\n{3,}')
        self._whitespace_lines = re.compile(r'^[ \t\xa0\u3000\ufeff]+$', re.MULTILINE)

    def clean(self, text: str) -> str:
        # 1. Normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # 2. Remove BOM and zero-width chars that may appear at file start
        text = text.lstrip('\ufeff')
        
        # 3. Remove Empty Lines (allow max 1 empty line between paragraphs)
        if self.remove_empty_lines:
            text = self._multiple_newlines.sub('\n\n', text)
            text = self._whitespace_lines.sub('', text)
            text = self._multiple_newlines.sub('\n\n', text)

        # 4. Fix Indentation: strip leading/trailing whitespace from each line
        #    使用 BLANK_CHARS 处理全角空格、NBSP 等特殊空白
        #    (actual indent handled by CSS text-indent, not inline spaces)
        if self.fix_indent:
            lines = text.split('\n')
            cleaned_lines = []
            for line in lines:
                stripped = line.strip(BLANK_CHARS)
                cleaned_lines.append(stripped)
            text = '\n'.join(cleaned_lines)
            
        return text
