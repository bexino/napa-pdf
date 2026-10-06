[![简体中文](https://img.shields.io/badge/简体中文-zh__cn-red)](#简体中文)
[![QuickStart](https://img.shields.io/badge/Quick-Start-orange)](#quick-start)
[![GitHub release](https://img.shields.io/github/v/release/bexino/napa-pdf?color=yellow)](https://github.com/bexino/napa-pdf/releases)
[![Commit Activity](https://img.shields.io/github/commit-activity/t/bexino/napa-pdf?color=green)](https://github.com/bexino/napa-pdf/commits/main/)
[![License](https://img.shields.io/github/license/bexino/napa-pdf?color=blue)](https://github.com/bexino/napa-pdf/blob/main/LICENSE)
[![MadeWith♥](https://img.shields.io/badge/@bexino-Made_With_♥-purple)](https://github.com/bexino)
[![ViewInGithub](https://img.shields.io/badge/Github-bexino%2Fnapa--pdf-white?logo=github&logoColor=auto&labelColor=555555&color=000000)](https://github.com/bexino/napa-pdf/)

# napa-pdf

Add file names to PDF headers in batches.

---

## Features

For all PDF files in the input target folder:

1. Resize all of them to A4 while preserving their orientation;
2. Write **the PDF's file name** into the header at the top-left corner of each page, without the `.pdf` extension.

Output: to `output\` under the source folder.

> [!IMPORTANT]
> - The file name occupies its own 28 pt header strip, and the original content is shifted down as a whole below the strip;
> - A4 scaling may cause extremely small font sizes to be slightly blurred by anti-aliasing. This is unavoidable and is also very difficult to reproduce in actual use.
>
> - Subdirectories are not processed; only the first level of the folder is scanned;
> - Encrypted PDFs are skipped.

## Quick Start

Download the latest release:  

https://github.com/bexino/napa-pdf/releases

> [!NOTE]
> Because PyMuPDF and the Python runtime need to be embedded, the exe is relatively large.

Or:

### Running from Source

Double-click `napa-pdf.bat` (it will automatically find an available Python), or run manually:

```powershell
python main.py
```

Dependencies:

```powershell
pip install -r requirements.txt
```

---

## Technical Details

### Building

```powershell
python build.py --clean --test
```

`--test` performs a quick test on the build artifact after compilation: it runs `--version` and `--help`,
then actually processes a batch of samples and verifies the header text and A4 dimensions.

### Processing Rules

| Item | Rule |
|---|---|
| Page size | Each page is scaled to A4 (210 x 297 mm). When the source page is smaller than A4, it is proportionally enlarged and centered, with automatic margins on all sides |
| Landscape pages | Determined by the display size after upright orientation: if width > height, landscape A4 (297 x 210 mm) is used, and **no rotation is performed** |
| Rotated pages | `/Rotate` 90/180/270 is first baked into the content before processing, and output pages always have rotation = 0 |
| Header strip | A 28 pt (about 9.9 mm) blank strip is reserved at the top of the canvas, and **the original content is shifted down as a whole below the strip**; the file name is written only within the strip |
| File name position | Left inner margin 28 pt, baseline 17.6 pt, font size 10 pt, pure black |
| Font | Chinese SimSun + Western Times-Roman are mixed by character; spaces between Chinese and Western text are laid out using Chinese width |
| Background color | The header strip is filled with **the page's own background color** (the mode color from a low-resolution render of the entire page), so a beige background will not produce a white bar |
| Text layer | Preserved; it remains searchable/copyable after scaling; the file name is searchable character by character (the Times subset soft hyphen issue has been fixed) |
| Images | Not re-encoded; pixels after decoding are identical to the original |
| Original files | **Never modified**; results are written only to `output\`, and file names remain unchanged |

### Command Line

In addition to the interface, batch processing can also be performed directly (suitable for scheduled tasks):

```powershell
python main.py                          # interactive menu
python main.py "E:\docs" --no-tui       # process directly without opening the interface
python main.py "E:\docs" --no-tui -o results   # custom output directory name
python main.py --version
```

Exit codes: `0` for all successes, `2` if any file failed to process (details are in the log).

### Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `NAPAPDF_SIZE` | Label font size (pt) | 10 |
| `NAPAPDF_STRIP` | Header strip height (pt) | 28 |
| `NAPAPDF_LATIN_FONT` | Force the Western font file path | Built-in Times-Roman |
| `NAPAPDF_THEME` | `light` / `dark`, overrides automatic detection | Determined by terminal background |

```powershell
$env:NAPAPDF_SIZE = "12"
$env:NAPAPDF_THEME = "light"
```

### Code Structure

```
main.py              Startup entry point (includes dependency check)
build.py             One-click build into a dependency-free exe (PyInstaller)
napa-pdf.bat         Launcher when running from source (automatically finds Python)
AGENTS.md            Development notes for maintainers

napa_pdf/
  cli.py             Command-line arguments, stdout encoding fallback
  tui.py             Menu / path input / progress interface
  theme.py           Light and dark color schemes and terminal background detection
  styles.py          Translates color schemes into prompt_toolkit Style
  batch.py           Batch scheduling, cancellation, log callbacks
  processor.py       Single-file processing: A4 normalization + header writing + saving
  fonts.py           Font loading and Chinese-Western mixed-typesetting segmentation
  cmap_fix.py        Fixes the ToUnicode of Times subset fonts (soft hyphen -> hyphen)
  config.py          Constants, defaults, and environment variable overrides

tests/               Acceptance scripts (see "Tests" at the end)
```

### Tests

```powershell
python tests\run_all.py
```

It first automatically generates test samples, then runs 9 acceptance groups (exit code must be 0):

| File | What it covers |
|---|---|
| `test_robustness.py` | GBK console, callbacks throwing exceptions, actual run without setting `PYTHONIOENCODING` |
| `test_colors.py` | Contrast calculation, colors actually rendered by light and dark themes, key line styles |
| `test_progress.py` | Status transition from "processing" to "complete", cancellation path |
| `test_interaction.py` | Menu keys, up/down selection, Esc to return, special characters in input boxes not being captured |
| `test_output.py` | End-to-end: dimensions / orientation / header / no overlapping text / background color / images not re-encoded |
| `test_fidelity.py` | Geometric fidelity: content is not lost or deformed, text is preserved, aspect ratio is unchanged |
| `test_searchable.py` | File name is searchable character by character (ToUnicode) |
| `test_paths.py` | Path cleaning: drag-and-drop quotes / trailing slash / environment variables / `~` |

---

## License

Apache-2.0 license

---


# 简体中文

将文件名批量添加至 PDF 页眉。

## 特性

将输入的目标文件夹中的全部 PDF 文件：

1. 全部调整为 A4 大小，方向不变；  
2. 在每页左上角的页眉里写入 **该 PDF 的文件名**，不含 `.pdf` 扩展名。

输出：至源文件夹下的 `output\` 。

> [!IMPORTANT]
> - 文件名独占一条 28 pt 的页眉带，原内容被整体下移到带子下方；
> - A4 缩放可能会导致极小字号被抗锯齿轻微糊化，不可避免，实际使用过程中也很难复现。
> 
> - 不会处理子目录，只扫描文件夹第一层；
> - 加密 PDF 会被跳过。

## 快速开始

下载最新发布版本：  

https://github.com/bexino/napa-pdf/releases

> [!NOTE]
> 因为需要内嵌 PyMuPDF 与 Python 运行时，故 exe 体积较大。

或者：

### 从源码运行

双击 `napa-pdf.bat`（会自动找可用的 Python），或手动运行：

```powershell
python main.py
```

依赖：

```powershell
pip install -r requirements.txt
```

---

## 技术细节

### 编译

```powershell
python build.py --clean --test
```

`--test` 会在编译后对产物做快速测试：运行 `--version`、`--help`，  
再真实处理一批样本并校验页眉文字与 A4 尺寸。

### 处理规则

| 项 | 规则 |
|---|---|
| 页面尺寸 | 每页缩放到 A4（210 x 297 mm）。源页小于 A4 时等比放大并居中，四周自动留白 |
| 横向页面 | 按摆正后的显示尺寸判定：宽 > 高就用横向 A4（297 x 210 mm），**不做旋转** |
| 旋转页 | `/Rotate` 90/180/270 会先烘焙进内容再处理，输出页一律 rotation = 0 |
| 页眉带 | 画布顶部留 28 pt（约 9.9 mm）空白带，**原内容整体下移到带子下方**，文件名只写在带内 |
| 文件名位置 | 左内边距 28 pt，基线 17.6 pt，字号 10 pt，纯黑 |
| 字体 | 中文宋体（SimSun）+ 西文 Times-Roman 按字符混排；中西文之间的空格按中文宽度排版 |
| 底色 | 页眉带用**该页自身底色**填充（整页低分辨率渲染取众数色），米色底不会出现白条 |
| 文本层 | 保留，缩放后仍可检索/复制；文件名逐字可搜（已修 Times 子集的软连字符问题） |
| 图像 | 不重新编码，解码后像素与原件一致 |
| 原件 | **绝不修改**，结果只写入 `output\`，文件名保持不变 |

### 命令行

除了界面，也可以直接批处理（适合做成计划任务）：

```powershell
python main.py                          # 交互式菜单
python main.py "E:\docs" --no-tui       # 不开界面直接处理
python main.py "E:\docs" --no-tui -o 结果   # 自定义输出目录名
python main.py --version
```

退出码：`0` 全部成功，`2` 有文件处理失败（明细在日志里）。

### 环境变量

| 变量 | 作用 | 默认 |
|---|---|---|
| `NAPAPDF_SIZE` | 标签字号（pt） | 10 |
| `NAPAPDF_STRIP` | 页眉带高（pt） | 28 |
| `NAPAPDF_LATIN_FONT` | 强制西文字体文件路径 | 内置 Times-Roman |
| `NAPAPDF_THEME` | `light` / `dark`，覆盖自动探测 | 按终端背景判断 |

```powershell
$env:NAPAPDF_SIZE = "12"
$env:NAPAPDF_THEME = "light"
```

### 代码结构

```
main.py              启动入口（含依赖检查）
build.py             一键编译成免依赖 exe（PyInstaller）
napa-pdf.bat         源码运行时的启动器（自动找 Python）
AGENTS.md            面向维护者的开发说明

napa_pdf/
  cli.py             命令行参数、stdout 编码兜底
  tui.py             菜单 / 路径输入 / 进度界面
  theme.py           明暗两套配色与终端背景探测
  styles.py          把配色翻译成 prompt_toolkit Style
  batch.py           批处理调度、取消、日志回调
  processor.py       单文件处理：A4 归一化 + 页眉写入 + 保存
  fonts.py           字体加载与中西文混排分段
  cmap_fix.py        修正 Times 子集字体的 ToUnicode（软连字符 -> 连字符）
  config.py          常量、默认值与环境变量覆盖

tests/                验收脚本（见文末「测试」）
```

### 测试

```powershell
python tests\run_all.py
```

会先自动生成测试样本，然后跑 9 组验收（退出码必须为 0）：

| 文件 | 覆盖什么 |
|---|---|
| `test_robustness.py` | GBK 控制台、回调抛异常、不设 `PYTHONIOENCODING` 实跑 |
| `test_colors.py` | 对比度计算、明暗双主题实际渲染的颜色码、关键行样式 |
| `test_progress.py` | 「正在处理」到「完成」的状态翻页、取消路径 |
| `test_interaction.py` | 菜单键、上下选择、Esc 返回、输入框特殊字符不被抢 |
| `test_output.py` | 端到端：尺寸 / 方向 / 页眉 / 无叠字 / 底色 / 图像未重编码 |
| `test_fidelity.py` | 几何保真：内容不丢不变形、文本保留、纵横比不变 |
| `test_searchable.py` | 文件名逐字可检索（ToUnicode） |
| `test_paths.py` | 路径清洗：拖拽引号 / 尾斜杠 / 环境变量 / `~` |

---

## 许可证

Apache-2.0 license
