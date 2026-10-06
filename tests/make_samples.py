# -*- coding: utf-8 -*-
"""生成测试样本，覆盖各类边界情况。"""
import os

import pymupdf

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
os.makedirs(OUT, exist_ok=True)


def save(doc, name):
    p = os.path.join(OUT, name)
    doc.save(p, garbage=4, deflate=True)
    doc.close()
    print("  生成", name, "%.1f KB" % (os.path.getsize(p) / 1024))


def dense_scan(w, h, bg, label, tag):
    d = pymupdf.open()
    p = d.new_page(width=w, height=h)
    p.draw_rect(p.rect, color=None, fill=bg)
    rows = int(h // 16)
    for i in range(rows):
        y = 14 + i * 16
        if y > h - 4:
            break
        p.draw_line(pymupdf.Point(10, y), pymupdf.Point(w - 10, y),
                    color=(0.85, 0.85, 0.85), width=0.4)
        p.insert_text((14, y - 3), "%s 第%d行 测试文本 ABC-123" % (tag, i),
                      fontsize=7.5, color=(0.1, 0.1, 0.1), fontname="china-s")
    p.insert_text((2, 6), "顶部贴边内容", fontsize=6, fontname="china-s")
    save(d, label)


print("生成测试样本 ->", OUT)

d = pymupdf.open()
d.new_page(width=595, height=842).insert_text(
    (60, 400), "正好 A4 纵向", fontsize=18, fontname="china-s")
save(d, "a4_exact.pdf")

d = pymupdf.open()
d.new_page(width=842, height=595).insert_text(
    (60, 300), "正好 A4 横向", fontsize=18, fontname="china-s")
save(d, "a4_landscape.pdf")

dense_scan(612, 792, (1, 1, 1), "bigger_than_a4.pdf", "Letter竖版")
dense_scan(300, 200, (1, 1, 1), "smaller_than_a4.pdf", "小票据")
dense_scan(595, 842, (249 / 255, 249 / 255, 245 / 255), "cream_bg.pdf", "米色底")

d = pymupdf.open()
p = d.new_page(width=595, height=842)
p.insert_text((60, 400), "rot90 变横向", fontsize=18, fontname="china-s")
p.set_rotation(90)
save(d, "rot90.pdf")

d = pymupdf.open()
p = d.new_page(width=842, height=595)
p.insert_text((60, 300), "rot270 变纵向", fontsize=18, fontname="china-s")
p.set_rotation(270)
save(d, "rot270.pdf")

d = pymupdf.open()
for i in range(4):
    w, h = (842, 595) if i % 2 else (595, 842)
    p = d.new_page(width=w, height=h)
    p.insert_text((50, h / 2), "混合方向 第%d页" % (i + 1),
                  fontsize=20, fontname="china-s")
    if i == 2:
        p.set_rotation(90)
save(d, "附件4-1. 测试用户_背调报告_2026-09-18.pdf")

src = pymupdf.open()
sp = src.new_page(width=800, height=1000)
sp.insert_text((60, 300), "含图片", fontsize=20, fontname="china-s")
png = sp.get_pixmap(dpi=150)
src.close()
d = pymupdf.open()
d.new_page(width=595, height=842).insert_image(
    pymupdf.Rect(40, 60, 555, 782), pixmap=png)
save(d, "with_image.pdf")

d = pymupdf.open()
d.new_page(width=595, height=842).insert_text(
    (60, 400), "加密文件", fontsize=18, fontname="china-s")
buf = d.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256,
                 owner_pw="owner", user_pw="secret")
d.close()
with open(os.path.join(OUT, "encrypted.pdf"), "wb") as f:
    f.write(buf)
print("  生成 encrypted.pdf (需要密码，应失败)")

with open(os.path.join(OUT, "readme.txt"), "w", encoding="utf-8") as f:
    f.write("不应被处理")
print("完成")
