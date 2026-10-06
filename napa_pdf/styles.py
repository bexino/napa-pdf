# -*- coding: utf-8 -*-
"""终端样式表。配色见 theme.py（自动适配明/暗背景）。"""
from prompt_toolkit.styles import Style

from .theme import detect_theme, palette


def build_style() -> Style:
    p = palette()
    return Style.from_dict({
        "": p["text"],
        "accent": p["accent"],
        "hl": p["hl"] + " bold",
        "text": p["text"],
        "dim": p["dim"],
        "ok": p["ok"],
        "warn": p["warn"],
        "err": p["err"],
        "rule": p["rule"],
        "title": p["accent"] + " bold",
        "prompt": p["accent"],
        "input": p["text"],
        "bottom-toolbar": p["dim"],
    })


__all__ = ["build_style", "detect_theme"]
