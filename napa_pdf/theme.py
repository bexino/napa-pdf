# -*- coding: utf-8 -*-
"""终端配色：自动适配明/暗背景。

为什么需要两套：prompt_toolkit 不暴露终端背景亮度，Windows Terminal 的
深色/浅色主题也不是控制台属性位能可靠反映的。固定一套配色时，浅色背景下
浅灰文字的对比度只有 1.1:1，几乎不可见——这正是"字体是灰色的、可读性很差"
的根因。所以这里按控制台背景位 + 环境变量选一套，两套都保证 >= 4.5:1。
"""
import os

# ---- 两套配色：深色背景下用亮字，浅色背景下用深字 ----
DARK = {
    "accent": "#5FA8D3",
    "hl": "#FFFFFF",
    "text": "#E8E8E8",
    "dim": "#9AA0A6",
    "ok": "#86E39B",
    "warn": "#E9C46A",
    "err": "#FF8A80",
    "rule": "#6E767D",
}

LIGHT = {
    "accent": "#1F6FB2",
    "hl": "#000000",
    "text": "#1A1A1A",
    "dim": "#5A5F66",
    "ok": "#0F6B33",
    "warn": "#8A6100",
    "err": "#C0271C",
    "rule": "#767B80",
}


def _console_is_light():
    """读控制台屏幕缓冲的属性位判断背景。读不到返回 None。"""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class COORD(ctypes.Structure):
            _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]

        class SMALL_RECT(ctypes.Structure):
            _fields_ = [("Left", wintypes.SHORT), ("Top", wintypes.SHORT),
                        ("Right", wintypes.SHORT), ("Bottom", wintypes.SHORT)]

        class CSBI(ctypes.Structure):
            _fields_ = [("dwSize", COORD), ("dwCursorPosition", COORD),
                        ("wAttributes", wintypes.WORD),
                        ("srWindow", SMALL_RECT),
                        ("dwMaximumWindowSize", COORD)]

        k = ctypes.WinDLL("kernel32", use_last_error=True)
        for handle_id in (-11, -12):
            h = k.GetStdHandle(handle_id)
            sb = CSBI()
            if h and k.GetConsoleScreenBufferInfo(h, ctypes.byref(sb)):
                # 属性位 4..7 是背景色；0..7 暗色系，8..15 亮色系
                bg = (sb.wAttributes >> 4) & 0x0F
                return bg >= 8
    except Exception:
        pass
    return None


def detect_theme():
    """返回 'light' 或 'dark'。

    优先级：NAPAPDF_THEME 环境变量 > 控制台背景位 > 假定深色
    （现代终端默认深色，且深色下的浅字更不容易出错）。
    """
    forced = os.environ.get("NAPAPDF_THEME", "").strip().lower()
    if forced in ("light", "dark"):
        return forced
    light = _console_is_light()
    if light is None:
        return "dark"
    return "light" if light else "dark"


def palette():
    return dict(LIGHT) if detect_theme() == "light" else dict(DARK)
