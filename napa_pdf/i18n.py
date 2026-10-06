# -*- coding: utf-8 -*-
"""界面文案与错误信息的双语文案库。

只翻译**界面与日志**，绝不翻译写进 PDF 的内容——页眉上的文件名是用户的数据，
必须原样保留。

用法：
    from .i18n import t
    t("menu_1_title", lang)
    t("run_files", lang, done=3, total=9)

占位符一律用**命名**写法（``%(n)s``），配合 ``**kw`` 展开。
不要写成 ``t("x", lang, n) % n`` 这种位置式——两种语言的分词顺序不同，
位置式要求两种语言的占位符顺序完全一致，很容易出错。
"""

ZH = "zh"
EN = "en"
LANGUAGES = (ZH, EN)
DEFAULT_LANG = ZH


def normalize(lang: str) -> str:
    """把 'zh-CN' / 'en_US' 之类归一到 'zh' / 'en'。"""
    if not lang:
        return DEFAULT_LANG
    s = str(lang).strip().lower().replace("_", "-")
    if s.startswith("zh") or s in ("cn", "chs", "chinese"):
        return ZH
    if s.startswith("en"):
        return EN
    return DEFAULT_LANG


STRINGS = {
    # ================= 语言选择 =================
    # 语言页固定中英对照：用户不懂英文也能找到自己的语言
    "lang_title": {
        ZH: "选择界面语言 / Choose interface language",
        EN: "选择界面语言 / Choose interface language",
    },
    "lang_hint": {
        ZH: "  ↑↓ 选择     数字键 1 / 2 直选     回车 确认     q 退出\n",
        EN: "  ↑↓ select     keys 1 / 2     Enter to confirm     q to quit\n",
    },
    "lang_option_zh": {ZH: "简体中文", EN: "简体中文"},
    "lang_option_en": {ZH: "English", EN: "English"},

    # ================= 主菜单 =================
    "menu_subtitle": {
        ZH: "  批量把 PDF 归一化为 A4，并在每页页眉标注文件名\n\n",
        EN: "  Normalize every PDF page to A4 and stamp the filename in the header\n\n",
    },
    "menu_1_title": {ZH: "给页眉加上文件名", EN: "Stamp filename in header"},
    "menu_1_desc": {
        ZH: "批量归一化 A4 + 每页页眉标注文件名",
        EN: "Batch A4 normalization + per-page header stamp",
    },
    "menu_2_title": {ZH: "查看当前参数", EN: "Show current settings"},
    "menu_2_desc": {ZH: "字号、页眉带、字体", EN: "Font size, header band, fonts"},
    "menu_0_title": {ZH: "退出", EN: "Quit"},
    "menu_hint": {
        ZH: "  ↑↓ 选择     数字键直达     回车 进入     Ctrl+C 退出\n",
        EN: "  ↑↓ select     number keys     Enter to open     Ctrl+C to quit\n",
    },

    # ================= 参数页 =================
    "params_title": {ZH: "  当前参数", EN: "  Current settings"},
    "params_strip": {ZH: "页眉带高", EN: "Header band"},
    "params_left": {ZH: "左内边距", EN: "Left margin"},
    "params_base": {ZH: "标签基线", EN: "Label baseline"},
    "params_size": {ZH: "字号", EN: "Font size"},
    "params_canvas": {
        ZH: "A4 画布",
        EN: "A4 canvas",
    },
    "params_canvas_val": {
        ZH: "210 × 297 mm，横向页自动改用 297 × 210",
        EN: "210 x 297 mm; landscape pages use 297 x 210",
    },
    "params_latin": {ZH: "西文字体", EN: "Latin font"},
    "params_cjk": {ZH: "中文字体", EN: "CJK font"},
    "params_outdir": {ZH: "输出目录", EN: "Output folder"},
    "params_outdir_val": {
        ZH: "源文件夹下的 output/",
        EN: "output/ inside the source folder",
    },
    "params_override": {
        ZH: "可覆盖项",
        EN: "Overrides",
    },
    "params_override_val": {
        ZH: "环境变量 NAPAPDF_SIZE / NAPAPDF_STRIP",
        EN: "env NAPAPDF_SIZE / NAPAPDF_STRIP",
    },
    "params_back": {ZH: "  Esc / 回车 返回\n", EN: "  Esc / Enter to go back\n"},
    "builtin_font": {ZH: "内置 ", EN: "built-in "},
    "params_in_band": {ZH: "（在页眉带内）", EN: "(inside the band)"},
    "params_mm": {ZH: "%.1f pt  ~ %.1f mm", EN: "%.1f pt  ~ %.1f mm"},

    # ================= 路径输入页 =================
    "prompt_label": {ZH: "  文件夹路径 > ", EN: "  Folder > "},
    "input_title": {ZH: "  选择要处理的文件夹", EN: "  Choose a folder to process"},
    "input_hint_drag": {
        ZH: "    可把文件夹从资源管理器直接拖进本窗口",
        EN: "    You can drag a folder from Explorer straight into this window",
    },
    "input_found": {ZH: "  找到 ", EN: "  Found "},
    "input_count_pdf": {ZH: "%(n)d 个 PDF", EN: "%(n)d PDF file(s)"},
    "input_output_to": {ZH: "  输出到   ", EN: "  Output to   "},
    "input_bad_path": {ZH: "  路径不存在：", EN: "  Path does not exist: "},
    "input_example": {
        ZH: "  例如   E:\\Personal\\Desktop\\Index",
        EN: "  e.g.   E:\\Personal\\Desktop\\Index",
    },
    "input_hint": {
        ZH: "  ↑↓ 切换历史路径     回车 开始     Esc 返回\n",
        EN: "  ↑↓ history     Enter to start     Esc to go back\n",
    },
    "run_preparing": {ZH: "准备中", EN: "preparing"},
    "err_not_a_folder": {
        ZH: "路径不存在或不是文件夹",
        EN: "Path does not exist or is not a folder",
    },
    "err_no_pdf": {ZH: "该文件夹下没有 PDF 文件", EN: "No PDF files in that folder"},

    # ================= 运行页 =================
    "run_title": {ZH: "  正在处理", EN: "  Processing"},
    "run_files": {ZH: "%(done)d / %(total)d 个文件", EN: "%(done)d / %(total)d file(s)"},
    "run_page": {ZH: "    当前 %(done)d / %(total)d 页", EN: "    page %(done)d / %(total)d"},
    "run_elapsed": {ZH: "  已用 %(sec).1f 秒", EN: "  Elapsed %(sec).1fs"},
    "run_eta": {ZH: "    预计剩余 %(sec).0f 秒", EN: "    about %(sec).0fs left"},
    "run_cancel_hint": {ZH: "  Ctrl+C 可随时取消", EN: "  Ctrl+C to cancel"},
    "run_starting": {ZH: "正在处理 %(n)d 个文件…", EN: "Processing %(n)d file(s)..."},

    # ================= 完成页 =================
    "done_finished": {ZH: "处理完成   ", EN: "Done   "},
    "done_cancelled": {ZH: "已取消   ", EN: "Cancelled   "},
    "done_summary_ok": {ZH: "成功 %(n)d", EN: "succeeded %(n)d"},
    "done_summary_fail": {ZH: "失败 %(n)d", EN: "failed %(n)d"},
    "done_summary_skip": {ZH: "跳过 %(n)d", EN: "skipped %(n)d"},
    "done_summary_left": {
        ZH: "已取消，未处理 %(n)d",
        EN: "cancelled, %(n)d not processed",
    },
    "done_outdir": {ZH: "  输出目录   ", EN: "  Output folder   "},
    "done_took": {ZH: "  用时 %(sec).1f 秒", EN: "  Took %(sec).1fs"},
    "done_cancelled_note": {
        ZH: "  已中途取消，部分文件未处理",
        EN: "  Cancelled partway; some files were not processed",
    },
    "done_ok_count": {ZH: "  成功 %(n)d 个", EN: "  %(n)d succeeded"},
    "done_fail_count": {
        ZH: "  失败 %(n)d 个，详见下方日志",
        EN: "  %(n)d failed - see the log below",
    },
    "done_hint": {
        ZH: "  r  再处理一次     回车 / Esc 返回     q 退出\n",
        EN: "  r  run again     Enter / Esc to go back     q to quit\n",
    },
    "done_fallback": {ZH: "完成", EN: "Done"},
    "log_title": {ZH: "  ── 日志 ", EN: "  -- Log "},

    # ================= 批处理日志 =================
    "batch_none": {
        ZH: "该文件夹下没有找到 PDF 文件",
        EN: "No PDF files found in that folder",
    },
    "batch_no_outdir": {
        ZH: "无法创建输出目录：%(e)s",
        EN: "Cannot create output folder: %(e)s",
    },
    "batch_cancelled": {
        ZH: "已取消，剩余 %(left)d 个文件未处理",
        EN: "Cancelled, %(left)d file(s) not processed",
    },
    "batch_skip_exists": {
        ZH: "跳过已存在：%(name)s",
        EN: "Skipped (already exists): %(name)s",
    },
    "batch_orient": {
        ZH: " 纵向 %(p)d / 横向 %(l)d 页",
        EN: " %(p)d portrait / %(l)d landscape",
    },
    "batch_ok": {
        ZH: "✓ %(name)s  %(pages)d 页%(orient)s  %(mb).2f MB",
        EN: "OK %(name)s  %(pages)d page(s)%(orient)s  %(mb).2f MB",
    },
    "batch_err": {ZH: "✗ %(name)s  %(err)s", EN: "FAIL %(name)s  %(err)s"},
    "batch_unexpected": {
        ZH: "✗ %(name)s  未预期错误：%(err)s",
        EN: "FAIL %(name)s  unexpected error: %(err)s",
    },

    # ================= 处理错误 =================
    "err_bad_page_size": {ZH: "页面尺寸非法", EN: "Invalid page dimensions"},
    "err_cannot_open": {ZH: "无法打开：%(e)s", EN: "Cannot open: %(e)s"},
    "err_encrypted": {
        ZH: "PDF 已加密，需要密码",
        EN: "PDF is encrypted, a password is required",
    },
    "err_no_pages": {ZH: "PDF 没有任何页面", EN: "PDF has no pages"},
    "err_page_failed": {
        ZH: "第 %(page)d 页处理失败：%(err)s",
        EN: "Page %(page)d failed: %(err)s",
    },

    # ================= 命令行 =================
    "cli_prog": {ZH: "napa-pdf", EN: "napa-pdf"},
    "cli_desc": {
        ZH: "把 PDF 逐页归一化为 A4，并在页眉标注文件名。",
        EN: "Normalize PDF pages to A4 and stamp the filename in the header.",
    },
    "cli_folder_help": {
        ZH: "要处理的文件夹；不填则进入交互式菜单",
        EN: "folder to process; omit to open the interactive menu",
    },
    "cli_no_tui": {
        ZH: "不启动界面，直接处理指定文件夹",
        EN: "run without the interface",
    },
    "cli_output": {
        ZH: "输出目录名，默认 output（建在源文件夹下）",
        EN: "output folder name (default: output)",
    },
    "cli_lang": {
        ZH: "界面语言 zh / en（默认 zh）",
        EN: "interface language zh / en (default: zh)",
    },
    "cli_version": {ZH: "显示版本", EN: "show version"},
    "cli_missing_dep": {
        ZH: "缺少依赖 pymupdf，请先运行：pip install pymupdf fonttools\n",
        EN: "missing dependency pymupdf; run: pip install pymupdf fonttools\n",
    },
    "cli_start_fail": {ZH: "启动失败：%(e)s\n", EN: "Failed to start: %(e)s\n"},
    "cli_no_pdf_out": {
        ZH: "该文件夹下没有 PDF 文件：%(folder)s",
        EN: "No PDF files in: %(folder)s",
    },
    "cli_outdir": {ZH: "输出目录：%(out)s", EN: "Output folder: %(out)s"},
}


def t(key: str, lang: str = DEFAULT_LANG, **kw) -> str:
    """取指定语言的文案并做命名占位符替换。

    - 缺 key 时回退到中文，再缺就返回 key 本身（不让文案表漏一条就崩掉）
    - 占位符与参数不匹配时返回原始模板，而不是抛异常
    """
    lg = normalize(lang)
    entry = STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(lg) or entry.get(DEFAULT_LANG) or key
    if not kw:
        return text
    try:
        return text % kw
    except (KeyError, TypeError, ValueError):
        return text
