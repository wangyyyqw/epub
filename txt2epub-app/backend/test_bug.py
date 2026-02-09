import unittest
import zipfile
import os
import shutil
import sys
from unittest.mock import MagicMock
from bs4 import BeautifulSoup

# Add backend path to sys.path
sys.path.append(os.getcwd())

# Mock modules
sys.modules['plugins.epub_tool.log'] = MagicMock()

from plugins.epub_tool.utils.footnote_to_comment import run

class TestFootnoteBug(unittest.TestCase):
    def setUp(self):
        self.epub_path = 'test_bug.epub'
        self.out_path = 'test_bug_out'
        if os.path.exists(self.out_path):
             shutil.rmtree(self.out_path)
        os.makedirs(self.out_path)

        # Create dummy epub with structure similar to user request
        # User said: <span ... data-wr-footernote="(1)"></span>注释内容呢
        # This implies:
        # Original Link: <a href="#jz_1_43" id="jzyy_1_43"><sup>(1)</sup></a>
        # Target: <element id="jz_1_43">...</element>
        # Maybe the target id is on the anchor itself? No, href="#jz_1_43".
        # If the user says the result is data-wr-footernote="(1)", it means the text extracted from target is "(1)".
        # This happens if target IS the anchor definition?
        # e.g. <a href="#jzyy_1_43" id="jz_1_43"><sup>(1)</sup> Note Content</a>
        # Let's try to simulate what structure yields "(1)" as text.
        
        # Scenario 1: Target is the back-link?
        # <a href="#jzyy_1_43" id="jz_1_43"><sup>(1)</sup></a>  <-- Link in text
        # <div id="jzyy_1_43">...</div> <-- Footnote content
        # Wait, user's example link: <a href="#jz_1_43" id="jzyy_1_43"><sup>(1)</sup></a>
        # href points to #jz_1_43.
        # id is jzyy_1_43.
        # So the TARGET should have id="jz_1_43".
        
        # If the target (id="jz_1_43") contains only "(1)", then the result is correct from code perspective but wrong for user.
        # Usually footnotes are mutual:
        # Text: <a href="#note1" id="ref1"><sup>(1)</sup></a>
        # Footnote: <p id="note1"><a href="#ref1">^</a> Actual content</p>
        
        # If the code extracts "Actual content", it's good.
        # If it extracts "^ Actual content", it's okay (cleanup needed).
        # If it extracts "(1)", it implies the target might be: <p id="note1">(1) Actual content</p>
        
        html_content = '''
        <html>
        <body>
            <p>Text<a href="#jz_1_43" id="jzyy_1_43"><sup>(1)</sup></a></p>
            
            <div class="footnote">
                <p><a href="#jzyy_1_43" id="jz_1_43"><sup>(1)</sup></a> 真实注释内容</p>
            </div>
        </body>
        </html>
        '''
        
        with zipfile.ZipFile(self.epub_path, 'w') as z:
            z.writestr('OEBPS/Text/chap1.html', html_content.strip().encode('utf-8'))
            z.writestr('OEBPS/Styles/style.css', ''.encode('utf-8'))
            
    def tearDown(self):
        if os.path.exists(self.epub_path):
             os.remove(self.epub_path)
        if os.path.exists(self.out_path):
             shutil.rmtree(self.out_path)
            
    def test_run(self):
        run(self.epub_path, self.out_path)
        
        out_epub = os.path.join(self.out_path, 'test_bug_ftc.epub')
        with zipfile.ZipFile(out_epub, 'r') as z:
            html = z.read('OEBPS/Text/chap1.html').decode('utf-8')
            print(f"DEBUG HTML: {html}")
            # We want to see if data-wr-footernote contains "真实注释内容"
            # And DOES NOT contain just "(1)" or starts with "(1)" if possible (cleanup).
            
            # BeautifulSoup get_text() on <p id="jz_1_43"><a ...>(1)</a> 真实注释内容</p>
            # will return "(1) 真实注释内容".
            
            # The user says result is "(1)".
            # Maybe the target is JUST <a id="jz_1_43"><sup>(1)</sup></a>?
            # If so, where is the content?
            # Maybe the structure is:
            # <p><a id="jz_1_43"><sup>(1)</sup></a> 注释内容</p> (Target is the anchor, but content is sibling?)
            
            pass

if __name__ == '__main__':
    unittest.main()
