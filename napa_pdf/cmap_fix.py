# -*- coding: utf-8 -*-
"""修正 Times New Roman 子集字体的 ToUnicode CMap。

背景：PyMuPDF 用系统 times.ttf 生成子集字体时，反查字体 cmap 会为连字符字形
选到 U+00AD（软连字符）、为空格字形选到 U+00A0（不间断空格），导致：
  - 复制/检索标签文字时得到软连字符，搜 "附件1-1" 匹配不上；
  - 视觉渲染本身正确（字形就是连字符）。
本模块把这两个 CID 的映射改回 U+002D / U+0020，其余映射原样保留（含区间形式的
bfrange）。实现沿用 .skill/scripts/cmap_fix.py，收进包内以便程序独立运行。
"""

CN_DIGITS = "0123456789abcdef"


def _h(v: int) -> str:
    return "%04x" % v


def parse_cmap(text: str):
    """解析 CMap 文本，返回 (header, ranges, chars, footer)。
    ranges: [(lo, hi, ustart)]  chars: [(cid, uni)]
    """
    lines = text.splitlines()
    i = 0
    header_end = None
    while i < len(lines):
        if lines[i].strip().endswith("begincodespacerange"):
            while "endcodespacerange" not in lines[i]:
                i += 1
            header_end = i
            break
        i += 1
    if header_end is None:
        return None, [], [], []
    header = lines[: header_end + 1]

    ranges, chars = [], []
    i = header_end + 1
    while i < len(lines):
        s = lines[i].strip()
        if s.endswith("beginbfrange"):
            i += 1
            while "endbfrange" not in lines[i]:
                p = lines[i].split()
                if len(p) == 3:
                    ranges.append((int(p[0][1:-1], 16), int(p[1][1:-1], 16),
                                   int(p[2][1:-1], 16)))
                i += 1
            i += 1
        elif s.endswith("beginbfchar"):
            i += 1
            while "endbfchar" not in lines[i]:
                p = lines[i].split()
                if len(p) == 2:
                    chars.append((int(p[0][1:-1], 16), int(p[1][1:-1], 16)))
                i += 1
            i += 1
        elif s == "endcmap":
            break
        else:
            i += 1
    footer = lines[i:]
    return header, ranges, chars, footer


def build_cmap(header, ranges, chars, footer):
    out = list(header)
    for blk in _chunks(ranges, 100):
        out.append("%d beginbfrange" % len(blk))
        for lo, hi, us in blk:
            out.append("<%s> <%s> <%s>" % (_h(lo), _h(hi), _h(us)))
        out.append("endbfrange")
    for blk in _chunks(chars, 100):
        out.append("%d beginbfchar" % len(blk))
        for cid, uni in blk:
            out.append("<%s> <%s>" % (_h(cid), _h(uni)))
        out.append("endbfchar")
    out.extend(footer)
    return "\n".join(out) + "\n"


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i: i + n]


def fix_to_unicode(text: str, remap: dict) -> tuple:
    """remap: {旧 Unicode 码位: 新 Unicode 码位}。返回 (新 CMap 文本, 修正条目列表)。"""
    header, ranges, chars, footer = parse_cmap(text)
    if header is None:
        return text, []
    fixed = []
    new_ranges, new_chars = [], []

    for lo, hi, us in ranges:
        hit = [u for u in range(us, us + (hi - lo) + 1) if u in remap]
        if not hit:
            new_ranges.append((lo, hi, us))
            continue
        cur = lo
        while cur <= hi:
            uni = us + (cur - lo)
            if uni in remap:
                new_chars.append((cur, remap[uni]))
                fixed.append((cur, uni, remap[uni]))
                cur += 1
                continue
            start = cur
            while cur <= hi and (us + (cur - lo)) not in remap:
                cur += 1
            new_ranges.append((start, cur - 1, us + (start - lo)))

    for cid, uni in chars:
        if uni in remap:
            new_chars.append((cid, remap[uni]))
            fixed.append((cid, uni, remap[uni]))
        else:
            new_chars.append((cid, uni))

    new_chars.sort()
    return build_cmap(header, new_ranges, new_chars, footer), fixed


REMAP = {0x00AD: 0x002D, 0x00A0: 0x0020}   # 软连字符->连字符；不间断空格->空格


def fix_doc(doc) -> list:
    """修正文档中所有 Times 字体的 ToUnicode；返回修正记录。

    注意：必须在 doc.subset_fonts() 之后调用——子集化之前字体名与 CMap 结构尚未确定。
    """
    log = []
    for x in range(1, doc.xref_length()):
        try:
            obj = doc.xref_object(x)
        except Exception:
            continue
        if "/ToUnicode" not in obj or "/Font" not in obj:
            continue
        base = doc.xref_get_key(x, "BaseFont")
        name = base[1] if base else ""
        if "Times" not in name:
            continue
        tu = doc.xref_get_key(x, "ToUnicode")
        if tu[0] != "xref":
            continue
        try:
            sid = int(tu[1].split()[0])
            raw = doc.xref_stream(sid).decode("latin-1")
        except Exception:
            continue
        new, fixed = fix_to_unicode(raw, REMAP)
        if fixed:
            doc.update_stream(sid, new.encode("latin-1"))
            log.append((name.replace("#20", " "), fixed))
    return log
