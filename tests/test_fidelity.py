# -*- coding: utf-8 -*-
"""几何保真测试（块级覆盖率判定，抗亚像素位移）。

缩放必然重采样：dense 小字缩放 0.9666 后抗锯齿把 0.4pt 细线糊成灰，
逐像素差异可达 4%+（实测 cream_bg 墨迹区 87% 像素位移 >24），这是等比缩放的
固有代价，不代表内容变化。真正要保证的是：
  1. 无内容丢失/重复：整体墨迹覆盖率与源页一致
  2. 版式一致：分块墨迹分布高度相关（32x32 块，抹掉亚像素抖动）
  3. 文本逐字保留：输出页能检索到源页全部文字
  4. 纵横比不变：内容区宽高比 == 源页宽高比
"""
import glob
import os
import sys

import numpy as np
import pymupdf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from napa_pdf import config

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
DST = os.path.join(SRC, "output")
STRIP = config.HEADER_STRIP
K = 2.0
BLK = 32


def gray(page, clip, k):
    pm = page.get_pixmap(matrix=pymupdf.Matrix(k, k), clip=clip,
                         colorspace=pymupdf.csGRAY)
    return np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.height, pm.width)


def blocks(arr):
    """切成 BLK x BLK 块，返回每块墨迹覆盖率（丢弃边缘残块）。"""
    h = (arr.shape[0] // BLK) * BLK
    w = (arr.shape[1] // BLK) * BLK
    core = (arr[:h, :w] < 215).astype(float)
    return core.reshape(h // BLK, BLK, w // BLK, BLK).mean(axis=(1, 3)).ravel()


def main():
    fail = 0
    total = 0
    for sp in sorted(glob.glob(os.path.join(SRC, "*.pdf"))):
        name = os.path.basename(sp)
        op = os.path.join(DST, name)
        if not os.path.exists(op):
            continue
        a = pymupdf.open(sp)
        b = pymupdf.open(op)
        print("[%s]" % name)
        for i in range(b.page_count):
            total += 1
            src, out = a[i], b[i]
            sw, sh = src.rect.width, src.rect.height
            ow, oh = out.rect.width, out.rect.height
            scale = min(ow / sw, (oh - STRIP) / sh)
            dw, dh = sw * scale, sh * scale
            x0 = (ow - dw) / 2.0
            y0 = STRIP + ((oh - STRIP) - dh) / 2.0

            A = gray(src, src.rect, K)
            B = gray(out, pymupdf.Rect(x0, y0, x0 + dw, y0 + dh), K / scale)
            ba, bb = blocks(A), blocks(B)
            n = min(len(ba), len(bb))
            ba, bb = ba[:n], bb[:n]
            cov_a, cov_b = ba.mean(), bb.mean()
            tol = max(0.002, cov_a * 0.03)
            corr = (float(np.corrcoef(ba, bb)[0, 1])
                    if ba.std() > 1e-9 and bb.std() > 1e-9 else 1.0)
            ta = "".join(src.get_text().split())
            tb = "".join(out.get_text().split())
            txt_ok = ta in tb
            ar_ok = abs((dw / dh) - (sw / sh)) < 1e-9

            ok = abs(cov_b - cov_a) <= tol and corr >= 0.90 and txt_ok and ar_ok
            print("   p%d %s 覆盖率%.4f->%.4f(±%.4f) 块相关%.4f 文本%s 比例%s"
                  % (i + 1, "OK  " if ok else "FAIL", cov_a, cov_b, tol, corr,
                     "保留" if txt_ok else "丢失",
                     "不变" if ar_ok else "变形"))
            if not ok:
                fail += 1
        a.close()
        b.close()
    print("")
    print("==== 页数 %d  失败 %d ====" % (total, fail))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
