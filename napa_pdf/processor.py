# -*- coding: utf-8 -*-
"""PDF 逐页归一化为 A4 并在页眉标注文件名。

每页处理分三步：
  1. 归一化：先 remove_rotation() 把页面摆正（show_pdf_page 的 clip 用的是未旋转
     坐标，直接传 page.rect 会在旋转页上裁掉 3/4 内容），再按「显示尺寸宽>高判横向」
     决定目标 A4 画布为纵向还是横向，把原页等比缩放居中放入。
  2. 页眉带：在画布顶部留出 HEADER_STRIP 高度，用源页底色填充（避免白条割裂），
     文件名只写在这条带子里，因此不可能压住任何原有内容。
  3. 保存前 subset_fonts() + fix_doc() 修 ToUnicode，避免嵌入整个 18MB 宋体、
     也避免软连字符导致文件名搜不到。
"""
import os
import re

import pymupdf

from . import config
from .cmap_fix import fix_doc
from .i18n import DEFAULT_LANG, t
from .fonts import get_fonts

_ILLEGAL = re.compile(r'[\\/:*?"<>|]')


class ProcessError(Exception):
    """单个文件处理失败（不中断整批）。"""


def sanitize(name: str) -> str:
    return _ILLEGAL.sub("_", name)


def page_background(page: pymupdf.Page, dpi: int = 18) -> tuple:
    """返回页面底色 (r, g, b)，取值 0~1。

    整页低分辨率渲染后取众数色：文字、边框、印章、骑缝章都只占少数像素，
    众数天然就是纸张底色。原版只采样左上角一小块，遇到顶部有黑边的扫描件
    会取到黑色、把整条页眉带涂黑。"""
    try:
        pm = page.get_pixmap(dpi=dpi)
    except Exception:
        return (1.0, 1.0, 1.0)
    if pm.width == 0 or pm.height == 0:
        return (1.0, 1.0, 1.0)
    s = pm.samples
    n = pm.n
    buckets = {}
    step = max(1, n)
    for i in range(0, len(s), step):
        key = (s[i] >> 4, s[i + 1] >> 4, s[i + 2] >> 4)
        b = buckets.get(key)
        if b is None:
            buckets[key] = b = [0, 0, 0, 0]
        b[0] += s[i]
        b[1] += s[i + 1]
        b[2] += s[i + 2]
        b[3] += 1
    best = max(buckets.values(), key=lambda b: b[3])
    cnt = max(1, best[3])
    return tuple(best[i] / cnt / 255.0 for i in range(3))


def _a4_canvas(landscape: bool):
    if landscape:
        return config.A4_LONG, config.A4_SHORT
    return config.A4_SHORT, config.A4_LONG


def _write_label(page: pymupdf.Page, label: str) -> float:
    """在页眉带左上角写入文件名（中西文混排），返回文本右边界 x。"""
    fonts = get_fonts()
    tw = pymupdf.TextWriter(page.rect)
    x = config.HEADER_LEFT
    for seg, font in fonts.segments(label):
        tw.append(pymupdf.Point(x, config.HEADER_BASE_Y), seg,
                  font=font, fontsize=config.LABEL_SIZE)
        x += font.text_length(seg, config.LABEL_SIZE)
    tw.write_text(page, color=config.LABEL_COLOR)
    return x


def normalize_page(src: pymupdf.Page, dst_doc: pymupdf.Document, label: str,
                  lang: str = DEFAULT_LANG) -> tuple:
    """把一个源页归一化后追加到 dst_doc，返回 (横向?, 缩放比)。

    show_pdf_page 的 clip 走的是未旋转坐标，所以旋转页必须先 remove_rotation()
    烘焙进内容，此时 page.rect 才是人眼看到的真实尺寸，横向判定也才可靠。
    """
    if src.rotation:
        src.remove_rotation()
    clip = pymupdf.Rect(src.rect)
    clip.normalize()
    src_w, src_h = clip.width, clip.height
    if src_w <= 0 or src_h <= 0:
        raise ProcessError(t("err_bad_page_size", lang))

    landscape = src_w > src_h
    cw, ch = _a4_canvas(landscape)

    page = dst_doc.new_page(width=cw, height=ch)
    bg = page_background(src)
    # 先铺底色：新页眉带和四周空出的边距颜色必须一致，否则会出现白条割裂
    page.draw_rect(page.rect, color=None, fill=bg, overlay=True)

    avail_h = ch - config.HEADER_STRIP
    scale = min(cw / src_w, avail_h / src_h)
    dw, dh = src_w * scale, src_h * scale
    x0 = (cw - dw) / 2.0
    y0 = config.HEADER_STRIP + (avail_h - dh) / 2.0
    page.show_pdf_page(pymupdf.Rect(x0, y0, x0 + dw, y0 + dh),
                       src.parent, src.number, clip=clip,
                       keep_proportion=False, overlay=True)

    page.draw_rect(pymupdf.Rect(0, 0, cw, config.HEADER_STRIP),
                   color=None, fill=bg, overlay=True)
    _write_label(page, label)
    return landscape, scale


def process_pdf(src_path: str, out_path: str, label: str = None,
                progress=None, lang: str = DEFAULT_LANG) -> dict:
    """处理单个 PDF：A4 归一化 + 页眉文件名，保存到 out_path。

    progress: 可选回调 progress(已完成页数, 总页数)。
    返回统计字典。
    """
    label = label or os.path.splitext(os.path.basename(src_path))[0]
    tmp_path = out_path + ".napa.tmp"
    out_doc = pymupdf.open()
    src = None
    result = {"pages": 0, "landscape": 0, "portrait": 0, "tounicode_fixed": 0}
    try:
        try:
            src = pymupdf.open(src_path)
        except Exception as e:
            raise ProcessError(t("err_cannot_open", lang, e=e))
        if src.needs_pass and not src.authenticate(""):
            raise ProcessError(t("err_encrypted", lang))
        if src.page_count == 0:
            raise ProcessError(t("err_no_pages", lang))

        for pno in range(src.page_count):
            try:
                landscape, _scale = normalize_page(src[pno], out_doc, label,
                                                    lang)
            except ProcessError:
                raise
            except Exception as e:
                raise ProcessError(t("err_page_failed", lang, page=pno + 1, err=e))
            result["landscape" if landscape else "portrait"] += 1
            result["pages"] += 1
            if progress:
                progress(result["pages"], src.page_count)

        out_doc.subset_fonts(verbose=False)     # 只嵌入用到的字形，否则宋体整库 18MB
        try:
            fixed = fix_doc(out_doc)             # 子集化之后再修 ToUnicode（顺序不能反）
            result["tounicode_fixed"] = sum(len(f[1]) for f in fixed)
        except Exception as e:
            result["tounicode_error"] = str(e)

        out_dir = os.path.dirname(os.path.abspath(out_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        out_doc.save(tmp_path, garbage=4, deflate=True)
    finally:
        out_doc.close()
        if src is not None:
            src.close()

    os.replace(tmp_path, out_path)
    return result
