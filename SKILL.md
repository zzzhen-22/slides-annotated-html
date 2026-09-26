---
name: pdf-slides-annotated-html
description: >-
  把 PDF / PPT 课件、讲义、论文投影片做成「逐页对照讲解」的单文件 HTML：左侧两级可折叠目录、
  每页配原页缩略图（可收起侧栏让缩略图自动放大）、关键公式用 LaTeX 排版、完全离线可打开，
  并支持在正文里划词标记 → 汇入「我的标记」笔记抽屉（可备注、定位、导出）。
  适用于：课件逐页精解、PDF 转讲解文档、教材/讲义中文注释、生成便于对照原文阅读的 HTML、
  把 slide 变成可检索可批注的学习笔记。
  触发词：逐页讲解、逐页精解、对照原文件、PDF 转 HTML 讲解、课件解析、讲义讲解、
  公式用 LaTeX、离线 HTML、划词标记、笔记、目录折叠、annotated slides、slides to html。
agent_created: true
---

# PDF / PPT 课件 → 逐页对照讲解单文件 HTML

> 本文件是给 AI agent 的执行指令。人类读者请看 [README.md](README.md) 与
> [docs/workflow.md](docs/workflow.md)，不需要读这里。

把一份课件 PDF 变成「左看讲解、右对原文」的单文件 HTML。默认产出：自包含 `.html`、
断网可开、公式正常渲染、每页有缩略图与页码跳转。

## 🛑 第 0 步（强制）：先问清四件事，再跑任何脚本

第一次接手一份课件，第一个动作必须是 `AskUserQuestion` **一次问完**下面四件，别分多轮挤牙膏。
这四件没确认前，不许跑 `run_all.py` / `init_project.py` / `prepare_pdf.py`，也不许写 `content/`。
（唯一例外：用户同一句话已交代清楚——那也要先用一句话复述理解再开工；用户说「你看着办」时
自己拍板，但必须把拍板结果明说。）

| # | 问题 | 选项（推荐项第一） |
|---|---|---|
| 1 | 单文件还是多文件？ | 单文件（推荐）／多文件（index.html + katex/ + img/） |
| 2 | 「打开原文件该页」怎么做？ | 绝对路径深链（默认，仅本机）／与产物同目录走相对路径／embed_pdf 内嵌（体积 = PDF × 1.34） |
| 3 | 纯图页怎么处理？ | 详细讲解图示（推荐）／只放缩略图／跳到下一段 |
| 4 | 大纲与正文不一致怎么办？ | 正文保持原序、缺的另立补充篇放最后（推荐）／按大纲重组 |

> 前两件事后改要**重建整个产物**，所以先问。补充项（有则问，无则用默认并说明）：
> 是否完全离线（默认是，走内嵌 KaTeX，**别改 CDN**）；读者定位（零基础／补细节／考前速查）；
> 讲解深度（逐页详讲／抓重点）。

问完把四项决定用一句话写进回复，再开始执行。

## 🧭 两条路线：结构从哪来

| 路线 | 分段依据 | 适用 | 怎么走 |
|---|---|---|---|
| **A · 语义**（推荐） | 先巡读全课件，按内容语义定分节，用户确认后才写内容 | 正式交付、结构重要、首页自带目录 | 下面「三步走」 |
| **B · 机械** | 靠 PDF 书签 / 页数切段 | 只想快速看效果、结构简单 | 直接跑 `run_all.py`（见「入口」） |

结构重要的课件一律走 A。原因一句话：B 在「读内容之前」就把分段焊死，页标题会抓到公式/人名、
作者的分段会被按页数硬切碾碎——这些坑只有先读内容才能避开（详见 docs/workflow.md「两条路线」）。

### A 路线三步走

```bash
KIT="$(cd "$(dirname "$0")" && pwd)"
PY="$(command -v python || command -v python3)"

# ① 巡读结构：渲染逐页图 + 产出 outline 草案（不建骨架、不构建）
"$PY" "$KIT/scripts/run_all.py" "<课件.pdf>" --out "<项目目录>" --stage plan

# ② 【agent】逐页看图 + 填语义 + 给用户确认（硬闸门，见下）
#    —— 编辑 <项目目录>/_plan/outline.json，把 _todo 项全部填掉

# ③ 按确认过的结构建骨架 + 跑完整流水线
"$PY" "$KIT/scripts/init_project.py" "<课件.pdf>" --out "<项目目录>" \
      --outline "<项目目录>/_plan/outline.json"
"$PY" "$KIT/scripts/run_all.py" "<课件.pdf>" --out "<项目目录>" --skip-init
```

**② 是硬闸门，不许跳过：**
1. 逐页 Read `_extract/page-NN.png`（`--stage plan` 已渲染好）；
2. 逐条处理 outline 里的 `warnings`——存疑页**必须**看图复核，不许当噪音忽略；
3. `sections[].name` 改成语义段名，`sections[].toc_label` 填「N · 段名（P起–P止）」；
4. 把 outline 拿给用户确认，确认后 `confirmed=true`、`confirmed_by` 填确认人；
5. 结构一旦确认**不再轻改**，要改就整轮重跑（分片文件名、锚点全会变）。
   **注意：带 `--force` 重建骨架会覆盖 `content/` 里已写好的讲解——动手前必须先备份 `content/`**，
   迁移办法：从备份按 `<section class="pg" id="pNN">` 抽取各页讲解，填回新分片。

## ⚡ 换新课件入口（B 路线 / 结构简单时）

需求确认后一条命令把机械部分全做完（建骨架 → 渲染 → 组装 → 四项体检 → 截图）：

```bash
KIT="$(cd "$(dirname "$0")" && pwd)"
PY="$(command -v python || command -v python3)"
"$PY" "$KIT/scripts/kitpath.py"                          # 先自查环境
"$PY" "$KIT/scripts/run_all.py" "<课件.pdf>" --out "<输出目录>"
```

跑完得到 `config.json` + `content/`（带 TODO 的逐页骨架）+ `_extract/`（逐页图/缩略图）+
`_katex/` + 单文件 HTML；⑦ 报「待补页面 N/M」，目标是 0。

**剩下唯一一步：逐页看图写讲解。** 改完 `content/` 复检（跳过建骨架与渲染，快得多）：

```bash
"$PY" "$KIT/scripts/run_all.py" "<课件.pdf>" --out "<同一目录>" --skip-init --skip-prepare
```

## 逐页写讲解的硬规则（写 content/ 时必守）

- 每个分片是若干 `<section>` 的拼接（**不是完整页面**），供 build.py 拼进外壳。
- 逐页区块骨架（可复制 `examples/section-template.html`）：
  ```html
  <section class="pg" id="p12" data-page="12">
    <div class="pg-head">
      <span class="pg-badge">原文件 P12</span>
      <h3>English Title <em>中文副标题</em></h3>
      <a class="pdf-link" data-page="12">打开原 PDF 该页 ↗</a>
    </div>
    <div class="pg-text"> …讲解… </div>
    <!-- 缩略图由 build.py 自动注入，不要手写 -->
  </section>
  ```
  `id="pNN"` 与 `data-page="N"` 是硬要求（build.py 靠它匹配缩略图）。
- 公式两种写法：`<script type="math/tex">行内</script>`、
  `<script type="math/tex; mode=display">独立</script>`（script 内容按原文本解析，反斜杠不用转义）。
- 中文别写进 `\text{}`（KaTeX 无 CJK 字体），中文注释用 `<span class="gloss">（…）</span>` 放公式后。
- 数学 `#` 必须写 `\#`。
- 正文矢量用 `<b class="vec">J</b>`，**禁止**组合箭头 U+20D7（中文字体栈无此字形 → 方框）。
  目录标签里的也要改；JSON 字符串里 HTML 属性用**单引号**：`"<b class='vec'>J</b>"`。
- 别用 `&oiint;` `&iint;` 等非 HTML5 命名实体（浏览器不解码，原样显示）——直接写字符或放 KaTeX。
- 四种提示框：`.tip` 绿=直觉、`.note` 蓝=补充、`.flag` 红=原稿问题、`.quote` 灰=原文引用。
  新增的解释放 `.note`/`.tip`，并在文首说明「灰底卡片是补充内容」。
- 每个大节开头放一张「本节概述」卡（见 `examples/section-template.html`）；分片按节切，
  概述卡单独成 `NN_ovN.html`，紧跟其后的正文分片同序号。
- 分片只放 `<section>`，**不放 `<footer>`**（页脚由外壳统一生成，否则出现两个）。
- 零基础读者：开头加 `.card.primer` + `<details class="pill">` 折叠卡补前置知识。

**内容质量标准**（这个技能的价值所在，别只做翻译）：
1. 每页先说「这页在干什么」再讲细节。2. 结论前置。3. 补原文跳过的推导（放 `.note`）。
4. 指出原稿问题（放 `.flag`）。5. 跨页串联伏笔与回收。6. 结尾给全文脉络 + 一页速查表。

## 验证与交付

改完内容必须三校验 + 截图。`run_all.py` 的 ④–⑧ 已自动跑；手动复检或单独重跑：

```bash
node  "$KIT/scripts/check_math.js" "输出.html" "_katex/katex.min.js"     # 公式/标签配对/目录锚点/缺字/TODO
"$PY" "$KIT/scripts/check_ui.py"   "输出.html"                             # 四类交互接线
"$PY" "$KIT/scripts/probe.py"      "输出.html" "$KIT/scripts/probe_marks.js"  # 标记回归（DOM 断言）
"$PY" "$KIT/scripts/probe.py"      "输出.html" "$KIT/templates/probe_doc.js"  # 待补页面=0、断链、缺字
"$PY" "$KIT/scripts/shot.py"       "输出.html" "_extract/shot.png"          # 截图看长相
```

各脚本管什么、不管什么见 [README.md](README.md)「三重校验」。动了标记相关代码时 `probe.py`
一行不能省（截图看不出 `<mark>` 里多出的空块级元素）。

**套件自检**（验证套件本身没坏）：`"$PY" "$KIT/scripts/selftest.py"`，期望结尾「自检结果: PASS」。

## 铁律

1. **不许跳过逐页看图。** 抽象文字层的课件先渲染再读，否则必然讲错公式。
2. **不许没验证就交付。** 公式自检 + 至少 3 张截图，缺一不可。
3. **忠于原文件顺序。** 页码/标题/公式位置不得擅调；补充内容单独成篇并标明。
4. **新增内容显式标注。** 读者要一眼分清「原文有什么」与「讲解者加了什么」。
5. **原稿问题如实标注**并给处理说明，不静默修正。

## 参考资料

- `references/content-quality.md` — 讲解质量验收标准（写讲解照着它）。
- `references/pitfalls.md` — 踩坑清单，动笔前先扫一遍（含本机环境备忘、标记交互、迁移）。
- `examples/config.example.json` / `examples/section-template.html` — 可复制骨架。
- `README.md` / `docs/workflow.md` — 原理、手工分步、目录结构（人看）。
- 改 `assets/`/`scripts/`（套件本身）时的纪律见 `README.md`「改这个套件时的纪律」。
