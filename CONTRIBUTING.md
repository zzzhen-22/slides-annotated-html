# 贡献指南

这个项目有两个身份：一份**可安装的 Agent Skill**（放进 agent 的技能目录就能用），
和一个**普通 Git 仓库**（`scripts/` + `assets/` + `templates/` 是套件本体）。
改仓库里的代码，等于改所有装了这个技能的人手里的东西 —— 所以这里的门槛写得很具体。

先读三份东西（约 15 分钟，值得花）：

| 文件 | 为什么先读它 |
|---|---|
| [`SKILL.md`](SKILL.md) | 套件自己的执行指令，说清「哪些事必须做、哪些不许做」 |
| [`references/pitfalls.md`](references/pitfalls.md) | 踩坑清单，按「频率 × 隐蔽度」排序。**动手前搜一遍关键词**，多数怪现象的根因都在里面 |
| [`TODO.md`](TODO.md) | 路线图 + 现状基线。挑活干之前先看这里，避免做完发现方向已经变了 |

---

## 开始之前

```bash
python scripts/kitpath.py        # 环境自查：python / 浏览器（必需）+ node（可选）+ Python 依赖
python scripts/selftest.py       # 四条自查线，约 1–3 分钟；必须是「自检结果: PASS」
```

第二步不是可选项：**先确认你从一个已知基线出发**。如果 `selftest.py` 不是 PASS，
先修它，不要在上面叠新改动 —— 否则你分不清哪一处红是你弄出来的。

> 无头体检与截图需要 Chromium 系浏览器（Chrome / Edge）。自动探测失败时用
> `KIT_BROWSER=<浏览器可执行文件绝对路径>` 指定。`node` 只影响公式语法自检，
> 缺了会自动跳过（见 README「不装 Node 会少什么」）。

---

## 改之前的第一个动作：看 mtime

不要凭记忆假定文件内容 —— `assets/` 与 `scripts/` 可能刚被别的会话或别的分支改过。

```bash
ls -l assets scripts | head -30
```

---

## 五条纪律

1. **改完必须「重建 + 体检 + 截图」三连。**
   单讲改完重跑 `run_all.py`，课程层改完重跑 `run_course.py`；
   只改外壳（`assets/`）也要按下面的表跑一遍对应体检，并把新产物与旧产物 diff ——
   **目录块应当逐字节一致**，差一个字节就说明你改了不该改的地方。

2. **资产是耦合的。**
   改 `assets/shell.html` 的类名，就得同步改 `assets/site.css` / `assets/site.extra.css` /
   `assets/site.js`。只改一处，页面要么裸奔（无样式）要么交互失效（点了没反应）。
   课程层同理，但它的三份资产（`course-shell.html` / `course.css` / `course.js`）
   与单讲**完全分开**，不要互相引。

3. **不许写死本机路径。**
   校验：`grep -rn "/home/\|/Users/\|C:/Users/" scripts/ assets/ templates/` 应当无命中。
   路径一律交给 `scripts/kitpath.py` 探测，或走相对路径。

4. **模板注释里不许出现字面标签。**
   `build.py` 用非贪婪正则匹配整段区块，注释里写一个假的 `<section>` 会让它提前收尾。
   症状是「图在文件里，但 DOM 里查不到」，极难排查（见 pitfalls 第 18 条）。
   描述标签时写成「开标签 / 收尾标签」，或把 `<` 换成全角。

5. **新增检查必须配「反向注入」。**
   先把代码改坏 → 确认它**真的报红** → 再还原。没有这一步，你写的可能是一条
   「永绿的空检查」：断言恒为真，看着全绿，实际上什么都没查（pitfalls 第 48 条）。
   仓库里的 `_analysis/` 外部脚本与 `selftest.py` 的反向注入用例都是这么来的。

---

## 改完必须跑什么

| 你改了什么 | 必须跑什么 |
|---|---|
| README / SKILL / TODO / 任何文档 | `python scripts/check_docs.py`（秒级） |
| `assets/`（外壳 CSS / JS / shell.html） | 重建 demo → `check_math.js` + `check_ui.py` + 对应探针；**外壳改动通常还要重截预览图** |
| `scripts/*.py`（机械链路） | `python scripts/selftest.py`（四条线） |
| 课程层（`course_*.py` / `assets/course-*`） | `python scripts/run_course.py <课程目录>`（含课程探针） |
| demo 源工程（`examples/demo/`） | `python scripts/build_demo.py` → `shoot_previews.py` → `build_demo.py --check` |
| **任何改动之后** | `python scripts/selftest.py` |

`selftest.py` 是唯一的兜底：它把机械路线、语义路线、课程路线（含两发真实浏览器探针）
与文档口径四条线串在一起。**它绿了才算改完。**

表里那几号脚本各自管什么，见 README 的「三重校验各管一段」。

---

## 改完必须同步哪些文档

这套文档曾经因为「代码改了、文档没跟上」漂移过 6 处，所以现在由 `check_docs.py`
常驻把关。但它只能查**有共同真源**的口径，下面这些仍需你手动同步：

| 你改了什么 | 必须同步的位置 |
|---|---|
| 交互项数（增删一项交互） | `scripts/check_ui.py` 的 docstring（**唯一真源**）→ `README.md` / `README.en.md` / `SKILL.md` / `docs/workflow.md` / `run_all.py` 注释 |
| 流水线新增一步 | `scripts/run_all.py` docstring 的步骤列表 → README 与 README.en 的校验表（两个都要） |
| 新增脚本 / 模板 | `README.md` 的「目录结构」目录树（`check_docs.py` ⑥ 会抓漏列） |
| 新增 pitfalls 条目 | 只改 `references/pitfalls.md`；别处的「N 条」由 `check_docs.py` ⑤ 自动核对 |
| 版本号 / 发版 | `CHANGELOG.md`（Keep a Changelog 格式）+ README 的基线表 |
| 改了 `assets/` 或 demo | 重截 `docs/images/` 的四张预览图（`shoot_previews.py`），否则门面会静默过期 |

**数字不要写死在文档里。** 说「全套体检」而不是「七项体检」，说「六类交互」时以
`check_ui.py` 的 docstring 为准 —— 写死的数字一定会漂。

---

## 提交与 PR

- **一次提交只做一件事。** 内容跨版本交错时（同一个文件里两版的新增行挨着），
  逐行点名归属，不要用「按行号切」的锚点法。
- commit message 用传统前缀：`feat:` / `fix:` / `docs:` / `test:` / `release:`，
  后半句写「为什么」而不是「改了什么」（改了什么看 diff 就知道）。
- PR 描述里请附上：**改了什么 → 动了哪条链（单讲 / 课程层 / 套件自身）→ 跑了哪些体检 →
  输出里的关键几行**。CI 会在 ubuntu 与 windows 双平台跑 `selftest.py` 与
  `build_demo.py --check`，本地全绿不等于 CI 全绿（中文编码、换行、字体差异都踩过）。

---

## 发布（维护者）

1. `CHANGELOG.md` 顶部加 `## [vX.Y.Z] - YYYY-MM-DD`（Keep a Changelog 格式）。
2. README 与 README.en 的版本号、TODO 的基线表同步更新，跑 `check_docs.py`。
3. 打 **annotated** tag（tag message 第一行就是 Release 标题），推送后建 Release。
4. 推完核验远程 tag SHA 与本地 `git rev-parse <tag>` 一致。

版本号用 SemVer：新增功能升 minor，修复升 patch。开发期的快照 tag（`v2.0-semantic-outline-step*`
这类）不是版本号，不要写进 CHANGELOG 的正式段落。

---

## 有问题

先搜 `references/pitfalls.md` 与已有的 Issue。还找不到，按
[`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/) 里的模板提 Issue ——
**bug 报告里请附 `python scripts/kitpath.py --json` 的输出**，它能一次性回答
「哪个平台、哪个浏览器、缺哪个包」这三个最常来回问的问题。
