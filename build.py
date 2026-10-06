# -*- coding: utf-8 -*-
"""一键编译成免依赖的 Windows x64 单文件可执行程序。

用法：
    python build.py --clean --test

产物：dist\\napa-pdf.exe   目标机器无需安装 Python 或任何第三方库。
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
BUILD = os.path.join(ROOT, "build")
EXE_NAME = "napa-pdf"

# 打进产物的字体。运行时默认从 C:\\Windows\\Fonts 读宋体，但目标机器未必装了
# （Server Core、精简版系统都没有），那就会回退到内置字体，外观和原件不一致。
BUNDLED_FONTS = [r"C:\Windows\Fonts\simsun.ttc", r"C:\Windows\Fonts\STSONG.TTF"]

EXCLUDES = ["tkinter", "unittest", "pydoc", "doctest", "email", "http",
            "xmlrpc", "numpy", "PIL", "IPython", "setuptools", "pip"]

HIDDEN = ["napa_pdf", "napa_pdf.tui", "napa_pdf.styles", "napa_pdf.theme",
          "napa_pdf.batch", "napa_pdf.processor", "napa_pdf.fonts",
          "napa_pdf.cmap_fix", "napa_pdf.config", "napa_pdf.cli",
          "pymupdf", "fontTools", "fontTools.subset", "prompt_toolkit"]


def log(msg):
    print("[build] " + msg, flush=True)


def clean():
    for d in (DIST, BUILD):
        if os.path.isdir(d):
            log("清理 " + os.path.relpath(d, ROOT))
            shutil.rmtree(d, ignore_errors=True)


def ensure_pyinstaller():
    try:
        import PyInstaller  # noqa: F401
        return True
    except ImportError:
        return False


def install_pyinstaller():
    log("未安装 PyInstaller，正在安装…")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        log("安装失败：\n" + (r.stderr or r.stdout))
        return False
    return True


def collect_fonts():
    staging = os.path.join(BUILD, "_fonts")
    os.makedirs(staging, exist_ok=True)
    got = []
    for src in BUNDLED_FONTS:
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(staging, os.path.basename(src)))
            got.append(os.path.basename(src))
        else:
            log("跳过不存在的字体：" + src)
    log("已打包字体：" + ("、".join(got) if got else "无"))
    return staging, got


def run_pyinstaller():
    staging, fonts = collect_fonts()
    cmd = [sys.executable, "-m", "PyInstaller", "--onefile", "--console",
           "--name", EXE_NAME, "--distpath", DIST, "--workpath", BUILD,
           "--specpath", BUILD, "--paths", ROOT]
    for m in EXCLUDES:
        cmd += ["--exclude-module", m]
    for m in HIDDEN:
        cmd += ["--hidden-import", m]
    for f in fonts:
        cmd += ["--add-data", os.path.join(staging, f) + ";fonts"]
    cmd.append(os.path.join(ROOT, "main.py"))

    log("调用 PyInstaller…（首次较慢）")
    t0 = time.time()
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        log("PyInstaller 失败，返回码 %d" % r.returncode)
        return None
    exe = os.path.join(DIST, EXE_NAME + ".exe")
    if not os.path.isfile(exe):
        log("未生成预期 exe：" + exe)
        return None
    log("完成，用时 %.1f 秒" % (time.time() - t0))
    return exe


def make_samples():
    d = os.path.join(ROOT, "tests", "samples")
    if os.path.isdir(d) and os.listdir(d):
        return d
    script = os.path.join(ROOT, "tests", "make_samples.py")
    subprocess.run([sys.executable, script], capture_output=True)
    return d


def smoke_test(exe):
    fail = 0
    log("冒烟测试：" + os.path.basename(exe))

    r = subprocess.run([exe, "--version"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180)
    if r.returncode == 0 and r.stdout.strip():
        log("OK   --version -> %s" % r.stdout.strip())
    else:
        log("FAIL --version 返回 %r" % (r.stdout or r.stderr))
        fail += 1

    r = subprocess.run([exe, "--help"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180)
    if r.returncode == 0 and "napa-pdf" in (r.stdout + r.stderr):
        log("OK   --help")
    else:
        log("FAIL --help")
        fail += 1

    samples = make_samples()
    out = os.path.join(samples, "exe_测试输出")
    r = subprocess.run([exe, samples, "--no-tui", "-o", "exe_测试输出"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=900)
    n = 0
    if os.path.isdir(out):
        n = len([f for f in os.listdir(out) if f.lower().endswith(".pdf")])
    if n >= 5:
        log("OK   实际处理出 %d 个 PDF" % n)
    else:
        log("FAIL 实际处理只产出 %d 个 PDF" % n)
        if r.stderr:
            log("stderr: " + r.stderr[-600:])
        fail += 1

    target = os.path.join(out, "cream_bg.pdf")
    if n and os.path.exists(target):
        import pymupdf
        d = pymupdf.open(target)
        pg = d[0]
        spans = [s for b in pg.get_text("dict")["blocks"] if b["type"] == 0
                 for l in b["lines"] for s in l["spans"]]
        # 只取页眉带内、且字号等于标签字号的 span。源内容顶边正好落在 28.0pt
        # （保存后有浮点误差），不能单靠 y < 28 判断，否则会把原内容算进来。
        head = "".join(s["text"] for s in spans
                       if s["bbox"][1] < 28 and abs(s["size"] - 10.0) < 0.5)
        w, h = pg.rect.width, pg.rect.height
        d.close()
        good = (head == "cream_bg" and abs(w - 595.276) < 1
                and abs(h - 841.89) < 1)
        log("%s 产物页眉='%s' 尺寸=%.1fx%.1f"
            % ("OK  " if good else "FAIL", head, w, h))
        if not good:
            fail += 1
    return fail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true", help="编译前清理")
    ap.add_argument("--test", action="store_true", help="编译后跑冒烟测试")
    ap.add_argument("--clean-only", action="store_true", help="只清理")
    args = ap.parse_args()

    if sys.platform != "win32":
        log("本脚本只支持 Windows")
        return 1
    if sys.maxsize <= 2 ** 32:
        log("请用 64 位 Python 编译（当前是 32 位）")
        return 1

    if args.clean_only:
        clean()
        return 0
    if args.clean:
        clean()
    if not ensure_pyinstaller() and not install_pyinstaller():
        return 1

    exe = run_pyinstaller()
    if not exe:
        return 1

    log("")
    log("产物：%s  (%.1f MB)"
        % (exe, os.path.getsize(exe) / 1048576))
    log("可直接拷到任意 Windows x64 机器运行，无需 Python 及任何依赖。")

    if args.test:
        log("")
        rc = smoke_test(exe)
        if rc:
            log("冒烟测试失败 %d 项" % rc)
            return 1
        log("冒烟测试全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
