# Changelog

本项目所有显著变更都记录在此文件。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

> **标签约定**：Releases 页只看 SemVer 标签（`vX.Y.Z`）。形如 `v2.0-semantic-outline-stepN`、
> `v1.0-classic-pipeline` 的标签是**开发期快照**，不是正式发布，请勿当作版本号引用。

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
