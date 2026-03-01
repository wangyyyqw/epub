import re
import sys
from typing import List, Tuple, Dict, Any, Optional
from .text_cleaner import BLANK_CHARS


MAX_LEVEL = 99


class DefaultChapterSplitter:
    """
    Chapter splitter supporting both flat and hierarchical splitting.
    Supports split control per pattern (like SplitChapter plugin).
    Regex rules adapted from legado (https://github.com/gedoor/legado).
    """

    # 数字字符类
    _D = r"[\d〇零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]"

    # ── 基于 legado txtTocRule.json 的预设规则 ──
    # level: 0=卷/部, 1=章/回, 2=节/小标题
    # enable=False 的规则仍保留在列表中供扫描，但 suggest_hierarchy 会根据匹配数量自动选择
    PRESET_PATTERNS = [
        # -2: 目录（legado 默认启用主规则）
        {
            "name": "目录 (第X章/节/卷/集/部/篇)",
            "pattern": rf"^[ 　\t]{{0,4}}(?:序章|楔子|正文(?!完|结)|终章|后记|尾声|番外|第\s{{0,4}}{_D}+?\s{{0,4}}(?:章|节(?!课)|卷|集(?![合和])|部(?![分赛游])|篇(?!张))).{{0,30}}$",
            "level": 1, "split": True,
        },
        # -4: 目录(古典、轻小说备用) — 多了 回/场/话
        {
            "name": "目录-古典 (含回/场/话)",
            "pattern": rf"^[ 　\t]{{0,4}}(?:序章|楔子|正文(?!完|结)|终章|后记|尾声|番外|第\s{{0,4}}{_D}+?\s{{0,4}}(?:章|节(?!课)|卷|集(?![合和])|部(?![分赛游])|回(?![合来事去])|场(?![和合比电是])|话|篇(?!张))).{{0,30}}$",
            "level": 1, "split": True,
        },
        # -8: 数字 分隔符 标题名称
        {
            "name": "数字+分隔符 (1、标题)",
            "pattern": r"^[ 　\t]{0,4}\d{1,5}[:：,.， 、_—\-].{1,30}$",
            "level": 2, "split": True,
        },
        # -9: 大写数字 分隔符 标题名称
        {
            "name": "中文数字+分隔符 (一、标题)",
            "pattern": rf"^[ 　\t]{{0,4}}(?:序章|楔子|正文(?!完|结)|终章|后记|尾声|番外|[零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]{{1,8}}章?)[ 、_—\-].{{1,30}}$",
            "level": 2, "split": True,
        },
        # -11: 正文 标题/序号
        {
            "name": "正文+标题",
            "pattern": r"^[ 　\t]{0,4}正文[ 　]{1,4}.{0,20}$",
            "level": 1, "split": True,
        },
        # -12: Chapter/Section/Part/Episode 序号 标题
        {
            "name": "Chapter/Section/Part/Episode",
            "pattern": rf"^[ 　\t]{{0,4}}(?:[Cc]hapter|[Ss]ection|[Pp]art|ＰＡＲＴ|[Nn][oO][.、]|[Ee]pisode|(?:内容|文章)?简介|文案|前言|序章|楔子|正文(?!完|结)|终章|后记|尾声|番外)\s{{0,4}}\d{{1,4}}.{{0,30}}$",
            "level": 1, "split": True,
        },
        # -14: 特殊符号 序号 标题 (【第一章 ...)
        {
            "name": "特殊符号+序号 (【第X章】)",
            "pattern": rf"^[ 　\t]{{0,4}}[【〔〖「『〈［\[](?:第|[Cc]hapter){_D}{{1,10}}[章节].{{0,20}}$",
            "level": 2, "split": True,
        },
        # -16: 特殊符号 标题(单个) ☆★✦✧
        {
            "name": "特殊符号+标题 (☆、标题)",
            "pattern": r"^[ 　\t]{0,4}(?:[☆★✦✧].{1,30}|(?:内容|文章)?简介|文案|前言|序章|楔子|正文(?!完|结)|终章|后记|尾声|番外)[ 　]{0,4}$",
            "level": 2, "split": True,
        },
        # -17: 章/卷 序号 标题
        {
            "name": "章/卷+序号 (卷五 标题)",
            "pattern": rf"^[ \t　]{{0,4}}(?:(?:内容|文章)?简介|文案|前言|序章|楔子|正文(?!完|结)|终章|后记|尾声|番外|[卷章]{_D}{{1,8}})[ 　]{{0,4}}.{{0,30}}$",
            "level": 1, "split": True,
        },
        # -21: 书名 括号 序号
        {
            "name": "书名+括号序号 (标题(12))",
            "pattern": rf"^[\u4e00-\u9fa5]{{1,20}}[ 　\t]{{0,4}}[(（]{_D}{{1,8}}[)）][ 　\t]{{0,4}}$",
            "level": 2, "split": True,
        },
        # -22: 书名 序号
        {
            "name": "书名+序号 (标题124)",
            "pattern": rf"^[\u4e00-\u9fa5]{{1,20}}[ 　\t]{{0,4}}{_D}{{1,8}}[ 　\t]{{0,4}}$",
            "level": 2, "split": True,
        },
        # -24: 字数分割 分节阅读
        {
            "name": "分页/分节阅读",
            "pattern": rf"^[ 　\t]{{0,4}}(?:.{{0,15}}分[页节章段]阅读[-_ ]|第\s{{0,4}}{_D}{{1,6}}\s{{0,4}}[页节]).{{0,30}}$",
            "level": 2, "split": False,
        },
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
            # Default pattern aligned with legado's main tocRule
            pattern_str = r"^[ 　\t]{0,4}(?:序章|楔子|正文(?!完|结)|终章|后记|尾声|番外|第\s{0,4}[\d〇零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]+?\s{0,4}(?:章|节(?!课)|卷|集(?![合和])|部(?![分赛游])|篇(?!张))).{0,30}$"

        chapter_pattern = re.compile(pattern_str, re.M)
        matches = list(chapter_pattern.finditer(text))
        
        if not matches:
            return [("正文", text)]

        chapters = []
        
        if matches[0].start() > 0:
            preamble = text[:matches[0].start()].strip(BLANK_CHARS)
            if preamble:
                chapters.append(("前言", preamble))
                
        for i, match in enumerate(matches):
            title = match.group().strip(BLANK_CHARS)
            start = match.end()
            end = matches[i+1].start() if (i + 1) < len(matches) else len(text)
            content = text[start:end].strip(BLANK_CHARS)
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
                preamble = content[:matches[0].start()].strip(BLANK_CHARS)
                if preamble and pattern_idx == 0:
                    result.append({
                        "title": "前言",
                        "content": preamble,
                        "level": heading_level,
                        "children": []
                    })
            
            for i, match in enumerate(matches):
                title = match.group().strip(BLANK_CHARS)
                start = match.end()
                end = matches[i+1].start() if (i + 1) < len(matches) else len(content)
                section_content = content[start:end].strip(BLANK_CHARS)
                
                children = split_level(section_content, pattern_idx + 1)
                
                if children:
                    first_child_title = children[0]["title"]
                    escaped_title = re.escape(first_child_title)
                    child_match = re.search(f'^\\s*{escaped_title}', section_content, re.M)
                    if child_match and child_match.start() > 0:
                        remaining_content = section_content[:child_match.start()].strip(BLANK_CHARS)
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
                        "chapters": [m.group(0).strip(BLANK_CHARS) for m in matches],
                        "example": matches[0].group(0).strip(BLANK_CHARS),
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
