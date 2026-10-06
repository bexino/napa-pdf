# -*- coding: utf-8 -*-
"""prompt_toolkit 实现的 TUI：主菜单 -> 文件夹输入 -> 运行进度。"""
import asyncio
import os
import queue
import time
import unicodedata
from datetime import datetime

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (ConditionalContainer, HSplit, Layout,
                                   VSplit, Window)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl

from . import __version__, config
from .batch import BatchRunner, list_pdfs, output_dir_for
from .i18n import EN, ZH, normalize, t
from .theme import palette

_PAL = palette()
C_ACCENT = _PAL["accent"]
C_OK = _PAL["ok"]
C_WARN = _PAL["warn"]
C_ERR = _PAL["err"]
C_DIM = _PAL["dim"]
C_TEXT = _PAL["text"]

MM = 2.834645669          # pt per mm


def _menu_items(lang):
    """主菜单项。返回 (key, title_key, desc_key)。"""
    return [
        ("1", "menu_1_title", "menu_1_desc"),
        ("2", "menu_2_title", "menu_2_desc"),
        ("0", "menu_0_title", None),
    ]


LANG_ITEMS = [("1", ZH), ("2", EN)]


def _bar(done, total, width=24):
    if total <= 0:
        return "[" + " " * width + "]"
    filled = int(round(min(1.0, done / float(total)) * width))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def clean_path(raw):
    """清洗从资源管理器拖进来 / 带引号粘贴的路径。"""
    s = (raw or "").strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1]
    s = s.strip()
    if len(s) > 3 and s.endswith("\\") and not s.endswith(":\\"):
        s = s[:-1]
    return os.path.expandvars(os.path.expanduser(s))


def dwidth(s):
    """终端显示宽度：CJK / 全角字符占 2 列。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _prompt_text(lang):
    return t("prompt_label", lang)


# 输入提示的标签窗口宽度在 __init__ 时就固定了，而语言可以在语言选择页切换。
# 取两种语言里更宽的那个，保证切换后提示不会被截断（之前按中文的字数算宽度，
# 结果 "文件夹路径 > " 被截成 "文件夹路"）。
_PROMPT_WIDTH = max(dwidth(_prompt_text(ZH)), dwidth(_prompt_text(EN))) + 1


class NapaApp:
    def __init__(self, initial_folder: str = "", lang: str = None):
        self.app = None
        # 语言选择页也要显示文案，而它本身不能用当前语言决定内容，
        # 所以语言页固定用中英对照标题。
        self.lang = normalize(lang) if lang else ZH
        # 调用方显式给了语言就跳过询问页（命令行 --lang / 测试用）；
        # 没给才从语言选择页开始。
        self.lang_confirmed = lang is not None
        self.mode = "menu" if self.lang_confirmed else "lang"
        self.status = ""
        self.status_kind = "dim"
        self.selected = "1"
        self.lang_selected = "1"
        self.log = []
        self.runner = None
        self.events = queue.Queue()
        self.folder = ""
        self.out_dir = ""
        self.preview = []
        self.n_files = 0
        self.ok = 0
        self.failed = 0
        self.cur = ""
        self.page_done = 0
        self.page_total = 0
        self.summary = ""
        self.cancelled = False
        self.t0 = None
        self.elapsed = 0.0
        self.hist = []
        self.hist_idx = -1
        self.initial_folder = initial_folder
        # 自己管 Buffer：TextArea 不能被塞进第二个容器（无 reset() 方法），
        # 而模式切换时布局会整体重建，必须用一个可重复挂载的 BufferControl。
        self.buf = Buffer(multiline=False)
        self.buf.on_text_changed += self._on_edit
        self.win_prompt_label = Window(
            FormattedTextControl(
                lambda: [("class:accent", _prompt_text(self.lang))]),
            width=_PROMPT_WIDTH,
        )
        self.win_prompt_input = Window(
            BufferControl(buffer=self.buf), wrap_lines=False)
        self.prompt_win = VSplit(
            [self.win_prompt_label, self.win_prompt_input],
            height=1,
        )
        self.kb = KeyBindings()
        self._bind()

    # ============ 事件：后台线程 -> UI 线程 ============
    def _pump(self):
        """消费后台线程投递的事件，更新界面状态。返回是否有变化。"""
        dirty = False
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            dirty = True
            getattr(self, "_ev_" + kind)(payload)
        if dirty and self.app:
            self.app.invalidate()
        return dirty

    async def _pump_loop(self):
        """持续轮询事件队列。

        之前只把 _pump 挂在 pre_run_callables 上，那只在启动时执行一次；批处理
        线程完成后的事件全堆在队列里没人取，于是界面一直停在"正在处理"。
        refresh_interval 只负责重绘，不会重新调用 pre_run，所以必须在事件循环里
        常驻一个轮询任务。
        """
        while True:
            try:
                self._pump()
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                raise
            except Exception:
                # 轮询循环绝不能因单个事件异常而死掉，否则界面永远卡住
                await asyncio.sleep(0.2)

    def _ev_log(self, payload):
        level, text = payload
        self.log.append((level, text))
        if len(self.log) > 300:
            del self.log[:len(self.log) - 300]
        self.status = text
        self.status_kind = {"ok": C_OK, "err": C_ERR, "warn": C_WARN}.get(level, C_ACCENT)

    def _ev_file(self, payload):
        idx, total, name = payload
        self.n_files = total
        self.cur = name
        self.page_done = 0
        self.page_total = 0
        self.status = "[%d/%d] %s" % (idx, total, name)
        self.status_kind = C_ACCENT

    def _ev_page(self, payload):
        self.page_done, self.page_total = payload

    def _ev_done(self, payload):
        ok, failed, elapsed = payload
        self.ok, self.failed, self.elapsed = ok, failed, elapsed
        lg = self.lang
        cancelled = bool(self.runner and self.runner.cancel.is_set())
        bits = [t("done_summary_ok", lg, n=ok)]
        if failed:
            bits.append(t("done_summary_fail", lg, n=failed))
        if self.runner and self.runner.skipped:
            bits.append(t("done_summary_skip", lg, n=self.runner.skipped))
        if cancelled:
            left = self.n_files - (ok + failed + (self.runner.skipped or 0))
            bits.append(t("done_summary_left", lg, n=max(0, left)))
        self.summary = "   ·   ".join(bits)
        self.cancelled = cancelled
        prefix = t("done_cancelled", lg) if cancelled else t("done_finished", lg)
        self.status = prefix + self.summary
        self.status_kind = C_WARN if (failed or cancelled) else C_OK
        self.mode = "done"
        self._rebuild()

    # ============ 按键 ============
    def _bind(self):
        kb = self.kb
        keys = [m[0] for m in _menu_items(self.lang)]
        lang_keys = [k for k, _ in LANG_ITEMS]

        def not_input():
            """路径输入时不要抢 q / r / 0 1 2，否则路径里这些字符输不进去。"""
            return self.mode not in ("input",)

        no_input = Condition(not_input)

        @kb.add("up", eager=True)
        def _(e):
            if self.mode == "menu":
                self.selected = keys[(keys.index(self.selected) - 1) % len(keys)]
                self._repaint()
            elif self.mode == "input":
                self._hist_move(-1)
            elif self.mode == "lang":
                self.lang_selected = lang_keys[
                    (lang_keys.index(self.lang_selected) - 1) % len(lang_keys)]
                self._repaint()

        @kb.add("down", eager=True)
        def _(e):
            if self.mode == "menu":
                self.selected = keys[(keys.index(self.selected) + 1) % len(keys)]
                self._repaint()
            elif self.mode == "input":
                self._hist_move(1)
            elif self.mode == "lang":
                self.lang_selected = lang_keys[
                    (lang_keys.index(self.lang_selected) + 1) % len(lang_keys)]
                self._repaint()

        @kb.add("c-c", eager=True)
        def _(e):
            self._quit()

        @kb.add("q", eager=True, filter=no_input)
        def _(e):
            if self.mode in ("lang", "menu", "done"):
                self._quit()

        # Esc 统一返回上一层。本程序没有任何搜索功能，所以不需要把 Esc 让给
        # 内置的"确认搜索"绑定——那条 eager escape 在输入框聚焦时同样生效，
        # 会把 Esc 吃掉导致回不了菜单。editing_mode 设成 VI 后它就不参与匹配，
        # Esc 由我们独占。
        @kb.add("escape", eager=True)
        def _(e):
            if self.mode in ("input", "done", "params"):
                self._back()
            elif self.mode == "lang":
                # 语言页按 Esc 直接用当前选中项，不退出——启动时必须能进主菜单
                self._confirm_lang()

        @kb.add("enter", eager=True)
        def _(e):
            self._enter()

        @kb.add("r", eager=True, filter=no_input)
        def _(e):
            if self.mode == "done":
                self._goto_input()

        for ch in "012":
            @kb.add(ch, eager=True, filter=no_input)
            def _(e, ch=ch):
                if self.mode == "lang" and ch in lang_keys:
                    self.lang_selected = ch
                    self._confirm_lang()
                elif self.mode == "menu" and ch in keys:
                    self.selected = ch
                    self._activate(ch)

    def _repaint(self):
        if self.app:
            self.app.invalidate()

    def _quit(self):
        if self.runner and self.runner.is_alive():
            self.runner.request_cancel()
        if self.app:
            self.app.exit()

    def _back(self):
        self.runner = None
        self.mode = "menu"
        self.status = ""
        self._rebuild()

    def _confirm_lang(self):
        """语言选择页确认：切到选中语言，进入主菜单。"""
        lang = dict(LANG_ITEMS).get(self.lang_selected, ZH)
        if self.lang != lang:
            self.lang = lang
        # 标记为已确认：同一进程内不再回到语言页。
        # 注意这只存在于内存，绝不落盘——每次启动都会重新询问。
        self.lang_confirmed = True
        self.mode = "menu"
        self.status = ""
        self.status_kind = "dim"
        # 菜单项按键要按新语言重算（键位集合一致，但保持实现自洽）
        self._rebuild()

    def _activate(self, choice):
        if choice == "1":
            self._goto_input()
        elif choice == "2":
            self.mode = "params"
            self._rebuild()
        elif choice == "0":
            self._quit()

    def _enter(self):
        if self.mode == "lang":
            self._confirm_lang()
        elif self.mode == "menu":
            self._activate(self.selected)
        elif self.mode == "input":
            self._start()
        else:
            self._back()

    def _hist_move(self, delta):
        if not self.hist:
            return
        self.hist_idx = max(-1, min(len(self.hist) - 1, self.hist_idx + delta))
        val = "" if self.hist_idx < 0 else self.hist[self.hist_idx]
        self.buf.document = self.buf.document.__class__(val, 0)

    # ============ 流程 ============
    def _goto_input(self):
        self.mode = "input"
        self.status = ""
        self.hist_idx = -1
        self.buf.document = self.buf.document.__class__(
            self.folder or self.initial_folder, 0)
        if self.initial_folder:
            self.folder = ""
        self._rebuild()
        self._preview()

    def _preview(self):
        self.folder = clean_path(self.buf.text)
        if os.path.isdir(self.folder):
            files = list_pdfs(self.folder)
            self.n_files = len(files)
            self.preview = [os.path.basename(p) for p in files[:5]]
            self.out_dir = output_dir_for(self.folder)
        else:
            self.n_files = 0
            self.preview = []
            self.out_dir = ""

    def _on_edit(self, _buf):
        self._preview()
        self._repaint()

    def _start(self):
        self._preview()
        lg = self.lang
        if not os.path.isdir(self.folder):
            self.status = t("err_not_a_folder", lg)
            self.status_kind = C_ERR
            return
        files = list_pdfs(self.folder)
        if not files:
            self.status = t("err_no_pdf", lg)
            self.status_kind = C_WARN
            return
        self.out_dir = output_dir_for(self.folder)
        self.log = []
        self.ok = 0
        self.failed = 0
        self.t0 = time.time()
        self.mode = "running"
        self.n_files = len(files)
        self.status = t("run_starting", lg, n=len(files))
        self.status_kind = C_ACCENT
        if self.folder not in self.hist:
            self.hist.insert(0, self.folder)

        def put(kind, payload):
            self.events.put((kind, payload))

        self.runner = BatchRunner(
            self.folder, self.out_dir, files=files,
            lang=self.lang,
            on_log=lambda lv, t: put("log", (lv, t)),
            on_file=lambda i, t, n: put("file", (i, t, n)),
            on_page=lambda d, t: put("page", (d, t)),
            on_done=lambda o, f, e: put("done", (o, f, e)),
        ).start()
        self._rebuild()

    # ============ 渲染 ============
    def _header(self):
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        return [("class:accent", " napa-pdf "),
                ("class:text", "v%s    %s\n" % (__version__, stamp)),
                ("class:rule", "─" * 64 + "\n")]

    def _lang(self):
        """语言选择页。标题永远中英对照，用户不懂英文也能看懂。"""
        out = [("", "\n")]
        out.append(("class:hl", t("lang_title", ZH)))
        out.append(("", "\n\n"))
        for key, code in LANG_ITEMS:
            on = self.lang_selected == key
            label = "lang_option_zh" if code == ZH else "lang_option_en"
            out.append(("class:accent", "  ▸ " if on else "    "))
            out.append(("class:dim", "["))
            out.append(("class:hl" if on else "class:accent", key))
            out.append(("class:dim", "] "))
            out.append(("class:hl" if on else "class:text", t(label, ZH)))
            out.append(("", "\n"))
        out.append(("", "\n"))
        out.append(("class:dim", t("lang_hint", ZH)))
        return out

    def _menu(self):
        out = [("", "\n")]
        out.append(("class:text", t("menu_subtitle", self.lang)))
        for key, title_key, desc_key in _menu_items(self.lang):
            on = self.selected == key
            out.append(("class:accent", "  ▸ " if on else "    "))
            out.append(("class:dim", "["))
            out.append(("class:hl" if on else "class:accent", key))
            out.append(("class:dim", "] "))
            out.append(("class:hl" if on else "class:text",
                        t(title_key, self.lang)))
            if desc_key:
                out.append(("class:text", "    " + t(desc_key, self.lang)))
            out.append(("", "\n"))
        out.append(("", "\n"))
        out.append(("class:dim", t("menu_hint", self.lang)))
        return out

    def _params(self):
        builtin = t("builtin_font", self.lang)
        latin = builtin + config.BUILTIN_LATIN
        cjk = builtin + config.BUILTIN_CJK
        try:
            from .fonts import get_fonts
            f = get_fonts()
            latin = os.path.basename(f.latin_path) if f.latin_path else latin
            cjk = os.path.basename(f.cjk_path) if f.cjk_path else cjk
        except Exception:
            pass
        rows = [
            (t("params_strip", self.lang),
             t("params_mm", self.lang) % (config.HEADER_STRIP,
                                          config.HEADER_STRIP / MM)),
            (t("params_left", self.lang),
             t("params_mm", self.lang) % (config.HEADER_LEFT,
                                          config.HEADER_LEFT / MM)),
            (t("params_base", self.lang),
             "%.1f pt %s" % (config.HEADER_BASE_Y,
                              t("params_in_band", self.lang))),
            (t("params_size", self.lang), "%.1f pt" % config.LABEL_SIZE),
            (t("params_canvas", self.lang),
             t("params_canvas_val", self.lang)),
            (t("params_latin", self.lang), latin),
            (t("params_cjk", self.lang), cjk),
            (t("params_outdir", self.lang),
             t("params_outdir_val", self.lang)),
            (t("params_override", self.lang),
             t("params_override_val", self.lang)),
        ]
        out = [("", "\n"), ("class:hl", t("params_title", self.lang)),
               ("", "\n\n")]
        # 中英标签长度不同，用显示列宽对齐，不能用 %-9s
        pad = max(dwidth(k) for k, _ in rows) + 2
        for k, v in rows:
            out.append(("class:text", "  " + k + " " * (pad - dwidth(k))))
            if v:
                out.append(("class:accent", v))
            out.append(("", "\n"))
        out.append(("", "\n"))
        out.append(("class:dim", t("params_back", self.lang)))
        return out

    def _input(self):
        out = [("", "\n")]
        out.append(("class:hl", t("input_title", self.lang)))
        out.append(("class:text", t("input_hint_drag", self.lang)))
        out.append(("", "\n\n"))
        if os.path.isdir(self.folder):
            out.append(("class:text", t("input_found", self.lang)))
            out.append((C_OK if self.n_files else C_WARN,
                        t("input_count_pdf", self.lang, n=self.n_files)))
            out.append(("", "\n"))
            if self.preview:
                more = "  ..." if self.n_files > len(self.preview) else ""
                out.append(("class:text", "  " + "  .  ".join(self.preview) + more))
                out.append(("", "\n"))
            out.append(("class:text",
                        t("input_output_to", self.lang) + self.out_dir))
            out.append(("", "\n\n"))
        elif self.folder:
            out.append(("class:err",
                        t("input_bad_path", self.lang) + self.folder))
            out.append(("", "\n\n"))
        else:
            out.append(("class:dim", t("input_example", self.lang)))
            out.append(("", "\n\n"))
        out.append(("class:dim", t("input_hint", self.lang)))
        return out

    def _running(self):
        done = self.ok + self.failed
        lg = self.lang
        out = [("", "\n"), ("class:hl", t("run_title", lg)), ("", "\n\n")]
        out.append(("class:text", "  "))
        out.append(("class:accent", _bar(done, self.n_files)))
        out.append(("class:text", "    " + t("run_files", lg,
                                              done=done, total=self.n_files)))
        out.append(("", "\n"))
        if self.page_total:
            out.append(("class:text", "  "))
            out.append(("class:accent", _bar(self.page_done, self.page_total, 16)))
            out.append(("class:text", t("run_page", lg,
                                          done=self.page_done,
                                          total=self.page_total)))
            out.append(("", "\n"))
        out.append(("class:text", "  " + (self.cur or t("run_preparing", lg))))
        out.append(("", "\n"))
        if self.t0:
            el = time.time() - self.t0
            tail = ""
            if done and done < self.n_files:
                tail = t("run_eta", lg,
                         sec=(el / done) * (self.n_files - done))
            out.append(("class:text",
                        t("run_elapsed", lg, sec=el) + tail))
            out.append(("", "\n"))
        out.append(("", "\n"))
        out.append(("class:warn", t("run_cancel_hint", lg)))
        out.append(("", "\n"))
        return out

    def _done(self):
        lg = self.lang
        bad = bool(self.failed) or self.cancelled
        out = [("", "\n")]
        out.append((C_WARN if bad else C_OK, "  ! " if bad else "  + "))
        out.append(("class:hl", self.summary or t("done_fallback", lg)))
        out.append(("", "\n\n"))
        out.append(("class:text", t("done_outdir", lg)))
        out.append(("class:accent", self.out_dir))
        out.append(("", "\n"))
        out.append(("class:text", t("done_took", lg, sec=self.elapsed)))
        out.append(("", "\n\n"))
        if self.cancelled:
            out.append((C_WARN, t("done_cancelled_note", lg)))
            out.append(("", "\n"))
        if self.ok:
            out.append((C_OK, t("done_ok_count", lg, n=self.ok)))
            out.append(("", "\n"))
        if self.failed:
            out.append((C_ERR, t("done_fail_count", lg, n=self.failed)))
            out.append(("", "\n"))
        out.append(("", "\n"))
        out.append(("class:dim", t("done_hint", lg)))
        return out

    def _loglines(self, limit):
        style = {"ok": C_OK, "err": C_ERR, "warn": C_WARN, "info": "class:text"}
        out = [("class:dim", t("log_title", self.lang) + "─" * 54 + "\n")]
        for lv, msg in self.log[-limit:]:
            out.append((style.get(lv, "class:text"), "  " + msg))
            out.append(("", "\n"))
        return out

    def _body(self):
        if self.mode == "lang":
            return self._lang()
        if self.mode == "menu":
            return self._menu()
        if self.mode == "params":
            return self._params()
        if self.mode == "input":
            return self._input()
        if self.mode == "running":
            return self._running()
        return self._done()

    # ============ 布局 ============
    def _build(self):
        """一次性建好所有窗口，之后只切换显示/隐藏，不再重建。

        之前每次切模式都 new 一批 Window 挂到 HSplit 上，导致 Layout 的焦点栈
        里残留已脱离容器的旧窗口，按键会被送到那个没人管的窗口——表现就是
        Esc 之类的绑定时灵时不灵。窗口对象终身不变就不会有这个问题。
        """
        self.show_prompt = Condition(lambda: self.mode == "input")
        self.show_log = Condition(lambda: self.mode in ("running", "done"))
        self.win_header = Window(
            FormattedTextControl(lambda: self._header()), height=3)
        self.win_body = Window(
            FormattedTextControl(self._body, key_bindings=self.kb),
            always_hide_cursor=True)
        self.win_prompt = ConditionalContainer(self.prompt_win,
                                               filter=self.show_prompt)
        self.win_log = Window(
            FormattedTextControl(lambda: self._loglines(8)), height=10)
        self.win_status = Window(FormattedTextControl(self._statusline), height=1)
        self.container = HSplit([
            self.win_header,
            self.win_body,
            self.win_prompt,
            ConditionalContainer(self.win_log, filter=self.show_log),
            self.win_status,
        ])

    def _parts(self):
        return [self.win_header, self.win_body,
                self.win_prompt, self.win_log, self.win_status]

    def _rebuild(self):
        if not self.app:
            return
        self.app.layout.container = self.container
        # 焦点必须跟着模式走。win_prompt 被 ConditionalContainer 隐藏后，
        # Layout 的焦点栈仍然指向它（内部是 BufferControl），按键会送到一个
        # 看不见的输入框上——表现就是 Esc 之类的全局快捷键时灵时不灵。
        want = self.win_prompt_input if self.mode == "input" else self.win_body
        if self.app.layout.current_window is not want:
            self.app.layout.focus(want)
        self.app.invalidate()

    def _statusline(self):
        text = ("  " + self.status) if self.status else ""
        return [("class:" + self.status_kind, text)]

    def run(self, style=None):
        self._build()
        self.app = Application(
            layout=Layout(self.container,
                          focused_element=self.win_body),
            full_screen=False,
            key_bindings=self.kb,
            mouse_support=False,
            refresh_interval=0.15,
            style=style,
        )
        self._rebuild()
        self.app.pre_run_callables.append(
            lambda: self.app.create_background_task(self._pump_loop()))
        self.app.run()


def run_tui(initial_folder: str = "", lang: str = None):
    from .styles import build_style
    NapaApp(initial_folder, lang).run(style=build_style())
