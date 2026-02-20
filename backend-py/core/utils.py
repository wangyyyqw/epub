import chardet
import os

def detect_encoding(file_path: str, verbose: bool = True) -> str:
    """
    Detect file encoding by reading the first 50KB.
    Falls back to utf-8 if detection fails.
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
        import sys
        print(f"PROGRESS: 10% (Detected encoding: {encoding}, confidence: {confidence})", file=sys.stderr)
    
    # chardet may return None for unrecognizable content
    if encoding is None:
        return 'utf-8'
        
    return encoding
