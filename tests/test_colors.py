# -*- coding: utf-8 -*-
"""配色验收。

用户反馈过"字体是灰色的，可读性很差"。根因是固定用一套深色配色，浅色终端
背景下对比度只有 1.1:1。这里不靠肉眼判断，而是：
  A. 按 WCAG 公式验证两套配色各自在匹配背景下都 >= 4.5:1
  B. 断言承载实际信息的行没有用 dim
  C. 检查实际渲染的 ANSI 码里含高亮色（明暗两套都验）
"""
import io
import os
import re
import sys

from prompt_toolkit.data_structures import Size
from prompt_toolkit.output import ColorDepth
from prompt_toolkit.output.vt100 import Vt100_Output
from prompt_toolkit.renderer import print_formatted_text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from napa_pdf.theme import DARK, LIGHT


def lum(hex_color):
    r = int(hex_color[1:3], 16) / 255.0
    g = int(hex_color[3:5], 16) / 255.0
    b = int(hex_color[5:7], 16) / 255.0

    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(fg, bg):
    a, b = lum(fg), lum(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def check_contrast(fail):
    print("--- A. 两套配色在各自匹配背景下的对比度（>= 4.5:1）---")
    tests = [("深色", DARK, ["#0C0C0C", "#1E1E1E"]),
             ("浅色", LIGHT, ["#FFFFFF", "#F0F0F0"])]
    for name, pal, bgs in tests:
        for bg in bgs:
            worst, wkey = 99.0, ""
            for key, fg in pal.items():
                # rule 是纯装饰性分隔线，不承载信息，不按正文标准要求
                if key == "rule":
                    continue
                r = contrast(fg, bg)
                if r < worst:
                    worst, wkey = r, key
                if r < 4.5:
                    fail.append("contrast-%s-%s-on-%s" % (name, key, bg))
            mark = "OK  " if worst >= 4.5 else "FAIL"
            print("  %s %s配色 背景 %-9s 最低 %.1f:1（%s）"
                  % (mark, name, bg, worst, wkey))

    print("")
    print("--- A2. 旧配色（不区分背景）在白底上的表现 ---")
    for fg in ("#E8E8E8", "#9AA0A6"):
        r = contrast(fg, "#FFFFFF")
        print("    浅色字 %s 在白底上仅 %.1f:1  <-- 用户反馈的根因" % (fg, r))


def reload_modules(theme):
    os.environ["NAPAPDF_THEME"] = theme
    keys = ("napa_pdf.tui", "napa_pdf.styles", "napa_pdf.theme")
    for k in [m for m in list(sys.modules) if m.startswith(keys)]:
        del sys.modules[k]
    import napa_pdf.styles as S
    import napa_pdf.theme as TH
    import napa_pdf.tui as T
    return T, S, TH


def check_theme_detect(fail):
    print("")
    print("--- A3. 主题探测与环境变量覆盖 ---")
    from napa_pdf.theme import detect_theme
    for want in ("dark", "light"):
        os.environ["NAPAPDF_THEME"] = want
        got = detect_theme()
        ok = got == want
        print("  %s NAPAPDF_THEME=%-5s -> %s"
              % ("OK  " if ok else "FAIL", want, got))
        if not ok:
            fail.append("theme-" + want)
    os.environ.pop("NAPAPDF_THEME", None)
    got = detect_theme()
    ok = got in ("dark", "light")
    print("  %s 无环境变量时自动判定 = %s" % ("OK  " if ok else "FAIL", got))
    if not ok:
        fail.append("theme-default")


def check_styles(fail):
    print("")
    print("--- B. 关键信息行不应使用 dim ---")
    T, S, TH = reload_modules("dark")
    app = T.NapaApp("")
    app._build()
    here = os.path.dirname(os.path.abspath(__file__))

    def rows(mode):
        app.mode = mode
        # 输入页的"输出到"是条件渲染的，得先给一个真实路径
        if mode == "input":
            app.folder = here
            app.out_dir = os.path.join(here, "output")
        return [(s, t.strip()) for s, t in app._body() if t.strip()]

    cases = [("menu", "主菜单说明", "批量把 PDF"),
             ("menu", "菜单项描述", "批量归一化 A4"),
             ("input", "拖拽提示", "拖进本窗口"),
             ("input", "输出目录", "输出到"),
             ("done", "输出目录", "输出目录"),
             ("done", "用时", "用时")]
    for mode, label, needle in cases:
        rs = rows(mode)
        hit = [s for s, t in rs if needle in t]
        ok = bool(hit) and all(h != "class:dim" for h in hit)
        print("  %s %-12s 样式=%s" % ("OK  " if ok else "FAIL", label, hit))
        if not ok:
            fail.append("style-" + label)


def check_render(fail):
    print("")
    print("--- C. 实际渲染的 ANSI 颜色码（明暗两套）---")
    pat = r"\x1b\[0;38;2;(\d+);(\d+);(\d+)"
    for theme in ("dark", "light"):
        for m in [k for k in list(sys.modules)
                  if k.startswith("napa_pdf.tui")]:
            del sys.modules[m]
        os.environ["NAPAPDF_THEME"] = theme
        import napa_pdf.styles as S
        import napa_pdf.theme as TH
        import napa_pdf.tui as T
        app = T.NapaApp("")
        app._build()
        app.mode = "done"
        app.ok, app.failed, app.elapsed = 9, 1, 1.2
        app.summary = "成功 9"
        app.out_dir = "E:\\docs\\output"
        app.log = [("ok", "OK a.pdf"), ("err", "X b.pdf")]
        buf = io.StringIO()
        out = Vt100_Output(buf, lambda: Size(rows=40, columns=100))
        for s, t in app._body():
            print_formatted_text(output=out, style=S.build_style(),
                                 formatted_text=[(s, t)],
                                 color_depth=ColorDepth.DEPTH_24_BIT)
        out.flush()
        codes = set(re.findall(pat, buf.getvalue()))
        p = TH.palette()
        has_ok = any(abs(int(g) - int(p["ok"][3:5], 16)) < 14
                     for _, g, _ in codes)
        has_err = any(abs(int(r) - int(p["err"][1:3], 16)) < 14
                      for r, _, _ in codes)
        ok = len(codes) >= 3 and has_ok and has_err
        print("  %s %-6s 渲染出 %d 种前景色，成功/错误色均出现"
              % ("OK  " if ok else "FAIL", theme, len(codes)))
        if not ok:
            fail.append("render-" + theme)
    os.environ.pop("NAPAPDF_THEME", None)


def main():
    fail = []
    check_contrast(fail)
    check_theme_detect(fail)
    check_styles(fail)
    check_render(fail)
    print("")
    print("==== 失败 %d ====" % len(fail))
    for f in fail:
        print("  - " + f)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
