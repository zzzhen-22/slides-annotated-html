# v2 设计：多课件课程合集（Course Collection）

> **状态**：设计稿，待实现。**适用对象**：接手 v2 的 agent。
> **前置**：v1 已稳定（v2.1.1）。本方案是**纯增量**——v1 的任何产物、任何命令都不得失效。
> 动笔前请先读 `README.md`「改这个套件时的纪律」与 `references/pitfalls.md`（46 条）。

---

## 〇、一句话目标

v1 解决「一份课件 → 一份逐页精解」。**v2 解决「一门课的 N 份精解 → 一个互相知道对方存在的整体」**：

1. **生成侧**：写第 N 讲的讲解时，能拿到「这门课至今已经讲过什么」，从而做出跨讲关联——不重复展开、术语统一、伏笔跨讲回收。
2. **组织侧**：把这门课的 N 份精解组成一个「课程合集」入口，可导航、可跨讲检索、可对照取用。

---

## 一、v1 的现状与缺口（先把问题说准）

v1 的一个「讲次」就是一个自包含项目目录：

```
<某讲目录>/
├─ config.json          ← 讲次元数据（out/pdf/title/shards/groups/pages…）
├─ content/             ← 逐页讲解分片（人工写）
├─ _extract/            ← 逐页图 + 缩略图
├─ _katex/              ← 离线 KaTeX
├─ _plan/outline.json   ← 语义大纲（含 14 段的语义名、每页标题、confirmed 标记）
├─ README-项目.md
└─ <讲次名>-逐页精解.html   ← 单文件产物（内嵌 CSS/JS/KaTeX/缩略图/可选原 PDF）
```

**已经具备、v2 可以直接复用的资产**（这是本方案能做得轻的关键）：

| 资产 | 为什么 v2 能白拿 |
|---|---|
| `_plan/outline.json` | 每讲的**语义分段 + 每页标题**已经是结构化的。跨讲「讲了什么」不必重新解析正文。 |
| `config.json` 的 `pages` / `groups` | 讲次的页清单与目录结构，直接可做课程地图。 |
| 产物 HTML 的 `section.pg[id=pNN]` | 每页有稳定 id，跨讲深链直接用 `…#p51`。 |
| v1 的正文搜索（`Find` 模块） | **v2 的跨讲检索是它的放大版**，索引结构可以复用同一套思路。 |
| `check_docs.py` 的「单一真源 + 派生断言」 | 课程层的术语一致性检查照这个模式写即可。 |

**缺口**：

1. 讲次之间**零关联**。同一概念在两讲里可能用不同译名；同一段推导可能被讲两遍；前一讲留的伏笔（如「梯度消失后面再讲」）在后一讲不会被认领。
2. 写第 N 讲的 agent **读不到第 1…N-1 讲写了什么**——它只有当前这份 PDF 和页面图。
3. 没有任何东西知道「这门课一共有几讲、叫什么、哪讲讲什么」。

---

## 二、不可破坏的硬约束（先立规矩，再谈设计）

这四条来自 v1 的设计底线，**任何 v2 方案违反一条即否决**：

| # | 约束 | 理由 |
|---|---|---|
| C1 | **`file://` 直接打开、断网可用** | v1 全部价值的基础。**推论：不能 `fetch()` 同目录 JSON**——`file://` 是不透明源，本地 JSON 会被 CORS 拦死。因此任何「入口页 + 外部索引」的方案都必须把索引**内联**进 HTML。 |
| C2 | **单讲目录可独立使用** | 别人可能只拿走第 3 讲。合集层只能是「在上面加一层」，不能要求讲次依赖课程目录才能打开。 |
| C3 | **不做巨型合并单文件** | 一讲产物已 9–10 MB（含内嵌 PDF）。14 讲合并 ≈ 140 MB，浏览器直接崩；而且笔记的 localStorage 命名空间、内嵌 PDF blob 都会互相打架。 |
| C4 | **讲次目录名可迁移** | 所有跨讲引用用**相对路径**，不写绝对路径（v1 已有这条纪律，`check_docs.py` 有对应断言）。 |

---

## 三、目录与数据模型

课程 = 一个目录，讲次 = 它的子目录（v1 结构**原样不动**）：

```
<课程目录>/
├─ course.json               ← 课程级元数据（本方案新增，唯一真源）
├─ _course/                  ← 课程级派生物（全部可重建，不入版本控制可选）
│   ├─ glossary.json         ← 术语权威表
│   ├─ briefing-L07.md       ← 第 7 讲的「前序知识简报」（给 agent 读）
│   └─ index.json            ← 跨讲索引（由各讲产物 + outline 派生）
├─ lecture-01-why-dl/        ← v1 项目目录，结构不变
├─ lecture-02-cnn/           ← v1 项目目录，结构不变
└─ index.html                ← 课程合集入口（新产物，单文件、索引内联）
```

### `course.json`（草案 schema）

```json
{
  "schema": "course/v1",
  "name": "清华大学 · 深度学习",
  "instructor": "苏航（Hang Su）",
  "term": "2026 秋",
  "created": "2026-10-14",
  "lectures": [
    {
      "id": "L01",
      "dir": "lecture-01-why-dl",
      "title": "深度学习导论（一）：Why deep Learning?",
      "pdf": "3-Deep Learning-I.pdf",
      "page_count": 82,
      "status": "done",
      "topics": ["why-dl", "feature-learning"],
      "outline": "lecture-01-why-dl/_plan/outline.json",
      "product": "lecture-01-why-dl/3-Deep Learning-I-逐页精解.html"
    }
  ],
  "unknowns": []
}
```

要点：

- **`dir` 是唯一键**，其它字段全部可由它派生（title 从 outline/config 抓，page_count 从 config 抓）。派生得出来的就不要手写——写两份必然漂移（这正是 v1 `check_docs.py` 要治的病）。所以 `course_init.py` 只让用户填**最少的东西**：课程名 + 讲次目录列表。
- `status`：`pending`（还没建）/ `skeleton`（骨架建了、讲解没写完）/ `done`。由 `probe_doc.js` 的「待补页面 N/M」自动判定，**不手工维护**。
- `topics` 是自由标签，用来在课程地图上做粗分类；真正的细粒度概念关系在 `glossary.json` 与各讲的 `data-concepts` 里。

### `_course/glossary.json`（术语权威表）

```json
{
  "schema": "glossary/v1",
  "terms": [
    {
      "id": "residual-connection",
      "zh": "残差连接",
      "en": "residual connection",
      "aliases": ["跳跃连接", "skip connection", "恒等捷径"],
      "def": "把输入直接加到子层输出上，使梯度有一条恒等通路。",
      "first": "L01:p58",
      "seen": ["L01:p58", "L01:p59", "L02:p12"]
    }
  ]
}
```

**这是 A 侧能不能成立的关键**：

- 第 1 讲第一次出现某概念时，agent 在页面上写 `data-concepts="residual-connection"`，`course_index.py` 发现 glossary 里没有这个 id，**追加**一条（zh/en 从页面的中英文标题或 `.gloss` 卡里抓，抓不到就留空待补）。
- 第 2 讲再遇到这个概念，`briefing` 会直接把 `zh` 给出，agent **必须沿用**（不许新造译名）；`check_course.py` 会扫后续所有讲，发现同一 `id` 被用了不同 `zh` 就报 FAIL。
- `aliases` 记录历史上用过的别的说法——不是纵容，而是**让检查能报出「这两讲说的其实是同一件事」**，从而提供合并建议。

---

## 四、A 侧：内容层方法（生成新讲解时关联前序知识）

### 4.1 核心动作：写讲解前先拿一份 briefing

新增脚本：

```bash
python scripts/course_brief.py <课程目录> --for L07 --out <L07>/_plan/briefing.md
```

`briefing.md` 是**给 agent 读的**（不是给人看的），固定五节：

| 节 | 内容 | 数据来源 |
|---|---|---|
| ① 前序讲次地图 | 每讲的标题、页数、各语义段名 + 页码区间（一张表） | 各讲 `_plan/outline.json` |
| ② 术语权威表 | 已被前序讲次确立的 中/英/别名/首见位置 | `_course/glossary.json` |
| ③ 概念落点索引 | 「这个概念在前序哪讲的哪一页展开过」 | 各讲产物的 `data-concepts` 抽出的 `_course/index.json` |
| ④ 本讲大纲的**已讲预警** | 本讲每个语义段，若与前序讲次的某段标题相似度超阈值 → 「⚠ 前序已详述（L03 P12–P18），本讲应写『回顾一句 + 指路』而非重新展开」 | 本讲 `outline.json` × 前序 `outline.json`（标题 + 该段页标题的词面重合度） |
| ⑤ 待回收的伏笔 | 前序讲次里标了 `data-forward` 的开放问题，若与本讲大纲有交集 → 列出 | 各讲产物的 `data-forward` |

**为什么用 markdown 而不是 JSON**：agent 读 markdown 更省 token、也更不容易误读结构；机器消费的部分（术语、索引用 JSON 另存 `_course/`）。

### 4.2 内容层的三个新声明（这是「更新生成内容层的方法」的本体）

在页区块上**加三个 `data-*` 属性**即可，不改渲染、不改 build 流程：

```html
<section class="pg" id="p58" data-page="58"
         data-concepts="residual-connection,degradation"
         data-pays-off="vanishing-gradients@L01:p77"
         data-forward="depth-vs-width">
```

| 属性 | 语义 | 谁用 |
|---|---|---|
| `data-concepts` | 本页**引入或重点讲解**的概念 id（对应 glossary） | 建 glossary、建概念索引、后续讲次的 briefing |
| `data-pays-off` | 本页**回收**了前序讲次的伏笔，格式 `概念id@讲次:页` | 生成「跨讲伏笔回收图」；反向可查「哪条伏笔还没人回收」 |
| `data-forward` | 本页**留下**的、后讲应当回收的开放问题 | 后续讲次 briefing 的第 ⑤ 节 |

**约束与纪律**：

- 这三个属性**全部可选**。不写就不进课程索引，但不能让 build 失败——v1 的产物必须继续可用。
- id 用小写连字符（`residual-connection`），不用中文（中文作 id 会在 URL / JSON / 文件名三处惹麻烦）。
- `data-page` / `id` 仍是硬要求（v1 已有），三个新属性是软要求。

### 4.3 讲解模板的新增两格（写进 `content-quality.md` 与 `SKILL.md`）

v1 的「单页讲解五段结构」第 5 条是「与前后页的伏笔/回收」。v2 把它**拆成两格**：

5. **页内串联**（原有）：与本节前后页的伏笔/回收。
6. **跨讲串联**（新增，**有前序讲次时才写**）：
   - **前序已讲过** → 用 `.xref` 卡，给「第 3 讲 P14 已详述」+ **相对路径链接**；
   - **本讲首次引入** → 补 `data-concepts`，并在本讲末尾的术语表补一条；
   - **回收前序伏笔** → 补 `data-pays-off`，并在正文里显式写「这一页回答了第 1 讲 P77 留下的问题」。

新增一个卡片样式 `.xref`（浅灰蓝底 + 左侧竖线，视觉上与 `.note` 区分）：

```html
<div class="xref"><b>跨讲：</b>第 1 讲 <a href="../lecture-01-why-dl/xxx-逐页精解.html#p77">P77</a>
  曾把「梯度消失」留作伏笔，本页的残差连接正是它的答案。</div>
```

### 4.4 待定的判断（下一任 agent 需拍板）

- **相似度阈值取多少**？建议先**不做相似度**，改为「本讲大纲的每个语义段标题，与前序讲次所有页标题做**词面重合度**（去掉停用词后 Jaccard ≥ 0.34）」——简单、可解释、可调。用嵌入模型会引入依赖（违反「不联网、零依赖」的轻量约束）。
- **briefing 是否强制**？建议 `init_project.py --course <dir>` 时**自动生成**并在终端提示「已生成 briefing，写讲解前先读它」。强制到「不读就报错」是做不到的（agent 行为不可控），所以靠提示 + `check_course.py` 事后审计。

---

## 五、B 侧：课程合集框架

### 5.1 新增产物：`index.html`（课程合集入口）

单文件、`file://` 可开、索引内联。四个区块：

**① 课程地图**（主区）
讲次卡片列表：`L01 · 深度学习导论（一）` / 82 页 / 14 段 / 完成度 100% / 主题标签。点进对应产物 HTML。
数据来自 `course.json` + 各讲 `config.json` + `outline.json`。

**② 跨讲检索**（核心价值）
复用 v1 `Find` 的设计：一个输入框，命中列表形如
`L03 · CNN 基础（二） · P51 · 朴素 Inception 的计算代价` + 上下文片段，点击打开
`lecture-03-xxx/xxx-逐页精解.html#p51`，并**让目标讲自动把命中词高亮**。

> **跨讲跳转怎么带高亮**：给 v1 的 `site.js` 加一段「启动时读 `location.hash`」——
> 支持 `#p51`（滚到该页，v1 已有）与新增的 `#q=<词>`（自动填入搜索框并 `Find.run`）。
> 合集里生成 `<a href="../L03/xxx.html#q=残差">`。**这是 v1 刚做完的搜索功能的直接延伸**，
> 也是为什么「先做搜索」是对的排期。

**③ 术语总表**
`glossary.json` 渲染成一张表：中文 / English / 别名 / 一句话定义 / **首见**（可点，跳到那一讲的该页）/ 全部出现过的位置。

**④ 进度看板**
每讲的「待补页面 N / M」（由 `course_index.py` 读各讲产物算出，或调 `probe_doc.js`）。一眼看出哪讲没写完。

### 5.2 跨讲索引怎么生成（关键取舍）

```bash
python scripts/course_index.py <课程目录>          # 扫各讲产物 → _course/index.json
python scripts/course_site.py  <课程目录>          # index.json 内联进 index.html
```

**索引只从「产物 HTML」抽，不从 `content/` 抽。** 理由：产物是最终交付物，索引与它一致才有意义；从 `content/` 抽会出现「索引里有、产物里没有」（比如某分片没被加进 `config.shards`）。

抽取内容：每个 `section.pg` 的 `id / data-page / h3 文本 / 正文纯文本 / data-concepts / data-pays-off / data-forward`。
抽取方式：**正则 + 轻量清洗**即可，不引入 HTML 解析库（保持 `requirements.txt` 只有 pymupdf + pillow）。用 v1 里已有的字符归一化经验（NFKC、康熙部首、U+20D0–20FF 体检）。

**体积控制**（必须做，否则入口页会到几十 MB）：

| 模式 | 内联内容 | 14 讲估算 | 用途 |
|---|---|---|---|
| 默认 | 每页标题 + 每页**前 120 字** + 概念标签 | 约 1–2 MB | 找得到、跳得过去；全文精确搜索留给各讲自己的搜索框 |
| `--full` | 每页全文 | 约 15–25 MB | 想在一个框里搜遍全课程时用 |

默认模式必须明说这一限制（入口页上写一行提示），不能让用户以为「搜不到＝没有」——这是 v1 `probe_doc.js`「断言要问『是不是我无法接受的样子』」的同一条原则（pitfalls 第 44 条）。

### 5.3 讲次改名 / 增删之后

`course.json` 里的 `dir` 是键。改目录名 → 必须重跑 `course_index.py` + `course_site.py`。
新增 `course_check.py` 断言：

- `course.json` 里每个 `dir` 都存在，且其 `config.json` 可解析；
- `index.html` 里每条跨讲链接的目标文件真实存在、锚点（`#pNN`）在目标产物里真实存在；
- 每讲的 `glossary` id 使用一致（`zh` 不漂移）；
- 各讲产物与 `index.json` 的内容哈希一致（briefing 是否过期）。

---

## 六、组件清单（新增 / 修改）

### 新增脚本（`scripts/`）

| 脚本 | 职责 | 是否致命 |
|---|---|---|
| `course_init.py` | 初始化/更新 `course.json` 与 `_course/`（幂等；只让用户填课程名 + 讲次目录） | 是 |
| `course_brief.py` | 产出 `_course/briefing-LNN.md`（A 侧的核心） | 是 |
| `course_index.py` | 扫各讲产物 → `_course/index.json`（含 glossary 汇总） | 是 |
| `course_site.py` | 由 `course.json` + `index.json` 生成合集 `index.html` | 是 |
| `course_check.py` | 课程层体检（术语一致 / 跨讲链接可达 / 索引与产物一致 / briefing 新鲜度） | 是 |

### 新增探针（`templates/`）

| 探针 | 断言 |
|---|---|
| `probe_course.js` | 合集入口在浏览器里的行为：地图条目数 = `course.json` 讲次数、检索有命中且行数合理、点结果生成的目标 URL 形态正确（相对路径 + `#q=`）、术语总表每行都有首见链接、进度看板数字与内联索引自洽 |

### 修改（每处都要遵守 v1 纪律：改 assets/scripts 前看 mtime、改完重建 + 三校验 + 截图 + 与旧产物 diff）

| 文件 | 改什么 |
|---|---|
| `assets/site.js` | ① 启动时支持 `#q=<词>` 深链自动搜索；② `.xref` 不需要 JS（纯 CSS 样式） |
| `assets/site.extra.css` | `.xref` 卡样式 |
| `assets/shell.html` | 若有需要（预计不需要：`.xref` 走正文） |
| `scripts/build.py` | 把 `data-concepts / data-pays-off / data-forward` 原样保留（当前 build 不碰 section 属性，预计零改动）→ **先去确认**，能不改就不改 |
| `scripts/init_project.py` | 加 `--course <课程目录>`：建骨架后自动生成 briefing，并在终端提示 |
| `templates/content-skeleton/20_page.html` | 页骨架补三个 `data-*` 的注释示例 |
| `examples/section-template.html` | 补 `.xref` 卡与三个 `data-*` 的样例 |
| `references/content-quality.md` | 「五段结构」→ 六段（加跨讲串联）；补 `.xref` 的用法 |
| `SKILL.md` | 加「多讲课程」小节：briefing → 写讲解（含跨讲串联）→ course_index → course_site |
| `README.md` / `README.en.md` / `docs/workflow.md` / `scripts/run_all.py` | 口径同步（新增脚本、新增步骤号、目录树）——`check_docs.py` 会逐条验 |
| `references/pitfalls.md` | 实现过程中踩到的必记（建议预留第 47 条起） |
| `CHANGELOG.md` | 记在 `[Unreleased]`，实现完成、自检全绿后再切 `v2.2.0` |

---

## 七、已否决的方案（连同否决理由，避免下一任 agent 重新走一遍）

| 方案 | 否决理由 |
|---|---|
| 把所有讲合并成一个巨型 HTML | 违反 C3。140 MB、浏览器崩、笔记命名空间与内嵌 PDF 互相打架。 |
| 合集入口 `fetch()` 外部 `index.json` | 违反 C1。`file://` 下本地 JSON 被 CORS 拦死，用户双击打开就是空白页。**必须内联。** |
| 上一个小型本地服务（`python -m http.server`） | 违反 C1 的精神（「双击就能看」）。可以作为**可选的**开发期便利，但不能是唯一路径。 |
| 用 SQLite / 数据库存索引 | 违反「零依赖、可迁移」。JSON + 内联即可。 |
| 用嵌入模型做「已讲预警」的语义相似度 | 引入模型依赖、可能联网。先用词面重合度，够用且可解释。 |
| 让讲次产物依赖课程目录才能打开 | 违反 C2。别人只拿走一讲时必须照样能看。 |
| 在课程层再建一套「统一渲染」的产物 | 重复劳动，且会与各讲产物漂移。课程层只做**索引与聚合**，正文仍归各讲。 |

---

## 八、分阶段落地（每阶段独立可验收）

> 铁律：**每一阶段结束时，v1 的 `selftest.py` 必须仍然全绿。** 这是「不破坏 v1」的机器判据。

### 阶段 0 · 数据模型与初始化（不含 agent 侧变化）

- 定稿 `course.json` / `glossary.json` schema；
- 写 `course_init.py`（幂等、只问最少信息、能对已有讲次目录自动补齐字段）；
- 用 **现有的 `3-Deep Learning-I` 项目** 作单讲样例（单讲课程也必须是合法课程——这保证它从小规模可用）；
- 补 `check_docs.py` 的目录树条目（新增脚本必须进 README 树，否则 ⑥ 组 FAIL）。

**验收**：`course_init.py` 跑两遍结果一致；`check_docs.py` ALL PASS。

### 阶段 1 · A 侧（内容层方法）

- `course_index.py` 先做最小版：只抽 `section.pg` 的 `id/page/title/text`，建 `_course/index.json` 与 glossary 种子；
- `course_brief.py` 产出五节简报；
- `init_project.py --course`：建骨架后自动出 briefing + 终端提示；
- 更新 `content-quality.md`（六段结构）、`examples/section-template.html`（`.xref` + `data-*`）、`templates/content-skeleton/20_page.html`；
- `site.extra.css` 加 `.xref`。

**验收**：对样例课程跑 `course_brief.py`，briefing 五节非空、术语表与索引自洽；人工抽查一条「已讲预警」是真预警而非噪音。

### 阶段 2 · B 侧（合集入口）

- `course_site.py` 生成 `index.html`（四区块，索引默认「标题 + 前 120 字」内联）；
- `site.js` 加 `#q=<词>` 深链搜索；
- `probe_course.js` 写出来并接入 `run_all.py`（建议 `⑨` 或 `⑥d`，注意 `check_docs.py` 的步骤号正则已放宽到 `[a-z]?`）。

**验收**：`file://` 双击打开合集入口、断网、检索命中、点结果能跳到目标讲的该页并高亮；`probe_course.js` PASS。

### 阶段 3 · 课程层体检与文档

- `course_check.py`（四条断言见 5.3）；
- 接进 `selftest.py`（**放在「有课程样例」时才跑**的分支里，避免单讲场景报错）；
- 五份文档口径同步 + `check_docs.py` ALL PASS；
- `CHANGELOG.md` 切 `v2.2.0`。

**验收**：**故意**制造三条错误（改一个 `dir`、改一个术语 `zh`、删一个锚点），`course_check.py` 必须逐条报 FAIL。这是「体检脚本自身有效」的证明——v1 的 pitfalls 第 44 条就是断言写错形态导致体检永远 PASS 的事故。

### 阶段 4 · 增强（可延后）

- `--full` 全文内联模式；
- 对照阅读（选 2 讲并排 `iframe`，同步滚动）；
- 「伏笔回收图」可视化（哪些 `data-forward` 还没人 `data-pays-off`）。

---

## 九、风险清单

| 风险 | 触发条件 | 对策 |
|---|---|---|
| **索引与产物漂移** | 某讲重跑过 build、别的讲没重跑 | `course_check.py` 比对「各讲产物内容哈希 vs `index.json` 里记录的哈希」，不一致就要求重跑 `course_index.py` |
| **briefing 过期** | 写 L07 时有人在改 L03 | briefing 里带各讲 `content/` 哈希；`course_check.py` 校验 |
| **术语表变成负担** | 概念太多、agent 忘了写 `data-concepts` | 三个 `data-*` 全可选；glossary 允许 `zh` 为空待补；`course_check.py` 只报「警告」不报 FAIL，除非同一 id 出现**冲突译名** |
| **入口页体积失控** | 讲次多、页数多 | 默认模式只内联标题 + 前 120 字；在入口页明示限制 |
| **`course/` 层与 v1 命令打架** | 有人在课程目录里跑 `run_all.py` | `run_all.py` 增加「检测到 `course.json` 就提示应先 `cd` 进讲次目录」，不自动改行为 |
| **改名断链** | 用户手动重命名讲次目录 | `course_check.py` 报断链 + 打印「应重跑 course_index/course_site」 |

---

## 十、给下一个 agent 的开工前 5 件事

1. **读** `README.md`「改这个套件时的纪律」+ `references/pitfalls.md` 第 43/44/45/46 条（都是关于「体检与文档口径」的血泪）。
2. **看 mtime**：`find . -type f -printf '%TY-%Tm-%Td %TH:%TM %P\n' | sort` —— 确认接手时 `assets/` 与 `scripts/` 没被别的会话改过。
3. **先跑** `python scripts/selftest.py`，确认接手时是 PASS 的基线（不要在一个已经红的套件上开工）。
4. **阶段 0 先做**，不要一上来写合集入口——数据模型（`course.json` / `glossary.json`）是所有后续的地基，改它会连带改派生脚本。
5. **每阶段收尾四连**：重建产物 → 三校验（check_math / check_ui / probe）→ 截图 → 与旧产物 diff（**目录块与正文块应当逐字节一致**，不一致就说明你动了不该动的东西）。

---

## 附：v2 与 v1 的关系一览

| 维度 | v1 | v2 |
|---|---|---|
| 单位 | 一讲 | 一门课（含 N 讲） |
| 关联 | 无 | `data-concepts` / `data-pays-off` / `data-forward` + glossary |
| 生成时输入 | 当前 PDF + 逐页图 | 再加一份 `briefing.md`（前序知识地图） |
| 上手成本 | 一个 PDF 一条命令 | **不变**：单人单讲仍可完全按 v1 用；课程层是可选叠加 |
| 产物 | `<讲次>-逐页精解.html` | 再加一个 `index.html`（课程合集入口） |
| 体检 | `check_math` / `check_ui` / `probe_*` / `check_docs` | 再加 `course_check.py` |
