# TODO — 让陌生人能用起来

> 这份清单只服务于一个目标：**一个不认识作者的人，从点进这个仓库到跑出第一份产物，  
> 需要多久、会不会半路放弃。**
>
> 每条都写了「为什么值得做」和「怎么算做完」，可以直接当 issue 用。  
> 优先级按「拦不拦人」排，不按「技术含量」排。
>
> **已完成条目已从正文移除**（不再跟踪），只留在文末「已完成索引」一行。  
> 基线数据是 2026-10-03 实测，不是估算。

## 当前基线（2026-10-07 实测）

| 项目 | 现状 |
|---|---|
| 仓库 | 49 个受版本控制的文件 ｜ 4.9 MB（不含 `.git`） ｜ 34 个提交 ｜ 与 `origin/main` 逐字节一致 |
| 文档 | `README.md`（中文）、`README.en.md`（英文精简版）、`SKILL.md`（面向 agent）、`docs/workflow.md`（人类向流程）、`references/pitfalls.md`（**45 条**，三段式、按对象分 A–I 九组）、`references/content-quality.md`、`CHANGELOG.md` |
| 图片资源 | ✅ 3 张（`docs/images/`，hero / notes / overview，各约 230 KB） |
| 示例产物 | ✅ 在线 demo（`docs/demo/index.html`，1.19 MB）→ <https://zzzhen-22.github.io/slides-annotated-html/demo/>；**英文版**（`docs/demo-en/index.html`，1.19 MB）→ <https://zzzhen-22.github.io/slides-annotated-html/demo-en/>。两份均已按 v2.1.0 重建 |
| 示例素材 | ✅ `examples/sample-lecture.pdf`（8 页 / 590 KB，metadata 已中性化）+ `config.example.json` + `section-template.html` |
| 依赖清单 | ✅ `requirements.txt`（`pymupdf` + `pillow`，不锁版本；`node` 与浏览器为可选/外部） |
| 自检体系 | ✅ 三条线：`selftest.py` = 机械路线 + 语义路线 + **文档口径**（`check_docs.py`，6 组断言）；已接进 `selftest.py`，**CI 已建**（第 3 条） |
| CI | ✅ `.github/workflows/selftest.yml`：push 到 `main` / 每个 PR，ubuntu + windows 双平台跑 `selftest.py`（三条线） |
| 版本号 | ✅ `v2.1.1`（annotated tag + GitHub Release）+ `CHANGELOG.md`（第 6 条已完成） |
| tag 状况 | 9 个 tag，其中 6 个非 SemVer（5 个 `v2.0-semantic-outline-step3/4/5/6/12` + 1 个 `v1.0-classic-pipeline`），会干扰 Releases 页（见第 12 条） |
| 跨平台 | 代码里有 macOS / Linux 分支；**Linux 已由 CI 覆盖**（ubuntu runner 装 `fonts-noto-cjk`），macOS 仍未真机验证（见第 7 条） |
| 文档口径 | ✅ 无已知漂移；`check_docs.py` 新增「pitfalls 裸计数」断言（第 1、13 条完成，`check_docs.py` 常驻把关） |

---

## P0 · 拦在门口

>✅ **两条 P0 全部完成（2026-10-03 / 2026-10-04）**。本节转为**归档记录**——
> 留着是为了记住「这两类问题长什么样」，它们不会再次发生：
> 第 1 条由 `check_docs.py` 常驻把关，第 2 条的根因（build.py 缺降级分支）已从源头修掉。
>
> **现在真正的门槛在 P1 第 3 条（CI）** —— 上面两条都靠手动跑验证，
> 而「一个会误报的体检比没有体检更糟」这条只有强制跑才能兜住。

### [x] 1. 修文档口径漂移：「四类交互」→「五类交互」+ 英文 README 补字号 ✅ **已完成（2026-10-03）**

**为什么**：这是**上一轮加字号功能时漏掉的**。陌生人打开 README，看到的第一段 bullet  
写着「五类交互」，往下翻到三重校验表又写「四类交互的接线是否完好」——他会以为 README 自相矛盾，  
进而怀疑整个项目的可信度。英文 README 更糟：它连字号功能都没有，还写着 "Four interactions"，  
等于**英文用户拿到的是上一个版本的说明书**。

**改动前的漂移点（`grep -rn "四类交互"` 实测，共 6 处，已全部修掉）**

| 文件:行                    | 改前                           | 改后                   |
| ----------------------- | ---------------------------- | -------------------- |
| `README.md:111`         | `# 四类交互的「接线」是否完好`            | 五类交互                 |
| `README.md:135`         | `← 四类交互的 DOM 与 CSS/JS 是否对齐`  | 五类交互                 |
| `README.md:144`         | `← 四类交互的追加样式`                | 五类交互                 |
| `docs/workflow.md:96`   | 四类交互                         | 五类交互                 |
| `SKILL.md:142`          | `# 四类交互接线`                   | 五类交互接线               |
| `scripts/run_all.py:23` | `⑤ check_ui.py  四类交互的接线（含…）` | 五类交互，**并补上「正文字号调节」** |

**顺带补齐的四处漏项**（同属口径不一致，只改「四→五」不够）

- `README.md` 分步命令块：补 `probe.py templates/probe_font.js` 一行（原来只有 marks / doc 两个探针）
- `README.md` 目录树：`templates/` 原来只有一行概括，现展开列出 `content-skeleton/`、`probe_doc.js`、  
  `probe_font.js`、两个 harness；`docs/` 补 `demo-en/`
- `README.en.md` "Four interactions" → "Five interactions: … / **A− / A＋ to adjust body text size  
  (level saved in your browser)**"
- `README.en.md` 校验表拆开 `probe.py` 一行，拆成 `probe_marks.js` / `probe_font.js` / `probe_doc.js` 三行；  
  **中英两边的校验表现在逐行对称**（原来英文只有 2 行泛指、中文有 4 行）

**刻意没改的两处**（改了就错）

- `README.en.md:10` hero 图 alt 里的 "four card types" —— 指的是**四种提示卡**（绿=直觉/蓝=补充推导/  
  红=原稿问题/灰=原文引用），与「N类交互」不是同一个概念
- `README.en.md:56` "a four-item check" —— 指 `kitpath.py` 的四项环境自查，不是交互数

**验收（已过）**

- `grep -rn "四类交互" --include=*.md --include=*.py` → 除本TODO.md 的历史记录外**清零**
- `grep -rn "four|Four" README.en.md` → 只剩上述两处刻意保留的
- `SKILL.md` 手动复检命令块新增 `probe_font.js` 一行，与 `run_all.py ⑥b` 一致
- `python scripts/run_all.py examples/sample-lecture.pdf` 全流水线①–⑧ 实跑通过（文档改动无副作用）

> **但根因没解决**：口径散在 6 个文件、没有单一真源，靠人记必然漏。  
> **对策是第 13 条的 `check_docs.py`**——让机器查口径。本条只修了这一次的破损，  
> 没修「还会再破」这件事。

> **教训（值得写进 pitfalls）**：加功能时改了 `check_ui.py` 的 docstring 和 README 顶部 bullet，  
> 却漏了 README 中段三处 + SKILL.md + workflow.md + run_all.py 的注释。  
> 根因是「文档口径」散在 6 个文件里、没有单一真源。  
> **对策**：第 13 条的 `check_docs.py` 就是为这条准备的——让机器查口径，而不是靠人记。

### [x] 2. `check_ui.py` / `probe_doc.js` 在「无原 PDF」文档上必然报 FAIL ✅ **已完成（2026-10-04）**

**为什么**：这是**做 demo 时实测撞出来的**，当时判为「demo 固有设计，不修」，
但它影响的不只是 demo——**任何不内嵌原 PDF、且原文件不可得的文档都会撞上**。
一个工具在其它检查全绿的情况下硬报 FAIL，使用者第一反应是「工具坏了」，而不是「配置不同」。

**根因比原判断更深一层**（原判断只看到体检这一侧，漏了 build.py 那一侧）
- `scripts/build.py:227-235` —— **只处理两种形态**：内嵌（`data-embed-page`）与
  `config` 给了 `pdf`（`file:///…#page=N`）。**`config` 没给 `pdf` 时两个分支都不命中**，
  模板里的 `<a class="pdf-link" data-page="N">` 原样留下，成了**没有 `href` 的悬空链接**。
  demo 之所以「能用」，是因为当初手工把它改成了 `<span aria-disabled>` —— **等于把缺陷藏起来了**
- `scripts/check_ui.py` ⑥ 组 —— 非内嵌分支硬性要求 `'file:///' in html and '#page=' in html`
- `scripts/check_ui.py` 「数量一致性」组 —— `pl = html.count('class="pdf-link"')` 是**字符串计数**，
  `<a>` 与 `<span>` 混在一起算，**数字对上了，于是掩盖了「一个是死链一个是活链」这个本质差别**
- `templates/probe_doc.js:27` —— `$$('a.pdf-link')` 是**标签选择器**，停用的 `<span>` 一条都不算，
  于是「逐页区块 15 / 缩略图 15 / 深链 0」→ 报「✘ 不一致」

**实际改法（四处，缺一不可）**
- `build.py` 补**第三个分支**：`config` 无 `pdf` 时主动降级成
  `<span class="pdf-link" aria-disabled="true" title="本产物未包含原文件…">`，
  并打印「N 处已置为停用态」。**把「本来就没有原文件可跳」变成明示，不再留悬空链接**
- `check_ui.py` ⑥ 组按**形态分别断言**：检测到停用态就查「是否全停用 / 是否残留悬空 `<a>` /
  是否有 `aria-disabled` + `title`」；没有停用态才要求 `file:///`
- `check_ui.py` 数量组改为**按标签分别数**活链与停用态，并断言**两者不并存**
  （并存 = 降级做了一半，是真 bug）
- `probe_doc.js`：`a.pdf-link` → `.pdf-link`，另外单独报「活链 N / 停用 M」与
  「形态混用」，并把「只有停用态」标为 `✔ 一致（本产物未含原文件）`——**合法形态单列，不混进不一致**
- `references/pitfalls.md` 新增**第 44 条**（I 组「体检脚本自身的失效」）记录根因与处理法

**验收（已过，含「不能放水」那一半）**
- `docs/demo/index.html`（8 页、无 pdf）→ `check_ui.py` ALL PASS，
  ⑥ 组报「8 处停用 / 0 处仍是 `<a>`」、数量组报「8 / 8 / 8（活链 0 + 停用 8）」
- **正常产物（8 页、给了 pdf）→ 全流水线 ①–⑧ 全绿**，数量组报「活链 8 + 停用 0」。
  **这一步是必须的反向验证**——只测停用态通过，等于可能把断言改成永远 PASS

> **普适教训**（已写进第 44 条）：断言不能问「是不是我期望的样子」，
> 要问「**是不是我无法接受的样子**」。前者遇到未覆盖的合法形态就误报，
> 后者天然容纳新形态。


### [x] 3. 加 GitHub Actions，跑 `selftest.py` ✅ **已完成（2026-10-07）**

**为什么**：项目的质量承诺是「机械部分全绿」，但**没有任何自动化回归保障**。  
贡献者改了 `site.js` 或 `build.py`，没人拦得住。CI 是「这个项目还活着」的信号。  
本轮加字号功能时，`check_ui.py` 静态接线 + `probe_font.js` 运行时行为 + `run_all.py ⑥b`  
三层验证全是**手动跑的**——下一次就未必有人记得跑。

**怎么做**

- `.github/workflows/selftest.yml`，矩阵 `ubuntu-latest` + `windows-latest`
- 装依赖：`pip install -r requirements.txt`、`setup-node`（装 Node 才能跑 `check_math.js` 与  
  `probe_*.js`；注意 `probe.py` 用的是浏览器 `--dump-dom`，**不依赖 node**，只有 `check_math.js` 真依赖）
- **ubuntu 上要装中日韩字体**（`fonts-noto-cjk`），否则缺字体检项会误报
- 浏览器：ubuntu runner 用 `KIT_BROWSER` 指向自带的 chromium；或先只跑 `--no-shot` 部分
- 顺带在 workflow 里加一步 `check_docs.py`（第 13 条），让口径漂移也进 CI

**验收**：PR 上出现绿色 check；**顺带证明了 Linux 可用**（一举两得）

**实测落地（与草案的两处出入）**

- 浏览器**没用** `--no-shot`：截图本来在 `run_all.py` 里就是 `fatal=False`，跑全套不添风险。
- 草案写「runner 自带 chromium」**不准确**——ubuntu-24.04 runner 预装的是 **Google Chrome**
  （`/usr/bin/google-chrome`），chromium 在 24.04 是 snap-only、apt 装不了。所以 Linux 显式
  `KIT_BROWSER=/usr/bin/google-chrome`，Windows 留空交给 `kitpath` 自动找 Edge/Chrome。
- workflow 结构：`kitpath.py` 环境自查 → `check_docs.py` 秒级快速失败 → `selftest.py` 完整三条线。
  时间上限 30 分钟（本地实测 5m34s，留足余量）；`fail-fast: false`，一个平台挂不取消另一个。
- **不做发布**：`GITHUB_TOKEN` 只读，8 个 tag 里 4 个是开发快照，任何 push/release 都不进 CI。
- 顺带白送第 7 条的 Linux 半边：装了 `fonts-noto-cjk` 后，缺字体检在非 Windows 平台也跑得通。
- **首跑就抓到真 bug**：Windows runner（英文地区，stdout=cp1252）跑 `kitpath.py` 时 `print` 中文
  直接 `UnicodeEncodeError`，且它一挂、后面的 `check_docs` / `selftest` 因默认 `if: success()` 被跳过，
  ubuntu 侧全绿。修法两处缺一不可：① 全脚本顶部强制 `stdout/stderr` 走 UTF-8（`reconfigure`）；
  ② workflow 加 `PYTHONUTF8=1` 兜住子进程链。**这就是 CI 的价值——「中文地区 Windows 用 cp936
  能编码中文所以没事、英文地区就炸」这种 bug，手动跑永远发现不了。**

### [ ] 4. `CONTRIBUTING.md` + Issue / PR 模板

**为什么**：项目里其实有一套很成熟的「改套件的五条纪律」，  
但它埋在 `SKILL.md` 第 400 行附近，**贡献者根本看不到**。

**怎么做**

- 把纪律抽成 `CONTRIBUTING.md`（含：先看 mtime、改完必须重建 + 体检 + 截图、  
  资产耦合、不许写死本机路径、模板注释里不许出现字面标签）
- 明确写出**改完必须同步哪些文档**——本轮第 1 条的漂移就是这条缺失的直接后果
- `.github/ISSUE_TEMPLATE/bug_report.md`：要求附 `python scripts/kitpath.py` 的输出
- `.github/ISSUE_TEMPLATE/feature_request.md`

**验收**：打开 New Issue 时能看到模板

### [ ] 5. `init_project.py` 生成的 `README-项目.md` 写死套件绝对路径

**为什么**：`init_project.py:676` 现在还在写 `KIT="C:/Users/<用户名>/.workbuddy/skills/..."`。  
套件一旦被拷到别的机器、或者项目目录被单独拷走，README 里的所有重建命令**全部失效**，  
而这是新人**最依赖的一份文件**（第 3 条在 README 里留过同样的尾巴，最后靠占位符闭环解决）。

**怎么做**

- 改成相对路径（README 与脚本同深，用 `../../` 相对定位），或运行时探测（复用 `kitpath.py`）
- 至少在 README 顶部写明「套件搬家了？改这一行」

**验收**：把项目目录和套件分别拷到两个不同位置，README 里的命令照抄仍能跑

### [x] 6. `CHANGELOG.md` ✅ **已完成（2026-10-07，随 v2.1.1 发布）**

**为什么**：tag `v2.0.0` / `v2.1.0` 已建，Release notes 只存在于 GitHub 上，  
**仓库里没有任何一份可离线读的变更记录**。技能类项目会被反复迭代，没有 changelog 就没法追溯。

**怎么做**

- 按 Keep a Changelog 格式建 `CHANGELOG.md`
- 把 v2.0.0（语义驱动架构：结构先于内容确定）与 v2.1.0（正文字号调节、pitfalls 重构）的  
  release notes 收编进去；两者之间的 step tag 不必逐条收，只在「开发期标签」一节说明
- 版本号约定从 `0.1.0` 更正为 SemVer（这条在第 11 条里就写明了，一直没落地）

**验收**：`CHANGELOG.md` 有 v2.0.0 与 v2.1.0 两条，且与 GitHub Release 内容一致

**落地记录**：建了 `CHANGELOG.md`，收编 v2.0.0 / v2.1.0 / v2.1.1 三条，顶部写明
「Releases 页只看 SemVer tag，step tag 是开发快照」的标签约定（顺带覆盖第 12 条要说明的那半）。
第 12 条的「删 tag」这半仍未做（远端破坏性操作，需另行确认）。

---

## P2 · 提升「被发现」与「能贡献」

### [ ] 7. 在 macOS / Linux 上真机实测并写明支持矩阵

**为什么**：`kitpath.py` 里已经写了 `/Applications/Google Chrome.app/...`、  
`/usr/bin/chromium` 这些分支，但**从来没有在真机上验证过**，  
「代码里写了」和「能跑」是两件事。第 3 条的 CI 会顺带覆盖 Linux，macOS 仍需手动。

**怎么做**：至少跑一次 Ubuntu（WSL 也算）；有条件再跑一次 macOS。把结果写进 README 的支持矩阵表。

**验收**：README 有一张表，明确写出「已验证 / 未验证」的平台

### [ ] 8. 补 `argparse`，并统一致命错误格式

**为什么**：脚本已经有一半用了 argparse（`init_project` / `plan_outline` / `probe` / `run_all` /  
`selftest` / `shot` / `glyph_probe`），但 `build.py` / `prepare_pdf.py` / `kitpath.py` /  
`check_ui.py` / `katex_offline.py` 还在裸读 `sys.argv`，没有 `--help`，  
也没有像样的错误信息。**同一套件里两种风格**，是「专业度」最容易漏的地方。

**怎么做**

- 剩下 5 个脚本补 argparse（注意 `prepare_pdf.py` 的位置参数是 `pdf outdir [thumb_w] [quality]`，  
  补 argparse 时别把位置参数顺序改了，那是 `init_project.py` 生成命令依赖的）
- `run_all.py` 缺 `pdf` 参数时别甩 argparse 原文，改成打印「三步上手」
- 统一致命错误为三段式：**问题 + 原因 + 可直接照抄的解决命令**（`kitpath.require_deps` 已是这个风格）

**验收**：`python scripts/build.py --help` 等 5 个都有可用帮助；故意传错参数时给出的是人话不是 traceback

### [ ] 9. 评估去掉 Node 依赖

**为什么**：这是**门槛最实质**的一条。重新核过依赖面：`node` 的唯一用途是 `check_math.js`  
（KaTeX 语法自检）——`probe.py` 走的是浏览器 `--dump-dom`，**不需要 node**。  
也就是说砍掉 node 的代价，仅限于「离线校验公式语法」这一项能力。

**怎么做**

- 方案 A：用 Python 直接调 `vendor/katex/katex.min.js`（需要一个 JS 引擎，又多一个依赖，不划算）
- 方案 B：把公式语法自检也搬进浏览器探针（复用 `probe.py` 的 `--dump-dom` 机制，  
  在页面里注入 katex 后逐条 `renderToString`），这样 `check_math.js` 可以整个删掉
- 方案 C：诚实降级——在 README 里写清「不装 Node 会失去公式语法自检」，并让 `check_ui.py`  
  的静态检查补上「公式标签配对、括号闭合」等**不需要渲染**就能查的部分

**建议先做方案 C 的前半（降级说明 + 静态兜底），再评估 B**——B 的实现量不小，  
但它能把「Python + 浏览器」变成**唯一的两项依赖**，对新人门槛是数量级的下降。

**验收**：`check_math.js` 要么被删掉，要么 README 明确写出「没有它会少什么、怎么补」

### [ ] 10. demo 的生成脚本入库

**为什么**：`docs/demo/` 和 `docs/demo-en/` 是仓库里唯二**无法重建**的产物——  
原始课件 PDF 已因版权移除，重建只能靠「从单文件产物反解 content 分片 + 缩略图 + config」。  
本轮验证过这条路可行（重建后 DOC_NS 变化、8 页区块与公式全绿），但脚本是一次性的，  
**没进仓库**。半年后想改 demo，只能重新摸索一遍。

**怎么做**：把脱敏后的反解 + 重建流程写成 `docs/demo/build_demo.py`，参数化成  
「源产物 → 输出 demo」一步命令，并写清它依赖 build.py 的注入是确定性的（缩略图插在  
`</section>` 前、pdf-link 只改写 `<a>` 形式）。

**验收**：从任一在线 demo 反解并重建，得到字节级可复现的产物

---

## P3 · 细节打磨

- [x] **11.** `check_ui.py` 的分组输出顺序 ✅ **部分完成（2026-10-04）**
      - ~~原状：`⑧ → ⑨ → ⑩ → ⑥ → ⑦`，⑩ 插在 ⑨ 之后、⑥ 之前~~ → **现状：`⑤ → ⑧ → ⑨ → ⑥ → ⑦ → ⑩`**
      - 已把 ⑩（字号调节）移到末尾，读输出不再「跳回去」。**编号一律保留原样，不重排**
      - **有意留下的**：⑧⑨ 仍在 ⑤ 之后、⑥ 之前。这两组是历史上依次插在 ⑤ 后面的老组，
        重编号会让文档里「⑤ 之后是 ⑥」的说法失效，**收益 < 风险**，所以不动
      - 血泪教训见 `references/pitfalls.md` 第 45 条：**别用脚本按行号搬移源码块**
        （本轮试过，把 `def main()` 之前的文件头全吞了，靠 `git checkout` 还原）
- [ ] **12.** 清理开发期 tag：8 个 tag 里 4 个是 `v2.0-semantic-outline-step3/4/5/6`。  
      要么删掉，要么在 `CHANGELOG.md` 里说明「step 标签是开发快照，Releases 页只看 SemVer tag」。  
      现在 Releases 页会把这 4 个和 `v2.0.0` / `v2.1.0` 平级列出，容易让人误以为是正式发布  
      **建议与第 6 条（CHANGELOG）一起做**——写CHANGELOG 时顺手说明标签约定，一次改两件事
- [x] **13.** **加 `check_docs.py`：文档口径的机器化体检** ✅ **已完成（2026-10-04）**
      - 断言文档里提到的**带路径文件**真实存在（删了没改文档）
      - 断言「N类交互」在 `check_ui.py` docstring（**单一真源**）与 README / SKILL.md /
        workflow.md / run_all.py / README.en.md 之间一致
      - 断言每项交互的**功能名**在中文文档里都找得到（自动取稳定双字词，不维护别名表）
      - 断言 `run_all.py` docstring 里 ④–⑧ 各步引用的脚本，README 中英校验表都列了
      - 断言 `references/pitfalls.md` 编号 1..N **连续无空洞**，且全仓库「第 N 条」引用不越界
      - 断言 README 目录树列出的文件都存在，且 `scripts/` `templates/` 下新增的 `.py/.js` 没漏列
      - 成本约 260 行 Python（含注释），接进 **`selftest.py`**（不是 `run_all.py`），CI 待建（第 3 条）

  > **为什么真源选 `check_ui.py` 的 docstring**：它离实现最近、必然先改，
  > 所以「忘了改别人」的假设在它身上不成立。口径类事实应指定唯一出处，其余位置引用它。
  >
  > **为什么不接 `run_all.py`**：那条流水线是给用户跑课件的，
  > 让每个用户都体检一遍套件文档没意义；`selftest.py` 才是「套件自己体检自己」。
  >
  > **实测记录（反向测试比正向全绿重要）**：正向全绿只说明「现在没漂移」，
  > 不能说明「它抓得住」。故意注入三种漂移验证：
  > ① 在 `check_ui.py` 加第 ⑥ 项交互「全局搜索面板」→ **8 项 FAIL**，
  >    精确指出「真源说 6、5 处文档仍写 5」+「三份中文文档都没有『面板』」；
  > ② 从 README 校验表删掉 `probe_font.js` 一行 → ④ 组立刻 FAIL；
  > ③ 把 `pitfalls.md` 第 12 条改成 `12bis` → ⑤ 组报「缺 12」并给出实际编号序列。
  > 三次全部命中后已还原（`git diff scripts/check_ui.py` 为空）。
  >
  > **设计原则：宁可漏报，不可误报。** 第一版① 组把裸文件名（`README.en.md`、`Node.js`、
  > `config.json`…）也纳入校验 → 34 处误报。**一个会误报的体检比没有体检更糟**，
  > 会被直接关掉。改成只校验带路径分隔符的引用，裸文件名交给 ⑥ 组覆盖。
  > ③ 组第一版取功能名前两字，「本节概述」在 workflow.md 里写作「每节概述卡」→ 误报；
  > 改为取后两字（中文功能名后缀比前缀稳定）后消除。
  >
  > **顺带产出**：`references/pitfalls.md` 新增第 43 条（H 组「文档与口径」），
  > 把这次的根因与处理法记下来——这类漂移会再犯，得留记录。

- [ ] **14.** README 加一张「原 PDF 大小 → 产物大小」换算表（现在只有「≈ × 1.34」一行文字，  
  藏在「已知限制」里）。让用户提前知道内嵌 PDF 的代价，而不是做完才发现 20 MB
- [ ] **15.** 缩略图支持 WebP：`prepare_pdf.py` 只出 PNG（`grep webp` 零命中）。  
  demo 的 1.19 MB 里缩略图占大头，WebP 通常能省 30–50%。顺带记一条实测陷阱：  
  **PNG 降采样反而更大**（已在第 1 条截图的实测记录里踩过：1200 px → 380 KB vs 原始 240 KB，  
  插值在大片纯色区造出渐变，压缩率变差）
- [ ] **16.** `scripts/` 与 `templates/` 的 probe 文件放得不一致：`probe_marks.js` 在  
  `scripts/`，`probe_doc.js` / `probe_font.js` 在 `templates/`。统一到一处，或在 README 的  
  目录树里说清分工
- [x] **17.** `.gitignore` 补 `*.log`、`.pytest_cache/`（若以后加前端再加 `node_modules/`）。  
  现有条目已覆盖 `__pycache__/`、`.venv/`、编辑器与系统文件 ✅ **已完成（2026-10-07）**
- [ ] **18.** 各脚本头部加 SPDX 标识（GPL 的 "How to Apply" 建议这么做，但会让 diff 变吵，  
  可等版本稳定后一次性做）
- [ ] **19.** `TODO.md` 的基线表容易过期（本次已从 45 文件 / 9 提交 / 4.9 MB 更新到
      46 / 25 / 5.0 MB）。**故意不做自动化**：强制 agent 同步提交数会被绕过，
      「提示而非失败」才有效——`check_docs.py` 的定位是「抓事实矛盾」，不是「抓数字过期」

---

## 不建议做（看起来诱人，其实会伤害这个项目）

**不要打包成 pip 包 / 做成一条 CLI 命令。**  
这个工具的价值在「产出高质量讲解」，不在「自动转换」。包装成 `pip install xxx && xxx file.pdf`


会给人「一键转换」的错误预期 —— 而它的设计恰恰是**机械部分自动、判断部分留给人**。  
预期错了，收到的差评会比现在多。

**不要做 Docker 镜像。**  
依赖里含无头浏览器，镜像会到 GB 级；而目标用户多数在本地跑自己的课件。  
收益远低于维护成本。

**不要为了「直接读 PPTX」引入 LibreOffice 依赖。**  
让用户自己导一次 PDF 更省事、更可控（导出时字体和版式由他决定），  
引入一个几百 MB 的 Office 套件只为省一次导出，不划算。

**不要做在线服务 / SaaS 版本。**  
「离线、本地、课件不出自己电脑」是这个工具最实在的卖点之一。  
上传课件到别人的服务器，恰好破坏了它。

---

## 如果只做一件事

~~**做第 3 条：加 GitHub Actions。**~~ ✅ **已完成（2026-10-07）**

P0 已经清空了，但**现在所有验证都靠人手动跑**——这轮的三条自查线（机械 / 语义 / 文档口径）
一次要 5 分半钟，没有谁会天天跑。所以它们随时可能悄悄失效，而失效方式是**没人发现**。

第 3 条特殊在：**它一举两得**。① PR 上出现绿色 check = 「这个项目还活着」的信号，
顺带让贡献者放心；② ubuntu runner 自带 Chrome + `fonts-noto-cjk`，
**等于把第 7 条（macOS / Linux 真机验证）白送**（Linux 半边已落地）。

**下一步做第 6 条（`CHANGELOG.md`）**——它和第 12 条（清理开发期 tag）合起来做更划算，
写 CHANGELOG 时顺手把标签约定说清，一次改两件事。

---

## 已完成索引（2026-09-24 ~ 2026-10-07，不再跟踪）

正文里已勾掉的条目不再重复列出。这里记的是**没有对应 TODO 条目、但确实做掉的事**：

| 事项 | 完成于 |
|---|---|
| README 加效果截图（3 张） | 2026-09-25 |
| 在线 demo（中文 + 英文，Pages 已上线） | 2026-09-25；2026-10-03 按 v2.1.0 重建 |
| `requirements.txt` + 三步上手命令 | 2026-09-25 |
| 示例 PDF（`examples/sample-lecture.pdf`，8 页） | 2026-09-25 |
| README「已知限制」章节（中英对称） | 2026-09-25 |
| 英文 README `README.en.md` | 2026-09-25 |
| 仓库 topics（10 个）+ homepage 字段 | 2026-09-25 |
| `SKILL.md` 人类向内容拆到 `docs/workflow.md` + 定位调整 | 2026-09-25 |
| 在线 demo 地址写进 homepage 字段（徽章不做） | 2026-09-27 |
| 语义驱动架构（`--stage plan/check`、`--outline`、结构先于内容） | 2026-09-25 起逐步落地 |
| 版本化：`v2.0.0` + `v2.1.0` annotated tag 与 GitHub Release | 2026-09-27 / 2026-10-01 |
| 顶栏 A−/A＋ 调节正文字号（存 localStorage） | 2026-10-01（v2.1.0） |
| `pitfalls.md` 重构：1095 → 271 行、三段式、按对象分组 | 2026-10-02 |
| 文档口径漂移修复（6 处「四类交互」+ 英文 README 补字号） | 2026-10-03（第 1 条） |
| `check_docs.py`：文档口径机器化体检 + 接进 `selftest.py` | 2026-10-04（第 13 条） |
| `build.py` 无 pdf 降级分支（原先留悬空 `<a>`） | 2026-10-04（第 2 条） |
| `check_ui.py` 深链按形态断言 + 按标签分别计数 | 2026-10-04（第 2 条） |
| `probe_doc.js` 深链两种形态分别统计 | 2026-10-04（第 2 条） |
| `pitfalls.md` 新增第 43/44/45 条（43 → 45 条，分组扩到 A–I） | 2026-10-03 ~ 04 |
| GitHub Actions CI（`selftest.yml`，ubuntu + windows 跑三条线） | 2026-10-07（第 3 条） |
| `.gitignore` 补 `*.log` / `.pytest_cache/` | 2026-10-07（第 17 条） |
| 文档口径漂移修复：「42 条踩坑」→「45 条」（README ×2 + workflow ×1） | 2026-10-07 |
| `check_docs.py` ⑤ 补「pitfalls 裸计数」断言（曾漏拦 42→45 漂移） | 2026-10-07 |
| Windows cp1252 编码修复（全脚本 stdout UTF-8 + CI `PYTHONUTF8=1`） | 2026-10-07 |
| `CHANGELOG.md`（Keep a Changelog，收编 v2.0.0/v2.1.0/v2.1.1 + 标签约定） | 2026-10-07（第 6 条） |
| 发布 `v2.1.1`（annotated tag + GitHub Release） | 2026-10-07 |

已完成条目的**实测记录**没有丢：README 相关截图与体积实测在 `README.md`，
构建纪律在 `SKILL.md`，具体踩坑（含反向测试的记录）在 `references/pitfalls.md`。

---

## 这三轮学到的一件事（比上面任何一条清单都重要）

**「改了实现忘了改另一处」不是人的问题，是结构问题。**

三次漂移（6 处「四类交互」、英文 README 落后一版、`pitfalls.md` 重排后 15 处交叉引用要跟着改）
看着像粗心，实则同源：**同一句事实被抄在多个文件里，没有唯一出处**。

有效的解法都不是「更仔细一点」，而是**改结构**：
- 口径类事实**指定唯一真源**（本项目是 `check_ui.py` docstring），其余位置引用它 → `check_docs.py`
- 重排编号这种会连锁的事，**先 grep 出全部引用、建映射表再动手**，别边改边发现

推论：**下一个类似的动作是给「版本号 / 文件数」也指定真源**，但故意不做自动化
（见第 19 条）——「提示而非失败」才有效，强制维护会被绕过。
