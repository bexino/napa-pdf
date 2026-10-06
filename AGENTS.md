# AGENTS.md

本文件是给 AI 助手（及维护者）看的工作说明。面向用户的使用文档见 `README.md`。

## 一、项目是什么

`napa-pdf` 是一个 Windows TUI 工具：把一个文件夹里的所有 PDF **逐页归一化为 A4**，
并在每页左上角的页眉里写入**该 PDF 的文件名**（去扩展名）。

原始需求只有四句，但每句都有隐含约束，务必读完第二节再动手：

1. 打开进菜单，输入 `1` 进入加文件名页眉
2. 提示输入文件夹路径，**支持从资源管理器拖拽**
3. 回车运行：缩放到 A4，不够自动空出，识别横向页面并继续用横向 A4（**不旋转**）
4. 自动在源文件夹下建 `output\`，**文件名保持不变**

外加一条硬性视觉要求：**页眉不能压住任何原有文字**。

项目源头是 `.skill/` 里的提示词与脚本（`SKILL.md` + 3 个 py）。那是**只读参考**，
不要修改它；需要复用逻辑时从 `napa_pdf/` 抄，不要反向依赖 `.skill` 的路径。

## 二、不可违反的约束

这些是验收脚本逐页断言的性质，改动代码时**必须保证它们继续成立**。

### 1. 原件绝不被修改

所有产物只写进 `output\`，用 `os.replace()` 原子替换半成品文件。

### 2. 页眉绝不压住内容（结构性保证，不是启发式）

不要改成「先检测有没有空白，有空位才写」这种启发式做法。
当前实现是**几何上不可能相交**：画布顶部留 28pt 的页眉带，原内容整体下移到带子下方，
文件名只写在带内。

验收断言：逐页检查「页眉带内除标签外零墨迹」。

### 3. 输出页 rotation 必须为 0

即使源页有 `/Rotate`，也要先 `remove_rotation()` 烘焙进内容再处理。
横向判定按**摆正后的显示尺寸**（宽 > 高 = 横向），横向页用横向 A4，不做旋转。

### 4. 图像不得重新编码

`show_pdf_page` 走的是 Form XObject，原始图像字节保持不变。
验收断言：逐 xref 取解码像素的 md5 与原件一致。

> 注意：**不要用 `extract_image()` 的原始字节做比对**。保存时 `deflate=True` 会重压
> 图像流，字节必然变化，比字节会得到假阴性。要比解码后的像素。

### 5. 文件名必须逐字可检索

用户要靠搜索文件名定位页面。PyMuPDF 对系统 `times.ttf` 生成子集时，会把连字符字形
反查成 U+00AD（软连字符）、空格字形反查成 U+00A0，搜 `附件1-1` 会搜不到。
`cmap_fix.fix_doc()` 负责修回来，**必须在 `subset_fonts()` 之后调用**（顺序不能反）。

## 三、目录结构与职责

```
main.py              启动入口（含依赖检查）
build.py             一键编译成免依赖 exe（PyInstaller）
napa-pdf.bat         源码运行时的启动器（会自动找 Python）
requirements.txt     运行时依赖

napa_pdf/
  config.py          所有常量与默认值；环境变量覆盖也在这里
  fonts.py           字体加载、中西文混排分段
  cmap_fix.py        修正 Times 子集字体的 ToUnicode
  processor.py       单文件处理管线（本项目最核心的文件）
  batch.py           批处理调度、取消、日志回调
  tui.py             菜单 / 路径输入 / 进度界面
  theme.py           明暗两套配色与自动探测
  styles.py          把配色翻译成 prompt_toolkit Style
  cli.py             命令行参数解析、stdin/stdout 编码兜底

tests/
  make_samples.py    生成覆盖各类边界的测试样本
  run_all.py         跑完整验收
  test_*.py          各项专项验收（见第七节）
```

## 四、核心处理管线（processor.py）

`process_pdf()` 对每个 PDF 逐页做三件事：

1. **归一化** — `normalize_page()`
   - `remove_rotation()` 摆正页面
   - 按显示尺寸判定横向/纵向，选 A4 画布
   - 整页铺底色，用 `show_pdf_page` 把源页**等比**缩放居中放入「去掉页眉带后的版心」
   - 空间不够就自动留白
2. **写页眉** — `_write_label()`
   - 用 `TextWriter` 按字符分 run 写入（中文宋体 / 西文 Times）
3. **保存**
   - `subset_fonts(verbose=False)` → `fix_doc()` → `save(garbage=4, deflate=True)`

## 五、代码规范

- **注释写「为什么」，不写「是什么」**。本项目大部分坑都很反直觉，
  注释要写清楚背后的原因和实测数据，否则下一个人会「优化」回去。
- 中文注释与中文文档（本项目面向中文用户）。
- 纯函数优先；`processor.py` / `fonts.py` 不依赖界面，可独立测试。
- 失败要**局部化**：单个文件出错不能中断整批，用 `ProcessError` 包装。
- 不新增运行时依赖，除非确有必要（exe 体积已经 66MB）。

## 六、已踩过的坑（改动时务必重读）

### PyMuPDF

- **`show_pdf_page` 的 clip 用未旋转坐标**。直接传 `page.rect` 给旋转页会裁掉 3/4
  内容，必须先 `page.remove_rotation()`。
- **`page.rect` 已经是含旋转的显示尺寸**。别再按 `/Rotate` 交换一次，否则横向判定全反。
- **对 `times.ttf` 的 `subset_fonts()` 几乎无效**：只用 1 个字形仍嵌入 51KB（保留了
  完整字形表），36 个字形也才 76KB。因此西文改用内置 base-14 `tiro`（Times-Roman），
  子集化后整份文件约 11KB，视觉几乎一致。需要还原原版字体用
  `NAPAPDF_LATIN_FONT`。
- **CJK 字体子集化同样几乎无效**（2 个字形嵌 163KB），但 CFF 流压缩率高，整份文件仍
  只有 11KB，可以接受。
- **缩放必然带来重采样**。密排小字缩到 0.9666 后抗锯齿会把 0.4pt 细线糊成灰，
  逐像素差异可达 4%。这是等比缩放的固有代价，**不代表内容变化**——墨迹总量、文本、
  纵横比都不变（块相关性 >0.996）。因此验收标准是「有无丢失变形」而非「逐像素等同」，
  用 32x32 块统计覆盖率来抹掉亚像素抖动。

### 底色

- **别只采样左上角一小块**。扫描件顶部常有黑边，会把整条页眉带涂黑。
  `page_background()` 用整页低分辨率渲染取**众数色**，对文字、边框、印章都不敏感。

### prompt_toolkit

- **`kb.add()` 默认 `eager=Never`**，此时按键先交给焦点控件处理。焦点在
  `FormattedTextControl` 上时，菜单快捷键会被内置 EMACS 绑定吞掉（`q`/`r`/`0`/`1`/`2`
  全部失效）。菜单键必须显式 `eager=True`，并用 `filter` 排除输入态，
  否则路径里含这些字符就输不进去。
- **布局不要在切模式时重建**。`Window` 换新对象后，`Layout` 的焦点栈仍指向已脱离容器
  的旧窗口，按键会发给没人管的窗口（表现为快捷键时灵时不灵）。
  用 `_build()` 一次性建好窗口 + `ConditionalContainer` 控制显隐，并在 `_rebuild()`
  里显式对齐焦点。
- **`TextArea` 不能被挂进第二个容器**（缺 `reset()` 方法）。要复用输入框就自己管
  `Buffer` + `BufferControl`。
- **后台线程的事件必须有人持续消费**。只把 `_pump` 挂进 `pre_run_callables` 的话它
  只在启动时跑一次，批处理完成的事件全堆在队列里，界面永远停在「正在处理」。
  要用 `create_background_task` 常驻一个轮询协程；`refresh_interval` 只负责重绘，
  **不会**重新调用 `pre_run`。
- **不暴露终端背景亮度**。固定一套深色配色时，浅色终端背景下对比度只有 1.1:1，
  文字几乎不可见。`theme.py` 按控制台属性位自动选配色，两套都保证正文 >= 4.5:1
  （WCAG AA）。

### 打包

- **exe 里 stdout 是 GBK，不是 UTF-8**。没有 `-X utf8` 的话，日志里的对勾/叉号/横线
  会抛 `UnicodeEncodeError`，把批处理线程整个打挂——症状是「只处理了第一个文件就
  停住」。源码运行时因为 `napa-pdf.bat` 带了 `-X utf8` 而侥幸避开。
  `cli._force_utf8_stdio()` 负责兜底。
- **所有回调都要过 `batch.BatchRunner._safe`**——**包括 `progress` 回调**。
  它是被 `process_pdf` 逐页调用的，漏掉保护会让整批文件被误判为失败。
  日志失败绝不能中断批处理。
- **字体要打进包里**。运行时默认读 `C:\Windows\Fonts\simsun.ttc`，但 Server Core、
  精简版系统根本没装，会静默回退到内置字体、外观和原件不一致。
  `fonts.py` 优先读 `_MEIPASS/fonts`。

## 七、测试

```powershell
python tests\run_all.py          # 全部 9 项
python build.py --clean --test   # 编译 + 产物冒烟测试
```

| 文件 | 覆盖什么 |
|---|---|
| `test_robustness.py` | GBK 控制台、回调抛异常、不设 `PYTHONIOENCODING` 实跑 |
| `test_colors.py` | WCAG 对比度计算、明暗双主题实际渲染的 ANSI 码、关键行样式 |
| `test_progress.py` | `running -> done` 状态翻页、取消路径 |
| `test_interaction.py` | 菜单键、上下选择、Esc 返回、输入框特殊字符不被抢 |
| `test_output.py` | 端到端：尺寸/方向/页眉/无叠字/底色/图像未重编码 |
| `test_fidelity.py` | 几何保真：内容不丢不变形、文本保留、纵横比不变 |
| `test_searchable.py` | 文件名逐字可检索（ToUnicode） |
| `test_paths.py` | 路径清洗：拖拽引号/尾斜杠/环境变量/`~` |

**改代码后必须跑 `tests\run_all.py`**，退出码必须为 0。
新增行为要在 `tests\` 下加对应验收，别只靠肉眼判断。

## 八、环境变量

在 `config.py` 里读取，菜单页按 `2` 可查看当前值。

| 变量 | 作用 |
|---|---|
| `NAPAPDF_SIZE` | 标签字号 pt（默认 10） |
| `NAPAPDF_STRIP` | 页眉带高 pt（默认 28） |
| `NAPAPDF_LATIN_FONT` | 强制西文字体文件路径 |
| `NAPAPDF_THEME` | `light` / `dark`，覆盖自动探测 |

## 九、构建产物

```powershell
python build.py --clean --test
```

产物 `dist\napa-pdf.exe`（约 66MB，单文件，Windows x64）。
目标机器**不需要 Python，也不需要任何第三方库**。

验证免依赖时**必须清空 `PATH` 实测**，不能想当然：
清到只剩 `C:\Windows\System32;C:\Windows`、确认 `which python` 为空、
清掉 `PYTHONHOME`，然后跑真实处理任务。

`dist/`、`build/`、`*.spec`、`tests/samples/`、`__pycache__/` 已在 `.gitignore` 中。

## 十、当前已知限制

- **加密 PDF 会被跳过**，在日志里报错，不中断整批（没做密码输入交互）。
- **不处理子目录**。`list_pdfs()` 只扫一层。`BatchRunner` 有 `recursive` 参数但
  CLI 未接通。
- **A4 缩放有损**：矢量内容清晰，但极小字号扫描件放大后会有重采样痕迹（见第六节）。
- **exe 体积 66MB**，主要来自 PyMuPDF 与 Python 运行时本身。