# -*- coding: utf-8 -*-
# 共享的 EPUB 路径工具函数

import re


# 相对路径计算函数
def get_relpath(from_path, to_path):
    # from_path 和 to_path 都需要是绝对路径
    from_path = re.split(r"[\\/]", from_path)
    to_path = re.split(r"[\\/]", to_path)
    while from_path[0] == to_path[0]:
        from_path.pop(0), to_path.pop(0)
    to_path = "../" * (len(from_path) - 1) + "/".join(to_path)
    return to_path


# 计算bookpath
def get_bookpath(relative_path, refer_bkpath):
    # relative_path 相对路径，一般是href
    # refer_bkpath 参考的绝对路径

    relative_ = re.split(r"[\\/]", relative_path)
    refer_ = re.split(r"[\\/]", refer_bkpath)

    back_step = 0
    while relative_[0] == "..":
        back_step += 1
        relative_.pop(0)

    if len(refer_) <= 1:
        return "/".join(relative_)
    else:
        refer_.pop(-1)

    if back_step < 1:
        return "/".join(refer_ + relative_)
    elif back_step > len(refer_):
        return "/".join(relative_)

    # len(refer_) > 1 and back_step <= len(refer_):
    while back_step > 0 and len(refer_) > 0:
        refer_.pop(-1)
        back_step -= 1

    return "/".join(refer_ + relative_)
