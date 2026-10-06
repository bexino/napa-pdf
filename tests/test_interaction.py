# -*- coding: utf-8 -*-
"""按键交互验收：像真人一样驱动 TUI。

重点验证两件事：
  1. 菜单页的数字键 / q / Esc 确实生效（曾经因为 eager=Never 被输入控件吞掉）
  2. 路径输入框里 q / r / 0 1 2 这些字符能正常输入（不能被快捷键抢走）
"""
import asyncio
import os
import sys
import threading
import time

from prompt_toolkit.application import Application
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.eventloop import run_in_executor_with_context
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.layout import HSplit, Layout
from prompt_toolkit.output import DummyOutput

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from napa_pdf.styles import build_style
from napa_pdf.i18n import EN, ZH
from napa_pdf.tui import NapaApp


class Session:
    """启动一个后台运行的 TUI，供测试注入按键。"""

    def __init__(self, initial="", lang=None):
        self.mgr = create_pipe_input()
        self.inp = self.mgr.__enter__()
        # lang=ZH 直接进主菜单（跳过语言页）；
        # lang=None 则从语言页开始，两种路径都覆盖到。
        self.app = NapaApp(initial, lang)
        self.app._build()
        self.real = Application(layout=Layout(self.app.container),
                                input=self.inp, output=DummyOutput(),
                                style=build_style(),
                                key_bindings=self.app.kb,
                                full_screen=False, refresh_interval=0.03)
        self.app.app = self.real
        self.app._rebuild()
        self.real.pre_run_callables.append(self.app._pump)

        async def m():
            await run_in_executor_with_context(self.real.run)

        self.thread = threading.Thread(
            target=lambda: asyncio.run(m()), daemon=True)
        self.thread.start()
        time.sleep(0.5)

    def send(self, text, delay=0.03):
        for ch in text:
            self.inp.send_text(ch)
            time.sleep(delay)
        time.sleep(0.35)

    def clear(self):
        while self.app.buf.text:
            self.inp.send_text("\x7f")
            time.sleep(0.02)
        time.sleep(0.2)

    def close(self):
        try:
            self.real.exit()
        except Exception:
            pass
        time.sleep(0.1)
        try:
            self.mgr.__exit__(None, None, None)
        except Exception:
            pass


def lang_cases(fail):
    print("--- A0. 语言选择页（启动首页）---")
    s = Session()                      # 不预置语言 -> 应停在语言页
    ok = s.app.mode == "lang"
    print("  %s 启动后 mode=%s（期望 lang）"
          % ("OK  " if ok else "FAIL", s.app.mode))
    if not ok:
        fail.append("lang-initial")
    s.send("2")
    ok = s.app.mode == "menu" and s.app.lang == EN
    print("  %s 按 2 选 English -> mode=%s lang=%s"
          % ("OK  " if ok else "FAIL", s.app.mode, s.app.lang))
    if not ok:
        fail.append("lang-pick-en")
    s.close()

    s = Session()
    s.send("\x1b[B")
    s.send("\r")
    ok = s.app.mode == "menu" and s.app.lang == EN
    print("  %s 下移键 + 回车选 English -> lang=%s"
          % ("OK  " if ok else "FAIL", s.app.lang))
    if not ok:
        fail.append("lang-arrow")
    s.close()

    s = Session()
    s.send("\x1b[B")
    s.send("\x1b[A")
    s.send("\r")
    ok = s.app.mode == "menu" and s.app.lang == ZH
    print("  %s 上下回到第一项确认 -> lang=%s"
          % ("OK  " if ok else "FAIL", s.app.lang))
    if not ok:
        fail.append("lang-back-to-zh")
    s.close()


def menu_cases(fail):
    print("--- A. 菜单页按键 ---")
    cases = [("1", "input", False, "进入输入页"),
             ("2", "params", False, "进入参数页"),
             ("0", None, True, "退出程序"),
             ("q", None, True, "退出程序")]
    for key, want_mode, want_exit, label in cases:
        s = Session(lang=ZH)
        s.send(key)
        exited = not s.real.is_running
        ok = exited if want_exit else ((not exited) and s.app.mode == want_mode)
        print("  %s 按 %-3r %-10s mode=%-7s exited=%s"
              % ("OK  " if ok else "FAIL", key, label, s.app.mode, exited))
        if not ok:
            fail.append("menu-" + key)
        s.close()


def nav_cases(fail):
    print("")
    print("--- B. 菜单上下选择 ---")
    s = Session(lang=ZH)
    start = s.app.selected
    s.inp.send_text("\x1b[B")
    time.sleep(0.35)
    after = s.app.selected
    s.inp.send_text("\x1b[A")
    time.sleep(0.35)
    back = s.app.selected
    ok = after != start and back == start
    print("  %s 选中项 %s -> 下 -> %s -> 上 -> %s"
          % ("OK  " if ok else "FAIL", start, after, back))
    if not ok:
        fail.append("nav")
    s.close()


def esc_cases(fail):
    print("")
    print("--- C. Esc 返回 ---")
    cases = [("2", "params", "参数页"), ("1", "input", "输入页")]
    for key, want_mode, label in cases:
        s = Session(lang=ZH)
        s.send(key)
        entered = s.app.mode == want_mode
        # 切换模式后按键分发要等布局重建完成，这里多等一拍
        time.sleep(0.4)
        for _ in range(3):
            s.inp.send_text("\x1b")
            time.sleep(0.25)
            if s.app.mode == "menu":
                break
        ok = entered and s.app.mode == "menu"
        print("  %s %s -> Esc -> 菜单页（进入=%s, 现在=%s）"
              % ("OK  " if ok else "FAIL", label, entered, s.app.mode))
        if not ok:
            fail.append("esc-" + label)
        s.close()


def typing_cases(fail):
    print("")
    print("--- D. 输入框内特殊字符（不能被快捷键抢走）---")
    cases = [("q", "q"),
             ("r", "r"),
             ("0", "0"),
             ("C:/2026/qr", "C:/2026/qr"),
             ("D:/目录/qr 报告", "D:/目录/qr 报告")]
    for typed, want in cases:
        s = Session(lang=ZH)
        s.send("1")
        s.clear()
        s.send(typed)
        got = s.app.buf.text
        ok = got == want and s.app.mode == "input"
        print("  %s 输入 %-18r -> %-18r mode=%s"
              % ("OK  " if ok else "FAIL", typed, got, s.app.mode))
        if not ok:
            fail.append("typing:" + typed)
        s.close()


def main():
    fail = []
    lang_cases(fail)
    menu_cases(fail)
    nav_cases(fail)
    esc_cases(fail)
    typing_cases(fail)
    print("")
    print("==== 失败 %d ====" % len(fail))
    for f in fail:
        print("  - " + f)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
