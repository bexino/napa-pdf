# -*- coding: utf-8 -*-
"""全局常量与参数默认值。

页眉相关的取值（页眉带高 28pt / 左内边距 28pt / 基线 17.6pt / 字号 10pt）与
原始 stamp_filename.py 保持一致：先在页面顶部留出一条空白页眉带，把内容整体
下移到带子下方，文件名只写在带内。这样标签在数学上不可能压住任何原有内容。
"""
import os

# ---- A4 尺寸（pt，1mm = 2.834645669pt）----
A4_SHORT = 595.276        # 210mm
A4_LONG = 841.890         # 297mm

# ---- 页眉带（与原版一致）----
HEADER_STRIP = 28.0       # 页眉带高度 pt ≈ 9.9mm
HEADER_LEFT = 28.0        # 左内边距 pt ≈ 9.9mm
HEADER_BASE_Y = 17.6      # 基线在页眉带内的 y 位置 pt
LABEL_SIZE = 10.0         # 字号 pt
LABEL_COLOR = (0, 0, 0)   # 纯黑

# ---- 输出 ----
OUTPUT_DIRNAME = "output"
PDF_GLOB = "*.pdf"

# ---- 字体 ----
# 西文：默认用内置 base-14 "tiro"（Times-Roman）。PyMuPDF 对系统 times.ttf 的
# 子集化几乎无效（1 个字形也嵌 51KB），而内置字体子集化后整份文件仅约 11KB。
# 需要还原原版字体时设 NAPAPDF_LATIN_FONT=C:\Windows\Fonts\times.ttf。
LATIN_FONT_CANDIDATES = ()
CJK_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\STSONG.TTF",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
)

# 内置字体名（找不到系统字体文件时的兜底）
BUILTIN_LATIN = "tiro"        # Times-Roman
BUILTIN_CJK = "china-s"       # Droid Sans Fallback

# 覆盖环境变量：NAPAPDF_SIZE 可调字号，NAPAPDF_STRIP 可调页眉带高
def _env_float(name, default):
    try:
        v = float(os.environ.get(name, ""))
        return v if v > 0 else default
    except (TypeError, ValueError):
        return default


HEADER_STRIP = _env_float("NAPAPDF_STRIP", HEADER_STRIP)
LABEL_SIZE = _env_float("NAPAPDF_SIZE", LABEL_SIZE)
