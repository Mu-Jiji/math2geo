# math2geo：拍一道题，AI 读懂，画出 GeoGebra 图形

**版本：261109_beta**

题目拍下来，交给模型读懂；坐标由本地程序算准，再输出成能直接打开的 GeoGebra 页面。

没有 OCR、没有本地题库、没有手写几何语法。模型负责理解题意，`construct.py` 负责把
“中点、垂足、交点、角平分线”这些关系算成准确坐标——所以图是算出来的，不是随手画的示意。

```text
图片 / 文字 / Word
        │
        ▼
   大模型读题
        │
        ▼
   作图方案 JSON
        │
        ▼
 construct.py 计算坐标
        │
        ▼
      Scene
        ├─ preview.png
        ├─ 可拖动 HTML + 可复制的 GeoGebra 命令
        ├─ 几何画板构造步骤
        └─ report.md（题干、思路、自检、答案）
```

---

## 一、安装

需要 Python 3.10 或更高版本：

```powershell
python -m pip install -r requirements.txt
```

Windows 用户也可以双击 `install.bat`。它会自动寻找可用的 Python，安装依赖，默认源失败时
切换到清华镜像，最后做一次环境自检。

主要依赖：

| 依赖 | 用途 |
| --- | --- |
| numpy / pillow | 数值计算、图片压缩 |
| sympy | 表达式与几何推导 |
| matplotlib | 预览图渲染 |
| PySide6 | 图形界面 |

只使用命令行时可以不装 PySide6。

---

## 二、配置 API

命令行按以下顺序查找 Key：

1. 启动参数 `--ai-key sk-...`
2. 环境变量 `MATH2GEO_API_KEY` / `DEEPSEEK_API_KEY`

图形界面则直接使用「模型预设」里保存的 Key（存于 `%APPDATA%\math2geo\config.json`）；
如果界面的 API Key 留空，程序会按「Key 环境变量」里填的名字去系统环境变量里取。

注意两个容易混淆的字段：

- **API Key**：真正的密钥，通常以 `sk-` 开头；
- **Key 环境变量**：变量名，例如 `MATH2GEO_API_KEY`，不是密钥本身。

程序会优先使用界面的 API Key；为空时，再按环境变量名去系统环境变量里取。

可选环境变量：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `MATH2GEO_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI 兼容接口地址 |
| `MATH2GEO_MODEL` | `deepseek-flash` | 需要支持图片输入 |
| `MATH2GEO_TIMEOUT` | `120` | 单次请求超时（秒） |
| `MATH2GEO_EFFORT` | `low` | 推理强度，`low` 更省 token |

---

## 三、图形界面

```powershell
python -m math2geo gui
```

查看版本：

```powershell
python -m math2geo --version
```

也可以用 `Go GUI.bat` 启动。

| 页面 | 内容 |
| --- | --- |
| 绘制区域 | 拖拽/点击上传图片、Word 或直接输入文字；支持截图识别；下方是日志和已完成任务 |
| 模型预设 | 本地模型 / 云端 API；云端可选服务商、填写 Base URL 与模型、测试连接；用户 API 配置支持多套预设、密码和教室模式 |
| 题目设置 | 是否在输出中包含题目、答案详细程度、难度系数、突破点 |
| 绘图设置 | 二维 / 三维、坐标轴、网格、截面方向、token 倍率、输出格式与 DPI、颜色 |
| 其他设置 | 动画、主题、通知、截图热键、输出目录、离线运行组件、缓存清理 |

### 上传与截图

- 拖拽或点击上传区即可选择文件；
- 「截图识别」会隐藏主窗口，进入全屏框选；
- 框选时按 `Esc` 或鼠标右键取消；
- 默认全局截图热键是 `Ctrl+Alt+S`，可在「其他设置」修改，旁边有「恢复默认」；
- 截图后可选择二次确认，确认框支持「以后不再提示」。

### 二维与三维

上传卡片右上角可以直接切换二维 / 三维，不用进设置页。

三维模式额外提供：

- GeoGebra 3D 主视图，可自由旋转、缩放、重置视角；
- 右侧平面直角坐标系实时显示截面；
- 方位角、仰角、偏移滑杆，以及可拖动的转球；
- 截面透明度、截面坐标轴、截面图形、截面平面开关；
- 可折叠的「横截面」和「解答」卡片；
- 复制 GeoGebra 命令、下载 `.ggb`、隐藏 3D 坐标平面。

### 完成提醒

- 可播放自定义提示音；支持 `.wav`、`.mp3`，可试听、删除当前预设；
- 可开启 Windows 系统通知，绘制完成后在通知中心显示用时、token 和费用。

### 窗口与动画

- 使用 Windows 原生标题栏与边框，窗口可自由缩放，最小 `760 × 540`；
- 窗口过矮时会隐藏大标题，页面内容可滚动；
- 关闭时记住位置、大小和最大化状态，下次启动恢复；
- 启动动画和标题动画可以分别关闭；
- 标题随窗口宽度连续缩放，不会突然跳变。

---

## 四、命令行

```powershell
# 图片
python -m math2geo run 题目.jpg

# 文字
python -m math2geo run --text "在△ABC中，∠C=60°，c=√3，CD 平分∠C 交 AB 于 D，求 CD 最大值。"

# 指定输出目录和文件名
python -m math2geo run 题目.jpg -o out/我的题 --title 我的题

# 复用上次的作图方案，不再调用模型
python -m math2geo run 题目.jpg --plan-file out/我的题/plan.json

# 换模型
python -m math2geo run 题目.jpg --ai-model deepseek-v4-pro
```

图片输入需要模型支持视觉，默认模型可以直接读图。

---

## 五、输出文件

| 文件 | 内容 |
| --- | --- |
| `preview.png` | 预览图，标签自动避让，直角和角会有标记 |
| `<名字>.html` | 浏览器直接打开，可拖动、缩放、查看解答 |
| `geogebra_dynamic.txt` | 逐行命令，派生点使用依赖式，拖动顶点不会散 |
| `geogebra_static.txt` | 纯坐标版本，作为保底 |
| `geogebra_paste.txt` | 单行 `Execute[...]` |
| `sketchpad_steps.md` | 几何画板分步构造说明 |
| `plan.json` | 模型返回的原始作图方案 |
| `scene.json` | 中间表示：点、线、圆、函数、自检结果 |
| `report.md` | 题干、理解、点表、自检、答案与思路 |
| `deployggb.js` | 勾选「输出离线运行组件」时复制到输出目录 |

GeoGebra 6 网页版不接受 `SetColor` 这类脚本命令，所以颜色和线型由 HTML 里的 JS API 设置，
文本命令只负责创建对象。

> 「输出离线运行组件」会把 `deployggb.js` 一起放进输出目录，解决加载脚本的问题；
> GeoGebra 本体仍可能按浏览器缓存或网络情况加载。

---

## 六、图是怎么算出来的

模型只负责描述结构，例如：

```json
{"name": "D", "construct": "bisector_foot", "args": ["C", "A", "B"]}
```

本地根据角平分线定理算出坐标，并生成对应的 GeoGebra 依赖式：

```text
D = Intersect(Line(A, B), AngleBisector(A, C, B))
```

支持的构造包括：中点、垂足、交点、角平分线交点、重心 / 外心 / 内心 / 垂心、分点、
圆与直线交点、两圆交点、旋转、对称、平移。

模型还会给出一组 `checks`（长度、角度、斜率、点是否在圆上等），画完逐条核验。
对不上的会在报告里标出来，这是判断“图有没有画对”的硬指标。

---

## 七、项目结构

```text
math2geo/
├─ math2geo/
│  ├─ ai.py               读题：发图/发文、JSON 容错、超时重试
│  ├─ plan.py             作图方案 → Scene
│  ├─ construct.py        构图原语：算坐标 + 生成依赖式
│  ├─ algebra.py          函数采样与表达式处理
│  ├─ model.py            Scene 中间表示
│  ├─ preview.py          matplotlib 预览
│  ├─ render_ggb.py       GeoGebra 命令、HTML 页面
│  ├─ render_sketchpad.py 几何画板步骤
│  ├─ pipeline.py         一条龙流程 + 报告
│  ├─ cli.py              命令行入口
│  ├─ gui.py              图形界面
│  ├─ api_dialogs.py      用户 API 预设、密码键盘
│  ├─ docx_text.py        读取 .docx 题面
│  ├─ textnorm.py         LaTeX → 纯文本
│  └─ templates/          提示词与 HTML 模板
├─ assets/                图标、启动动画、标题动画、帮助截图
├─ tests/run_tests.py     单元测试 + GUI 冒烟
├─ tools/                 依赖检查、动画生成、GeoGebra 验证、离线脚本
├─ packaging/             PyInstaller 配置
├─ build_exe.bat          Windows 打包脚本
├─ VERSION                当前版本号
└─ requirements.txt
```

---

## 八、Token 与费用

- 默认 `max_tokens = 4000`，推理强度 `low`；
- 「题目设置 → 答案与过程」默认「简单」，省掉大段推导；
- 详细度调到「丰富」会明显增加输出，按需使用；
- 三维模式有单独的 token 倍率，可在「绘图设置」里调；
- 开启「显示价格」后，任务完成时会按当时的高峰 / 低谷单价估算费用。

---

## 九、用户 API 配置

「模型预设 → 用户 API 配置」会打开独立窗口：

- 最多保存 10 个预设；
- 支持新建、编辑、删除、启用；
- 字段修改会自动保存，不需要反复点保存；
- 可设置 0–6 位数字密码（留空表示不设密码）；
- 开启「教室模式」后，主界面的 API Key 与环境变量会锁定，只能在该窗口修改。

---

## 十、检查与测试

检查运行环境：

```powershell
python tools/check_deps.py
```

Windows 也可以双击 `check_deps.bat`。

跑测试：

```powershell
python tests/run_tests.py
```

覆盖构图原语、方案转场景、自检、AI JSON 容错、LaTeX 转纯文本、预览渲染、
完整流水线和 GUI 冒烟。

用无头 Edge 实际验证 GeoGebra 命令（需要 `playwright` 和本机 Edge）：

```powershell
python tools/ggb_check.py --scene out/xxx/scene.json
python tools/ggb_check.py out/xxx/geogebra_dynamic.txt
```

---

## 十一、隐私

- 只把题目图片（长边压到 1800px）或题干文字发给模型，不发送其他文件；
- 配置与 API Key 只保存在本机 `%APPDATA%\math2geo\config.json`；
- 生成的 HTML 默认会从 `geogebra.org` 加载脚本；需要离线时勾选「输出离线运行组件」，
  或把 `tools/deployggb.js` 放到 HTML 同目录；
- 仓库里不包含任何真实 API Key。

---

## 许可

本项目代码采用 **MIT License**。

第三方组件仍遵循各自许可：

- `tools/deployggb.js`：GeoGebra Non-Commercial License；
- PySide6 / Qt：LGPL；
- NumPy、Pillow、SymPy、Matplotlib：各自的开源许可。

使用或分发时请同时遵守这些第三方许可。

---

©2026 Mu-Jiji @ GitHub
