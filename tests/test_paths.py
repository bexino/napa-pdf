# -*- coding: utf-8 -*-
"""验证路径清洗覆盖各种粘贴 / 拖拽形态。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from napa_pdf.tui import clean_path

BS = chr(92)      # 反斜杠，用变量拼避免源码里出现裸尾随反斜杠
Q = chr(34)

CASES = [
    ("裸路径", "E:" + BS + "Personal" + BS + "Desktop" + BS + "Index"),
    ("双引号（拖入）", Q + "E:" + BS + "P" + BS + "Index" + Q),
    ("尾随反斜杠", "E:" + BS + "P" + BS + "Index" + BS),
    ("引号加尾斜杠", Q + "E:" + BS + "P" + BS + "Index" + BS + Q),
    ("首尾空格", "  E:" + BS + "P" + BS + "Index  "),
    ("带换行", "E:" + BS + "P" + BS + "Index" + chr(10)),
    ("家目录", "~/Documents/Index"),
    ("环境变量", "%USERPROFILE%" + BS + "Documents" + BS + "Index"),
    ("中文与空格", "D:" + BS + "工作" + BS + "档案 2026" + BS + "最终版"),
    ("盘符根目录", "D:" + BS),
]


def is_clean(p):
    if p.startswith(Q) or p.endswith(Q):
        return False
    if len(p) > 3 and p.endswith(BS) and not p.endswith(":" + BS):
        return False
    return True


def main():
    fail = 0
    print("--- 清洗结果 ---")
    for tag, raw in CASES:
        out = clean_path(raw)
        ok = is_clean(out)
        print("  %s %-16s %-38r -> %r"
              % ("OK  " if ok else "FAIL", tag, raw, out))
        if not ok:
            fail += 1

    print("")
    print("--- 目录判定 ---")
    here = os.path.dirname(os.path.abspath(__file__))
    checks = [
        ("当前目录", here, True),
        ("带引号", Q + here + Q, True),
        ("尾斜杠", here + BS, True),
        ("不存在的盘", "Z:" + BS + "不存在" + BS + "xxx", False),
        ("空输入", "", False),
        ("文件非目录", os.path.join(here, "test_paths.py"), False),
    ]
    for tag, raw, want in checks:
        p = clean_path(raw)
        isdir = os.path.isdir(p)
        ok = isdir == want
        print("  %s %-14s isdir=%-5s %s"
              % ("OK  " if ok else "FAIL", tag, isdir, p))
        if not ok:
            fail += 1

    print("")
    print("==== 失败 %d ====" % fail)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
