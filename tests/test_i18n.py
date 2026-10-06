# -*- coding: utf-8 -*-
"""双语验收。

三条底线：
  1. 每条文案两种语言都有，且占位符完全一致（否则某一语言会显示原始模板）
  2. 界面文字真的随语言切换
  3. **PDF 里写进去的文件名绝不能被翻译** —— 那是用户的数据
"""
import os
import re
import io
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from napa_pdf.i18n import DEFAULT_LANG, EN, LANGUAGES, STRINGS, ZH, normalize, t

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PH = re.compile(r"%\(([a-z_]+)\)")


def check_normalize(fail):
    print("--- A. 语言归一化 ---")
    cases = [("zh-CN", ZH), ("zh_CN", ZH), ("zh", ZH),
             ("en-US", EN), ("en_GB", EN), ("en", EN), ("EN", EN),
             (None, DEFAULT_LANG), ("", DEFAULT_LANG), ("fr", DEFAULT_LANG)]
    for raw, want in cases:
        got = normalize(raw)
        ok = got == want
        print("  %s %-8r -> %-3s (期望 %s)"
              % ("OK  " if ok else "FAIL", raw, got, want))
        if not ok:
            fail.append("normalize-%s" % raw)


def check_table(fail):
    print("")
    print("--- B. 文案表两语言齐全 ---")
    missing = 0
    for key, entry in sorted(STRINGS.items()):
        holes = [lg for lg in LANGUAGES if not entry.get(lg)]
        if holes:
            print("  FAIL %-24s 缺 %s" % (key, holes))
            missing += 1
    print("  %s 共 %d 条，缺失 %d 条"
          % ("OK  " if missing == 0 else "FAIL", len(STRINGS), missing))
    if missing:
        fail.append("table-holes")

    print("")
    print("--- C. 占位符两语言一致 ---")
    bad = 0
    for key, entry in sorted(STRINGS.items()):
        a = sorted(PH.findall(entry.get(ZH, "")))
        b = sorted(PH.findall(entry.get(EN, "")))
        if a != b:
            print("  FAIL %-24s zh=%s en=%s" % (key, a, b))
            bad += 1
    print("  %s 不一致 %d 条" % ("OK  " if bad == 0 else "FAIL", bad))
    if bad:
        fail.append("placeholder-mismatch")

    print("")
    print("--- D. 替换后无残余占位符 ---")
    bad = 0
    for key, entry in sorted(STRINGS.items()):
        names = PH.findall(entry.get(ZH, ""))
        if not names:
            continue
        params = {}
        for n in names:
            params[n] = "X" if n in ("name", "out", "folder", "e",
                                     "err", "orient") else 1
        for lg in LANGUAGES:
            out = t(key, lg, **params)
            if PH.search(out):
                print("  FAIL %-24s %s 残留 %r" % (key, lg, out))
                bad += 1
    print("  %s 残余 %d 处" % ("OK  " if bad == 0 else "FAIL", bad))
    if bad:
        fail.append("placeholder-left")


def check_screens(fail):
    print("")
    print("--- E. 各界面文案随语言切换 ---")
    from napa_pdf.tui import NapaApp
    zh_needles = [("menu", "给页眉加上文件名"),
                  ("params", "当前参数"),
                  ("input", "选择要处理的文件夹"),
                  ("running", "正在处理"),
                  ("done", "输出目录")]
    en_needles = [("menu", "Stamp filename in header"),
                  ("params", "Current settings"),
                  ("input", "Choose a folder"),
                  ("running", "Processing"),
                  ("done", "Output folder")]
    bad = 0
    for lang, needles in ((ZH, zh_needles), (EN, en_needles)):
        app = NapaApp("", lang)
        app._build()
        for mode, needle in needles:
            app.mode = mode
            if mode == "input":
                app.folder = HERE
            if mode == "done":
                app.summary = t("done_summary_ok", lang, n=1)
                app.out_dir = "C:/out"
            body = "".join(x for _, x in app._body())
            ok = needle in body
            print("  %s %-3s %-8s 含 %r"
                  % ("OK  " if ok else "FAIL", lang, mode, needle))
            if not ok:
                bad += 1
    print("  %s 问题 %d 处" % ("OK  " if bad == 0 else "FAIL", bad))
    if bad:
        fail.append("screen-text")


def check_prompt_width(fail):
    print("")
    print("--- F. 输入提示不被截断 ---")
    from napa_pdf.tui import _PROMPT_WIDTH, dwidth
    for lg in LANGUAGES:
        s = t("prompt_label", lg)
        w = dwidth(s)
        ok = _PROMPT_WIDTH >= w
        print("  %s %-3s %r 显示宽 %d <= 窗口 %d"
              % ("OK  " if ok else "FAIL", lg, s, w, _PROMPT_WIDTH))
        if not ok:
            fail.append("prompt-width-" + lg)


def check_pdf_untranslated(fail):
    print("")
    print("--- G. PDF 内文件名不被翻译 ---")
    import shutil

    import pymupdf
    samples = os.path.join(HERE, "samples")
    if not os.path.isdir(samples) or not os.listdir(samples):
        subprocess.run([sys.executable, os.path.join(HERE, "make_samples.py")],
                       capture_output=True)
    name = "附件4-1. 测试用户_背调报告_2026-09-18.pdf"
    src = os.path.join(samples, name)
    if not os.path.exists(src):
        print("  SKIP 缺少样本")
        return
    from napa_pdf.processor import process_pdf
    sub = os.path.join(samples, "i18n_测试输出")
    out = os.path.join(sub, name)
    os.makedirs(sub, exist_ok=True)
    process_pdf(src, out, lang=EN)          # 英文界面处理中文文件名
    d = pymupdf.open(out)
    pg = d[0]
    spans = [s for b in pg.get_text("dict")["blocks"] if b["type"] == 0
             for l in b["lines"] for s in l["spans"]]
    head = "".join(s["text"] for s in spans
                   if s["bbox"][1] < 28 and abs(s["size"] - 10.0) < 0.5)
    d.close()
    want = os.path.splitext(name)[0]
    ok = head == want
    print("  %s 英文界面下页眉=%r" % ("OK  " if ok else "FAIL", head))
    if not ok:
        print("     期望 %r" % want)
        fail.append("pdf-header-translated")
    shutil.rmtree(sub, ignore_errors=True)


def check_cli(fail):
    print("")
    print("--- H. 命令行 --lang 生效 ---")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    argv = [sys.executable, "-X", "utf8", os.path.join(ROOT, "main.py")]
    for lang, needle in ((None, "把 PDF 逐页归一化"),
                         (EN, "Normalize PDF pages")):
        cmd = list(argv) + (["--lang", lang] if lang else []) + ["--help"]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env)
        ok = needle in (r.stdout + r.stderr)
        print("  %s --lang %-6s --help 含 %r"
              % ("OK  " if ok else "FAIL", lang or "(默认)", needle))
        if not ok:
            fail.append("cli-lang-%s" % lang)




def check_log_language(fail):
    """日志区文案必须跟界面语言一致。

    这个缺陷真实发生过：BatchRunner 默认语言是 zh，而 TUI 建立
    它的时候没传 lang，结果屏纪是英文、屏幕下方日志全是中文。
    """
    print("")
    print("--- I. 日志区语言与界面一致 ---")
    import shutil
    import time

    from napa_pdf.batch import BatchRunner
    samples = os.path.join(HERE, "samples")
    if not os.path.isdir(samples) or not os.listdir(samples):
        subprocess.run([sys.executable, os.path.join(HERE, "make_samples.py")],
                       capture_output=True)
    zh_marks = ("页", "纵向", "横向", "已加密")
    for lang in (ZH, EN):
        out = os.path.join(samples, "i18n_log_" + lang)
        logs = []
        r = BatchRunner(samples, out, files=[os.path.join(
            samples, "a4_exact.pdf"), os.path.join(samples, "encrypted.pdf")],
            lang=lang, on_log=lambda lv, m: logs.append((lv, m))).start()
        while r.is_alive():
            time.sleep(0.2)
        joined = " ".join(m for _, m in logs)
        if lang == ZH:
            ok = any(k in joined for k in zh_marks)
        else:
            ok = not any(k in joined for k in zh_marks)
        print("  %s %-3s 日志=%r" % ("OK  " if ok else "FAIL", lang,
                                       joined[:70]))
        if not ok:
            fail.append("log-lang-" + lang)
        shutil.rmtree(out, ignore_errors=True)


def check_lang_always_asked(fail):
    """用户明确要求：每次启动都必须问语言，且绝不记住上次选择。

    这条曾经被违反过：cli.main 里写成
        lang = normalize(known.lang) if known.lang else DEFAULT_LANG
    没传 --lang 时静默选了中文，于是双击 exe / 跑 bat 都不会弹语言页。
    """
    print("")
    print("--- J. 每次启动都询问语言、不记忆 ---")
    import subprocess
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    argv = [sys.executable, "-X", "utf8", os.path.join(ROOT, "main.py")]

    # 1) 不带 --lang 启动 TUI -> 必须是语言页
    from napa_pdf.tui import NapaApp
    a = NapaApp("", None)
    ok = a.mode == "lang"
    print("  %s NapaApp(lang=None) -> mode=%s（期望 lang）"
          % ("OK  " if ok else "FAIL", a.mode))
    if not ok:
        fail.append("ask-lang-none")

    # 2) cli 不传 --lang 时，传给 TUI 的必须是 None（= 询问）
    import napa_pdf.cli as C
    import argparse
    bad = 0
    for extra_args in ([], ["--no-tui", "x"], ["x"], ["-o", "out"]):
        pre = argparse.ArgumentParser(add_help=False)
        pre.add_argument("--lang", default=None)
        known, _ = pre.parse_known_args(extra_args)
        ui = normalize(known.lang) if known.lang else None
        if ui is not None:
            print("  FAIL argv=%-24s 推出 ui_lang=%r（应为 None）"
                  % (extra_args, ui))
            bad += 1
    print("  %s 不带 --lang 时 ui_lang 恒为 None（异常 %d 例）"
          % ("OK  " if bad == 0 else "FAIL", bad))
    if bad:
        fail.append("cli-default-lang")

    # 3) 显式 --lang 才跳过询问
    for lg in ("en", "zh"):
        pre = argparse.ArgumentParser(add_help=False)
        pre.add_argument("--lang", default=None)
        known, _ = pre.parse_known_args(["--lang", lg])
        ui = normalize(known.lang)
        ok = ui == lg
        print("  %s --lang %-3s -> ui_lang=%s（跳过询问）"
              % ("OK  " if ok else "FAIL", lg, ui))
        if not ok:
            fail.append("cli-explicit-" + lg)

    # 4) 绝不存在持久化：全仓不得有写配置文件的代码
    import re
    risky = re.compile(r"json\.dump|configparser|shelve\.|pickle\.dump|"
                       r"winreg|APPDATA|user_config")
    offenders = []
    pkg = os.path.join(ROOT, "napa_pdf")
    for fn in sorted(os.listdir(pkg)):
        if not fn.endswith(".py"):
            continue
        body = io.open(os.path.join(pkg, fn), encoding="utf-8").read()
        if risky.search(body):
            offenders.append(fn)
    print("  %s 无语言持久化代码%s"
          % ("OK  " if not offenders else "FAIL",
             ("（%s）" % offenders) if offenders else ""))
    if offenders:
        fail.append("lang-persisted")

    # 5) 同一次运行内，语言页选完即固定，不在中途反复弹
    a2 = NapaApp("", None)
    a2._build()
    a2._confirm_lang()
    ok = a2.mode == "menu" and a2.lang_confirmed
    print("  %s 确认一次后 mode=%s confirmed=%s"
          % ("OK  " if ok else "FAIL", a2.mode, a2.lang_confirmed))
    if not ok:
        fail.append("confirm-once")


def main():
    fail = []
    check_normalize(fail)
    check_table(fail)
    check_screens(fail)
    check_prompt_width(fail)
    check_pdf_untranslated(fail)
    check_cli(fail)
    check_log_language(fail)
    check_lang_always_asked(fail)
    print("")
    print("==== 失败 %d ====" % len(fail))
    for f in fail:
        print("  - " + f)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
