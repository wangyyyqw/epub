import chardet
import os

def detect_encoding(file_path: str, verbose: bool = True) -> str:
    """
    Detect file encoding by reading the first 50KB.
    """
    if not os.path.exists(file_path):
        return 'utf-8' # Or raise error
        
    with open(file_path, 'rb') as f:
        rawdata = f.read(50000)
    result = chardet.detect(rawdata)
    encoding = result['encoding']
    confidence = result['confidence']
    
    if verbose:
        import sys
        print(f"PROGRESS: 10% (Detected encoding: {encoding}, confidence: {confidence})", file=sys.stderr)
        
    return encoding
