import chardet
import os
import sys


def detect_encoding(file_path: str, verbose: bool = True) -> str:
    """
    Detect file encoding using chardet + fallback chain.
    
    Strategy (inspired by SplitChapter):
    1. Use chardet for high-confidence detection
    2. If chardet confidence < 0.7, try fallback chain: utf-8 → utf-16 → gbk
    3. Final fallback: utf-8 with errors='replace'
    """
    if not os.path.exists(file_path):
        return 'utf-8'
        
    with open(file_path, 'rb') as f:
        rawdata = f.read(50000)
    
    if not rawdata:
        return 'utf-8'
    
    result = chardet.detect(rawdata)
    encoding = result.get('encoding')
    confidence = result.get('confidence', 0)
    
    if verbose:
        print(f"PROGRESS: 10% (Detected encoding: {encoding}, confidence: {confidence})", file=sys.stderr)
    
    # High confidence: trust chardet
    if encoding and confidence >= 0.7:
        return encoding
    
    # Low confidence or None: try fallback chain (utf-8 → gbk → utf-16)
    # gbk 在 utf-16 前面，因为中文 TXT 文件 GBK 编码更常见
    for fallback in ('utf-8', 'gbk', 'utf-16'):
        try:
            rawdata.decode(fallback)
            if verbose:
                print(f"PROGRESS: 10% (Fallback encoding: {fallback})", file=sys.stderr)
            return fallback
        except (UnicodeDecodeError, Exception):
            continue
    
    # chardet gave something, use it even with low confidence
    if encoding:
        return encoding
        
    return 'utf-8'
