# Changelog

本项目所有显著变更都记录在此文件。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

> **标签约定**：Releases 页只看 SemVer 标签（`vX.Y.Z`）。形如 `v2.0-semantic-outline-stepN`、
> `v1.0-classic-pipeline` 的标签是**开发期快照**，不是正式发布，请勿当作版本号引用。

## [v2.4.3] - 2026-10-16

> 主题：**课程主页从「能用」到「好用」** —— 先修一批交互（检索键盘可达、结果不再硬截断），
> 再补上第二梯队（scrollspy / 要点折叠开关 / 术语过滤 / URL 状态同步）；
> 课程合集获得自己的在线 demo，门面（demo + 预览图）开始被脚本与 CI 管起来；
> **课程探针补上自动入口**（此前它没有任何入口、静默红过很久）。
> 另修两个静默缺陷：一个在路径展开、一个在探针的字段引用。

### 新增

- **课程合集在线 demo**（`docs/demo-course/`）：把已有的两份单讲 demo 当作一门课的两讲讲，
  外加一个课程入口页，用来演示课程层的五个区块（课程地图 / 要点总结 / 跨讲检索 / 术语总表 /
  进度看板）。中英两份 README 都加了**直达链接**（与现有两份 demo 并列）与**课程主页预览图**。
  - 讲次是**预构建副本**（课程层只消费各讲产物 HTML，`coursekit` 既不启浏览器也不读 PDF），
    讲次 `config.json` 只为课程层提供 `title / brand / pages / out`；两讲的标题由 `brand` 区分
    （「逻辑回归 · 中文精解」/「Logistic Regression · English walkthrough」），
    两份单讲 demo 的产物与外壳**一个字节都没改**。
- **`scripts/shoot_previews.py`**：README 那几张预览图的取景参数固化 + 一键重截。
  此前它们是**手工截的、没留脚本**，于是悄悄过期了很久 —— 2026-10-16 重截时才发现旧图里
  工具栏还没有字号按钮（A−/100%/A＋）、左侧目录也还没有「本讲要点」这一条。
  四张图：`hero` 1500×1500 / `overview` 1500×1250 / `notes` 1500×1500 / **`course` 1500×2042（新增）**；
  `notes` 走 `window.__doc.addNote()` 注入两条示例笔记（与真实入口同一条路），
  `course` 折叠 `.klec` 后用 `trim_bottom()` 把整页截图底部的空背景裁掉。
- **`build_demo.py` 收编课程层**：`python scripts/build_demo.py` 现在一键重建三份 demo
  （`zh` / `en` / `course`）；`--check` 扩成**两条忠实性断言** ——
  ① 讲次副本必须与当前单讲 demo 逐字节一致（防「单讲更新了、课程 demo 没跟上」）；
  ② 课程层五个产物（`index.html` / `course.json` / `_course/` 三份 JSON）必须能由
  「讲次副本 + course.json」重跑出来且**逐字节一致**。
- **CI 新增一步 `build_demo.py --check`**（`.github/workflows/selftest.yml`）：纯 Python、
  不开浏览器，十几秒。**门面过期属于「没人跑所以没人发现」**，这一步就是它的入口。
- demo 内容层增补：两份 demo 各加一张 **「本讲要点」卡**（`#keypoints`，5 条、每条指回原文页码），
  中文侧另挂 6 处 `data-concept`（术语行）与 5 处 `data-concepts`（正文区块）；
  中英目录各补一条「本讲要点 / Key points」。**这是课程层的演示素材**——
  它让 `docs/demo-course/` 的要点总表与术语总表有真实内容，而不是空转 PASS。
- 新增 `docs/v2-course-collection-todo.md`：课程主页优化的待办（第二 / 三梯队 + 小项 +
  「发布注意」），来源是 2026-10-15 的批判性审查。
- **课程探针补上自动入口**（课程 TODO 的 S5）：`selftest.py` 的课程线现在跑**两发真实探针** ——
  ① 裸跑（五区块 + 本轮新增的 ⑧–⑬ 组）；② `--hash` 验「打开带参链接 → 参数已恢复 +
  页面已滚到那个区块」；另加**空转守卫**（输出里必须出现本轮新增组的标题，防止探针文件
  悄悄退回旧版而整体照旧 PASS）。在此之前它只在手动跑 `run_course.py`（不带 `--no-probe`）
  时执行、selftest 与 CI 都不跑 ——「没人跑所以没人发现」的典型，详见「修复」节那条。

### 修复

- **`coursekit.long_path()` 遇到「不存在」的路径整串不展开**：`GetLongPathNameW` 只认
  **整条路径都存在**的情形，中间任一段缺失就原样返回。而课程层要展开的常常是还不存在的文件
  （如 `course.json` 里记的 `lecture-01-zh/_plan/outline.json`）。当时若 `rel_posix` 的两端
  一个展开了、一个没展开，`os.path.relpath` 找不出公共前缀，会算出
  `../../../../SHENYU~1/AppData/...` 这种又长又错位的相对路径 ——
  2026-10-16 在临时目录里重建课程 demo 时实测到（也正是它让「课程层产物逐字节可重建」这条
  断言一开始假红）。改为**从最长的存在前缀往下退**，展开能展开的那一截再拼回去。
- **`templates/probe_course.js` 的检索断言恒假**：它引用 `C.find.MAX_ROWS`，而该字段在
  课程主页 A7 改动里已改名为 `PAGE_ROWS` ⇒ `Math.min(n, undefined)` = `NaN`，
  `rows === NaN` 永远为假。此前没人发现，是因为**它只在手动跑 `run_course.py`
  （不带 `--no-probe`）时才执行** —— `selftest.py` 的课程线用的是 `--no-probe`，CI 也不跑它。
  除了改名，同时补上**分页断言**（④c 组）：临时把每批条数调成 1，验「首批只渲染一批 →
  按钮报出剩余条数 → 点一次多渲染一批 → 显示完按钮自行消失」；用**反向注入**证明它不是
  「永绿的空检查」（分别打断 `showMore` 与首批截断，各自被抓到 2 条 / 4 条断言）。
- **本轮被探针自己逮到的两处测试缺陷**（改的是测试手法，不是产品）：
  ① ⑥ 组「导出 Markdown」的断言没考虑「打开时带着 0 命中的过滤词」—— 那时导出
  「空表 + 覆盖说明」本来就是设计（`markdown()` 导出的是**当前可见的那一份**），
  断言却不依不饶地要讲次小标题；改为**按可见量条件式**断言。
  ② ⑧ 组的滚动测试最初是「临时改 `<html>` 的 `scroll-behavior` 再 `scrollTo`」——
  style 写入后 computed 值还没 recalc，`scrollTo` 仍可能按 smooth 起动画、随即读到
  旧位置（「打开就带 hash、页面已在滚动位置」的场景实测翻车）；改用
  `window.scrollTo({top, behavior:'instant'})` —— 显式参数永远压过 CSS。
- **scrollspy 判定线过宽（开发中修掉）**：最初用「视口 45%」做判定线，在「连续矮区块」
  的小课程页（地图区只有 250px 高）上，滚到顶部时多个区块同时越线 —— 高亮从一开头就
  跳到第二节，还让「打开带参链接的自动滚动」误判「已经在该区块、不用滚」。
  改为**顶部撞击线（80px）**后：顶部正确点亮第一节，探针的「中间块」覆盖也从 1 个扩到 3 个。
  这个缺陷是 `selftest.py` 的两讲课样例（页面矮）暴露的 —— demo-course（页面高）
  恰好掩盖了它。

### 变更（课程主页交互，第一梯队）

- **检索结果键盘可达**（A1）：`.ck-hit` 由 `div` + JS 跳转改为真 `<a href>`
  （Tab 可聚焦、可新标签打开、可复制链接一次解决），补 `:focus-visible` 焦点环；
  检索框 **Enter 聚焦第一条命中**（两步式防误跳）。
- **检索结果不再硬截断**（A7）：`MAX_ROWS` → `PAGE_ROWS`（语义：每批条数），
  列表底部加「**显示更多（还剩 N 条）**」按钮逐批追加（增量 append，不重渲染整段），
  摘要显示「已显示 N 条」；`.res-more` 从共享基样式拆出为通栏按钮（原来是**死样式**：
  有 CSS、JS 从不创建该元素）。
- **hero 占位文案去字段名**（B1）：不再把「（还没写课程目标：course.json 的 summary）」
  这种内部字段名暴露给读者。
- **地图卡片去掉重复状态词**（B2）：徽标已有状态，`.lmeta` 只留「N 页」。
- **要点区讲次标题变直链**（B3）：`.klec summary` 的标题在「有产物」时改为
  `<a class="ktitle">` 直链（实测点击不触发折叠）。

### 变更（课程主页交互，第二梯队）

- **顶栏 scrollspy**（A4）：`course.js` 新增 `Spy`，滚动时点亮「当前区块」——判定线是
  **顶部撞击线（80px，与 `.card` 的 `scroll-margin-top:64px` 配套）**，滚到底点亮最后一节、
  一个都没撞线（还在顶部）时点亮第一节。实现是**计算式**（`update()` 现场数区块），
  而不是 `IntersectionObserver` —— 同套件踩过「无头下原生事件不派发」的坑（#toTop 的假象），
  可同步调用的实现才能被探针钉死。高亮用 `box-shadow: inset` 下划线，不改变文字盒宽度
  （切换高亮时导航整体不位移）。
- **要点「全部折叠 / 展开」开关**（B4）：`.kp-tools` 新增按钮，**不动默认全展开**；
  按钮文案跟随「是否还有展开的块」，手动逐个折叠也同步（`<details>` 的 toggle 事件
  不冒泡，用捕获阶段监听）；`@media print` 的「打印时展开全部」不受影响。
- **术语总表过滤框**（B5①）：与要点过滤同一套模式（纯 DOM `indexOf`、多词是「且」、
  0 命中显式空态）；没有术语时整个工具条收起（`.kp-tools[hidden]` 需显式补
  `display:none` —— 作者样式会压过 UA 的 `[hidden]`）。只加过滤、不堆视图（三表分工的克制）。
- **URL 状态同步**（A2）：hash 采用**全 kv 格式** `#sec=<区块>&kp=<词>&find=<词>&gl=<词>` ——
  第一段故意不用裸锚点：裸 `#keypoints` 形态在「写入」瞬间会让浏览器原生滚动、把页面滚走；
  kv 形态没有匹配 id，**写入永不产生意外滚动**，而手动敲裸 `#glossary` 仍兼容（parse 认成 sec）。
  输入防抖 300ms 写入（`location.hash`，`file://` 下最稳）；打开带参链接 → 恢复 + 滚到 `sec`；
  前进后退 / 手改地址栏 → 以 URL 为准**全量套用**（缺参数 = 清空该项）；点击页内锚点被接管
  （滚动 + 高亮 + 参数段随行，筛选不丢）。
- **S1–S4 顺手修**：地图卡片段与段之间补**真空格**（flex 的 gap 只撑视觉、进不了文本流，
  缺了它复制卡片行会得到「L01标题部分完成」粘连串）；「还有 N 页没写」抽 `pages_left()` 共用；
  0 命中的检索摘要补上「索引只含每页前段正文，找不到不等于没有」；`course_check.py`
  给缺 `summary` 的 course.json 报一条 WARN。

### 文档

- README 中英：课程 demo 直达链接、课程主页预览图与图注、目录树补
  `scripts/shoot_previews.py` 与 `docs/demo-course/`、`images/` 注明可重截；
  「套件自查」从一条（`check_docs.py`）扩为两条（+ `build_demo.py --check`），
  自检命令块同步补一行。
- TODO.md 现状表（图片 3 → 4 张、示例产物加课程合集版、CI 加一步）与「已完成索引」补 5 行。
- 课程 TODO 修正一条**事实写错的发布注意**：原文说「两份单讲 demo 里内联的课程页是旧版
  `course.js` 快照（含旧 `MAX_ROWS` 逻辑）」——实测 `docs/demo/index.html` 里 `id="cdata"`
  与 `PAGE_ROWS` 各出现 0 次，根本没有课程层资源；里面的 4 处 `MAX_ROWS` 属于
  **`site.js` 的正文搜索**（单讲功能）。两处同名常量被当成了同一个东西。
- **（第二梯队同期）** README 中英各补一段「课程入口页自带一套前端交互」（scrollspy /
  双过滤框 / 折叠开关 / URL 状态）；`TODO.md` 的「已完成索引」补 2 行；
  `docs/v2-course-collection-todo.md` 把第二梯队与小项全部归档（原条目描述折叠留档，
  第三梯队保持「待拍板」状态原样）。

## [v2.4.2] - 2026-10-15

> 主题：**把散落各处的版本口径统一到 v2.4.1，并给「表格行数」这类漏网的漂移补上机器守护**。
> v2.4.1 的文档同步只覆盖了「与代码块直接相关」的几处（README 顶部 bullet、
> 目录树、三份校验表、pitfalls 条数）。这一轮做全仓库口径普查，发现还有 5 类漂移
> 是**上一轮没扫到**的——它们不属于代码块，所以没被那次同步带上。

### 修复（文档口径漂移）

- **README.md / README.en.md 的校验表行数说法**：v2.4.1 给校验表加了
  `probe_codecopy.js` 一行（7 行 → 8 行），但紧跟的散文仍写「上表**七**行」
  （英文 `The **seven** rows above`）——**表加了行、说法没跟着数**。
- **英文 README 校验表结构本身就是坏的**：表头只有 2 列（`Check | Catches`），
  数据行里却有好几行是 3 个单元格 —— 多的那个 `looks` 列在渲染时被丢掉。
  补全为 `Check | Catches | Doesn't catch` 三列，与中文版逐行对称。
- **英文 README 特性列表缺代码块**：中文 README 已在 v2.4.1 补了「**代码块**：语法着色…」
  bullet，英文版没有；`check_ui.py` 那一行也没提代码块组。两处补上，中英重新对称。
- **自检线数口径**：`selftest.py` 实际跑**四条**线（机械 / 语义 / 课程 / 文档口径），
  但 README 目录树、英文 README、`selftest.yml` 注释、设计稿仍写「两条路线 / three checks /
  三条线」——都是课程路线（v2.3.0）加进来时漏改的。
- **`docs/v2-course-collection.md` 的 pitfalls 总数**：仍写「（48 条）」（实为 51 条）。
  它一直没被发现，是因为 ⑤ 组的裸总数扫描只覆盖 5 个文件、不含 `docs/`。
- **「N 项体检」写死在多处**：`SKILL.md`、`init_project.py`（docstring + 生成的
  `README-项目.md` 模板）、`selftest.py` docstring 分别写「四项 / 三项体检」，
  而流水线体检项已涨到七项（④⑤⑥⑥b⑥c⑥d⑦）。**数字写死必然再漂**，
  统一改成「全套体检」，不再承诺具体项数。
- **README.md 分步命令块与 SKILL.md 手动复检命令块**都漏了 `probe_codecopy.js`
  一行（校验表里有、命令块里没有）。
- **TODO.md 基线表**：文件数 / 提交数 / tag 数 / 版本号 / v2.3.0 段的状态均落后于实际；
  版本号一栏从「进行中：v2.3.0」更正为「最新 `v2.4.1`；已发布 tag 停在 v2.3.0，
  v2.3.1 / v2.4.0 / v2.4.1 三段待提交、待打 tag」。

### 新增

- **`check_docs.py` 新增 ⑦ 组「校验表行数 ↔ 『上表 N 行』说法一致」**：
  数出 README 校验表的实际数据行数，断言中文「上表 N 行」与英文「N rows above」
  的 N 都等于它。**这类漂移（表加了行、散文没改数）此前没有任何一组拦得住**——
  ② 只管「N 类交互」、⑤ 只管 pitfalls 数字。
  已用**反向注入**验证会真报错：把「八行」改回「七行」→ 精确指出
  「README.md →『上表 七 行』（实际 8 行）」。与 pitfalls.md 第 48 条同一原则：
  **新检查必须配反向注入，否则可能是「永绿的空检查」**。
- **`check_docs.py` ⑤ 组的 pitfalls 裸总数扫描面扩到 `docs/*.md`**：
  设计稿里那处「（48 条）」正是从这个缺口漏过去的。反向注入同样验证会命中。

### 变更

- **`check_docs.py` 组数 6 → 7**（docstring 的「它查六件事」同步改为「七件事」）。
- 与 v2.4.1 一样，本轮**只动文档与体检脚本**，不碰任何产物生成路径 ——
  所以产物无回归风险；`check_docs.py` 收尾 ALL PASS，反向注入三次全部命中后已还原。

## [v2.4.1] - 2026-10-15

> 主题：**让代码块从「能放代码」变成「能读、能抄」**。
> v2.4.0 只给了容器与配色变量，但实测发现三个坑：
> ① `.codeblk-head` 的样式写了却**没有任何代码生成它**（分片里只写 `data-src` 属性，
> 产物里标题栏计数是 0）；② `.c/.s/.k/.n` 四类配色同样无人写入，代码整块是黑的；
> ③ 顺手发现 `site.js` 里 **8 处 `toast()` 调用一直没有实现**，
> 那些分支一执行就 `ReferenceError`（模块加载期不报错，所以静态体检与截图都照不出来）。

### 新增

- **`build.py` 新增 `decorate_codeblocks()` 后处理**（构建期一步做完三件事）：
  - **语法着色**：注释 / 字符串 / 关键字 / 数字四类。**按整段扫描而非逐行** ——
    三引号文档字符串常常跨行，逐行扫会把它中间几行当普通代码，一片绿中间夹一段黑的；
    单引号 / 双引号字符串则按 Python 语义**不跨行**（一处笔误不至于把后面整篇染成字符串色）。
    **不引任何高亮库**：单文件产物要断网可用。颜色写在产物里，打印 / 另存 / 离线打开都还在。
  - **标题栏注入**：按 `data-lang` / `data-src` 生成「语言名 + 来源 + 复制按钮」。
    分片里不再手写标题栏（20 个块各写一遍必然漏改）。
  - **行高亮**：`data-hl="12,18"`（行号从 1 数）→ 对应行加 `.ln-hl` 底色。
- **`build.py` 自带自证断言**：剥掉注入的标签后，代码块里的文字必须与原码**逐字相同**。
  这条守的是「笔记能否继续定位」——标记与笔记的定位靠文字投影拼串，
  着色只许加 `<span>`，一旦顺手改了字，全部已有笔记就会失效。
- **`site.js` 新增 `initCodeCopy()`**：复制按钮挂逻辑，取 `pre.textContent`
  （**不是 `innerHTML`** —— 否则会把着色标记一起复制走），并复用既有的
  `navigator.clipboard` → `execCommand` 降级路径。老产物没有标题栏时**现场补一个按钮**，
  不让「有没有按钮」变成「代码能不能复制」的前提。
- **`site.js` 补上缺失的 `toast()` 实现**（连带 `.toast` 样式）：
  此前 8 处调用有调用无实现，跑到就抛 `ReferenceError`。
- **`site.js` 的 `copyText()` 加 600ms 超时兜底** —— 这是实测踩出来的真实缺陷：
  `navigator.clipboard.writeText()` 在**文档没有焦点**时既不 resolve 也不 reject，
  Promise 永远挂着（无头浏览器 100% 复现；真实场景里用快捷键或脚本触发也会遇到）。
  没有超时的话，复制按钮点下去**完全没有任何反馈** —— 不弹提示、按钮不变色，
  用户只会以为按钮坏了。现在超时后落回 `execCommand`，成功报成功、失败报失败，
  无论如何都有反馈。复制按钮本身也改成复用这个统一入口，不再自己写一套 clipboard 分支。
- **`templates/probe_codecopy.js`（新）**：代码块专项探针，接进 `run_all.py` 的 ⑥d。
  静态体检只能看「span 有没有出现」，看不了「按下去到底复制到了什么」。该探针覆盖：
  标题栏位置、四类着色不越界、**剥离 span 后与 `textContent` 逐字一致**、
  `codeOf()` 结果干净（无标签、无 `&lt;` 残留）、真点一次按钮看 UI 反馈。
  因为无头下剪贴板必然失败，探针额外把 `writeText` stub 成 resolve，
  把**成功路径**（「已复制 N 行」文案、按钮 done 态）也覆盖上，否则成功分支永远没被测过。
- **`site.extra.css`**：`.code-copy` 按钮（含 `.done` / `.fail` 两态）、
  `.toast` 提示条。`@media print` 下隐藏复制按钮（纸上按不了）并把代码块改白底。

### 变更

- **`check_math.js` 的标签配对白名单加入 `pre`**：代码块现在内部有 `span`/`button`/`b`，
  `pre` 不入白名单就少了一层配对体检。
- **`check_ui.py` 新增「⑫ 代码块」一组断言**（每块都有标题栏与复制按钮、
  分片里没有残留的手写标题栏、四类着色 span 齐全、按钮两态、打印时隐藏、
  `toast` 有实现、`initCodeCopy` 已挂进 `boot`、**`copyText` 有超时兜底**）。
  该组**不计入 docstring 里的「六项交互」**（编号延续历史顺序，改总数会让
  「⑥ 之后是 ⑦」的说法处处失效）—— 这一点在 `workflow.md` 里写明了。
  **该组是条件式的**：课件里没有源码是合法形态（自检用的合成 PDF 就没有），
  没有块时输出 SKIP 而非 FAIL —— 否则套件自检会永远红着（pitfalls 第 44 条）。
- **`selftest.py` 新增 `inject_codeblock_sample()` 与两条「空转守卫」**：
  往语义路线的骨架里塞两个代码块（覆盖四类着色、行尾注释、`&gt;` 转义），
  并断言「⑫ 组与 ⑥d 探针**确实跑了**」而不是 SKIP。没有这一步，
  代码块这条路在自检里一次都不会被验证（pitfalls 第 48 条）。
  判定取**产物证据**而不是输出里的字面标签 —— `run_all` 的 `parse_check_ui`
  只透传「结果：ALL PASS」一行、`parse_probe` 按白名单前缀过滤，标签匹配会永远不命中。
- **内容纪律：「解释某一行」的注释写在该行上方，不写行尾**（`SKILL.md` /
  `references/content-quality.md` / CHANGELOG 三处同步）。代码块可用宽度约
  72 个半角字符，行尾注释极易把行顶出容器，逼读者横向拖动 —— 正好抵消了
  「注释便于阅读」的初衷。实测某份课件里 31 行因此溢出，全部上移后降到 0。
- `SKILL.md` / `references/content-quality.md` 的代码块一节改写：
  明确「**只写容器，别写标题栏**」、着色与标题栏在构建期完成、
  「**解释某一行的话优先写进代码当注释**」及其与「公式↔代码对照表」的分工。
- `README.md` / `README.en.md` / `docs/workflow.md` / `TODO.md` 同步：
  新增 `templates/probe_codecopy.js` 与 ⑥d 阶段（含 pitfalls 条数 50 → 51）。
- **`references/pitfalls.md` 新增第 51 条**：`clipboard.writeText()` 在文档失焦时
  **永不 settle**（既不 resolve 也不 reject）→ 复制按钮点了毫无反应。
  静态体检、生成期、截图三道都照不出来（它们看「元素在不在」，看不出「回调会不会回来」）。

## [v2.4.0] - 2026-10-15

> 主题：**给逐页讲解补上「代码块」这一等公民**。
> 起因是实测一份含完整源码的课件（TensorFlow Actor-Critic 十页代码）时发现：
> 套件原先只有行内 `<code>`，没有能承载多行源码的容器，
> 讲解者只能把代码塞进 `<pre>` 里裸着或用引用卡片顶替，缩进与可读性都不达标。

### 新增

- **`assets/site.extra.css` 新增代码块样式族**（纯新增，不改任何既有选择器，向后兼容）：
  - `.codeblk` + `.codeblk-head`：带标题栏的多行代码容器，标题栏右侧可挂源码出处
    （`data-src` 属性，用 `.code-src` 显示）；
  - `.codeblk.inline`：行内短命令形态（单行 pip / shell 命令用），不占满整行；
  - `.code .ln-hl`：给被正文点名的那一行加底色，**用行内高亮而非改 `display`**，
    以免破坏划词与标记的文本投影；
  - `.code .c / .s / .k / .n`：注释 / 字符串 / 关键字 / 数字的轻量配色，
    **不依赖任何高亮库**（断网可用，也不需要引入 hljs）；
  - `@media print` 下 `white-space: pre-wrap` + `word-break: break-word`：
    长行在打印与 PDF 导出时折行，不截断。
- `SKILL.md` 与 `references/content-quality.md` 补「代码块怎么写」一节：
  推荐写法是 `<div class="codeblk" data-lang="python" data-src="原文件 P24 · ...">`
  内放 `<pre class="code">` 存源码原文。

### 说明

- **代码内容里的 HTML 特殊字符必须转义**（`<` `>` `&`），否则会被浏览器当标签吃掉；
  实测最容易漏的是 `&gt; /dev/null`、`if running_reward &gt; threshold`、泛型 `List[tf.Tensor]`。
- **源码请逐字照抄自页面图，不要照抄 PDF 文字层**：实测一份课件里
  文字层的换行错乱、下标丢失、右括号被裁，直接采信必然写错。
- 配方（源码怎么抄准、代码块怎么与公式混排）见 `references/pitfalls.md` 第 50 条附注。

## [v2.3.1] - 2026-10-15

> 主题：**课程主页的公式渲染** + 无头浏览器「静默空转」的根治。
> 两个 bug 都是「生成期全绿、打开页面才看得见」那一类，所以修的同时补了静态断言。

### 修复 · 课程主页的公式显示成〔公式〕（issue 报告见下）

- **现象**：`index.html` 的「要点总结」与「术语总表」里，公式全显示为占位符〔公式〕。
- **根因（两层，各自独立、都会单独致病）**：
  1. 课程页三件套（`course_site.py` / `course-shell.html` / `course.js`）**没有任何公式渲染能力**：
     `coursekit.html_text()` 按设计把公式塌成〔公式〕供**检索索引用**，主页却直接把它当正文显示了。
  2. `build_glossary()` 汇总术语时**只搬运 `zh`/`en`/`def` 纯文本**，新加的 `*_html` 富文本字段
     没跟着汇总上去，渲染端回退到转义纯文本，公式又变回占位符。
- **修复**：
  - `scripts/coursekit.py` 新增 **`html_rich()`** 与 `RE_MATH_SCRIPT`：把一段 HTML 净化成
    「安全、可显示公式」的片段（保留 `math/tex` 标签与行内强调、剥掉非公式 script 与缩略图 base64、
    标签白名单、剥离 `on*=` 与 `javascript:`）。与 `html_text()` **分工不互替**：
    前者给显示、后者给检索索引。要点抽取新增 `html` 字段、术语抽取新增 `zh_html`/`en_html`/`def_html`。
  - `scripts/course_site.py` 新增 **`load_katex()`**：内联 `vendor/katex/katex.offline.css` +
    `katex.min.js`（约 630 KB，字体已转 data URI）。缺文件时**降级告警而非报错**
    （公式不渲染，但正文照样读得到）。成品 0.77 MB，远低于 3 MB 闸门。
  - `assets/course-shell.html` 加 `__KATEX_CSS__` / `__KATEX_JS__` 占位符（CSS 放在最前防 FOUC）。
  - `assets/course.js` 新增 **`renderMath(root)`**：把 `script[type^="math/tex"]` 换成
    `katex.render(...)` 的结果，失败则标 `.katex-failed`。**必须在 `Kp.build()` 之前执行** ——
    要点索引读的是 `li.textContent`，公式没渲染完就会索引到 LaTeX 源码，过滤随之失灵。
  - `assets/course.css` 加公式字号与失败态样式。

### 修复 · 内联 JS 的注释里写了字面闭合标签 → 整页脚本被提前闭合

- **现象**：`course.js` 里一段**注释**为了举例写了字面的 `<script type="math/tex">…</script>`。
  它被内联进 `<script>` 后，**HTML 解析器把那个闭合标签当成脚本结尾**，后面全部代码降级成页面文本。
  连带 `body_html()` 挖 script 的非贪婪正则从假标签起算、配对错位，误报「可见正文里有〔公式〕占位符」。
- **修复（三层）**：
  - 改掉那处注释（`course.js` 段头已注明「故意不写字面起止标签」），`course-shell.html` 同类注释一并改；
  - `course_site._assert_no_script_end()` —— 扫待内联的 `.js`/`.css`，出现未转义闭合标签即 `SystemExit`
    （放行 `<\/script` 这类转义写法）；
  - `course_site.check_script_tags_balanced()` —— 数**成品**里的 `<script` 与 `</script`，
    不配对即报错。护栏建在可交付产物上，才能覆盖渲染函数拼串等别处引入的截断。
- 详见 `references/pitfalls.md` 第 49 条。

### 修复 · 抽取器升级后缓存被复用 → 新字段全空，而流水线全绿

- `scripts/course_index.py` 新增 **`EXTRACTOR_VERSION = 2`**：增量缓存命中条件从「产物哈希一致」
  升级为「产物哈希 **且** 抽取器版本一致」。此前抽取器加了字段、产物没变，旧缓存被原样复用，
  新字段没机会生成（正是术语表公式退化的隐藏原因之一）。
- `build_glossary()` 汇总时**成对收集**纯文本与富文本字段（同源同序 append），
  杜绝「`zh` 取自 L01、`zh_html` 取自 L03」的错配。
- 详见 `references/pitfalls.md` 第 50 条。

### 修复 · 无头浏览器「退出码 0 + 0 字节 + 不产文件」的根治

- **根因**：Chromium 启动时若认为进程处于「提升的完整性级别」（某些宿主进程/沙箱会给出这种令牌），
  会**派生一个去提权的子进程、父进程立刻退出** —— `subprocess.run` 抓到的是那个马上退场的父进程，
  渲染结果留在子进程里、句柄已跟丢。加 `--enable-logging=stderr --v=1` 才看得到
  `RunDeElevated: Started process, PID: …` / `Histogram: Windows.AutoDeElevateResult`。
- **修复**：`scripts/kitpath.py` 新增 **`browser_flags()`**（Windows 返回 `['--do-not-de-elevate']`），
  `shot.py` / `probe.py` 自动带上；`browser_exe()` 的候选表补上 Chrome **用户级安装**路径
  （`%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe`）。
- **实测结论**：Chrome + `--do-not-de-elevate` 可用；Chrome 不加该参数、Edge（加不加都）不可用。
  遇到仍报「0 字节」时按提示 `set KIT_BROWSER=<Chrome 路径>` 换浏览器。
- `shot.py --selftest` 与失败提示已改成指向这个真因（此前怀疑「Edge 用久了会失灵、需重启」，
  归因错误）。详见 `references/pitfalls.md` 第 29 条（已重写为三种成因）。

### 新增 · 静态断言与自检覆盖

- `scripts/course_check.py` ② 组新增：「入口页内联了 KaTeX」「可见正文里没有〔公式〕占位符」；
  资源自检组新增：「course.js 会渲染公式」「渲染公式在 build 要点索引之前」（顺序断言修正为
  取 `boot()` 函数体内的**调用**位置，而不是 `initKp` 字面量 —— 后者先撞上函数定义，会误报）。
- `templates/probe_course.js` 新增 ①b 公式段：断言 `mathLeft === 0` / `mathFailed === 0` /
  `placeholderLeft === 0`。
- `scripts/selftest.py`：课程样例的要点与术语各补一条**带公式**的内容（空转守卫），
  并断言主页内联了 KaTeX、可见正文无〔公式〕占位符。按第 48 条立的规矩，新检查必须配
  「空转守卫」（断言对象非空）+「反向注入」（故意破坏必须被抓）。
- `scripts/check_docs.py` ⑤ 组：pitfalls 口径同步到 **50 条**（README 两处 + workflow + TODO）。

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
