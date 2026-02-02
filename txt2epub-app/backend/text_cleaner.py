import re

class TextCleaner:
    def __init__(self, remove_empty_lines=True, fix_indent=True):
        self.remove_empty_lines = remove_empty_lines
        self.fix_indent = fix_indent

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
                    # Add 2 full-width spaces (Chinese standard) or 4 spaces?
                    # Using global standard \u3000\u3000 is common for Chinese EPUBs.
                    cleaned_lines.append(f'\u3000\u3000{stripped}')
                else:
                    cleaned_lines.append('')
            text = '\n'.join(cleaned_lines)
            
        return text
