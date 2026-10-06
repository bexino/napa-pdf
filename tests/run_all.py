# -*- coding: utf-8 -*-
"""跑完整验收：造样本 -> 批处理 -> 逐项断言。

    python tests/run_all.py

退出码 0 表示全部通过。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

STEPS = [
    ("生成测试样本", "make_samples.py"),
    ("双语（文案表/界面切换/文件名不翻译）", "test_i18n.py"),
    ("打包鲁棒性（GBK 控制台 / 回调异常）", "test_robustness.py"),
    ("配色对比度（明暗主题 WCAG AA）", "test_colors.py"),
    ("运行状态翻页（running -> done）", "test_progress.py"),
    ("界面按键交互（菜单/输入/快捷键不被抢）", "test_interaction.py"),
    ("端到端断言（尺寸/方向/页眉/叠字/底色/图像）", "test_output.py"),
    ("几何保真（内容不丢不变形）", "test_fidelity.py"),
    ("文件名可检索（ToUnicode）", "test_searchable.py"),
    ("路径清洗（拖拽/引号/环境变量）", "test_paths.py"),
]


def run(script):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run([PY, os.path.join(HERE, script)],
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def main():
    failed = []
    for title, script in STEPS:
        print()
        print("#" * 70)
        print("# " + title)
        print("#" * 70)
        code, out, err = run(script)
        sys.stdout.write(out)
        if err.strip():
            sys.stdout.write("--- stderr ---\n" + err)
        if code != 0:
            failed.append(title)

    print()
    print("=" * 70)
    if failed:
        print("失败项 %d / %d：" % (len(failed), len(STEPS)))
        for f in failed:
            print("  - " + f)
    else:
        print("全部 %d 项通过" % len(STEPS))
    print("=" * 70)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
