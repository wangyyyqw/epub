"""OPF 查看模块 — 从 EPUB 中提取并格式化显示 OPF 文件内容和内部文件列表。"""

import sys
import re
import zipfile
import xml.dom.minidom
from typing import Optional


def _find_opf_path(epub_zip: zipfile.ZipFile) -> Optional[str]:
    """通过 META-INF/container.xml 定位 OPF 文件路径。"""
    try:
        container_xml = epub_zip.read("META-INF/container.xml").decode("utf-8")
    except KeyError:
        return None

    match = re.search(
        r'<rootfile[^>]*full-path="([^"]*\.opf)"',
        container_xml,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    return None


def _format_xml(raw_xml: str) -> str:
    """使用 xml.dom.minidom 格式化 XML，格式化失败时返回原始内容并输出警告。"""
    try:
        dom = xml.dom.minidom.parseString(raw_xml)
        formatted = dom.toprettyxml(indent="  ")
        # toprettyxml 会添加 XML 声明，如果原始内容已有则去重
        # 移除多余空行
        lines = [line for line in formatted.splitlines() if line.strip()]
        return "\n".join(lines)
    except Exception as e:
        print(f"WARNING: OPF XML 格式化失败，输出原始内容: {e}", file=sys.stderr)
        return raw_xml


def run(epub_path: str) -> int:
    """查看 EPUB 的 OPF 文件内容和内部文件列表。

    Args:
        epub_path: EPUB 文件路径

    Returns:
        0 表示成功，非零表示失败
    """
    try:
        epub_zip = zipfile.ZipFile(epub_path, "r")
    except Exception as e:
        print(f"ERROR: 无法打开 EPUB 文件: {e}", file=sys.stderr)
        return 1

    try:
        opf_path = _find_opf_path(epub_zip)
        if opf_path is None:
            print("ERROR: EPUB 中找不到 container.xml 或 OPF 文件路径", file=sys.stderr)
            return 1

        try:
            opf_content = epub_zip.read(opf_path).decode("utf-8")
        except KeyError:
            print(f"ERROR: EPUB 中找不到 OPF 文件: {opf_path}", file=sys.stderr)
            return 1

        formatted_xml = _format_xml(opf_content)

        # 输出 OPF 内容区段
        print("=== OPF Content ===")
        print(formatted_xml)

        # 输出文件列表区段
        print("=== File List ===")
        for name in epub_zip.namelist():
            print(name)

        return 0
    finally:
        epub_zip.close()
