# -*- coding: utf-8 -*-
"""打包后才暴露的两个缺陷的回归测试。

1. 打包成 exe 后没有 -X utf8，Windows stdout 走 GBK，日志里的 ✓/✗/─ 会抛
   UnicodeEncodeError，把批处理线程整个打挂——表现为"只处理了第一个文件就
   停住"。源码运行时因为启动脚本带了 -X utf8 而侥幸避开。
2. 任何日志回调抛异常都不该中断批处理。

这两个问题在"python main.py"下完全看不出来，只有打包后才发作。
"""
import io
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from napa_pdf.batch import BatchRunner, list_pdfs
from napa_pdf.cli import _force_utf8_stdio

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


class GbkStdout:
    """模拟 Windows 默认的 GBK 控制台：遇到无法编码的字符就抛异常。"""

    def __init__(self):
        self.encoding = "gbk"
        self.buffer = io.BytesIO()

    def write(self, s):
        s.encode("gbk")          # 抛 UnicodeEncodeError 就算复现
        return len(s)

    def flush(self):
        pass


def make_samples():
    d = os.path.join(HERE, "samples")
    if not os.path.isdir(d) or not os.listdir(d):
        subprocess.run([sys.executable, os.path.join(HERE, "make_samples.py")],
                       capture_output=True)
    return d


def check_stdio(fail):
    print("--- A. GBK 控制台应被自动切到 UTF-8 ---")
    real = sys.stdout
    fake = GbkStdout()
    got = {}
    try:
        sys.stdout = fake
        _force_utf8_stdio()
        enc = (getattr(sys.stdout, "encoding", "") or "").lower()
        got["enc"] = enc
        try:
            sys.stdout.write("✓ ✗ ─ 中文")
            got["write"] = True
        except Exception as e:
            got["write"] = False
            got["err"] = str(e)
    finally:
        sys.stdout = real
    ok_enc = "utf" in got.get("enc", "")
    print("  %s 切换后 encoding=%s" % ("OK  " if ok_enc else "FAIL",
                                      got.get("enc")))
    if not ok_enc:
        fail.append("stdio-encoding")
    if got.get("write"):
        print("  OK   特殊符号写入成功")
    else:
        print("  FAIL 写入仍报错：%s" % got.get("err"))
        fail.append("stdio-write")


def check_callbacks(fail):
    print("")
    print("--- B. 回调全部抛异常时仍应处理完全部文件 ---")
    samples = make_samples()
    files = list_pdfs(samples)
    out = os.path.join(samples, "鲁棒性测试输出")

    def boom(*a, **kw):
        raise UnicodeEncodeError("gbk", "✓", 0, 1, "模拟控制台炸了")

    r = BatchRunner(samples, out, files=files,
                    on_log=boom, on_file=boom, on_page=boom,
                    on_done=boom).start()
    while r.is_alive():
        time.sleep(0.2)
    n = len([f for f in os.listdir(out) if f.lower().endswith(".pdf")]) \
        if os.path.isdir(out) else 0
    ok = n >= len(files) - 1        # 加密那份本来就该失败
    print("  %s 输入 %d 个，产出 %d 个（ok=%d failed=%d）"
          % ("OK  " if ok else "FAIL", len(files), n, r.ok, r.failed))
    if not ok:
        fail.append("callback-crash")
    shutil.rmtree(out, ignore_errors=True)


def check_gbk_run(fail):
    print("")
    print("--- C. 不设 PYTHONIOENCODING 真实跑一批 ---")
    samples = make_samples()
    out = "gbk_实跑"
    env = dict(os.environ)
    env.pop("PYTHONIOENCODING", None)
    env["PYTHONIOLEGACYWINDOWSSTDIO"] = "1"
    argv = [sys.executable, os.path.join(ROOT, "main.py"),
            samples, "--no-tui", "-o", out]
    r = subprocess.run(argv, capture_output=True, env=env, timeout=600)
    produced = os.path.join(samples, out)
    n = len([f for f in os.listdir(produced) if f.lower().endswith(".pdf")]) \
        if os.path.isdir(produced) else 0
    ok = n >= 5
    print("  %s 产出 %d 个 PDF" % ("OK  " if ok else "FAIL", n))
    if not ok:
        fail.append("gbk-run")
        print("     stderr: %s" % (r.stderr or b"")[-400:])
    shutil.rmtree(produced, ignore_errors=True)


def main():
    fail = []
    check_stdio(fail)
    check_callbacks(fail)
    check_gbk_run(fail)
    print("")
    print("==== 失败 %d ====" % len(fail))
    for f in fail:
        print("  - " + f)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
