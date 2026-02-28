import re


class TextCleaner:
    """Text cleaner for Chinese novel content."""
    
    def __init__(self, remove_empty_lines: bool = True, fix_indent: bool = True):
        self.remove_empty_lines = remove_empty_lines
        self.fix_indent = fix_indent
        
        # Pre-compile regex patterns for performance
        self._multiple_newlines = re.compile(r'\n{3,}')
        self._whitespace_lines = re.compile(r'^\s+$', re.MULTILINE)

    def clean(self, text: str) -> str:
        # 1. Normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # 2. Remove Empty Lines (allow max 1 empty line between paragraphs)
        if self.remove_empty_lines:
            text = self._multiple_newlines.sub('\n\n', text)
            text = self._whitespace_lines.sub('', text)
            text = self._multiple_newlines.sub('\n\n', text)

        # 3. Fix Indentation: strip leading whitespace from each line
        #    (actual indent handled by CSS text-indent, not inline spaces)
        if self.fix_indent:
            lines = text.split('\n')
            cleaned_lines = []
            for line in lines:
                stripped = line.strip()
                cleaned_lines.append(stripped)
            text = '\n'.join(cleaned_lines)
            
        return text
