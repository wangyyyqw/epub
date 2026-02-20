import re
import sys
from typing import List, Tuple, Dict, Any, Optional


MAX_LEVEL = 99


class DefaultChapterSplitter:
    """
    Chapter splitter supporting both flat and hierarchical splitting.
    Supports split control per pattern (like SplitChapter plugin).
    """
    
    PRESET_PATTERNS = [
        {"name": "标准章节 (第X章/节)", "pattern": r"^[ 　\t]{0,4}第\s{0,4}[\d〇零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]+?\s{0,4}(?:章|节(?!课)).{0,30}$", "level": 1, "split": True},
        
        {"name": "卷/部/篇 (第X卷)", "pattern": r"^[ 　\t]{0,4}第\s{0,4}[\d〇零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]+?\s{0,4}(?:卷|部(?![分赛游])|篇(?!张)|集(?![合和])).{0,30}$", "level": 0, "split": True},
        
        {"name": "特殊章节 (序章/终章)", "pattern": r"^[ 　\t]{0,4}(?:序章|楔子|正文(?!完|结)|终章|后记|尾声|番外).{0,20}$", "level": 1, "split": True},
        
        {"name": "数字+分隔符 (1、Title)", "pattern": r"^[ 　\t]{0,4}\d{1,5}[:：,.， 、_—\-].{1,30}$", "level": 2, "split": True},
        
        {"name": "中文数字+分隔符 (一、Title)", "pattern": r"^[ 　\t]{0,4}[零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]{1,8}[ 、_—\-].{1,30}$", "level": 2, "split": True},
        
        {"name": "英文 (Chapter N)", "pattern": r"^[ 　\t]{0,4}(?:[Cc]hapter|[Ss]ection|[Pp]art|ＰＡＲＴ|[Nn][oO][.、]|[Ee]pisode)\s{0,4}\d{1,4}.{0,30}$", "level": 1, "split": True},
        
        {"name": "特殊符号封装 (【第一章】)", "pattern": r"^[ 　\t]{0,4}[【〔〖「『〈［\[](?:第|[Cc]hapter)[\d零一二三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]{1,10}[章节].{0,20}$", "level": 2, "split": True},
        
        {"name": "特殊符号引导 (☆、Title)", "pattern": r"^[ 　\t]{0,4}[☆★✦✧].{1,30}$", "level": 2, "split": True},
        
        {"name": "简介/前言", "pattern": r"^[ 　\t]{0,4}(?:(?:内容|文章)?简介|文案|前言).{0,20}$", "level": 1, "split": True},
        
        {"name": "书名+括号数字", "pattern": r"^[一-龥]{1,20}[ 　\t]{0,4}[(（][\d〇零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]{1,8}[)）][ 　\t]{0,4}$", "level": 2, "split": True},
        
        {"name": "书名+数字", "pattern": r"^[一-龥]{1,20}[ 　\t]{0,4}[\d〇零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]{1,8}[ 　\t]{0,4}$", "level": 2, "split": True},
        
        {"name": "分页/分节阅读", "pattern": r"^[ 　\t]{0,4}(?:.{0,15}分[页节章段]阅读[-_ ]|第\s{0,4}[\d零一二两三四五六七八九十百千万]{1,6}\s{0,4}[页节]).{0,30}$", "level": 2, "split": False},
        
        {"name": "简单章节 (第x节)", "pattern": r"^\s*第[零一二三四五六七八九十百千万\d]+节[：:、\s]*.*$", "level": 2, "split": True},
        {"name": "简单回目 (第x回)", "pattern": r"^\s*第[零一二三四五六七八九十百千万\d]+回[：:、\s]*.*$", "level": 1, "split": True},
        {"name": "简单部/集", "pattern": r"^\s*第[零一二三四五六七八九十百千万\d]+[部集][：:、\s]*.*$", "level": 0, "split": True},
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
                print(f"WARNING: Invalid custom regex '{custom_pattern}': {e}. Falling back to default.", file=sys.stderr)
                custom_pattern = None

        pattern_str = custom_pattern
        if not pattern_str:
            pattern_str = r"^\s*((?:第[零一二三四五六七八九十百千万\d]+章)|(?:Chapter\s+\d+)|(?:第\s*\d+\s*节)|(?:卷[零一二三四五六七八九十百千万\d]+))[：:、\s]*.*$"

        chapter_pattern = re.compile(pattern_str, re.M)
        matches = list(chapter_pattern.finditer(text))
        
        if not matches:
            return [("正文", text)]

        chapters = []
        
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

    def split_hierarchical(
        self, 
        text: str, 
        patterns: List[str], 
        levels: List[int] = None,
        splits: List[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        Hierarchical splitting with multiple regex levels and split control.
        
        Args:
            text: The full text content
            patterns: Ordered list of regex patterns
            levels: Heading levels for each pattern (1=h1, 2=h2, etc.)
            splits: Whether each pattern should create a new chapter file
        
        Returns:
            Nested structure: [{"title": str, "content": str, "level": int, "children": [...]}]
        """
        if not patterns:
            flat = self.split(text)
            return [{"title": t, "content": c, "level": 1, "children": []} for t, c in flat]
        
        if levels is None:
            levels = list(range(1, len(patterns) + 1))
        
        if splits is None:
            splits = [True] * len(patterns)
        
        def split_level(content: str, pattern_idx: int) -> List[Dict[str, Any]]:
            if pattern_idx >= len(patterns):
                return []
            
            pattern_str = patterns[pattern_idx]
            heading_level = levels[pattern_idx] if pattern_idx < len(levels) else pattern_idx + 1
            should_split = splits[pattern_idx] if pattern_idx < len(splits) else True
            
            try:
                pattern = re.compile(pattern_str, re.M)
            except re.error as e:
                print(f"WARNING: Invalid regex pattern at level {pattern_idx}: {e}", file=sys.stderr)
                return []
            
            matches = list(pattern.finditer(content))
            
            if not matches:
                return split_level(content, pattern_idx + 1)
            
            result = []
            
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
                
                children = split_level(section_content, pattern_idx + 1)
                
                if children:
                    first_child_title = children[0]["title"]
                    escaped_title = re.escape(first_child_title)
                    child_match = re.search(f'^\\s*{escaped_title}', section_content, re.M)
                    if child_match and child_match.start() > 0:
                        remaining_content = section_content[:child_match.start()].strip()
                    else:
                        remaining_content = ""
                else:
                    remaining_content = section_content
                
                if should_split:
                    result.append({
                        "title": title,
                        "content": remaining_content,
                        "level": heading_level,
                        "children": children
                    })
                else:
                    if result and not should_split:
                        result[-1]["content"] += "\n\n" + title + "\n" + remaining_content
                    else:
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
                matches = list(pattern.finditer(text))
                if matches:
                    results.append({
                        "name": preset["name"],
                        "pattern": preset["pattern"],
                        "count": len(matches),
                        "chapters": [m.group(0).strip() for m in matches],
                        "example": matches[0].group(0).strip(),
                        "suggested_level": preset["level"],
                        "split": preset.get("split", True)
                    })
            except re.error as e:
                print(f"Regex error in pattern {preset['name']}: {e}", file=sys.stderr)
        
        return results

    def suggest_hierarchy(self, scan_results: List[Dict]) -> List[Dict]:
        """
        Analyze scan results and suggest a hierarchy.
        """
        if not scan_results:
            return []
        
        sorted_results = sorted(scan_results, key=lambda x: x.get("suggested_level", MAX_LEVEL))
        valid_results = [r for r in sorted_results if r["count"] > 0]
        
        for i, result in enumerate(valid_results):
            result["assigned_level"] = i
        
        return valid_results
