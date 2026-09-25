---
name: pdf-slides-annotated-html
description: >-
  把 PDF / PPT 课件、讲义、论文投影片做成「逐页对照讲解」的单文件 HTML：左侧两级可折叠目录、
  每页配原页缩略图（可收起侧栏让缩略图自动放大）、关键公式用 LaTeX 排版、完全离线可打开，
  并支持在正文里划词标记 → 汇入「我的标记」笔记抽屉（可备注、定位、导出）。
  适用于：课件逐页精解、PDF 转讲解文档、教材/讲义中文注释、生成便于对照原文阅读的 HTML、
  把 slide 变成可检索可批注的学习笔记。
  内置四段流水线：① PDF 渲染成图 + 文字层（不靠 get_text 抽公式）；② KaTeX 字体内嵌（离线公式）；
  ③ 配置驱动组装单文件（目录/缩略图/深链/笔记命名空间自动注入）；④ 公式语法 + 结构接线 + 无头截图三重校验。
  触发词：逐页讲解、逐页精解、对照原文件、PDF 转 HTML 讲解、课件解析、讲义讲解、
  公式用 LaTeX、离线 HTML、划词标记、笔记、目录折叠、annotated slides、slides to html。
agent_created: true
---

# PDF / PPT 课件 → 逐页对照讲解单文件 HTML

> **你是人类读者？** 请先看 [README.md](README.md)（含「让 AI 替你做」的使用方式）与
> [docs/workflow.md](docs/workflow.md)（完整流程讲解）——不需要读本文件。
> 本文件是给 AI agent 的执行指令：怎么问清需求、怎么逐页看图写讲解、怎么验证交付。

把一份几十页的课件（PDF）变成「左看讲解、右对原文」的单文件 HTML。
**默认产出**：一个自包含的 `.html`，断网可开，公式正常渲染，每页有原页缩略图与页码跳转。

## ⚡ 换一份新课件：先跑这个（套件入口）

**拿到一份没做过的课件时，第一步不是手工建目录，而是跑 `run_all.py`。**
它会把「机械部分」全部做完，并直接告出「还差多少页没写讲解」：

```bash
# 套件目录：本文件所在目录就是 KIT（整个目录可任意搬迁）
KIT="$(cd "$(dirname "$0")" && pwd)"        # 或直接写套件实际路径
PY="$(command -v python || command -v python3)"

# 先自查环境（python / node / 浏览器 / pymupdf / pillow 是否就位）
"$PY" "$KIT/scripts/kitpath.py"

# 一条命令：建骨架 → 渲染逐页图+缩略图 → 组装单文件 → 四项体检 → 截图
"$PY" "$KIT/scripts/run_all.py" "<新课件.pdf>" --out "<输出目录>"
```

> **可迁移**：套件内所有脚本都用**相对自身位置**定位资源，不含任何写死的用户名或安装路径。
> `node` 与浏览器按「环境变量 → PATH → 常见安装位置」自动探测；
> 探测不到时用 `KIT_NODE` / `KIT_BROWSER` 指定，或先跑 `scripts/kitpath.py` 看诊断。
> Python 依赖只有两个（`pymupdf`、`pillow`，仓库根目录 `pip install -r requirements.txt` 一把装齐），
> 缺了会给出 `pip install` 命令而不是报 `ModuleNotFoundError`。

跑完你会得到：`config.json` · `content/`（封面/概述卡/逐页骨架/收尾，含 TODO 标记）·
`_extract/`（`page-NN.png` 逐页核对用 + `thumb_NN.jpg`）· `_katex/`（套件自带的离线 KaTeX，
**不需要联网**）· 单文件 HTML · `README-项目.md`（含待补清单）。

**剩下的唯一一步是人（或 agent）的工作：逐页看图写讲解。**
`run_all.py` 的 ⑦ 会报 `内容进度：待补页面 N / M`，目标是 **0**。
质量标准见 `references/content-quality.md`。

改完 `content/` 复检（跳过建骨架与渲染，快得多）：

```bash
"$PY" "$KIT/scripts/run_all.py" "<新课件.pdf>" --out "<同一目录>" --skip-init --skip-prepare
```

**验证套件本身没坏**（现造一份 6 页小 PDF，把整条流水线从零跑一遍）：

```bash
"$PY" "$KIT/scripts/selftest.py"        # 期望结尾「自检结果: PASS」
```

| 脚本 | 作用 |
|---|---|
| `scripts/run_all.py` | **主入口**：一键流水线（上述 ①–⑧） |
| `scripts/kitpath.py` | **环境自查**：报告 python / node / 浏览器 的位置 + `pymupdf`/`pillow` 是否就位（换机器先跑它） |
| `scripts/init_project.py` | 只建骨架（可单独用；`--group-by` 控制分段策略） |
| `scripts/selftest.py` | 套件自检（合成 PDF → 跑全流程 → 断言），不依赖任何已有项目 |
| `scripts/probe.py` | 无头跑探针 JS 并读回结果（DOM 断言；截图看不到「结构坏没坏」） |
| `scripts/probe_marks.js` | 标记功能回归（跨格/跨段/跨公式/单段 + 重开恢复） |
| `templates/probe_doc.js` | 交付体检（内容进度 / 缩略图一致性 / 断链 / P？残留 / 正文缺字 / 非法实体） |
| `scripts/glyph_probe.py` | **正文符号探针**：把成品里的非中文符号排成一页，肉眼查缺字（tofu）。「公式里正常、正文里方框」时先跑它 |

**模板规范（改 `templates/` 时必守）**：HTML 注释里**不要写任何字面标签**
（`<section>` / `</section>` 之类）—— `build.py` 用非贪婪正则匹配整段区块，
注释里的假标签会让它提前收尾，症状是「图在文件里、但 DOM 里查不到」，极难排查。
详见 `references/pitfalls.md` 第 30 条。

## 产物自带的四类交互（都已实现，改内容时别把它们改坏）

| 能力 | 实现要点 |
|---|---|
| **① 目录逐级折叠** | `config.groups` 递归 → 嵌套 `.toc-group` + `.toc-toggle` 按钮；`.gcount` 显示该组下页码数；「展开全部／折叠全部」；折叠状态存 localStorage；搜索时自动展开命中分支 |
| **② 每小节一张「本节概述」卡** | 正文里放 `<section class="card overview" id="ovN">`，用 `.ov-kicker / .ov-range / .ov-grid / .ov-item / .ov-questions / .ov-chips` 类；每个大节一张，放在该节第一页之前 |
| **③ 侧栏收起 + 缩略图自动放大** | 顶栏 `#navToggle` 给 `body` 加 `.nav-hidden`；CSS 里 `.pg` 的缩略图列由 **268 px → 400 px**，容器 `max-width` 由 1000 px → 1220 px。实测已确认列宽真的变了（`check_ui.py` 会验） |
| **④ 划词标记 → 笔记抽屉** | 选中正文任意文字 → 加入 `#drawer` 抽屉（列表项 `.note-item` + 备注 `.note-input`）；支持 `跳转 / 删除 / 导出 Markdown / 清空`；找不到原文的条目标 `.ni-stale`；数据存 localStorage，**用 `DOC_NS` 按文档隔离**。**位置徽标**：有页码的页显 `P12`，没页码的卡片按 `locOf()` 算可读位置，**不显示「P？」** |

**快捷键**：`J`/`K` 翻页 · `M` 标记选中 · `B` 侧栏 · `T` 缩略图 · `N` 笔记 · `Esc` 关闭。

### 标记相关：只在改 `assets/site.js` 时才需要读

> **做新课件时这段完全用不到**（你不碰 `site.js`）。要改套件的标记逻辑时再看，
> 每条都对应一个真实事故，完整复盘在 `references/pitfalls.md`。

- **上色只许动文字节点，绝不搬元素**（§26）。`surroundContents` 跨元素抛
  `InvalidStateError`，退回 `extractContents` 会把 `<p>`/`<td>` 克隆进行内 `<mark>`
  → 标记处多换行、表格散架。正确路径：`leafSegments()` → `blockAncestor()` 分组 →
  `wrapGroup()` 二分收敛。**任何 mark 里出现块级元素就是坏了**（`audit()` 的
  `blockInsideMark` 盯的就是它）。
- **存与找必须同源**（§27）。`Selection.toString()` 在块级边界插 `\n`、单元格边界插 `\t`，
  `TreeWalker` 拼接却不带分隔符 → 重开后必然「定位失效」。统一走 `projOf()` 的可见文本投影。
- **公式只认看得见的那一份**（§27）。KaTeX 同一串公式在 DOM 里有 2–3 份
  （`.katex-mathml` / `annotation` / `.katex-html`），投影必须跳过隐藏副本。
- **位置标签要兜底**（§29）。没页码的卡片（概述卡/封面/速查表）由 `locOf()` 算可读位置，
  不许显示 `P？`；没 id 的顶层 section 由 `ensureSectionIds()` 按文档序补 `sec-<n>`
  （文档静态，编号稳定，可当 pid 用）。
- **三条入口别简化掉**（§21）。Edge 的选区迷你菜单由浏览器 UI 层绘制，页面 `z-index`
  压不住。所以同时上：工具条避让到选区下方 + 顶栏 `#markBtn`/快捷键 `M` +
  有选区时接管右键（菜单里**必须留「复制」**，`Shift+右键` 放行系统菜单）。
- 一条笔记可能对应多个 `<mark>`（跨格/跨段按块拆开），取 mark 一律用
  `mark.hl[data-nid="…"]` 全量选择。重叠标记会嵌套，**是正常现象**（§28）。

**调试入口 `window.__doc`**（无头探针与手工排查共用）：
`audit()` · `structAudit(pid)` · `traceWrap(on)` + `lastTrace()` · `locOf(pid)` ·
`addNote(pid, 原文, 备注)` · `openDrawer()` · `exportMd()` · `clearNotes()`。

---

## 开工前必须问清的三件事

用户明确说「不清楚的先问我」时立刻问；没说也要问，因为这三点决定返工成本：

1. **单文件还是多文件？** 单文件的代价是体积（含 60 张缩略图约 3–5 MB），
   好处是能随便挪、能离线发。多文件（`index.html` + `katex/` + `img/`）体积小得多。
2. **纯图页怎么处理？**（几乎每份课件都有几页只有插图、没几个字）
   建议「详细讲解图示内容」，但要确认。
3. **大纲与正文不一致时怎么办？**（常见：大纲列了 5 个主题，正文只讲了 3 个）
   建议「正文严格保持原顺序，缺的部分作为补充篇章放最后，不占原页码」。

如果用户要求「完全离线」，确认公式渲染走内嵌 KaTeX 而不是 CDN。

**「打开原文件该页」怎么做**（默认生成的是绝对路径 `file:///D:/…pdf#page=N`，**换设备必失效**）：
两条路，开工时就要问清，事后改要重建整个产物 ——
① 让用户把原 PDF 与本文件放同一目录，链接改用相对路径；
② 在 config 里设 `"embed_pdf": true`，把原 PDF 整个 base64 内嵌进 HTML
（体积 = PDF 大小 × 1.34；点击时惰性解码成 `blob:` 打开并拼 `#page=N`，另给「另存原 PDF」按钮）。
注意 `#page=N` 在 `blob:` 上能否生效**无法在无头环境验证**（headless 不加载 PDF 阅读器插件），
要么让用户点一次确认，要么直接上 pdf.js；兜底是打开时用 toast 报出页码。

---

## 分步流程（想手工一步步做时才看；平时直接跑 `run_all.py` 就够了）

```
① prepare_pdf.py   →  page-01.png（逐页目视核对用）+ thumb_01.jpg（内嵌用）+ raw.txt
② 逐页读图 + 写讲解 →  content/xx.html（分片，纯 HTML 片段）
③ build.py         →  单文件 HTML
④ 验证            →  check_math.js + check_ui.py + probe.py + shot.py
```

> KaTeX **不用自己造**：套件自带 `vendor/katex/`（字体已内嵌的 CSS + 引擎），
> `init_project.py` 会直接拷进项目的 `_katex/`，全程不联网。
> 只有想换 KaTeX 版本时才需要跑 `scripts/katex_offline.py`。

### ① 准备素材

```bash
PY="$(command -v python || command -v python3)"
SK="<套件目录>"          # 即 pdf-slides-annotated-html 所在目录，可任意搬迁

"$PY" "$SK/scripts/prepare_pdf.py" "<课件.pdf>" "_extract" 860 75
```

输出 `_extract/report.txt` 先看一遍：页数、哪些页含图片对象、缩略图总体积是否合理。
**缩略图总宽建议 860–900 px / quality 75**（680 px 放大后会糊，1200 px 体积翻倍不值）。

### ② 逐页读图，写讲解（最花时间的一步，不能省）

**必须用 Read 工具把 `page-01.png … page-NN.png` 逐页看一遍。**
只读 `raw.txt` 一定会讲错公式 —— PPT 导出的 PDF 里数学符号字体映射常常是坏的
（`¡` 可能是减号、`¼` 可能是 π），详见 `references/pitfalls.md` 第一节。

写讲解时遵守这些约定：

- **HTML 片段，不是完整页面。** 每个分片是若干 `<section>` 的拼接，供 build.py 拼进外壳。
- **逐页区块固定骨架**（`examples/section-template.html` 有可复制模板）：
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
  `id="pNN"` 与 `data-page="N"` 是**硬要求**，build.py 靠它们匹配缩略图。
- **公式两种写法**：
  `<script type="math/tex">行内</script>` 与
  `<script type="math/tex; mode=display">独立成行</script>`。
  好处是 script 内容按原始文本解析，反斜杠花括号都不用转义。
- **中文不要写进 `\text{}`**（KaTeX 字体没有 CJK）。中文注释用
  `<span class="gloss">（样本均值）</span>` 放在公式后面。
- **数学里的 `#` 必须写成 `\#`**（TeX 里 `#` 是宏参数符）。
- **正文里的矢量（还有目录标签里的）一律用加粗，禁止用组合箭头 `U+20D7`**：
  写 `<em><b class="vec">J</b></em>`，**不要**写 `<em>J</em>` 后面跟一个 U+20D7
  （即 `J` 与组合箭头挤在同一个文字节点里，肉眼看着像「J 加箭头」）。
  `U+20D7` 属于「符号用组合附加记号」（U+20D0–U+20FF），
  **中文字体栈（PingFang SC / Microsoft YaHei / Source Han Sans / Noto CJK）普遍没有
  这个字形**，浏览器回退不到任何字体 → 直接渲染成方框（tofu）。
  公式区没这个问题（走 KaTeX 自带字体），所以只在正文里踩。
  同类写法：`<b class="vec">E</b><sub>ne</sub>`、`⟨<b class="vec">v</b>⟩`。
  `config.json` 的目录标签也要一起改（build.py 原样注入，标签能生效）；
  但 **JSON 字符串用双引号包着，所以那里的 HTML 属性要用单引号**：
  `"<b class='vec'>J</b>"`。`check_math.js` 的 ⑧ 会硬性拦住漏改的。
- **别用非 HTML5 的命名实体**：`&oiint;` `&iint;` `&iiint;` `&oint;` 这些只存在于
  MathML/LaTeX，**不在 HTML 实体表里**，浏览器不解码，会原样显示成「&oiint;」这串字面文本。
  要么直接写字符本身（`∯` `∬`，本机字体都有字形），要么放进 KaTeX 公式。
  `probe_doc.js` 会用真实解析器逐个试出来。
- **四种提示框**：`.tip` 绿=直觉/正面、`.note` 蓝=补充说明、`.flag` 红=警告/原稿有问题、`.quote` 灰=原文引用。
  凡是本文档新增的解释，都放 `.note` 或 `.tip` 里并在文首说明「灰底卡片是补充内容」。
- **面向零基础读者**时，开头加一段 `<section class="card primer" id="primer">`，
  用 `<details class="pill">` 折叠卡补前置知识（概率、导数、向量点积之类）。
  公式里出现新符号时，在讲解里先翻译成人话再用。
- **每个大节开头放一张「本节概述」卡**（需求 ②，别漏）：
  ```html
  <section class="card overview" id="ov2">
    <span class="ov-kicker">本节概述 · 第二节</span>
    <h2>这一节在讲什么<em>English Title — 一句副标题</em></h2>
    <p class="ov-range">覆盖原文件 P9–P39 ｜ 31 页 ｜ 建议 60 分钟</p>
    <p class="lead">三句话说明这一节的地位与它和前后节的连接。</p>
    <div class="ov-grid">
      <div class="ov-item"><h5>核心问题</h5><ul>…</ul></div>
      <div class="ov-item"><h5>读完应能</h5><ul>…</ul></div>
    </div>
    <div class="ov-chips"><span class="chip-label">本小节页面</span><a href="#p09">P9</a>…</div>
  </section>
  ```
  **分片按节切**，概述卡单独成文件，命名 `NN_ovN.html`，紧跟其后的正文分片同序号
  （如 `20_ov2.html` + `21_p09_p15.html` + `22_...`）。`config.shards` 按顺序列出即可。
- **分片只放 `<section>`，不要放 `<footer>`。** 页脚由外壳模板统一生成，
  正文自带一份就会在页面上出现两个（这个坑真踩过）。

**内容质量标准**（这是这个技能的价值所在，别只做翻译）：

1. **每页先说「这页在干什么」**，再说细节。
2. **把结论前置。**
3. **补原文跳过的推导**（放进 `.note`），例如「这一行是怎么从 Sigmoid 变出来的」。
4. **指出原稿的问题并如实标注**（遮挡、写错、配色矛盾），而不是假装没有。
5. **跨页串联**：前后页的伏笔与回收要显式点出来（「这正是第 47 页要证明的」）。
6. **结尾给全文脉络与一页纸速查表**，方便复习。

### ③ 组装 + 验证

> **平时不需要跑 `katex_offline.py`** —— 套件已带 `vendor/katex/`，`init_project.py` 会自动
> 拷进项目 `_katex/`。只有想升级 KaTeX 版本时才：`"$PY" "$SK/scripts/katex_offline.py" "_katex" [版本号]`
> （联网从 npmmirror 拉 tgz，把 woff2 转成 data URI；产出约 400 KB CSS + 275 KB JS，
> 生成后把两份文件放回 `vendor/katex/` 就能跟着套件一起迁移）。

写一份 `config.json`（照 `examples/config.example.json` 改），然后：

```bash
"$PY" "$SK/scripts/build.py" "config.json"
node "$SK/scripts/check_math.js" "输出.html" "_katex/katex.min.js"   # 公式语法 + 标签/锚点/数量
"$PY" "$SK/scripts/check_ui.py"  "输出.html"                        # 四类交互的「接线」是否完好
"$PY" "$SK/scripts/shot.py" "输出.html" "_extract/shot.png"         # 首屏
"$PY" "$SK/scripts/shot.py" "输出.html" "_extract/v_ov2.png"  --section ov2    # 概述卡
"$PY" "$SK/scripts/shot.py" "输出.html" "_extract/v_nav.png"  --section p52 \
       --script harness_nav.js                                     # 侧栏收起后缩略图变大
"$PY" "$SK/scripts/shot.py" "输出.html" "_extract/v_note.png" --section p53 \
       --script harness_markshot.js --profile notetest               # 标记 + 笔记抽屉
"$PY" "$SK/scripts/probe.py" "输出.html" "$SK/scripts/probe_marks.js"  # 标记功能回归（DOM 断言）
```

三重校验各管一段，**必须都过**：

| 脚本 | 管什么 | 不管什么 |
|---|---|---|
| `check_math.js` | 公式能不能渲染、CJK 有没有混进公式、标签配对、目录锚点、缩略图/区块/深链数量、**正文缺字（组合符号 U+20D0–U+20FF，硬失败）**、TODO 残留 | 长相、交互 |
| `check_ui.py` | 四类交互的 DOM 与 CSS/JS 是否对齐（分组数与按钮数相等、收起后列宽真的变大、抽屉与选择条元素齐全、`DOC_NS` 已注入、第 ⑧ 节专盯标记上色的结构安全） | 长相、实际行为 |
| `shot.py` | 长相与真实交互状态 | 细节正确性 |
| `probe.py` + `probe_marks.js` | **结构有没有被改坏**：自动找跨格/跨段/跨公式/单段四种选区，用**真实入口**标记后断言「块级元素数、可见文本、表格 tr/td 一字不变、无块级元素进 mark、无零宽 mark」，再拆掉全部 mark 重新定位一遍复查 | 长相 |

**截图看不出结构被改坏**（表格散架看截图看得出来，`<mark>` 里多了一个空 `<p>` 看不出来），
所以只要动了标记相关代码，`probe.py` 这一行不能省。

**`shot.py --script` 的用法**（触发交互后再截图，否则只能截到静态首屏）：

```js
// harness_nav.js
var st = document.createElement('style');
st.textContent = '.drawer,.toc,.selbar{transition:none!important}';  // 关键！见 pitfalls
document.head.appendChild(st);
window.addEventListener('load', function () {
  setTimeout(function () { document.getElementById('navToggle').click(); }, 700);
});
```

```js
// 片段示意（不是文件）：用页面自带的调试接口造几条标记
window.addEventListener('load', function () {
  setTimeout(function () {
    var d = window.__doc;                       // 页面暴露的测试入口
    d.addNote('p53', '要标记的原文片段', '我的备注');   // 传"看得见的"文字即可，内部走同一套投影口径
    d.openDrawer();
  }, 900);
});
```

```js
// 片段示意（不是文件）：想截「真实入口」造出来的标记（跨单元格那种最典型）：
// 造 Range → selection.addRange → dispatchEvent(new MouseEvent('mouseup',{bubbles:true}))
//   → document.querySelector('.selbar.on button[data-act="mark"]').click()
// 现成可用的版本在 templates/harness_markshot.js（不依赖具体课件内容，自己找选区）。
// 验证「重新打开页面后仍然划线」用两次 shot.py + 同一个 --profile：
//   第 1 跑做标记，第 2 跑只读（boot 里的 restoreAll 会自动重建高亮）。
```

造标记时**取词要取真实可见文本节点**（跳过 `.pg-head` 和 `.katex-mathml`，否则会拿到公式源码）；
`addNote` 内部会走和真实入口同一条 `locate → canon → wrapRange` 路径（历史上这里分叉过一次，
导致「测试全绿、真实入口红」，见 pitfalls 第 23 条）。其余调试入口见上文「标记相关」一节。

最后把可重建的目录结构留给用户（`content/` + `config.json` + 脚本），并在回复里说明怎么重新生成。

---

## 目录结构（推荐）

```
项目/
├─ 输出.html                  ← 交付物（单文件）
├─ config.json                ← build.py 的输入（含递归 groups、shards、pages）
├─ content/                   ← 讲解分片，按节切；只放 <section>，不放 <footer>
│   ├─ 00_intro.html          （封面 + 使用说明 + 前置知识 + 全文脉络）
│   ├─ 10_ov1.html            （第一节课概述卡）
│   ├─ 11_p01_p08.html        （第一节正文）
│   ├─ 20_ov2.html  21_..  22_.. 23_..
│   ├─ 30_ov3.html  31_..
│   ├─ 40_ov4.html  41_..
│   ├─ 50_ov5.html  51_extra.html
│   └─ 60_outro.html          （速查表 + 术语表 + 关于本文档）
├─ _extract/                  ← prepare_pdf.py 的产物
│   ├─ page-01.png …          （逐页图，核对用，交付后可删）
│   ├─ thumb_01.jpg …         （内嵌用，必须留）
│   └─ raw.txt  chroma.txt  report.txt
└─ _katex/                    ← 离线 KaTeX（可跨项目复用）
```

---

## 视觉规范（`assets/` 下四个文件，build.py 自动内联）

- `shell.html` —— 页面骨架（顶栏 / 目录栏 / 笔记抽屉 / 灯箱 / 脚本位），
  里面是 `__TOC__`、`__BODY__`、`__KATEX_CSS__`、`__DOC_NS__` 等占位符。
  **改版式改这里，不要改 build.py。**
- `site.css` —— 基础版式（封面、卡片、逐页 grid、提示框、表格、灯箱…）。
  里面的 `.vec`（`.vec{font-weight:700;font-style:inherit}`）是**正文矢量符号**的统一写法，
  配合 `<b class="vec">J</b>` 使用；**不要**用组合箭头 U+20D7（会渲染成方框，见 pitfalls 第 34 条）。
- `site.extra.css` —— 四类交互的追加样式（`.toc-toggle`、`.ov-*`、`.selbar`、`.drawer`、`.ni-*`、
  `body.nav-hidden` 下的列宽覆写）。**两个 CSS 都会内联，漏一个交互就会「裸奔」。**
- `site.js` —— 全部交互逻辑，暴露 `window.__doc` 供无头测试。

- **浅色主题**：底 `#f2f4f9`、卡片白、主色 `#2f4fd0`、强调红 `#b8352a`。
  若当前 IDE 是深色主题，需改两个 CSS 顶部的 `:root` 变量组。
- 版式：左侧固定 296 px 目录栏 + 主内容区最大 1000 px；逐页区块用 grid
  （正文 + 右侧 268 px 缩略图，缩略图 `position:sticky` 跟随阅读）；
  侧栏收起后缩略图列变 400 px、容器变 1220 px。
- 打印样式已写：自动隐藏侧栏、抽屉、缩略图与笔记按钮，卡片避免跨页断开，
  标记高亮带 `print-color-adjust:exact` 所以能打印出来。

---

## 铁律

1. **不许跳过逐页看图。** 抽象文字层的课件一律先渲染再读，否则必然讲错公式。
2. **不许在没有验证的情况下交付。** 公式批量自检 + 至少 3 张截图，缺一不可。
3. **忠于原文件顺序。** 页码顺序、标题、公式位置不得擅自调整；要补充的内容单独成篇并标明。
4. **新增内容必须显式标注。** 读者要能一眼分清「原文有什么」和「讲解者加了什么」。
5. **原生问题如实标注并给处理说明**，不要静默修正。

---

## 参考资料

- `references/content-quality.md` —— **讲解质量验收标准**（唯一不能自动化的部分，换课件照它写）。
- `references/pitfalls.md` —— 踩坑清单，**动笔前先扫一遍**（含本机环境备忘）。
  第 21–23 条是标记交互，第 26–28 条是 2026-09-24 修的「结构被搬坏 / 重开后定位失效 / 嵌套标记」，
  第 30 条是注释里字面标签，第 32 条是迁移（路径 + Python 依赖），第 33–35 条是零宽字符 / 组合箭头 / 自检静默。
- `examples/config.example.json` —— build.py 的完整配置样例（递归 `groups`）。
- `examples/section-template.html` —— 逐页区块 / 概述卡 / 封面 / 补充篇 / 速查表的可复制骨架。
- `scripts/probe.py` —— 无头跑一段探针 JS 并把结果读回来（`shot.py` 只能出图，读 DOM 靠它）；
  `--profile 名字` 复用 profile 就能测「重新打开页面」这类持久化路径。
- `scripts/probe_marks.js` —— 标记功能回归探针（自动找跨格/跨段/跨公式/单段选区 + DOM 结构断言）。
- `assets/shell.html`、`assets/site.css`、`assets/site.extra.css`、`assets/site.js` ——
  已验证的外壳、样式与交互，build.py 自动内联。

## 改这个技能时的五条纪律

1. **先看 mtime。** `assets/` 与 `scripts/` 可能是别的会话刚更新过的（本技能确实被并行会话
   改进过：`site.extra.css`、`check_ui.py`、`shot.py` 的短路径修复都是后来加的）。
   覆盖前先 `find <技能目录> -type f -printf '%TY-%Tm-%Td %TH:%TM %s %P\n'`，
   不要凭记忆假定文件内容。
2. **改完必须「重建 + 三校验 + 截图」四连**，并且把重建产物与旧产物做 diff。
   目录块应当逐字节一致——不一致就说明生成逻辑被动过，先查清再提交。
3. **资产是耦合的。** 改 `shell.html` 的类名就要同步改 `site.extra.css` 与 `site.js`；
   只改一处，页面要么裸奔要么交互失效。`check_ui.py` 就是为防这个而写的。
4. **不许写死本机路径，也不许让依赖变成黑盒。** 套件要能整体打包迁移，所以：
   - 脚本内部定位资源一律用 `HERE = os.path.dirname(os.path.abspath(__file__))` 往上推；
   - 「外部程序在哪」一律问 `scripts/kitpath.py`（环境变量 → PATH → 常见安装位置）；
   - 新增第三方 Python 包时，在 `kitpath.PY_DEPS` 里登记，并在脚本顶部用
     `kitpath.require_deps(...)` 包一层（别裸 `import pymupdf`，缺包时报错看不出要装什么）；
   - 文档里的命令示例用 `command -v python` 与 `<套件目录>` 占位，**不要**贴本机绝对路径；
   - 校验：`grep -rn "/home/\|/Users/\|C:/Users/" scripts/ assets/ templates/` 应当无命中
     （`references/pitfalls.md` 的「本机环境备忘」一节除外，那是刻意记录的环境事实；
     文档里只允许出现 `<用户名>` 这类占位符，**不要**写真实用户名）。
   - 改动后跑一次**迁移验证**：把套件拷到别处并改名，从新位置跑 `selftest.py` 应仍 PASS。
5. **模板注释里不许出现字面标签**（`<section>` / `</section>` 之类）。
   `build.py` 用非贪婪正则匹配整段区块，注释里的假标签会让它提前收尾，
   症状是「图在文件里、但 DOM 里查不到」。详见 `references/pitfalls.md` 第 30 条。
