import re
from typing import Optional


class TextCleaner:
    """Text cleaner for Chinese novel content."""
    
    # Common chapter title patterns to skip indentation
    TITLE_PATTERN = re.compile(
        r'^[\s　]*(?:'
        r'序章|楔子|前言|正文|终章|后记|尾声|番外|'
        r'第[零一二三四五六七八九十百千万\d]+[章节回部集卷]|'
        r'Chapter\s+\d+|'
        r'[【〔〖「『〈［\[]第|'
        r'卷[零一二三四五六七八九十百千万\d]+'
        r')',
        re.IGNORECASE
    )
    
    # Full-width indent (Chinese standard)
    INDENT = '\u3000\u3000'
    
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
            # Replace 3 or more newlines with 2 newlines (paragraph break)
            # Or strict mode: replace 2+ with 1? 
            # Usually in novels, 1 blank line is a scene break, 0 is paragraph break.
            # Let's collapse 3+ \n into 2 \n first.
            text = re.sub(r'\n{3,}', '\n\n', text)
            
            # If the user means "compact all", maybe replace \n\n with \n? 
            # 'TextProcessorApp' usually means removing lines that contain only whitespace, 
            # or collapsing excessive vertical space. 
            # Let's remove lines that are just whitespace first.
            text = re.sub(r'^\s+$', '', text, flags=re.MULTILINE)
            
            # Collapse multiple newlines again after cleaning whitespace lines
            text = re.sub(r'\n{3,}', '\n\n', text)

        # 3. Fix Indentation
        if self.fix_indent:
            lines = text.split('\n')
            cleaned_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped:
                    # Skip indentation for chapter title lines
                    if self.TITLE_PATTERN.match(stripped):
                        cleaned_lines.append(stripped)
                    else:
                        # Add 2 full-width spaces (Chinese standard)
                        cleaned_lines.append(f'{self.INDENT}{stripped}')
                else:
                    cleaned_lines.append('')
            text = '\n'.join(cleaned_lines)
            
        return text
