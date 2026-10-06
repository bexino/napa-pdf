# -*- coding: utf-8 -*-
"""批量处理一个文件夹下的所有 PDF。"""
import os
import threading
import time

import pymupdf

from . import config
from .i18n import DEFAULT_LANG, t
from .processor import ProcessError, process_pdf, sanitize


def list_pdfs(folder: str) -> list:
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    out = []
    for n in names:
        if not n.lower().endswith(".pdf"):
            continue
        p = os.path.join(folder, n)
        if os.path.isfile(p):
            out.append(p)
    return sorted(out, key=lambda s: os.path.basename(s).lower())


def output_dir_for(folder: str, dirname: str = None) -> str:
    return os.path.join(folder, dirname or config.OUTPUT_DIRNAME)


def collect_pdf_pages(path: str) -> int:
    try:
        with pymupdf.open(path) as d:
            return d.page_count
    except Exception:
        return 0


class BatchRunner:
    """在后台线程里跑批处理，通过回调把进度推给 TUI。

    回调约定：
      on_log(level, text)              level: info / ok / warn / err
      on_file(index, total, name)      开始处理某个文件
      on_page(done, total)             单文件内页进度
      on_done(ok, failed, elapsed)     整批结束
    """

    def __init__(self, folder: str, output_dir: str, files: list = None,
                 recursive: bool = False, overwrite: bool = True,
                 lang: str = DEFAULT_LANG,
                 on_log=None, on_file=None, on_page=None, on_done=None):
        self.lang = lang
        self.folder = folder
        self.output_dir = output_dir
        self.files = list(files) if files is not None else list_pdfs(folder)
        self.recursive = recursive
        self.overwrite = overwrite
        self.on_log = on_log or (lambda *a: None)
        self.on_file = on_file or (lambda *a: None)
        self.on_page = on_page or (lambda *a: None)
        self.on_done = on_done or (lambda *a: None)
        self.cancel = threading.Event()
        self.thread = None
        self.ok = 0
        self.failed = 0
        self.skipped = 0
        self.t0 = 0.0
        self.current = None

    # -- 生命周期 ------------------------------------------------------
    def start(self):
        self.thread = threading.Thread(target=self._run, name="napa-batch", daemon=True)
        self.thread.start()
        return self

    def join(self, timeout=None):
        if self.thread:
            self.thread.join(timeout)

    def is_alive(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    def request_cancel(self):
        self.cancel.set()

    def _safe(self, fn, *a):
        """调用回调，吞掉回调自身的异常。

        回调通常是 print 或 UI 更新，遇到控制台编码问题（如 Windows GBK
        无法输出 ✓/✗）会抛 UnicodeEncodeError。日志失败绝不能中断批处理，
        否则表现为"只处理了第一个文件就停住"。
        """
        try:
            return fn(*a)
        except Exception:
            return None

    @property
    def total(self) -> int:
        return len(self.files)

    # -- 主循环 --------------------------------------------------------
    def _out_path(self, src: str) -> str:
        name = sanitize(os.path.basename(src))
        target = os.path.join(self.output_dir, name)
        if self.recursive:
            rel = os.path.relpath(src, self.folder)
            target = os.path.join(self.output_dir, sanitize(os.path.dirname(rel)),
                                  name)
        return target

    def _run(self):
        self.t0 = time.time()
        total = self.total
        if total == 0:
            self._safe(self.on_log, "warn",
                      t("batch_none", self.lang))
            self._safe(self.on_done, 0, 0, 0.0)
            return
        try:
            os.makedirs(self.output_dir, exist_ok=True)
        except OSError as e:
            self._safe(self.on_log, "err",
                      t("batch_no_outdir", self.lang, e=e))
            self._safe(self.on_done, 0, total, time.time() - self.t0)
            return

        for i, src in enumerate(self.files):
            if self.cancel.is_set():
                self._safe(self.on_log, "warn",
                          t("batch_cancelled", self.lang, left=total - i))
                break
            name = os.path.basename(src)
            out = self._out_path(src)
            if os.path.exists(out) and not self.overwrite:
                self.skipped += 1
                self._safe(self.on_log, "warn", t("batch_skip_exists", self.lang, name=name))
                self._safe(self.on_file, i + 1, total, name)
                continue
            self.current = name
            self._safe(self.on_file, i + 1, total, name)
            try:
                # progress 回调在 process_pdf 内部被逐页调用，必须同样包 _safe：
                # 否则它一抛异常就会被下面的 except Exception 捕获，把整个文件
                # 误判为"处理失败"。
                res = process_pdf(src, out, lang=self.lang,
                                  progress=lambda d, t: self._safe(
                                      self.on_page, d, t))
                self.ok += 1
                orient = ""
                if res["landscape"] or res["portrait"]:
                    orient = t("batch_orient", self.lang,
                                       p=res["portrait"], l=res["landscape"])
                self._safe(self.on_log, "ok", t("batch_ok", self.lang, name=name, pages=res["pages"],
                       orient=orient, mb=os.path.getsize(out) / 1048576))
            except ProcessError as e:
                self.failed += 1
                self._safe(self.on_log, "err", t("batch_err", self.lang, name=name, err=e))
            except Exception as e:                       # 兜底，别让整批崩掉
                self.failed += 1
                self._safe(self.on_log, "err", t("batch_unexpected", self.lang, name=name, err=e))
            finally:
                self.current = None
        elapsed = time.time() - self.t0
        self._safe(self.on_done, self.ok, self.failed, elapsed)
