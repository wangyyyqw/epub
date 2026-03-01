"""中文数字转阿拉伯数字工具。
参考 SplitChapter/tools/turn_number.py，支持三种写法：
  1. 正常写法：一万三千零一十一、壹萬〇伍佰
  2. 口语写法：两千四百二十、两萬
  3. 简写：二〇〇一、三五一〇、贰零贰零
"""

import re
from typing import Optional

CN_TO_ARAB_MAP = {'两': 2, '百': 100, '佰': 100, '千': 1000, '仟': 1000, '万': 10000, '萬': 10000}
CN_NUM_SIM = '零一二三四五六七八九十'
CN_NUM_TRA = '〇壹贰叁肆伍陆柒捌玖拾'
for _i in range(11):
    CN_TO_ARAB_MAP[CN_NUM_SIM[_i]] = _i
    CN_TO_ARAB_MAP[CN_NUM_TRA[_i]] = _i

_DIGITS = '一二两三四五六七八九壹贰叁肆伍陆柒捌玖'
_SIMPLE_DIGITS = '一二三四五六七八九壹贰叁肆伍陆柒捌玖〇零'
_UNITS = '十百千万拾佰仟萬'
_ZEROS = '零〇'
_FULLWIDTH = '０１２３４５６７８９'

_RE_NORMAL = re.compile(
    r'[一二两三四五六七八九十壹贰叁肆伍陆柒捌玖拾]'
    r'[一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟萬〇零]+'
)
_RE_SIMPLE = re.compile(r'[一二三四五六七八九壹贰叁肆伍陆柒捌玖〇零]+')


def cn_to_arab(cn_num: str) -> Optional[int]:
    """将中文数字字符串转为阿拉伯数字。无法转换时返回 None。"""
    if not isinstance(cn_num, str) or cn_num == '':
        return None

    # 全角数字
    if cn_num[0] in _FULLWIDTH:
        try:
            return int(cn_num)
        except ValueError:
            return None

    # 单字
    if len(cn_num) == 1 and cn_num in '一二三四五六七八九十壹贰叁肆伍陆柒捌玖拾〇零':
        return CN_TO_ARAB_MAP[cn_num]

    test = _RE_NORMAL.match(cn_num)
    if test is None or len(test.group()) < len(cn_num):
        return None

    # 判断类型：简写 vs 正常
    if _RE_SIMPLE.match(cn_num) and len(_RE_SIMPLE.match(cn_num).group()) == len(cn_num):
        # 简写：二〇〇一 → 2001
        return int(''.join(str(CN_TO_ARAB_MAP[c]) for c in cn_num))

    # 正常写法：一千四百零三 → 1403
    arab_num = 0
    base_digit = 1
    for i, ch in enumerate(cn_num):
        if ch in _DIGITS:
            base_digit = CN_TO_ARAB_MAP[ch]
        elif ch in _UNITS:
            rate = CN_TO_ARAB_MAP[ch]
            arab_num += base_digit * rate
        elif ch in _ZEROS:
            if i > 0 and cn_num[i - 1] in _DIGITS:
                arab_num += base_digit * 10
    if cn_num[-1] in _DIGITS:
        arab_num += CN_TO_ARAB_MAP[cn_num[-1]]
    return arab_num


def extract_chapter_number(title: str) -> Optional[int]:
    """从章节标题中提取序号（支持阿拉伯数字和中文数字）。"""
    # 先尝试阿拉伯数字
    m = re.search(r'\d+', title)
    if m:
        return int(m.group())
    # 再尝试中文数字
    m = re.search(r'[零一二两三四五六七八九十百千万〇壹贰叁肆伍陆柒捌玖拾佰仟]+', title)
    if m:
        result = cn_to_arab(m.group())
        if result is not None:
            return result
    return None
