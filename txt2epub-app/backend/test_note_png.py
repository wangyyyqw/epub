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

class TestNotePng(unittest.TestCase):
    def setUp(self):
        self.epub_path = 'test_note.epub'
        self.out_path = 'test_note_out'
        if os.path.exists(self.out_path):
             shutil.rmtree(self.out_path)
        os.makedirs(self.out_path)

        # Create dummy epub with OPF
        with zipfile.ZipFile(self.epub_path, 'w') as z:
            opf_content = '''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uuid_id" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Test Book</dc:title>
  </metadata>
  <manifest>
    <item href="Text/chap1.html" id="chap1" media-type="application/xhtml+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="chap1"/>
  </spine>
</package>'''
            z.writestr('OEBPS/content.opf', opf_content.encode('utf-8'))
            z.writestr('OEBPS/Text/chap1.html', '<html><body><p>Test</p></body></html>'.encode('utf-8'))
            
    def tearDown(self):
        if os.path.exists(self.epub_path):
             os.remove(self.epub_path)
        if os.path.exists(self.out_path):
             shutil.rmtree(self.out_path)
            
    def test_run(self):
        # Run the tool
        # Ensure note.png exists in utils (we rely on real file moved there)
        
        run(self.epub_path, self.out_path)
        
        out_epub = os.path.join(self.out_path, 'test_note_ftc.epub')
        with zipfile.ZipFile(out_epub, 'r') as z:
            # Check image file
            self.assertIn('OEBPS/Images/note.png', z.namelist())
            
            # Check OPF
            opf = z.read('OEBPS/content.opf').decode('utf-8')
            print(f"DEBUG OPF: {opf}")
            self.assertIn('href="Images/note.png"', opf)
            self.assertIn('id="note_png_res"', opf)

if __name__ == '__main__':
    unittest.main()
