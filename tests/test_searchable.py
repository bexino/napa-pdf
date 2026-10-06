# -*- coding: utf-8 -*-
"""验证页眉文件名的可检索性（ToUnicode 修复是否生效）。"""
import glob
import os
import sys

import pymupdf

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
DST = os.path.join(SRC, "output")

fail = 0
for op in sorted(glob.glob(os.path.join(DST, "*.pdf"))):
    base = os.path.splitext(os.path.basename(op))[0]
    d = pymupdf.open(op)
    ok_all = True
    for pno in range(d.page_count):
        txt = d[pno].get_text()
        # 页眉标签逐字可检索
        if base not in txt:
            ok_all = False
            head = [l for l in txt.splitlines() if l.strip()][:3]
            print("  FAIL %s p%d %r 不在页文本中" % (base, pno + 1, base))
            print("       实际行:", [repr(x) for x in head])
            # 找出非法字符
            for ch in set(txt):
                if ord(ch) in (0xAD, 0xA0):
                    print("       出现非法码位 U+%04X" % ord(ch))
            break
    if ok_all:
        print("  OK   %-46s 全 %d 页可检索" % (base[:44], d.page_count))
    else:
        fail += 1
    d.close()

print("")
print("==== 失败 %d ====" % fail)
sys.exit(1 if fail else 0)
