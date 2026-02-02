import re
from typing import List, Tuple, Dict, Any

class DefaultChapterSplitter:
    """
    Chapter splitter supporting both flat and hierarchical splitting.
    """
    
    # Pattern definitions with suggested level for auto-detection
    PRESET_PATTERNS = [
        # --- Enabled Patterns (Default) ---
        
        # 1. 目录(去空白) - e.g. "第一章 标题"
        {"name": "通用中文 (第x章)", "pattern": r"(?<=[　\s])(?:序章|楔子|正文(?!完|结)|终章|后记|尾声|番外|第\s{0,4}[\d〇零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]+?\s{0,4}(?:章|节(?!课)|卷|集(?![合和]))).{0,30}$", "level": 1},
        
        # 2. 目录 - e.g. "第一章 标题" (start of line)
        {"name": "标准中文 (开头)", "pattern": r"^[ 　\t]{0,4}(?:序章|楔子|正文(?!完|结)|终章|后记|尾声|番外|第\s{0,4}[\d〇零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]+?\s{0,4}(?:章|节(?!课)|卷|集(?![合和])|部(?![分赛游])|篇(?!张))).{0,30}$", "level": 1},
        
        # 3. 数字 分隔符 标题名称 - e.g. "1、标题"
        {"name": "数字+分隔符 (1、Title)", "pattern": r"^[ 　\t]{0,4}\d{1,5}[:：,.， 、_—\-].{1,30}$", "level": 2},
        
        # 4. 大写数字 分隔符 标题名称 - e.g. "一、标题"
        {"name": "中文数字+分隔符 (一、Title)", "pattern": r"^[ 　\t]{0,4}(?:序章|楔子|正文(?!完|结)|终章|后记|尾声|番外|[零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]{1,8}章?)[ 、_—\-].{1,30}$", "level": 2},
        
        # 5. 正文 标题/序号 - e.g. "正文 标题"
        {"name": "正文+标题", "pattern": r"^[ 　\t]{0,4}正文[ 　]{1,4}.{0,20}$", "level": 1},
        
        # 6. Chapter/Section/Part - e.g. "Chapter 1"
        {"name": "英文 (Chapter N)", "pattern": r"^[ 　\t]{0,4}(?:[Cc]hapter|[Ss]ection|[Pp]art|ＰＡＲＴ|[Nn][oO][.、]|[Ee]pisode|(?:内容|文章)?简介|文案|前言|序章|楔子|正文(?!完|结)|终章|后记|尾声|番外)\s{0,4}\d{1,4}.{0,30}$", "level": 1},
        
        # 7. 特殊符号 序号 标题 - e.g. "【第一章】"
        {"name": "特殊符号封装 (【第一章】)", "pattern": r"(?<=[\s　])[【〔〖「『〈［\[](?:第|[Cc]hapter)[\d零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]{1,10}[章节].{0,20}$", "level": 2},
        
        # 8. 特殊符号 标题(单个) - e.g. "☆、标题"
        {"name": "特殊符号引导 (☆、Title)", "pattern": r"(?<=[\s　]{0,4})(?:[☆★✦✧].{1,30}|(?:内容|文章)?简介|文案|前言|序章|楔子|正文(?!完|结)|终章|后记|尾声|番外)[ 　]{0,4}$", "level": 2},
        
        # 9. 章/卷 序号 标题 - e.g. "卷五 标题"
        {"name": "卷/部 (卷x)", "pattern": r"^[ \t　]{0,4}(?:(?:内容|文章)?简介|文案|前言|序章|楔子|正文(?!完|结)|终章|后记|尾声|番外|[卷章][\d零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]{1,8})[ 　]{0,4}.{0,30}$", "level": 0},
        
        # 10. 书名 括号 序号 - e.g. "书名(12)"
        {"name": "书名+括号数字", "pattern": r"^[一-龥]{1,20}[ 　\t]{0,4}[(（][\d〇零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]{1,8}[)）][ 　\t]{0,4}$", "level": 2},
        
        # 11. 书名 序号 - e.g. "书名 123"
        {"name": "书名+数字", "pattern": r"^[一-龥]{1,20}[ 　\t]{0,4}[\d〇零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]{1,8}[ 　\t]{0,4}$", "level": 2},
        
        # 12. 分页/分节阅读
        {"name": "分页/分节阅读", "pattern": r"(?<=[ 　\t]{0,4})(?:.{0,15}分[页节章段]阅读[-_ ]|第\s{0,4}[\d零一二两三四五六七八九十百千万]{1,6}\s{0,4}[页节]).{0,30}$", "level": 2},
        
        # --- Common Simple Patterns (Fallback) ---
        {"name": "简单章节 (第x节)", "pattern": r"^\s*第[零一二三四五六七八九十百千万\d]+节[：:、\s]*.*$", "level": 2},
        {"name": "简单回目 (第x回)", "pattern": r"^\s*第[零一二三四五六七八九十百千万\d]+回[：:、\s]*.*$", "level": 1},
        {"name": "简单部/集", "pattern": r"^\s*第[零一二三四五六七八九十百千万\d]+[部集][：:、\s]*.*$", "level": 0},
    ]



    def split(self, text: str, custom_pattern: str = None) -> List[Tuple[str, str]]:
        """
        Simple flat splitting (backward compatible).
        Returns: [(title, content), ...]
        """
        if custom_pattern:
            try:
                re.compile(custom_pattern, re.M)
            except re.error as e:
                print(f"WARNING: Invalid custom regex '{custom_pattern}': {e}. Falling back to default.")
                custom_pattern = None

        pattern_str = custom_pattern
        if not pattern_str:
            pattern_str = r"^\s*((?:第[零一二三四五六七八九十百千万\d]+章)|(?:Chapter\s+\d+)|(?:第\s*\d+\s*节)|(?:卷[零一二三四五六七八九十百千万\d]+))[：:、\s]*.*$"

        chapter_pattern = re.compile(pattern_str, re.M)
        matches = list(chapter_pattern.finditer(text))
        
        if not matches:
            return [("正文", text)]

        chapters = []
        
        # Handle Prologue
        if matches[0].start() > 0:
            preamble = text[:matches[0].start()].strip()
            if preamble:
                chapters.append(("前言", preamble))
                
        for i, match in enumerate(matches):
            title = match.group().strip()
            start = match.end()
            end = matches[i+1].start() if (i + 1) < len(matches) else len(text)
            content = text[start:end].strip()
            chapters.append((title, content))
            
        return chapters

    def split_hierarchical(self, text: str, patterns: List[str], levels: List[int] = None) -> List[Dict[str, Any]]:
        """
        Hierarchical splitting with multiple regex levels.
        
        Args:
            text: The full text content
            patterns: Ordered list of regex patterns [level0, level1, level2, ...]
            levels: Heading levels for each pattern (1=h1, 2=h2, etc.). Defaults to sequential.
        
        Returns:
            Nested structure: [{"title": str, "content": str, "level": int, "children": [...]}]
        """
        if not patterns:
            # Fallback to flat split
            flat = self.split(text)
            return [{"title": t, "content": c, "level": 1, "children": []} for t, c in flat]
        
        # Default levels: 1, 2, 3, ...
        if levels is None:
            levels = list(range(1, len(patterns) + 1))
        
        def split_level(content: str, pattern_idx: int) -> List[Dict[str, Any]]:
            """Recursively split content at the given pattern index."""
            if pattern_idx >= len(patterns):
                return []
            
            pattern_str = patterns[pattern_idx]
            heading_level = levels[pattern_idx] if pattern_idx < len(levels) else pattern_idx + 1
            
            try:
                pattern = re.compile(pattern_str, re.M)
            except re.error:
                return []
            
            matches = list(pattern.finditer(content))
            
            if not matches:
                # No matches at this level, try next level
                return split_level(content, pattern_idx + 1)
            
            result = []
            
            # Handle preamble (content before first match)
            if matches[0].start() > 0:
                preamble = content[:matches[0].start()].strip()
                if preamble and pattern_idx == 0:
                    result.append({
                        "title": "前言",
                        "content": preamble,
                        "level": heading_level,
                        "children": []
                    })
            
            for i, match in enumerate(matches):
                title = match.group().strip()
                start = match.end()
                end = matches[i+1].start() if (i + 1) < len(matches) else len(content)
                section_content = content[start:end].strip()
                
                # Recursively split children at next level
                children = split_level(section_content, pattern_idx + 1)
                
                # If children exist, remove their content from this level
                if children:
                    # Content remaining after extracting children
                    first_child_start = section_content.find(children[0]["title"]) if children else -1
                    if first_child_start > 0:
                        remaining_content = section_content[:first_child_start].strip()
                    else:
                        remaining_content = ""
                else:
                    remaining_content = section_content
                
                result.append({
                    "title": title,
                    "content": remaining_content,
                    "level": heading_level,
                    "children": children
                })
            
            return result
        
        return split_level(text, 0)

    def scan(self, text: str) -> List[Dict]:
        """
        Scan text for all preset patterns.
        Returns results with suggested_level for hierarchy detection.
        """
        results = []

        for preset in self.PRESET_PATTERNS:
            try:
                pattern = re.compile(preset["pattern"], re.M)
                matches = pattern.findall(text)
                if matches:
                    results.append({
                        "name": preset["name"],
                        "pattern": preset["pattern"],
                        "count": len(matches),
                        "chapters": [m.strip() if isinstance(m, str) else m[0].strip() for m in matches],
                        "suggested_level": preset["level"]
                    })
            except Exception as e:
                print(f"Error scanning pattern {preset['name']}: {e}")
        
        return results

    def suggest_hierarchy(self, scan_results: List[Dict]) -> List[Dict]:
        """
        Analyze scan results and suggest a hierarchy.
        Returns sorted list with level assignments.
        """
        if not scan_results:
            return []
        
        # Sort by suggested_level
        sorted_results = sorted(scan_results, key=lambda x: x.get("suggested_level", 99))
        
        # Filter out patterns with 0 matches
        valid_results = [r for r in sorted_results if r["count"] > 0]
        
        # Assign levels based on position
        for i, result in enumerate(valid_results):
            result["assigned_level"] = i
        
        return valid_results
