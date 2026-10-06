# -*- coding: utf-8 -*-
"""napa-pdf 启动入口。

用法：
    python main.py              进入 TUI 菜单
    python main.py <文件夹> --no-tui    直接批处理
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    try:
        import pymupdf  # noqa: F401
    except ImportError:
        sys.stderr.write("缺少依赖 pymupdf，请先运行：pip install pymupdf fonttools\n")
        return 1
    try:
        from napa_pdf.cli import main as cli_main
    except ImportError as e:
        sys.stderr.write("启动失败：%s\n" % e)
        return 1
    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
