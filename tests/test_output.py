# -*- coding: utf-8 -*-
"""端到端验收：跑批处理，再对输出做确定性断言。"""
import glob
import hashlib
import os
import shutil
import sys
import time

import numpy as np
import pymupdf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from napa_pdf import config
from napa_pdf.batch import BatchRunner, output_dir_for

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
DST = output_dir_for(SRC)
if os.path.isdir(DST):
    shutil.rmtree(DST)


def log(lv, t):
    print("  [%s] %s" % (lv, t))


print("=== 跑批处理 ===")
r = BatchRunner(SRC, DST, on_log=log).start()
while r.is_alive():
    time.sleep(0.15)
print("  ok=%d failed=%d" % (r.ok, r.failed))

print("")
print("=== 逐文件断言 ===")
A4P = (config.A4_SHORT, config.A4_LONG)
A4L = (config.A4_LONG, config.A4_SHORT)
STRIP = config.HEADER_STRIP
fail_total = 0

for src in sorted(glob.glob(os.path.join(SRC, "*.pdf"))):
    name = os.path.basename(src)
    base = os.path.splitext(name)[0]
    out = os.path.join(DST, name)
    print("")
    print("[%s]" % name)

    expect_fail = name == "encrypted.pdf"
    if not os.path.exists(out):
        mark = "OK" if expect_fail else "FAIL"
        print("   %s 输出不存在（期望失败=%s）" % (mark, expect_fail))
        if not expect_fail:
            fail_total += 1
        continue
    if expect_fail:
        print("   FAIL 加密文件竟然产出了输出")
        fail_total += 1
        continue

    a = pymupdf.open(src)
    b = pymupdf.open(out)
    bad = []
    if a.page_count != b.page_count:
        bad.append("页数 %d->%d" % (a.page_count, b.page_count))

    for i in range(b.page_count):
        pg = b[i]
        w, h = pg.rect.width, pg.rect.height
        want = A4L if w > h else A4P
        if abs(w - want[0]) > 0.6 or abs(h - want[1]) > 0.6:
            bad.append("p%d 尺寸 %.1fx%.1f 不等于 A4" % (i + 1, w, h))

        sp = a[i]
        # page.rect 已是含旋转的显示尺寸，不要再交换一次
        if (sp.rect.width > sp.rect.height) != (w > h):
            bad.append("p%d 方向不符（源横向=%s）"
                       % (i + 1, sp.rect.width > sp.rect.height))
        if abs(pg.rotation) > 0.01:
            bad.append("p%d 残留 rotation=%s" % (i + 1, pg.rotation))

        spans = [s for blk in pg.get_text("dict")["blocks"] if blk["type"] == 0
                 for ln in blk["lines"] for s in ln["spans"]]
        # 内容顶边正好落在 STRIP，保存后浮点误差会到 27.999…，留 0.5pt 容差
        head = [s for s in spans if s["bbox"][1] < STRIP - 0.5]
        label_spans = [s for s in spans if abs(s["size"] - config.LABEL_SIZE) < 0.05
                       and s["bbox"][1] < STRIP]
        txt = "".join(s["text"] for s in label_spans)
        if txt != base:
            bad.append("p%d 页眉文本 %r != %r" % (i + 1, txt, base))
        if label_spans:
            if max(s["bbox"][3] for s in label_spans) > STRIP + 0.2:
                bad.append("p%d 标签越出页眉带" % (i + 1))
            if abs(min(s["bbox"][0] for s in label_spans) - config.HEADER_LEFT) > 0.8:
                bad.append("p%d 左边距不符" % (i + 1))
        # 带内除标签外的墨迹必须为零（证明原内容被整体下移、绝无叠字）
        band_others = [s for s in head if s not in label_spans]
        if band_others:
            bad.append("p%d 页眉带内混入了原内容：%r"
                       % (i + 1, "".join(s["text"] for s in band_others)[:30]))

        pm = pg.get_pixmap(dpi=144, colorspace=pymupdf.csGRAY)
        arr = np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.height, pm.width)
        band = arr[: int(STRIP * 2), :]
        x1 = max((s["bbox"][2] for s in label_spans), default=config.HEADER_LEFT)
        tail = band[:, int((x1 + 4) * 2):]
        if tail.size and int((tail < 215).sum()) > 0:
            bad.append("p%d 页眉带内有杂散墨迹（可能压住原内容）" % (i + 1))
        if int((band < 215).sum()) < 50:
            bad.append("p%d 标签未渲染出墨迹" % (i + 1))
    a.close()
    b.close()

    if bad:
        fail_total += 1
        for x in bad:
            print("   FAIL %s" % x)
    else:
        print("   OK 尺寸/方向/页眉文本/无叠字 全部通过")

print("")
print("=== 底色一致性（米色底不应出现白条） ===")
cream = os.path.join(DST, "cream_bg.pdf")
if os.path.exists(cream):
    d = pymupdf.open(cream)
    band = d[0].get_pixmap(dpi=144,
                           clip=pymupdf.Rect(0, 0, 400, STRIP),
                           colorspace=pymupdf.csRGB)
    arr = np.frombuffer(band.samples, dtype=np.uint8).reshape(
        band.height, band.width, band.n)
    patch = arr[4:20, 250:380, :3].reshape(-1, 3).mean(axis=0)
    print("   页眉带取样 RGB =", [round(float(v), 1) for v in patch],
          "（源底色约 249/249/245）")
    if patch.min() < 230:
        print("   FAIL 页眉带不是源底色")
        fail_total += 1
    else:
        print("   OK 与源底色一致")
    d.close()

print("")
print("=== 图像未被重编码 ===")
nm = "with_image.pdf"
sp, op = os.path.join(SRC, nm), os.path.join(DST, nm)
if os.path.exists(op):
    a = pymupdf.open(sp)
    b = pymupdf.open(op)

    def digs(doc, page):
        return sorted(hashlib.md5(pymupdf.Pixmap(doc, x[0]).samples).hexdigest()
                      for x in page.get_images(full=True))

    same = digs(a, a[0]) == digs(b, b[0])
    print("   %s 解码像素%s" % (nm, "一致 OK" if same else "不一致 FAIL"))
    if not same:
        fail_total += 1
    a.close()
    b.close()

print("")
print("=== 文件体积 ===")
for src in sorted(glob.glob(os.path.join(SRC, "*.pdf"))):
    out = os.path.join(DST, os.path.basename(src))
    if os.path.exists(out):
        print("   %-52s %7.1f KB -> %7.1f KB" % (
            os.path.basename(src)[:50], os.path.getsize(src) / 1024,
            os.path.getsize(out) / 1024))

print("")
print("==== 失败项: %d ====" % fail_total)
sys.exit(1 if fail_total else 0)
