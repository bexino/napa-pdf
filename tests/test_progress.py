# -*- coding: utf-8 -*-
"""运行状态翻页验收。

复现过一个真实缺陷：_pump 只挂在 pre_run_callables 上（启动时跑一次），
批处理线程投递的事件堆在队列里没人消费，界面永远停在"正在处理"。
这里验证事件循环里常驻的轮询任务能把 running 正确翻成 done。
"""
import asyncio
import os
import subprocess
import sys
import threading
import time

from prompt_toolkit.application import Application
from prompt_toolkit.eventloop import run_in_executor_with_context
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.layout import Layout
from prompt_toolkit.output import DummyOutput

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from napa_pdf.styles import build_style
from napa_pdf.tui import NapaApp

HERE = os.path.dirname(os.path.abspath(__file__))


def ensure_samples():
    d = os.path.join(HERE, "samples")
    if not os.path.isdir(d) or not os.listdir(d):
        subprocess.run([sys.executable, os.path.join(HERE, "make_samples.py")],
                       capture_output=True)
    return d


def body_text(app):
    return "".join(t for _, t in app._body())


def run_app(app, inp):
    real = Application(layout=Layout(app.container), input=inp,
                       output=DummyOutput(), style=build_style(),
                       key_bindings=app.kb, full_screen=False,
                       refresh_interval=0.05)
    app.app = real
    app._rebuild()
    # 关键：跟 run() 一样挂常驻轮询任务
    real.pre_run_callables.append(
        lambda: real.create_background_task(app._pump_loop()))

    async def m():
        await run_in_executor_with_context(real.run)

    threading.Thread(target=lambda: asyncio.run(m()), daemon=True).start()
    time.sleep(0.5)
    return real


def wait_done(app, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if app.mode == "done":
            return True
        time.sleep(0.2)
    return False


def main():
    samples = ensure_samples()
    fail = 0

    print("--- A. 完整跑一批，验证 running -> done ---")
    mgr = create_pipe_input()
    inp = mgr.__enter__()
    app = NapaApp(samples)
    app._build()
    real = run_app(app, inp)

    app._activate("1")
    time.sleep(0.3)
    app.buf.text = samples
    app._preview()
    app._start()

    # 不手动调 _pump，完全依赖轮询任务
    ok_mode = wait_done(app)
    print("  %s 批处理结束后 mode = %s"
          % ("OK  " if ok_mode else "FAIL", app.mode))
    if not ok_mode:
        fail += 1
        print("       正文仍是: %r" % body_text(app)[:150])

    txt = body_text(app)
    checks = [
        ("完成页含输出目录", app.out_dir in txt),
        ("成功数为 9", app.ok == 9),
        ("不再显示'正在处理'", "正在处理" not in txt),
        ("显示输出目录路径", "output" in txt),
    ]
    for label, ok in checks:
        print("  %s %s" % ("OK  " if ok else "FAIL", label))
        if not ok:
            fail += 1
    print("  成功 %d 失败 %d 用时 %.1fs" % (app.ok, app.failed, app.elapsed))
    try:
        real.exit()
    except Exception:
        pass
    mgr.__exit__(None, None, None)
    time.sleep(0.2)

    print("")
    print("--- B. 取消后也能翻到 done ---")
    mgr2 = create_pipe_input()
    inp2 = mgr2.__enter__()
    app2 = NapaApp(samples)
    app2._build()
    real2 = run_app(app2, inp2)
    app2._activate("1")
    time.sleep(0.2)
    app2.buf.text = samples
    app2._preview()
    app2._start()
    time.sleep(0.12)
    app2.runner.request_cancel()
    wait_done(app2, 30)
    ok = app2.mode == "done" and app2.cancelled
    print("  %s 取消后 mode=%s cancelled=%s summary=%r"
          % ("OK  " if ok else "FAIL", app2.mode, app2.cancelled, app2.summary))
    if not ok:
        fail += 1
    try:
        real2.exit()
    except Exception:
        pass
    mgr2.__exit__(None, None, None)

    print("")
    print("==== 失败 %d ====" % fail)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
