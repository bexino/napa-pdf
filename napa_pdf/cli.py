# -*- coding: utf-8 -*-
"""命令行入口。"""
import argparse
import io
import sys

from .i18n import DEFAULT_LANG, normalize, t


def _force_utf8_stdio():
    """把标准输出/错误切到 UTF-8。

    打包成 exe 后没有 -X utf8，Windows 上 stdout 默认走 GBK，日志里的
    ✓ / ✗ / ─ 等字符会抛 UnicodeEncodeError，把批处理线程整个打挂（表现为
    只处理了第一个文件就停住）。这里统一兜住，源码运行时也无害。
    """
    for name in ("stdout", "stderr"):
        raw = getattr(sys, name, None)
        if raw is None:
            continue
        enc = (getattr(raw, "encoding", "") or "").lower()
        if "utf" in enc:
            continue
        buf = getattr(raw, "buffer", None)
        if buf is None:
            continue
        try:
            setattr(sys, name, io.TextIOWrapper(buf, encoding="utf-8",
                                                errors="replace",
                                                line_buffering=True))
        except Exception:
            pass


def main(argv=None) -> int:
    _force_utf8_stdio()
    # --lang 在解析前就要知道，否则 --help 的说明文案
    # 会跟不上界面语言（命令行模式不询问语言）。
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--lang", default=None)
    known, _ = pre.parse_known_args(argv)
    # 注意区分两个"默认"：
    #   - help_lang：只用于 --help 的文案；没给 --lang 时用中文兜底
    #   - ui_lang：传给 TUI 的值；**必须是 None**，表示"启动时询问用户"。
    #     曾经写成 lang = normalize(known.lang) if known.lang else DEFAULT_LANG，
    #     结果 bat / 双击 exe 都没传 --lang -> 悄悄选了中文 -> 跳过语言选择页。
    # 用户明确要求"每次进入都需要选择"，所以只有显式传 --lang 才跳过询问，
    # 而且不落盘、不记忆。
    help_lang = normalize(known.lang) if known.lang else DEFAULT_LANG

    p = argparse.ArgumentParser(
        prog=t("cli_prog", help_lang),
        description=t("cli_desc", help_lang))
    p.add_argument("folder", nargs="?", help=t("cli_folder_help", help_lang))
    p.add_argument("--no-tui", action="store_true", help=t("cli_no_tui", help_lang))
    p.add_argument("-o", "--output", default=None, help=t("cli_output", help_lang))
    p.add_argument("--lang", default=None, help=t("cli_lang", help_lang))
    p.add_argument("--version", action="store_true",
                   help=t("cli_version", help_lang))
    args = p.parse_args(argv)
    # 只有显式 --lang 才跳过语言选择；否则 None -> 询问。
    # 命令行模式（--no-tui）不询问，直接用 help_lang。
    ui_lang = normalize(args.lang) if args.lang else None

    if args.version:
        from . import __version__
        print(__version__)
        return 0

    if args.folder and args.no_tui:
        return _run_headless(args.folder, args.output,
                             ui_lang or help_lang)
    return _run_tui(args.folder or "", ui_lang)


def _run_headless(folder: str, out_name: str, lang: str = DEFAULT_LANG) -> int:
    import os
    import time

    from .batch import BatchRunner, list_pdfs, output_dir_for

    files = list_pdfs(folder)
    if not files:
        print(t("cli_no_pdf_out", lang, folder=folder), file=sys.stderr)
        return 1
    out_dir = output_dir_for(folder, out_name)
    runner = BatchRunner(folder, out_dir, files=files, lang=lang,
                         on_log=lambda lv, msg: print(msg, flush=True)).start()
    while runner.is_alive():
        time.sleep(0.2)
    print(t("cli_outdir", lang, out=out_dir))
    return 0 if runner.failed == 0 else 2


def _run_tui(initial_folder: str = "", lang: str = None) -> int:
    from .tui import run_tui
    # lang=None 表示"询问用户"：启动时先进语言选择页
    run_tui(initial_folder, lang)
    return 0
