# pdf-slides-annotated-html

> 把 PDF / PPT 课件变成「左看讲解、右对原文」的**单文件 HTML**：逐页缩略图对照、公式离线渲染、目录折叠、划词标记＋笔记抽屉，断网可开。

一个面向**讲稿型课件**（大学课程 PPT 导出 PDF、技术分享、培训材料）的工具套件。
输入一份几十页的课件 PDF，输出一个自包含的 `.html`：

- **左侧**是中文逐页讲解，**右侧**贴着原页缩略图，不用来回切窗口
- 公式用 **KaTeX 离线渲染**（字体已转 data URI 内嵌，**完全不联网**）
- 四类交互：目录逐级折叠 / 每节概述卡 / 侧栏收起后缩略图自动放大 / **划词标记 → 笔记抽屉**
- 页面里明确区分「原文有什么」与「讲解者加了什么」（绿=直觉、蓝=补充推导、红=原稿问题、灰=原文引用）
- 可选把**原 PDF 整份 base64 内嵌**，点页码直接跳原页，换设备也不失效

> 它不是一个「一键转换器」：机械部分（建骨架、渲染逐页图、组装、体检、截图）全自动，
> **逐页看图写讲解这一步是留给人的**——因为 PPT 导出的 PDF 里数学符号字体映射常常是坏的，
> 只读文字层必然讲错公式。套件的作用是把这一步之外的一切都做掉，并且**告诉你还差多少页没写**。

---

## 快速开始

### 环境

| 依赖 | 用途 | 说明 |
|---|---|---|
| Python 3.9+ | 全部脚本 | 需要 `pymupdf`、`pillow`（脚本会在缺包时给出可直接照抄的 pip 命令） |
| Node.js | `check_math.js` 公式自检 | 唯一用到 node 的地方 |
| Chrome / Edge | 无头截图与 DOM 断言 | 自动探测：环境变量 → PATH → 常见安装位置 |

先自查环境（会打印 python / node / 浏览器 / Python 依赖四项）：

```bash
python scripts/kitpath.py
```

### 一条命令跑完机械部分

```bash
python scripts/run_all.py "<课件.pdf>" --out "<输出目录>"
```

跑完你会得到：

- `config.json` — 组装配置（目录结构、标题、内嵌开关）
- `content/` — 逐页骨架，**带 TODO 标记**，等人来写讲解
- `_extract/` — `page-NN.png`（逐页核对用）＋ `thumb_NN.jpg`（内嵌用）
- `_katex/` — 离线 KaTeX（已内置，无需下载）
- 单文件 HTML ＋ `README-项目.md`
- **⑦ 会报 `内容进度：待补页面 N / M`，目标是 0**

改完 `content/` 后复检（跳过建骨架与渲染，快得多）：

```bash
python scripts/run_all.py "<课件.pdf>" --out "<同一目录>" --skip-init --skip-prepare
```

### 分步执行

```bash
python scripts/prepare_pdf.py "<课件.pdf>" "_extract" 860 75   # 逐页图 + 缩略图 + 文字层
#   ↓ 逐页看 _extract/page-NN.png，写 content/*.html
python scripts/build.py config.json                             # 组装单文件
node   scripts/check_math.js "<输出.html>" "_katex/katex.min.js" # 公式语法 + 标签/锚点/数量
python scripts/check_ui.py   "<输出.html>"                      # 四类交互的「接线」是否完好
python scripts/probe.py      "<输出.html>" scripts/probe_marks.js
python scripts/probe.py      "<输出.html>" templates/probe_doc.js
python scripts/shot.py       "<输出.html>" "_extract/v_home.png" # 截图看长相
```

---

## 目录结构

```
├─ SKILL.md                 ← 技能主文档：完整工作流 + 铁律 + 改套件的纪律
├─ scripts/
│   ├─ run_all.py           ← 主入口：一键流水线（①–⑧）
│   ├─ kitpath.py           ← 路径自查：python / node / 浏览器 / Python 依赖
│   ├─ init_project.py      ← 只建骨架（--group-by 控制分段策略）
│   ├─ prepare_pdf.py       ← PDF → 逐页 png + 缩略图 + 文字层
│   ├─ katex_offline.py     ← 制作离线 KaTeX（一次即可，可跨项目复用）
│   ├─ build.py             ← 组装单文件（可用 0 命令行参数：python build.py config.json）
│   ├─ check_math.js        ← 公式语法、标签配对、目录锚点、正文缺字体检
│   ├─ check_ui.py          ← 四类交互的 DOM 与 CSS/JS 是否对齐
│   ├─ probe.py             ← 无头跑探针 JS 并把结果读回来（读 DOM 靠它）
│   ├─ probe_marks.js       ← 标记功能回归（跨格/跨段/跨公式/单段 + 重开恢复）
│   ├─ glyph_probe.py       ← 正文符号探针：把非中文符号排成一页，肉眼查方框
│   └─ shot.py              ← 无头截图（--script 可先触发交互再截）
├─ assets/                  ← 已验证的外壳与样式，build.py 自动内联
│   ├─ shell.html           ← 页面骨架（改版式改这里，不要改 build.py）
│   ├─ site.css             ← 基础版式
│   ├─ site.extra.css       ← 四类交互的追加样式
│   └─ site.js              ← 全部交互逻辑，暴露 window.__doc 供无头测试
├─ templates/               ← 可复制的内容骨架 + 交付体检 + 截图 harness
├─ examples/                ← 完整 config 样例、逐页区块模板
├─ references/
│   ├─ pitfalls.md          ← 踩坑清单（36 条，按「频率 × 隐蔽度」排序）
│   └─ content-quality.md   ← 讲解内容的质量标准
└─ vendor/katex/            ← 离线 KaTeX（MIT，见下方致谢）
```

**整个目录可以任意搬迁**：所有脚本都用相对自身位置定位资源，不含任何写死的用户名或安装路径。
「外部程序在哪」一律问 `scripts/kitpath.py`。

---

## 三重校验各管一段，都要过

| 脚本 | 管什么 | 不管什么 |
|---|---|---|
| `check_math.js` | 公式能不能渲染、CJK 有没有混进公式、标签配对、目录锚点、缩略图/区块/深链数量、正文缺字（组合符号 U+20D0–U+20FF，硬失败）、TODO 残留 | 长相、交互 |
| `check_ui.py` | 四类交互的 DOM 与 CSS/JS 是否对齐（分组数与按钮数相等、收起后列宽真的变大、抽屉元素齐全、`DOC_NS` 已注入、标记上色的结构安全） | 长相、实际行为 |
| `probe.py` + `probe_marks.js` | **结构有没有被改坏**：自动找跨格/跨段/跨公式/单段四种选区，用**真实入口**标记后断言「块级元素数、可见文本、表格 tr/td 一字不变、无块级元素进 mark、无零宽 mark」，再拆掉全部 mark 重新定位一遍复查 | 长相 |
| `shot.py` | 长相与真实交互状态 | 细节正确性 |

**截图看不出结构被改坏**，所以只要动了标记相关代码，`probe.py` 这一行不能省。

### 自检

```bash
python scripts/selftest.py        # 现造一份 6 页小 PDF，把整条流水线从零跑一遍，期望结尾「自检结果: PASS」
```

---

## 五条铁律

1. **不许跳过逐页看图。** 抽象文字层的课件一律先渲染再读，否则必然讲错公式。
2. **不许在没有验证的情况下交付。** 公式批量自检 ＋ 至少 3 张截图，缺一不可。
3. **忠于原文件顺序。** 页码、标题、公式位置不得擅自调整；要补充的内容单独成篇并标明。
4. **新增内容必须显式标注。** 读者要能一眼分清「原文有什么」和「讲解者加了什么」。
5. **原生问题如实标注并给处理说明**，不要静默修正。

---

## 改这个套件时的纪律

- **先看 mtime**，不要凭记忆假定文件内容——`assets/` 与 `scripts/` 可能刚被别的会话改过。
- **改完必须「重建 ＋ 三校验 ＋ 截图」四连**，并把新产物与旧产物 diff；目录块应当逐字节一致。
- **资产是耦合的**：改 `shell.html` 的类名就要同步改 `site.extra.css` 与 `site.js`，只改一处页面要么裸奔要么交互失效。
- **不许写死本机路径**。校验：`grep -rn "/home/\|/Users/\|C:/Users/" scripts/ assets/ templates/` 应当无命中。
- **模板注释里不许出现字面标签**。`build.py` 用非贪婪正则匹配整段区块，注释里的假 `<section>` 会让它提前收尾，症状是「图在文件里、但 DOM 里查不到」，极难排查。

动笔前先扫一遍 `references/pitfalls.md`（36 条，每条都对应一个真实事故）。

---

## 关于运行环境

套件本身是**独立的 Python + Node 脚本**，不依赖任何特定 Agent 平台，命令行即可跑通。
`SKILL.md` 与 `references/` 里的工作流是按「Agent 帮人做课件精解」这个场景写的，
所以里面大量提到「逐页读图」「标注原稿问题」「等用户确认」这类步骤——
纯手工使用时把那些步骤当作检查清单即可。

---

## 致谢 / 第三方

- [KaTeX](https://katex.org/) — 数学公式排版引擎，**MIT License**。
  `vendor/katex/` 下是构建好的离线版本（CSS 里的字体已转 data URI），版权归 KaTeX 作者所有。
  MIT 与 GPLv3 是**单向兼容**的（MIT 代码可以并入 GPLv3 作品），因此可以随本项目一起分发，
  只需保留其原始版权声明。
- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF 渲染与文字层抽取，**AGPL-3.0 / 商业双授权**。
  本项目**只把它当作运行时 pip 依赖调用，不复制、不分发它的任何代码**，所以本项目自身
  可以按 GPL-3.0 发布。但请注意一个真实的约束：**如果你要分发「本项目 ＋ PyMuPDF」的组合成品，
  仍需同时满足 PyMuPDF 的 AGPL 条款**（AGPLv3 与 GPLv3 可以组合，组合后的整体按 AGPL 约束）。
  只想避开这条，把 PyMuPDF 换成 pypdf 之类的宽松许可库即可（需自行改写 `prepare_pdf.py`）。

## License

**GNU General Public License v3.0** — 全文见 [LICENSE](LICENSE)。

Copyright (C) 2026 zzzhen-22

一句话说清它意味着什么：你可以自由使用、修改、再分发本项目，**但一旦发布了修改后的版本，
就必须同样以 GPL-3.0 开源**。选它的理由正是这个——希望基于它做出来的东西能回到社区，
而不是被闭源吃掉。
