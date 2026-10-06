# -*- coding: utf-8 -*-
"""字体加载与中西文混排。

规则沿用原版：CJK 字符用宋体（SimSun，衬线体，与 Times New Roman 同族风格），
其余字符用 Times；夹在中西文之间的空格按中文宽度排，避免视觉上挤在一起。

西文默认用 PyMuPDF 内置的 base-14 "Times-Roman"，而不是系统的 times.ttf：
实测 PyMuPDF 对 times.ttf 的 subset_fonts() 几乎不起作用——只用 1 个字形仍嵌入
51KB（完整字形表），36 个字形也才 76KB；而内置 Times-Roman 子集化后整个文件
仅约 11KB，视觉几乎一致，文本检索同样正常。

要强制使用系统字体，设环境变量 NAPAPDF_LATIN_FONT=<字体文件路径>。
"""
import os
import sys
import threading

import pymupdf

from . import config


def _bundle_fonts_dir():
    """打包后的资源目录（PyInstaller onefile 会解到 _MEIPASS/fonts）。

    源码直接运行时返回 None，此时走系统字体路径。"""
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        return None
    d = os.path.join(base, "fonts")
    return d if os.path.isdir(d) else None


def _first_existing(paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


class FontSet:
    """一次性加载西文 / 中文字体，并提供分段排版能力。"""

    def __init__(self):
        override = os.environ.get("NAPAPDF_LATIN_FONT", "").strip()
        self.latin_path = _first_existing((override,) if override
                                         else config.LATIN_FONT_CANDIDATES)
        # 包内字体优先：目标机器可能压根没装宋体（Server Core、精简版系统），
        # 那样会回退到内置 Droid Sans Fallback，外观和原件不一致。
        bundle = _bundle_fonts_dir()
        cjk = []
        if bundle:
            for name in ("simsun.ttc", "STSONG.TTF", "simhei.ttf"):
                cjk.append(os.path.join(bundle, name))
        self.cjk_path = _first_existing(cjk + list(config.CJK_FONT_CANDIDATES))
        self.f_latin = self._load(self.latin_path, config.BUILTIN_LATIN)
        self.f_cjk = self._load(self.cjk_path, config.BUILTIN_CJK)
        self._cache = {}
        self._lock = threading.Lock()

    @staticmethod
    def _load(path, builtin):
        if path:
            try:
                return pymupdf.Font(fontfile=path)
            except Exception:
                pass
        return pymupdf.Font(builtin)

    # -- 字符族判定 ----------------------------------------------------
    @staticmethod
    def is_cjk(ch: str) -> bool:
        o = ord(ch)
        return (
            0x2E80 <= o <= 0x9FFF        # CJK 部首/汉字
            or 0xF900 <= o <= 0xFAFF     # 兼容汉字
            or 0xFF00 <= o <= 0xFFEF     # 全角字符
            or 0x3000 <= o <= 0x303F     # 中文标点
            or 0xFE30 <= o <= 0xFE4F     # 兼容标点
        )

    def font_for(self, ch: str):
        return self.f_cjk if self.is_cjk(ch) else self.f_latin

    def segments(self, text: str):
        """把字符串切成 (片段, 字体) 列表，连续同族字符归为一段。
        夹在中/西文之间的空格按中文宽度排版（半角 5pt），避免中西文之间过于拥挤。"""
        if not text:
            return []
        with self._lock:
            cached = self._cache.get(text)
        if cached is not None:
            return cached

        per_char = []
        for i, ch in enumerate(text):
            if ch == " ":
                prev = text[i - 1] if i > 0 else ""
                nxt = text[i + 1] if i + 1 < len(text) else ""
                use_cjk = self.is_cjk(prev) or self.is_cjk(nxt)
            else:
                use_cjk = self.is_cjk(ch)
            per_char.append((ch, self.f_cjk if use_cjk else self.f_latin))

        out = []
        for ch, font in per_char:
            if out and out[-1][1] is font:
                out[-1] = (out[-1][0] + ch, font)
            else:
                out.append((ch, font))

        with self._lock:
            self._cache[text] = out
        return out

    def text_width(self, text: str, size: float = None) -> float:
        size = config.LABEL_SIZE if size is None else size
        return sum(f.text_length(seg, size) for seg, f in self.segments(text))


_FONTSET = None
_INIT_LOCK = threading.Lock()


def get_fonts() -> FontSet:
    """进程内单例。字体对象跨线程共享不安全，这里只做惰性加载 + 只读分段。"""
    global _FONTSET
    if _FONTSET is None:
        with _INIT_LOCK:
            if _FONTSET is None:
                _FONTSET = FontSet()
    return _FONTSET
