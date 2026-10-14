# Changelog

本项目所有显著变更都记录在此文件。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

> **标签约定**：Releases 页只看 SemVer 标签（`vX.Y.Z`）。形如 `v2.0-semantic-outline-stepN`、
> `v1.0-classic-pipeline` 的标签是**开发期快照**，不是正式发布，请勿当作版本号引用。

## [v2.3.0] - 2026-10-14

> 设计与施工计划见 [`docs/v2-course-collection.md`](docs/v2-course-collection.md)。
> **进度：阶段 0 ✔ ｜ 阶段 1 ✔ ｜ 阶段 2 ✔ ｜ 阶段 3 ✔ —— v2.3.0 已收尾。**
>
> ⚠ `docs/v2-course-collection.md` 于 2026-10-14 被外部写入覆盖两次（编辑器持旧缓冲区 +
> 保存时自动格式化），v2.1 正文丢失后已重新落盘。改它之前先确认没有编辑器开着。

### 新增 · 阶段 0（课程层地基）

- `scripts/coursekit.py` —— 课程层公共解析与状态判定，供 `course_*.py` 共用：
  - **讲次四态判定**（`pending` / `skeleton` / `partial` / `done`）：**纯静态**扫描产物 HTML，
    不启动浏览器。原因见 `references/pitfalls.md` 第 29 条（浏览器会静默失灵）——
    「课程地图」这种地基信息不该押在最不稳的一环上。判据与 `probe_doc.js` 同源（都认「待补」卡），
    所以课程层的完成度与单讲体检报的数字不会打架。
  - **逐页区块匹配式只看属性、不看顺序**（见下方「修复」）。
  - 路径工具：跨讲相对路径（posix）、URL 编码、Windows 8.3 短路径展开（`long_path`）。
- `scripts/course_init.py` —— 初始化 / 更新 `course.json`：
  **派生字段（标题 / 页数 / 产物路径 / 状态）每次重算直接覆盖；手写字段（课程名 / 教师 / 学期 /
  课程目标 / topics）原样保留。** 由此「写两遍必然漂移」这条病根被从结构上掐掉 ——
  想改讲次标题就改那一讲的 outline/config，改 `course.json` 也会被覆盖回来。幂等：两跑逐字节一致。

### 新增 · 阶段 1（A 侧内容层）

- `scripts/course_index.py` —— 扫各讲产物 → `_course/index.json` + `glossary.json` + `keypoints.json`：
  - **只从产物 HTML 抽，不从 `content/` 抽**（产物才是交付物，索引与它一致才有意义）；
  - **按产物 sha1 增量**：没变的讲次直接复用上次结果，14 讲重跑是毫秒级；
  - **不写时间戳**（会让每次重跑全文件变化，没法 diff）；
  - 抽取正文时先挖掉注释、`<script>`、**缩略图 base64**（不挖的话索引会从 37 KB 涨到数 MB）。
- `scripts/course_brief.py` —— 产出某一讲的「前序知识简报」`_course/briefing-LNN.md`，固定五节：
  前序讲次地图 / 术语权威表 / 概念落点索引 / **已讲预警（带分数）** / 待回收的伏笔。
  - **相似度阈值刻意没有拍板**：无论阈值多少都把 top-N 的分数打出来，让人在真实课程上先看几条再定。
    凭空定一个 0.34 很容易落到「要么全亮、要么全不亮」，那正是 pitfalls 第 44 条说的
    「一个会误报的体检比没有体检更糟」。简报里明写「默认值只是占位，尚未校准」。
  - 预警是**提示不是禁令**：写「建议回顾一句 + 指路」，不写「禁止展开」。
- `scripts/init_project.py --course <课程目录>` —— 建完骨架后自动登记进课程、刷新索引、出本讲简报。
- `templates/content-skeleton/90_outro.html` 新增 **`#keypoints`「本讲要点」卡** ——
  课程主页「要点总结页」的**唯一真源**（每讲 3–7 条，`li` 上可选 `data-at` / `data-topic`）；
  同时给术语表补了 `data-concept` 示例。`init_project.py` 的目录也加了「本讲要点」一项。
- `references/content-quality.md`：单页讲解 **五段 → 六段**（新增「跨讲串联」）、
  `.xref` 跨讲卡用法、**「本讲要点怎么写」**（含合格/不合格对照表）、
  三表分工（要点/速查/术语）、反面清单补 6 行。
- `assets/site.extra.css`：`.xref`（灰蓝底 + **虚线**左竖线，与四类提示卡的实线区分）、`.kpl` 要点列表。
- `examples/section-template.html`：补三个 `data-*`、`.xref`、`#keypoints` 的样例。

### 新增 · 阶段 2（B 侧课程合集 + 要点总结页）

- `scripts/course_site.py` —— 生成课程合集入口 `index.html`，五区块：
  **课程地图 / 要点总结 / 跨讲检索 / 术语总表 / 进度看板**。
  - **内容在 Python 侧预渲染**（不是让前端拿 JSON 画）：断网、禁用 JS、任何抓取工具都读得到全部内容，
    体检脚本也因此能对静态 DOM 下断言；JS 只做增强。
  - **索引内联**：`file://` 是不透明源，`fetch` 同目录 JSON 会被 CORS 拦死 —— 这是硬约束 C1。
  - **体积保护**：`--max-text`（默认 120 字）+ 产物超 3 MB 时**自动降到 60 字并在终端明示**。
  - `--full`（每页全文）带**体积闸门**：> 8 讲或 > 400 页时拒绝执行，需显式 `--force-full`。
- **课程主页「要点总结页」**（本轮新提的需求）—— 各讲 `#keypoints` 汇总成一张总表：
  每讲可折叠、纯 DOM 过滤（要点已内联，不建索引）、**导出 Markdown**（顶部自动附「生成时间 +
  覆盖讲次数 + 未完成讲次」，免得导出件被误当成完整版）。
  **没写要点的讲次给显式占位**（「本讲还没构建产物 —— 跑 run_all.py…」），绝不静默省略。
- `assets/course-shell.html` / `course.css` / `course.js` —— 课程页资源，**与单讲彻底分开**
  （单讲外壳承载缩略图/笔记抽屉/字号调节，课程页一样用不上；硬复用会污染被 `check_ui.py` +
  4 个探针严格守着的资产）。
- `scripts/run_course.py` —— **课程级流水线入口**：`init → index → brief → site → check → probe`。
  `--sync` 日常同步（**这就是「每加一讲就更新」的那条命令**）、`--add <讲目录>` 登记新讲并出简报、
  `--brief L07` 单独出简报。**刻意不并进 `run_all.py`**：后者是单讲流水线，产不出合集入口。
- `templates/probe_course.js` —— 课程入口行为探针，7 组断言：结构自洽 / 要点条目数与**显式占位** /
  出处链接形态与锚点自洽 / 跨讲检索（命中数、行数、跳转 URL 形态、片段高亮）/
  术语总表每行都有「首见」链接 / 导出 Markdown 非空且带覆盖范围 / 过滤 0 命中与清空复原。
- `assets/site.js` 支持 **`#q=<词>&p=<页id>` 深链**：课程页的检索结果用它跳到目标讲，
  自动填搜索框 + 跑一次搜索 + 跳到该页并高亮命中词。支持变体：`#q=<词>`（只搜不跳）。
  实测确认这是**纯新增** —— 改动前 `site.js` 里没有任何 `location.hash` 处理。
- `scripts/probe.py` 新增 `--hash`：探针可在指定 hash 下打开页面，用来测深链。

### 新增 · 阶段 3（课程层体检与文档）

- `scripts/course_check.py` —— **课程层体检**，查的是单讲体检答不了的「各部分之间还认不认得」：
  资源自检（`course.css`/`course.js` 花括号、`window.__course`、`course-shell.html` 五区块 id）
  ＋ 设计稿 §5.7 的七组断言：
  - **① course.json 与讲次目录**：每个 `dir` 存在、`config.json` 可解析、`done`/`partial` 的产物在；
  - **② 课程入口 `index.html`**：无未替换 `__XXX__` 占位符、href 无裸空白、每条相对链接的
    目标文件存在、带锚点的链接能在目标产物里找到该 id、**产物存在的讲次都有入口链接**、
    内联数据（`cdata`）可解析且讲次数与 `course.json` 一致；
  - **③ 术语一致性**：`glossary.json` 的 `conflicts` 必须为空（同一 concept id 在不同讲
    **译名不得漂移**）—— 这是唯一一条「术语层」的 FAIL，其余术语问题只报 WARN；
  - **④ `.xref` 跨讲外链可达**：文件与锚点都要在（含裸空白、绝对路径的显式报错）；
  - **⑤ `data-pays-off` / `data-forward`**：三段格式合法、概念在术语表、讲次在课程、页真实存在
    （目标讲还没产物时按 `course.json` 的页数卡上界并降级为 WARN）；
  - **⑥ 要点表**：每条 `data-at` 指向本讲真实存在的页；> 10 条、`data-topic` 不在术语表只报 WARN；
  - **⑦ 索引新鲜度**：各讲产物哈希 vs `index.json` 记录（不一致 = 改过没重跑 `--sync`）。
  FAIL 进退出码，`结果: ALL PASS` 才算过。
- **接进 `selftest.py`（第三条自查线「课程路线」）** —— 把前两条路线已经建好的**两份真实产物**
  就地组成一门两讲课（机械路线一份 + 语义路线一份），跑 `course_init → run_course --sync → course_check`。
  放在「有课程样例才跑」的分支里，单讲场景不受影响。
- `README.md` / `README.en.md` / `SKILL.md` / `docs/workflow.md` 补「多讲课程合集」小节：
  何时用、目录长什么样、四条命令、跨讲靠哪三个 `data-*` 串起来、改完课必跑体检。
- `scripts/run_all.py`：在**课程目录里**跑单讲流水线时给一句提示（「本意是同步整门课的话用
  `run_course.py`」），**只提示不改行为** —— 课程目录里跑单讲有可能是故意为之（设计稿 §9）。
- `references/pitfalls.md` 新增第 47、48 条（见下）。

### 修复

- **`build.py` 的「逐页区块」正则会因新增 `data-*` 而全数失配**（初稿判断「预计零改动」，
  实测证伪）。v1 的写法 `<section class="pg" id="p\d+" data-page="\d+">` 要求开标签在
  `data-page` 之后**立刻闭合**；v2 给 section 追加 `data-concepts` / `data-pays-off` / `data-forward`
  之后，**缩略图一个都不会注入**——产物每页都缺原页图。
  现在改为「只看属性、不看顺序」的匹配式，并**加了硬断言**：注入数 ≠ 逐页区块数就直接报错退出，
  不再留一个数字让人自己看。同一匹配式同步到 `check_math.js` ⑥ / `check_ui.py` / `coursekit.py`
  （四处口径必须一致，否则「缩略图 N / 逐页区块 M」会互相打架）。
- **`coursekit.py` 不对手写标题做 NFKC 归一化。** NFKC 是给「从 PDF 文字层刮出来的字符串」用的
  （同一个字可能有多个码位，见 pitfalls 第 10 条）；用到作者亲手写进 `config.json` / `outline.json`
  的标题上，会把 `CNN 基础（一）` 折成 `CNN 基础(一)` —— 全角括号变半角，中文排版上就错了。
- **`course_brief.py` 的段名重复拼页码**（`朴素贝叶斯分类器（P5–P8）（P5–P8）`）——
  正是 pitfalls 第 10 条的原始症状：`toc_label` 里已经带了页码区间，展示时又拼了一次。
  更隐蔽的是页码数字进了词袋，让「页码区间相同但内容无关」的两段白得相似度
  （实测：修掉后噪声从 0.10 降到 0.057）。
- **6 处踩坑条目引用指错**（详见下方「变更」）。
- **`course_index.py` 的声明探测会被骨架产物的注释误报**。判据原本是 `'data-concepts' in html`，
  可骨架产物（以及内容分片）的注释里到处是这三个属性的**说明文字**，于是「属性可能挂错了位置」
  这条 WARN 在**还没写任何内容**的讲次上必然亮起。改为在 `coursekit.body_html(html)` 上探测
  （挖掉注释与 script/style）后归零。
- **`course_site.py` 会给「骨架讲次」挂上死链**。skeleton 讲次的 `product` 是**预计路径**
  （文件还不存在），入口页照挂可点链接 → 点进去 404。`href_of()` 现在要求「`product` 非空
  **且文件真的存在**」，否则渲染成 `<span class="ltitle dim" title="这一讲还没有产物可打开">`
  —— 从「静默死链」变成「显式停用态」（与 pitfalls 第 44 条同一条思路：断言与渲染都要问
  「是不是我无法接受的样子」）。
- **`coursekit.py` 新增公共助手 `body_html(html)`**：一刀挖掉 `<script>` / `<style>` / HTML 注释，
  供所有「在页面里找元素、找链接」的检查复用。起因是 `assets/site.extra.css` 的**注释里带着
  `.xref` 的完整用法示例**（含一个字面 `<div class="xref">` 与假 href），不挖样式表就会把示例
  当真实跨讲链接去校验、直接误报（pitfalls 第 47 条）。

### 变更

- **两份在线 demo 已用本轮资产重建**（`docs/demo/index.html` / `docs/demo-en/index.html`）——
  改过 `assets/site.js` / `site.extra.css` 之后必须重建，否则在线那份还是旧交互。
  `build_demo.py --check` 确认目录与正文逐字节一致（改的是脚本与样式，不是正文）。
- `README.md` 目录树补课程层四个脚本、三个 `assets/course-*` 资源与 `probe_course.js`。
- **全仓库审计了 45 处「第 N 条」引用**，查出 6 处指错条目。**根因**：`references/pitfalls.md`
  在 2026-10-04 做过一次整体重排编号（v2.1.0 的「统一三段式、按对象分组重排」），重排后引用没跟着改，
  而 `check_docs.py` ⑤ 只验「编号存不存在」、**验不出「指错条目」**。已修：
  | 位置 | 原 | 改 |
  |---|---|---|
  | `assets/site.css`（`.vec` 的 U+20D7 说明） | 第 34 条 | **第 16 条** |
  | `templates/probe_doc.js`（探针扫到自己源码） | 第 16 条 | **第 46 条** |
  | `templates/content-skeleton/00_intro.html` | 第 30 条 | **第 18 条** |
  | `templates/content-skeleton/20_page.html` | 第 30 条 | **第 18 条** |
  | `examples/section-template.html` | 第 30 条 | **第 18 条** |
  | `scripts/probe.py`（探针结果怎么写回页面） | 第 30 条 | **第 23 条** |
- `README.md` 目录树补 `coursekit.py` / `course_init.py` / `course_index.py` / `course_brief.py`。
- `TODO.md` 基线刷新到 2026-10-14 实测（71 文件 / 9.8 MB / 36 提交 / 10 tag），
  版本号行的 `v2.1.1` 已陈旧（v2.2.0 发布时漏改）改为 `v2.2.0`；v2 段改指 v2.3.0 并标注进度。
- `references/pitfalls.md` 新增两条（46 → 48），都是本阶段施工时真实踩到的：
  - **第 47 条**：课程层「找元素找链接」没过剥离合成的样式表 → CSS 注释里的 `.xref` 用法示例
    被当成真实链接去校验。与第 46 条同源（挖噪声要按**类别**想全），但场景更近 ——
    「样式表里的用法示例」长得**就像真实标记**，按位置枚举（只挖注释、只挖 script）必漏。
  - **第 48 条**：新样例没铺开就断言 → 体检「ALL PASS」其实什么都没查。合成课件没有内容作者，
    产物里的 v2 声明全在模板 TODO 注释里（剥离后为 0），③④⑤⑥ 四组落在空集合上。
    对策是「空转守卫（断言统计数都 > 0）＋ 反向注入（故意破坏必须被抓）」两层。
- **README/SKILL/workflow/TODO 四处的 pitfalls 计数（46 → 48）同步**，`check_docs.py` ⑤ 组断言通过。
- **验收证据（设计稿 §8 阶段 3 硬要求）**：在课程夹具上**故意制造 7 种错误**，`course_check.py`
  **逐条**报 FAIL、退出码 1：
  | # | 注入 | 报 FAIL 的断言 |
  |---|---|---|
  | 1 | 改 `course.json` 的一个 `dir` | 每个讲次的 dir 都存在 |
  | 2 | 改一个术语 `zh`（`conflicts` 非空） | 没有术语冲突 |
  | 3 | 删产物里一个锚点 `id="p02"` | 带锚点链接在目标产物里都能找到该 id |
  | 4 | 把一条要点 `data-at` 指向不存在的页 | 每条的 data-at 都指向本讲真实存在的页 |
  | 5 | 端到端改产物译名 → 重跑 `course_index.py` | 没有术语冲突（**脚本自己算出** conflicts） |
  | 6 | 加 `.xref` 真卡指向坏文件 + 坏锚点 | 每个 .xref 外链都可达 |
  | 7 | 入口页 href 写入裸空格 | href 里没有裸空白（+ 目标文件存在 + 讲次都有链接） |
  干净夹具上则 `结果: ALL PASS`、退出码 0。第 6 项还附了一条旁证：`.xref` 组只数到注入的
  2 条真卡片 —— `site.extra.css` 注释里那张带假 href 的示例卡被正确剥离（第 47 条的回归）。

## [v2.2.0] - 2026-10-14

### 新增

- **正文搜索**（第六类交互）：搜索框从「只过滤目录标题」升级为「搜正文」。
  - 首次输入时惰性建一份正文索引（一节一个条目，走 `projOf` 的可见文本投影，
    **跳过 KaTeX 隐藏副本**），支持多词「且」查询；
  - 左栏 `#qres` 面板列出「页码 · 标题 · 上下文片段」，片段里的命中词高亮；
  - 点一条即跳转到该节，并把**该节内该词的全部命中**临时高亮，滚到第一处；
  - `↑`/`↓` 选择、`Enter` 跳转、`Esc` 清空；全局 `/` 对焦搜索框（侧栏收起时先展开）；
  - 正文一条都没命中时**回退到原来的目录标题过滤**，标题命中照样可见。
- `templates/probe_find.js` 正文搜索回归探针，接入 `run_all.py`（⑥c）。
- `check_ui.py` 新增「⑪ 正文搜索」接线体检组。
- **`scripts/build_demo.py` + `examples/demo/`**：两份在线 demo 的**源工程入库**，
  demo 从此可重建（此前是仓库里唯二无法重建的产物，见 `TODO.md` 第 10 条）。
  `--check` 是忠实性闸门：断言重建产物的目录与正文（含原页图）与已入库产物逐字节一致。
- `docs/v2-course-collection.md`：v2「多课件课程合集」设计稿（数据模型 / 内容层方法 /
  已否决方案 / 分阶段验收），供接手者照做，不必从零设计。

### 修复

- `check_math.js` ⑤b「TODO 残留」误报：挖内嵌载荷时只挖了 `<script>`，
  漏掉缩略图的 `data:image/jpeg;base64,…`——base64 是随机字符序列，小概率会碰巧拼出
  `TODO`（2026-10-13 实测同一份课件的 `thumb_42` 与 `thumb_77` 同时命中，一次报 2 处）。
  现在按**载荷类别**挖（script + 一切 `data:<mime>;base64,…`），不再按出现位置枚举。
- `check_docs.py` 的步骤号正则只认 `[④-⑳]b?`，新增 `⑥c` 这类步骤会被静默漏检；
  放宽为 `[④-⑳][a-z]?`。
- `probe_find.js` 抓测试词时只认汉字，在**英文产物**上直接假红
  （`能从正文里抓到测试词: FAIL (word=)`）。改为「汉字 → 拉丁词 → 自造词插进正文」
  三级兜底，并改成只在**单个文字节点内部**取词（跨节点的词套不上 mark，会假红）。

### 变更

- 交互项数 5 → **6**（`check_ui.py` docstring 是真源，其余五份文档已同步）。
- `site.js` 的上色机器泛化出 `cls` 参数：`mark.hl`（持久笔记）与 `mark.q-hit`（临时搜索高亮）
  共用同一套「只在文字节点内部动手」的封装，但类名严格隔离，互不误伤。
- 两份在线 demo 用 v2.2.0 重建（含搜索面板与新的快捷键提示）；英文 demo 的
  搜索框提示与页脚快捷键改为英文。
- `references/pitfalls.md` 新增第 46 条（内嵌载荷挖不全导致体检误报）。

## [v2.1.1] - 2026-10-07

### 新增

- **GitHub Actions CI**（`.github/workflows/selftest.yml`）：每次 push 到 `main` 与每个 PR，
  在 Ubuntu / Windows 双平台跑完整 `selftest.py`（机械 / 语义 / 文档口径三条自查线），
  顺带覆盖 Linux 真机验证。
- `check_docs.py` 新增「pitfalls 裸计数」断言：`「pitfalls.md（N 条」` 的总数必须等于真实条数，
  防「改了条数、忘了改文档」再犯。

### 修复

- **Windows 英文地区崩溃**：stdout 默认 cp1252，`print` 中文直接 `UnicodeEncodeError`。
  全部脚本顶部强制 stdout/stderr 走 UTF-8，CI 侧加 `PYTHONUTF8=1` 兜住子进程链。
- 文档口径漂移：「42 条踩坑」→「45 条」（`README.md` 两处 + `docs/workflow.md` 一处）。

### 变更

- `.gitignore` 补 `*.log`、`.pytest_cache/`。
- `README.md` 补 CI 说明与 `.github/` 目录树。

## [v2.1.0] - 2026-10-01

### 新增

- **顶栏 A−/A＋ 调节正文字号**（90%–140%，档位存浏览器 localStorage，重开保留）。
- `--stage plan` 默认只抽文字层、不渲染图，加 `--render` 才顺带渲染逐页图。

### 变更

- 重构 `references/pitfalls.md`：统一「症状 / 根因 / 处理」三段式，按对象分组、组内按破坏力排序。
- 新增 `templates/probe_font.js` 字号回归探针，接入 `run_all.py`（⑥b）；`check_ui.py` 新增「⑩ 正文字号调节」接线体检。

## [v2.0.0] - 2026-09-26

### 新增

- **语义驱动架构：结构先于内容确定。** 新增 `plan_outline.py` 结构巡读器（书签 / 编号 / 封面清单三路信号），
  产出 outline 草案；`run_all.py` 新增 `--stage full|plan|check`、`--outline`、`--force-outline`。
- 封面课程名 kicker：课程名进封面、文档名仍取 PDF 文件名。
- `selftest.py` 覆盖机械 + 语义两条路线，双路径自测。

### 变更

- `SKILL.md` 精简为直给指令（解释性内容下放 `README.md` / `docs/workflow.md`）。
- 修复 `plan_outline` fallback 在「页数 < 切段粒度」时的重复分段 bug。

### 兼容性

- **向后兼容**：不传 `--outline` 时行为与 v1 完全一致，机械路线照常可用。
