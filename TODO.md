# TODO — 让陌生人能用起来

> 这份清单只服务于一个目标：**一个不认识作者的人，从点进这个仓库到跑出第一份产物，
> 需要多久、会不会半路放弃。**
>
> 每条都写了「为什么值得做」和「怎么算做完」，可以直接当 issue 用。
> 优先级按「拦不拦人」排，不按「技术含量」排。

## 当前基线（2026-09-24 审计）

| 项目 | 现状 |
|---|---|
| 仓库 | 39 个文件 ｜ 489 KB ｜ 5 个提交 ｜ `main` 分支 |
| 文档 | `README.md`（中文）、`SKILL.md`（410 行 / 27.5 KB，面向 Agent）、`TODO.md` |
| 图片资源 | ✅ **3 张**（`docs/images/`，hero / notes / overview，各约 230 KB） |
| 示例产物 | ✅ **在线 demo 已上线**（`docs/demo/index.html`，1.18 MB）→ <https://zzzhen-22.github.io/slides-annotated-html/demo/> |
| 依赖清单 | **无** `requirements.txt`（真实依赖：`pymupdf`、`pillow`；可选 `node`） |
| CI | **无** |
| topics | **仍为空** —— GitHub 搜索里很难被找到（homepage 已填好） |
| 跨平台 | 代码里已有 macOS / Linux 分支，但**从未在真机验证** |
| 版本号 | 无 tag、无 CHANGELOG |

---

## P0 · 拦在门口：不做这三件，陌生人根本走不到"试用"

### [x] 1. README 加效果截图（至少 3 张）✅ **已完成**
**为什么**：原来 README 全是文字。陌生人无法判断产物长什么样，也就没有理由去装
`pymupdf` + 浏览器这一串依赖。**开源项目的第一转化率来自截图，不是特性列表。**

**怎么做**
- 用一份示例课件跑一遍，截三张最具说服力的：
  ① 首屏（目录 + 概览卡）② 逐页对照（左边讲解 + 右边原页缩略图）③ 划词标记 + 笔记抽屉
- 存 `docs/images/`，单张压到 300 KB 以内（WebP 更好）
- README 顶部放一张主图，特性段落里再插两张

**验收**：README 打开即有图；`git clone` 后离线看 README 图片也能显示（用相对路径，别用外链图床）

> **实测记录**：三张图放在 `docs/images/`，各约 230 KB（1500 px PNG，`optimize=True`）。
> 一个反直觉的点：**降采样到 1200 px 反而更大**（240 KB → 380 KB）—— 插值在大片纯色区域造出渐变，
> PNG 压缩率变差。UI 截图保持原始像素宽度即可。
> README 顶部放 hero（逐页对照），特性段落后并排放概述卡与笔记抽屉两张。

### [x] 2. 提供一份可直接打开的示例产物（demo）✅ **已完成（Pages 已上线，链接可点）**
**为什么**：截图能看，但摸不到。真正的「啊，这东西有用」发生在**自己点一下目录、划一句话**的时候。

**怎么做**
- 做一份 6–10 页的示例课件（内容自造或用公有领域材料），跑出产物
- 体积控制：不内嵌原 PDF 的话约 1–3 MB，适合直接放进仓库
- 放到 GitHub Pages（`docs/` 目录）或 Releases，README 给一个「点这里在线试」的链接

**验收**：README 里有一个可点击的在线预览链接，移动端也能打开

> **实测记录**：`docs/demo/index.html`，**1.18 MB 单文件**，从《逻辑回归 · 逐页精解》63 页里节选 **P1–P8**，
> 含封面、demo 说明卡、前置知识折叠卡、本节概述卡、8 页正文、速查表与术语表。
> 构建走套件自己的 `build.py`（不是手改 HTML），前置做了三件事：
> ① 把每页的「打开原 PDF 该页」换成**停用态 span**（删掉会让 `check_math` 的区块/深链计数对不上）；
> ② 中和 **60 个**指向未包含页面的死链；
> ③ 统一清洗隐私 —— 本机盘符路径（源文件路径里带微信 ID）、第三方个人邮箱。
> 出厂自检：无 `file:///`、无盘符路径、无 `wxid`、无邮箱；`check_math` 全绿（8 页 / 8 缩略图 / 8 按钮）。
>
> **✅ Pages 已开启并验证**：来源 `main` / `/docs`，`GET /repos/.../pages` 返回 `status: built`（HTTPS 已强制）。
> 站点 <https://zzzhen-22.github.io/slides-annotated-html/>，demo 落在 `/demo/`：
> 实测 **HTTP 200 ｜ 1,238,803 字节 ｜ `text/html; charset=utf-8`**，8 页区块与 191 条公式均在线可用。

### [x] 3. 补 `requirements.txt` 和一条最短上手命令 ✅ **已完成**
**为什么**：`kitpath.py` 会提示缺什么，但那要**先跑脚本才知道**。
陌生人习惯先看 README 的安装段，现在那一段只有一句「需要 pymupdf、pillow」。

**怎么做**
- 加 `requirements.txt`（`pymupdf`、`pillow`；注明 `node` 是可选、仅 `check_math.js` 用）
- README 开头给三步：
  ```bash
  pip install -r requirements.txt
  python scripts/kitpath.py          # 自查：python / node / 浏览器 / 依赖
  python scripts/run_all.py examples/sample-lecture.pdf --out demo
  ```

**验收**：在一个全新的 venv 里照抄这三行，能直接跑到出产物

> **实测记录（2026-09-25）**：`requirements.txt` 收 `pymupdf` + `pillow`，**不锁版本**——
> 没验证过旧版本就不写版本下限，脚本用的都是稳定基础 API，装最新版即可。
> 文件内注明 `node` 可选（仅 `check_math.js`）与浏览器的探测方式。
> README「快速开始」顶部加「三步上手」块，环境表同步标注 Node.js（可选）。
> **一处刻意的偏离**：README 第 ③ 步写成 `"<你的课件>.pdf"` 占位，而非本条原设计的
> `examples/sample-lecture.pdf` —— 示例 PDF 属于第 4 条、当时还不存在，
> README 不能指向不存在的文件；第 4 条落地后把占位符换成示例路径即可。
> **验收过程**：Python 3.13 全新 venv 照抄三行（③ 用真课件 7 页替换占位符）→
> pip 干净装上 `pymupdf 1.28.2` + `pillow 12.3.0`（走 pip 缓存，秒级）→
> `kitpath.py` 四项全 ✔ 退出码 0 → `run_all.py` ①–⑧ 全绿、产物正常生成。

### [x] 4. 放一份 3–6 页的示例 PDF 当测试素材 ✅ **已完成（8 页，见实测记录）**
**为什么**：`selftest.py` 会现造一份 PDF，但那是给程序用的，用户拿不到。
没有输入文件，「跑一遍看看」就无从谈起。

**怎么做**：`examples/sample-lecture.pdf`，自制内容（避免版权问题），3–6 页就够，
最好包含**一个公式 + 一张图 + 一个表格**，把套件的能力全展示到

**验收**：上面第 3 条那三行命令里的 `examples/sample-lecture.pdf` 真实存在且能跑通

> **实测记录（2026-09-25）**：`examples/sample-lecture.pdf`，8 页 / 590 KB，
> 节选自一份真实大学物理英文课件（横向 A4，含公式、插图与表格页），
> 经课件持有者确认可作示例使用，故未另造自制内容。metadata 已清为中性值
> （title=Sample Lecture (excerpt)，author/creator/producer 置空）。
> 页序保持原课件顺序，节选页码：原 P1、P2、P5–P10。
> README 快速开始 ③ 的占位符已同步换成 `examples/sample-lecture.pdf`（第 3 条留的尾巴闭环）。
> 验收：照三行命令实跑，`run_all.py` ①–⑧ 全绿。

---

## P1 · 决定「用不用得下去」

### [ ] 5. 加 GitHub Actions，跑 `selftest.py`
**为什么**：项目的质量承诺是「机械部分全绿」，但**没有任何自动化的回归保障**。
贡献者改了 `site.js` 或 `build.py`，没人拦得住。CI 是「这个项目还活着」的信号。

**怎么做**
- `.github/workflows/selftest.yml`，矩阵 `ubuntu-latest` + `windows-latest`
- 装依赖：`pip install pymupdf pillow`、`setup-node`
- **ubuntu 上要装中日韩字体**（`fonts-noto-cjk`），否则缺字体检项会误报
- 无头浏览器：ubuntu runner 自带 chromium，用 `KIT_BROWSER` 指过去；
  或先只跑不需要浏览器的部分（`run_all.py --no-shot`）

**验收**：PR 上出现绿色 check；**顺带证明了 Linux 可用**（一举两得）

### [ ] 6. 在 macOS / Linux 上真机实测并写明支持矩阵
**为什么**：`kitpath.py` 里已经写了 `/Applications/Google Chrome.app/...`、
`/usr/bin/chromium` 这些分支，但**从来没有在真机上验证过**，
「代码里写了」和「能跑」是两件事。

**怎么做**：至少跑一次 Ubuntu（WSL 也算）；有条件再跑一次 macOS。
把结果写进 README 的支持矩阵表。

**验收**：README 有一张表，明确写出「已验证 / 未验证」的平台

### [ ] 7. README 加「已知限制」章节
**为什么**：诚实标注限制比夸大能力更能建立信任，也能减少无效 issue。
这个项目有几条**必须提前说清**的约束，否则用户会认为是 bug。

**要写的（都是真实的）**
- 输入**只支持 PDF**；PPTX/Keynote 请先自行导出（不引入 LibreOffice 依赖是刻意的）
- **PDF 文字层不可靠**，所以流程图、公式必须逐页看图核对 —— 套件不替你判断内容对错
- 机械部分自动，**「逐页写讲解」这一步是留给人的**，套件只告诉你还差几页
- 内嵌原 PDF 时产物 ≈ 原 PDF × 1.34 + 缩略图，几十页课件可能到 20 MB+
- 默认产物是**中文排版优化**的（正文字体栈、标点挤压），英文内容也能用但排版不专门优化
- 无头截图依赖 Chromium 系浏览器

**验收**：README 有独立小节，读完知道什么情况不该用这个工具

### [ ] 8. 英文 README（`README.en.md`）
**为什么**：工具本身与语言无关（能处理任何语言的 PDF），但文档全中文，
国际用户 30 秒内就会关掉。这直接决定了仓库能不能被非中文社区用起来。

**怎么做**：中英双 README，顶部互加语言切换。英文版**精简**即可：
what it does / install / quick start / screenshots / limitations / license

**验收**：一个只读英文的开发者，能凭 `README.en.md` 跑出 demo

---

## P2 · 提升「被发现」与「能贡献」

### [ ] 9. 设置仓库 topics 和 homepage
**为什么**：现在 topics 为空，GitHub 搜索 `pdf slides to html` 之类基本找不到。
这是**成本最低、回报最高**的一条（点几下鼠标）。

> **homepage 已完成**（`https://zzzhen-22.github.io/slides-annotated-html/demo/`），
> **只剩 topics 待填**。一条 REST 请求即可：
> ```bash
> curl -X PUT -H "Authorization: Bearer $T" -H "Accept: application/vnd.github+json" \
>   https://api.github.com/repos/zzzhen-22/slides-annotated-html/topics \
>   -d '{"names":["pdf","slides","lecture-notes","katex","offline-first","html","annotation","courseware","python","agent-skill"]}'
> ```

建议 topics：`pdf` `slides` `lecture-notes` `katex` `offline-first` `html`
`annotation` `courseware` `python` `agent-skill`

**验收**：仓库页右侧出现 topics 标签

### [ ] 10. `CONTRIBUTING.md` + Issue / PR 模板
**为什么**：项目里其实有一套很成熟的「改套件的五条纪律」，
但它埋在 `SKILL.md` 第 400 行附近，**贡献者根本看不到**。

**怎么做**
- 把纪律抽成 `CONTRIBUTING.md`（含：先看 mtime、改完必须重建+三校验+截图、
  资产耦合、不许写死本机路径、模板注释里不许出现字面标签）
- `.github/ISSUE_TEMPLATE/bug_report.md`：要求附 `python scripts/kitpath.py` 的输出
- `.github/ISSUE_TEMPLATE/feature_request.md`

**验收**：打开 New Issue 时能看到模板

### [ ] 11. `CHANGELOG.md` + 语义化版本 tag
**为什么**：仓库没有版本号。用户无法判断「我手上这份是不是最新」「该不该更新」，
而且技能类项目会被反复迭代，没有版本号就没法追溯。

**怎么做**：定 `0.1.0`，打 git tag + Release，`CHANGELOG.md` 按 Keep a Changelog 格式

**验收**：仓库出现 Releases 页；`CHANGELOG.md` 有 `0.1.0` 条目

### [ ] 12. 把 `SKILL.md` 里「给人看」的部分拆到 `docs/`
**为什么**：`SKILL.md` 410 行 / 27.5 KB，**一半是写给 Agent 的指令**
（"先问用户""逐页读图""等主人确认"）。人类读者照着一半内容走会迷路。

**怎么做**
- `docs/workflow.md` —— 人类向：完整工作流、每步在干什么、为什么这一步不能省
- `docs/architecture.md` —— 为什么是这个目录结构、四类交互怎么协作
- `SKILL.md` 保持 Agent 指令，但在顶部声明「人类请先看 README 与 docs/」

**验收**：人类读者不需要读 `SKILL.md` 也能完整走完流程

---

## P3 · 细节打磨

- [ ] **13.** 给 `build.py` / `prepare_pdf.py` / `kitpath.py` 补 `argparse`（现在没有 `--help`）
- [ ] **14.** `run_all.py` 缺 `pdf` 参数时，别甩 argparse 原文，改成打印「三步上手」
- [ ] **15.** 统一所有脚本的致命错误格式为三段式：**问题 + 原因 + 可直接照抄的解决命令**
      （`kitpath.require_deps` 已经是这个风格，其它脚本对齐它）
- [ ] **16.** README 加一张「原 PDF 大小 → 产物大小」换算表，让用户提前知道内嵌 PDF 的代价
- [ ] **17.** 评估**去掉 Node 依赖**：`node` 唯一用途是跑 KaTeX 语法自检。
      若能用 Python 直接调 `vendor/katex`，整条链就只剩「Python + 浏览器」两个依赖，
      对新人的门槛是实质性的下降
- [ ] **18.** `init_project.py` 生成的 `README-项目.md` 里写的是套件绝对路径，迁移后失效 ——
      改成相对路径或运行时探测
- [ ] **19.** `.gitignore` 补 `*.log`、`.pytest_cache/`（若以后加前端再加 `node_modules/`）
- [ ] **20.** 各脚本头部加 SPDX 标识（GPL 的 "How to Apply" 建议这么做，但会让 diff 变吵，
      可等版本稳定后一次性做）
- [ ] **21.** **`check_ui.py` / `templates/probe_doc.js` 假定文档一定有原文件深链** ——
      前者在非内嵌模式下硬性要求存在 `file:///#page=N`，后者按「深链数 == 逐页区块数」比对。
      于是**不提供 PDF 的文档（例如本仓库的 demo）必然报 FAIL**，尽管其它检查全绿。
      建议：config 未给 `pdf` 时跳过这两项，或在输出里写明「本次未提供原文件，深链检查已跳过」。
      *（这一条是做 demo 时实测撞出来的，不是推测。）*
- [ ] **22.** demo 的生成脚本没进仓库（含作者本机路径与素材位置）。
      若希望 demo 可重建，把它脱敏后放进 `docs/`，参数化成「源项目目录 → 输出 demo」的一步命令
- [x] **23.** 在线 demo 地址已写进仓库 **homepage** 字段
      （`https://zzzhen-22.github.io/slides-annotated-html/demo/`）。
      徽章**不做** —— README 顶部已经有醒目的「▶ 点这里在线试一下」，比徽章显眼得多；
      再挂一排徽章只会让首屏变吵

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

**做第 1 条：放截图。**
成本最低（跑一次就有），收益最大（决定陌生人要不要继续往下读）。
第 2 条紧跟其后 —— 截图 + 在线 demo 之后，这个仓库才算「可以被别人评估」。
