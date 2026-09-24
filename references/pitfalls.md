# 踩坑清单（PDF/PPT 课件 → 对照式 HTML）

按「出现频率 × 隐蔽程度」排序。每条都写明**症状 → 原因 → 处理办法**。

---

## 一、内容准确性类（最致命，错了会讲错知识点）

### 1. 绝不能只靠 `get_text()` 抽文字就动笔

**症状**：抽出来的公式像这样 ——

```
Ã ® (v) = 1 / (1 + exp(¡ ®v))
p(yj¼) = ¼ ify = 1 ... 1 ¡ ¼ otherw ise
y¤= arg m ax y2 Y p(yjx)
```

**原因**：PPT 导出 PDF 时，数学符号用的是嵌入子集字体，ToUnicode 映射是坏的，
`get_text()` 拿到的码位与实际字形不对应。**同一个坏码位在不同文件里含义还不一样。**

**实测对照表（清华 AI 导论课件，仅供参考——换文件必须重新核对）**：

| 码位 | 真实含义 | | 码位 | 真实含义 |
|---|---|---|---|---|
| `¡` | 减号 `−` | | `¼` | `π` |
| `®` | `\mathbf{w}` | | `Ã` | `\sigma` |
| `2` | `\in` | | `¤` | `*` |
| `j` | `\mid`（条件竖线） | | `°` | `\cdot` |

**处理办法**：一律渲染成图（`prepare_pdf.py` 产出的 `page-*.png`）**逐页目视确认**。
遇到拿不准的公式，用高分片局部放大（`page.get_pixmap(dpi=400~900, clip=Rect(...))`）单独看。
判不出某个符号时，用「语义反推」交叉验证 —— 例如 `exp(¡ ®v)` 中的 `¡` 在
Sigmoid 公式里必然是减号，因为 \(\frac{1}{1+\exp(+v)}\) 不可能把实数压到 (0,1)。

### 2. 课件里的公式可能真的写得不严谨，照抄即可，但要在讲解里加注

**本任务遇到的三处**：

| 现象 | 处理方式 |
|---|---|
| P55 有一个蓝色色块挡住 Sigmoid 定义式（原 PPT 动画对象被压平） | 从 PDF 文字层还原被遮内容，并在讲解里加红框提示「原页此处有遮挡」 |
| P11–P15 红/蓝配色自相矛盾（沿用旧讲义图片，红色有时代表 A 类有时代表 B 类） | 讲解**一律以原页标注的数字为准**（10:2、3:9、6:6），不依赖颜色位置，并加提醒 |
| P20 积分上下限写作 `-1` 到 `1`（x 已归一化），与通用写法 `±∞` 不同 | 保留原样，加注「更一般的写法是 ±∞，含义相同」 |

**原则**：忠于原文件 ≠ 假装原文件没有毛病。**照原样保留 + 明确标注**，读者才不会混乱。

### 3. 大纲与正文可能不一致

**症状**：第 4 页 Outline 列了 5 个主题，正文只讲了 3 个。

**处理办法**：**先问用户**（这类偏差属于「该补还是该略」的判断，不该替用户决定）。
本任务的结论是：正文严格保持原顺序不插入，缺失的两节作为「补充篇 A/B」放在正文之后，
**不占用原页码**，并在文档里显式说明「原文提及但未展开」。

---

## 二、公式渲染类

### 4. KaTeX 的 `#` 是宏参数符

**症状**：`KaTeX parse error: Expected 'EOF', got '#' at position 49`

**原因**：正文里写 "`# of samples`"。`#` 在 TeX 里是参数占位符。

**处理**：写成 `\#`。或者干脆改成 "number of"。

### 5. 中文不要塞进 `\text{}`

**症状**：公式里的中文用兜底字体渲染，字距错乱、与符号对不齐。

**原因**：KaTeX 自带字体不含 CJK 字形。

**处理**：中文一律放在公式外的 HTML 里。需要旁边的注释就在公式后面加一个
`<span class="gloss">（样本均值）</span>`。`assets/site.css` 里已经定义了 `.gloss`。

### 6. 用 `<script type="math/tex">` 承载 LaTeX 源码

**好处**：`<script>` 的内容按**原始文本**解析 —— 反斜杠、花括号、`<`、`&` 全都不用转义，
只有出现 `</script` 才会截断（LaTeX 里不可能出现）。

```html
<script type="math/tex">\theta^{*}</script>                 <!-- 行内 -->
<script type="math/tex; mode=display">\frac{1}{2}</script>  <!-- 独立成行 -->
```

`assets/site.js` 会遍历它们并调 `katex.render` 替换成 `<span>`。

---

## 三、构建与体积类

### 7. woff2 之外的字体格式要删掉

**症状**：字体体积 1.2 MB（`du -sh fonts`），内嵌后 base64 膨胀到 1.6 MB。

**原因**：`katex.min.css` 每个 `@font-face` 的 `src` 都列了 woff2 / woff / ttf 三份。

**处理**：用正则把每条 `src:` 裁到只剩 `.woff2` —— **实测 20 个 woff2 合计只有 296 KB**，
base64 后约 400 KB，完全可接受。`katex_offline.py` 已内置这一步。

### 8. 缩略图分辨率要先算体积再定

实测规律（16:9 或 4:3 的单页 PPT，内容以白底文字为主）：

| 宽度 | 质量 | 63 页合计 | base64 后 |
|---|---|---|---|
| 680 px | 72 | 1.71 MB | 2.3 MB |
| 860 px | 75 | 2.44 MB | 3.27 MB |

**建议 860–900 px / quality 75**：占满屏放大时公式仍可读，总体积约 2.5 MB。
600 px 以下放大后公式会糊，不建议。

### 9. 先说清楚「单文件」还是「多文件」

单文件 HTML 的代价就是体积（本任务最终 4.12 MB）。如果用户在意体积，
可以走多文件：`index.html` + `katex/` 目录 + `img/` 目录，共享性更好、体积小得多。
**开工前问一句，比做完返工便宜。**

---

## 四、验证类

### 10. 无头截图时 `#fragment` 不生效

**症状**：`msedge --headless --screenshot ... "file:///x.html#p52"` 截到的永远是页面顶部。

**处理**：临时生成一份副本，注入
`<style>.card:not(#p52){display:none!important} .pg:not(#p52){display:none!important}</style>`，
让目标区块排到最前，截完删掉。`shot.py --section p52` 已封装好。

### 11. Edge 首次运行隐私弹窗会污染截图

**症状**：截到「微软重视您的隐私」对话框。

**处理**：必须同时加 `--user-data-dir=<临时目录>` 和 `--no-first-run --no-default-browser-check`。
`shot.py` 每次用 `tempfile.mkdtemp()` 建独立 profile 并清理。

### 12. URL 必须是三个斜杠

**症状**：页面白屏或 404。

**错误**：`file:////D%3A/...`（多一个斜杠 + 盘符冒号被编码）
**正确**：`file:///D:/path/to/x.html`
用 `urllib.parse.quote(path, safe='/:')`，**注意 safe 里要保留 `:`**。

### 13. 公式批量自检一定要做

**做法**：Node 里加载 `katex.min.js`，对每段调
`renderToString(tex, {throwOnError:true, strict:'error'})`。
本任务 897 条公式一次跑出 2 处 `#` 错误 —— 靠肉眼是绝对发现不了的。

`scripts/check_math.js` 除了公式，还会顺手做标签配对、目录锚点、缩略图数量三项体检。

### 14. PDF 深链（`#page=N`）可以点，但别当成唯一入口

`file:///D:/x.pdf#page=12` 在 Chrome/Edge 里能直接翻到第 12 页。
但仍然要提供页内锚点 + 缩略图，因为：① 系统可能改默认阅读器；② 部分浏览器限制 `file://` 跳转。
**深链是锦上添花，缩略图才是保底。**

---

## 五、环境类（本机实测）

> 这一节记的是**本机环境事实**，套件本身不依赖它们 ——
> 所有脚本都用相对自身位置定位资源，`node` / 浏览器自动探测
> （见 `scripts/kitpath.py`）。换机器后先跑一次 `python scripts/kitpath.py` 自查。

- **`agent-browser` 没装**，装它要下 ~500 MB Chromium。本地 HTML 验证用系统自带 Edge 无头截图即可（`shot.py`）。
- **Git Bash 的 `$PATH` 缺 `/usr/bin`**，`ls`/`head`/`dirname` 会报 command not found。
  补救：`export PATH="/usr/bin:/mingw64/bin:$PATH"`。
- **`reg.exe` 在黑名单里**，读注册表改走 Python `winreg`。
- **PowerShell 工具 stdou 抓不到**，要读结果就 `Out-File` 到临时文件再 Read。
  写 `.ps1` 一律纯 ASCII，含中文的结果用 `-Encoding UTF8` 输出到文件。
- Python 环境：本机用 `~/.workbuddy/binaries/python/envs/default`（已装 `pymupdf` / `pillow` / `numpy`）。
  **套件不写死这个路径** —— 脚本用 `sys.executable`，文档示例用 `command -v python`。


---

## 六、交互功能相关的坑（目录折叠 / 概述卡 / 侧栏收起 / 标记笔记）

### 15. file:// 下所有本地页面共享同一个 localStorage 域

**症状**：同一台机器上打开两份不同的讲解文档，A 里做的标记出现在 B 里。
**原因**：`file://` 是不透明源，Chromium 把本地页面归到同一个存储域。
**处理**：build.py 必须按文档注入命名空间 ——
`DOC_NS = 'lr-doc:' + md5(title + '|' + 配置里的输出路径)[:10] + ':'`，
`site.js` 里所有 key 都拼在 `NS` 前面。注意：改输出路径会让旧标记「消失」（预期行为，
所以种子要用配置里的 out，而不是 `--out` 的覆盖值，否则试构建会和正式构建串成两份）。

### 16. 无头截图里 CSS transition 不推进

**症状**：`--virtual-time-budget` 下截图，抽屉／侧栏停在动画**开始前**的位置
（表现为「抽屉跑到屏幕外」），用 `getBoundingClientRect()` 量出来的 x 也超出 viewport。
**原因**：virtual time 快进定时器，但不推进 CSS 过渡。**这是测试假象，不是产品 bug。**
**处理**：注入的测试脚本里先加一段样式禁用过渡再触发交互：
`st.textContent='.drawer,.toc,.selbar{transition:none!important}'`。

### 17. 脚本取词标记时，别取到 KaTeX 的 MathML

**症状**：用 `__doc.addNote(sec, quote)` 造测试标记，抽屉里显示 LaTeX 源码。
**原因**：KaTeX 渲染后同时产出 `.katex-html`（可见）与 `.katex-mathml`（隐藏，内含 LaTeX 原文）。
脚本按「第一个够长的文本节点」取词，很容易取到 MathML 里的源码；而用户的鼠标选择取不到它。

**处理（2026-09-24 起已从「靠人注意」升级成「代码里统一口径」）**：
`site.js` 的 `projOf()` 会跳过 `.katex-mathml` / `annotation`，取词与定位**共用这一套投影**，
所以 `__doc.addNote(pid, quote)` 只要传**可见文字**（原文里能看到的片段）即可，
不用再手搓 prefix，也不会再取到 LaTeX 源码。测试脚本仍然建议跳过 `.katex-mathml` 取词，
理由见第 26、27 条。

### 18. Chromium 在 8.3 短路径的 --user-data-dir 下静默失败

**症状**：截图命令退出码 0、无任何 stdout/stderr、不生成文件，看起来像「浏览器没反应」。
**原因**：`tempfile.gettempdir()` 在某些 Windows 环境下返回 `SHENYU~1` 这类短名，Chromium 不接受。
**处理**：`shot.py` 里的 `long_path()` 用 `GetLongPathNameW` 展开；profile 也不要放在项目盘上。
同类症状还可能是 Edge 长时间批量调用后整体失灵（此时 `--version` / `--dump-dom` 也全无输出），
应改用 `check_ui.py` 兜底，**不要反复重试，更不要 `taskkill msedge`**
（用户自己的浏览器也是同名进程，先按 CommandLine 过滤 headless 再动）。

### 19. 页脚会重复

**症状**：页面底部出现两个页脚。
**原因**：外壳模板有一份，正文最后一个分片里也有一份。
**处理**：正文分片只放 `<section>`，页脚交给 `shell.html`；
改完用 `html.count('class="doc-foot"')` 验一下，应为 1。

### 20. 覆盖技能资产之前先看 mtime（这条是给自己看的）

**本次真实事故**：重建项目时，把 `assets/site.css`、`assets/site.js`、`scripts/build.py`、
`scripts/check_math.js` 按「记忆中的旧版本」重写了，而这些文件**已被并行会话改过**
（新增了 `site.extra.css`、`check_ui.py`、`shot.py` 的短路径修复）。
幸好产物里带着那些功能，CSS/JS 能从 HTML 里抢救回来；`build.py` 则只能靠
「重建后与旧产物 diff、目录块逐字节一致」来反证还原正确。

**教训**：动技能文件前先
`find <技能目录> -type f -printf '%TY-%Tm-%Td %TH:%TM %s %P\n' | sort`；
改动后必须拿**旧产物做回归 diff**，而不是凭感觉说「应该没变」。


### 21. 网页压不住浏览器的「选区迷你菜单」（用户实际踩到的）

**症状**：选中文字后，自己画的「标记」浮层被系统菜单盖住、点不到。
**原因**：Edge 选中文本会浮出自己的迷你菜单（复制 / 搜索 / Copilot…）。
**那条菜单由浏览器 UI 层绘制，不是页面 DOM，`z-index` 调到多大都压不住。**
**解法（三管齐下，见 `assets/site.js`）**：

1. **避让**：把工具条优先放到选区**下方**（`useBelow`，`r.bottom + 12`）。
   系统迷你菜单默认出现在选区**上方**，错开即可；下方空间不足时才翻回上方。
   最后还要把 top 夹紧到视口内，避免贴边时只露出一半。
2. **给不依赖浮层的入口**：顶栏常驻 `#markBtn` + 快捷键 `M`。
   这两条完全不与系统菜单竞争，是真正的兜底。
   注意点按钮时浏览器可能已经把选区收起来了 —— 所以要有 `lastSel` 缓存，
   并在按钮上 `mousedown → preventDefault()` 保住选区。
3. **有选区时接管右键**：`contextmenu` + `preventDefault()` 弹自绘菜单，
   系统菜单根本不会出现，两者互斥自然不遮挡。**菜单里必须补上「复制」**，
   否则用户失去这个能力；并保留 `Shift + 右键` 放行给系统菜单。

顺带一提：也可以让用户自己在 Edge「设置 → 外观 → 迷你菜单」里关掉它，但**不能只靠这个**。

### 22. 无头虚拟时间下 `scroll-behavior: smooth` 同样不推进

**症状**：探针里 `element.scrollIntoView()` 之后，`getBoundingClientRect()` 返回的
`top` 仍是几万像素（说明页面根本没滚动），于是工具条定位、避让判定全部失真。
**原因**：和 CSS transition 一个道理 —— `html{scroll-behavior:smooth}` 让滚动变成动画，
`--virtual-time-budget` 快进定时器但不推进动画。
**处理**：探针脚本里连同过渡一起禁用：
`st.textContent='.drawer,.toc,.selbar{transition:none!important} html{scroll-behavior:auto!important}'`。
排查这类「量出来的坐标离谱」的问题时，**先怀疑是不是测试环境把动画按住了**，别急着改产品代码。


### 23. 「定位失效」误报：先 render 后上色 + 压缩空白比对（用户实际踩到的）

用户反馈「笔记卡片总是挂着黄框『定位失效』，但正文里明明有黄色高亮」。**其实是两个 bug 叠在一起。**

**Bug A（主因，必现）：渲染顺序反了。**
`Notes.add()` 内部会 `render()` 出卡片，而卡片的存活判定是
`document.querySelector('mark.hl[data-nid="…"]')`，**上色 `wrapRange()` 却发生在 `add()` 之后** ——
卡片生成那一刻 DOM 里根本没有这个 mark，于是被判成 stale；
而且之后没有任何一次重绘，徽标就一直留着。
> 为什么自动化测试没发现：`window.__doc.addNote()` 这个测试入口在 `restore()` 之后
> **又补了一次 `Notes.render()`**，正好把顺序补对了。`Notes.add()` 内部那次 render 没人重试。**测试入口和真实入口走了不同的代码路径 —— 这是最阴的一类假绿。**
**修法**：`markSelection()` 里 `wrapRange()` 之后无条件再 `Notes.render()` 一次。

**Bug B（潜伏，刷新后才现形）：比对空间不一致。**
存进笔记的 `quote` / `prefix` 是**压缩过空白**的（`\s+ → ' '`），而 `locate()` 却拿它去
`indexOf` **原始文本**。源码里一段写成两行的 `<p>`，原始文本中间就有换行 + 缩进，
跨行选区必然匹配失败 → 刷新后真的定位不到。
**修法**：`locate()` 里同步构造「压缩空白串 + 压缩下标 → 原始下标」的映射，
在压缩空间里匹配，再映射回真实文本节点。**别用 trim 后直接 indexOf 原始字符串。**

**验收方式**（探针要复现真实入口，别只调 API）：
选一段文字 → `mouseup` → **点工具条上的「标记」按钮** → 断言
`#drawerList .ni-stale` 数量为 0；再把所有 `mark.hl` 拆掉、跑一次 `restoreAll()`，
模拟「重新打开文件」，断言 `{ok:n, fail:0}`。


### 24. 原文件链接的可迁移性（绝对路径 → 内嵌）

**问题**：默认生成的深链是
`file:///D:/path/to/slides.pdf#page=N` ——
**绝对路径，换设备必然失效**；而且 `#page=N` 只在浏览器用内置阅读器打开 PDF 时有效，
浏览器若被设成「下载 PDF」就只会下载。
（正文缩略图是 base64 内嵌的，所以换设备后「对照原图」不受影响，只有这个按钮废掉。）

**解法**：`embed_pdf: true` —— 把原 PDF 以 base64 塞进 HTML（`<script type="text/plain" id="pdfB64">`），
点击时**惰性解码成 Blob**、用 `blob:` URL 打开并拼上 `#page=N`，另加一个「另存原 PDF」按钮。

要点：
- **用 `blob:` 不要用 `data:`**：浏览器会拦截顶层 `data:` 导航，`blob:` 不会。
- **惰性 + 缓存**：不要一打开页面就解码（1.5 MB），首次点击再解码，之后复用同一个 blob URL。
- **体积代价** = PDF 大小 × 1.34。本例 1.53 MB 的 PDF → HTML 从 4.20 MB 涨到 6.25 MB。
- **`<script type="text/plain">` 承载 base64**：script 内容按原始文本解析，
  base64 里不可能出现 `</`，不会截断；比塞进属性或 `data-uri` 都安全。
- **`#page=N` 在 `blob:` 上是否生效无法在无头环境验证** ——
  headless Chrome **不加载 PDF 阅读器插件**，导航到 PDF 只会得到一张空白截图
  （实测 `#page=1` 与 `#page=30` 的截图都是 5060 字节空白）。
  **所以：要么让用户自己点一次确认，要么直接上 pdf.js。**
  作为兜底，打开时用 toast 报出页码（「已打开内嵌原文件 · 第 12 页」），至少不会迷失。
- **`hidden` 属性会被 `display:inline-flex` 顶掉**：`.tb-btn[hidden]{display:none!important}` 必须显式写，
  否则那个「另存原 PDF」按钮在非内嵌模式下也会露出来。


### 25. 目录里「比视口高的章节」下半段永远滚不出来（用户实际踩到的）

**症状**：左侧大纲里把一级章节完全展开后，高度超过导航栏的章节（例如「二」1815px、
而导航栏只有 536px）**向下滚动时看不到它的下半段**。
更诡异的是：滚动条位置在动，但内容几乎不动。

**根因**：基础样式表 `site.css` 里遗留了**旧版扁平目录**的一条规则：

```css
.toc-group{ font-size:11.5px; font-weight:700; ... ; position:sticky; top:-10px; ... }
```

旧版里 `.toc-group` 是「分组标题」（一行文字，本来就该 sticky）；
改造成**两级嵌套**后 `.toc-group` 变成了**包住整章的容器**。
于是整个「二」容器被设成了粘性定位 ——
**粘性元素一旦比滚动视口高，被钉住后超出视口的那部分就再也无法通过滚动显示出来。**

**修法**：
- 删掉 `site.css` 里那条过期规则（并留下注释说明为何不能恢复）；
- 在 `site.extra.css` 里加**显式兜底**：`.toc-nav .toc-group{position:static}`；
- 保留真正需要的粘性：`.toc-nav>.toc-group>.toc-head{position:sticky}`（一级表头）。

**这个 bug 的排查手法值得记住（症状极其反直觉）**：

1. **先量「内容坐标」而不是看截图**：`contentY = rect.top + nav.scrollTop - nav.top`。
   修复前把 `scrollTop` 从 0 改成 1989，某个条目的 contentY 从 2471 **变成 3740**
   （漂移 +1269）—— 内容在滚动时被重新布局了，这是「容器被钉住」的铁证。
   修复后漂移为 **0**。
2. **别被截图骗**：`scrollTop` 读回来是对的（1989），但画面内容没动。
   截图与 DOM 读数矛盾时，**用 DOM 读数 + 在页面上叠加调试读数再截图**，
   两面互相印证，别只信其中一面。
3. **全文检索 CSS 属性**：`position:sticky` 只有在构建产物里搜才靠谱。
   注意**先把 CSS 注释剥掉再搜** —— 注释里提到过这个属性名的话，
   会把检查搞出一堆假阳性（我第一次就被自己的注释坑了）。
4. **别对 6MB 的产物全文跑复杂正则**：产物里含缩略图与内嵌 PDF 的 base64，
   `([^{}]+)\{...\}` 这类回溯型正则会退化到极慢、被环境 SIGTERM 杀掉。
   先用字符串 `find` 抠出 `<style>` 段（约 400KB）再匹配。
5. **同时新增回归检查**（已加进 `check_ui.py` 第 ⑦ 节）：
   断言 `.toc-group` 不带粘性定位、有 static 兜底、一级表头仍粘性。


### 26. 跨元素划词上色会把 DOM 结构搬坏（用户实际踩到的：标记处多出换行 / 表格散架）

**症状**（用户原话）：
- 「给表格内容跨格划线时，原文中表格的格式会乱掉」；
- 「标记处会插入不该有的换行，而且被标的内容没有高亮」。

**根因**：`wrapRange` 用 `range.surroundContents(mark)`，跨元素时它抛
`InvalidStateError`（有非 Text 节点被「部分包含」），旧代码于是退回
**取出内容再插回**那条退路（extractContents → appendChild → insertNode）。
那条退路会把被「部分包含」的元素**克隆进 `<mark>`**，而 `<mark>` 是行内元素：

- 吞了 `<p>`：浏览器把 `<p>` 当独立块渲染 → 标记处凭空多一个换行；
  同时 inline 盒子被块级子元素打断，`mark.hl` 的背景渐变画不出来 → 「不再高亮」。
- 吞了 `<td>`：单元格被搬进 `<mark>`，整张表散架。

**实测数据（修复前）**：

| 选区 | 段落块数 | `<mark>` 内的块级元素 | 表格 td 数 |
|---|---|---|---|
| 跨两段 | 27 → **29** | **2 个 `<p>`** | — |
| 跨两格 | — | **3 个** | 8 → **10**（表格里凭空多出 2 个 td） |

**修法（`assets/site.js` §7）**：**只对「文字节点内部的一段」动手，永不搬动元素。**
1. `leafSegments()`：把 range 拆成「文字节点级」的片段；**纯空白片段直接跳过**
   （它正是「标记处多一个换行」的另一种来源）。
2. `blockAncestor()` 按最近块级祖先**分组**（跨单元格 → 每格一组）。
3. `wrapGroup()` 组内**二分收敛**：先试整组包一个 mark，失败就对半拆开再试；
   最后落到单节点级别 —— 单节点内的 range `surroundContents` 必然成功且无副作用。
4. **刻意不用 extractContents 兜底**：宁可把一条笔记拆成多个 mark，也不克隆元素
   （克隆残骸会让「删除标记」不干净，反复标记/删除会不断堆积）。
   实测：跨格选区现在会拆成 6 个 mark（每格/每内联片段一个），但表格
   `tr/td` 数量、块级元素数量、可见文本**全部一字不变**。

**为什么 `audit()` 要同时看 `blockInsideMark`**：这是该 bug 的判定指标。
一条笔记拆成 N 个 mark 是正常的；**任何一个 mark 里有块级元素就是坏了**。

**回归验证**（两条命令，都应输出 PASS）：
```bash
python scripts/probe.py <输出.html> scripts/probe_marks.js
# 探针会自动找 4 种典型选区（跨格 / 跨段 / 跨公式 / 单段），断言
# 结构指纹不变 + 无块级元素进 mark + 无零宽 mark，然后拆掉全部 mark 再 restoreAll 复查一遍。
```


### 27. 「重新进入页面后标记全部失效」：记录的文本空间与定位的文本空间不同源

**症状**：标记时一切正常，重新打开文件后抽屉里挂着黄框「定位失效」，正文里没有高亮。
实测：跨格 / 含公式的两条笔记重开后 **0 个 mark**，单段纯文字那条正常。

**根因（两条叠加）**：

1. **空白口径不一致**。浏览器 `Selection.toString()` / `Range.toString()` 会在
   **块级边界插 `\n`、在表格单元格边界插 `\t`**（Blink 的
   `ShouldEmitNewlineBeforeNode` / `ShouldEmitTabBeforeNode`），
   而定位用的是 `TreeWalker` 直接拼接文本节点 —— **不带任何分隔符**。
   于是标记时存下的 `quote` 在回访时必然匹配不上：
   - 单元格：源码 `</td><td>` 之间没有空白，浏览器却插了 `\t` → 存 `"…值 实数…"`、找 `"…值实数…"`；
   - 含公式的选区更惨，见下条。
2. **KaTeX 隐藏副本被算进文本**。KaTeX 以 `htmlAndMathml` 输出，同一串公式在 DOM 里
   有 2–3 份：`.katex-mathml`（`M`）、`annotation`（`\mathcal{M}`）、`.katex-html`（可见的 `M`）。
   实测同一个数字 `20.50` 在文本里出现 **三次**（`20.5020.5020.50`），
   于是 quote 脏、`locate()` 还可能把标记打在 `.katex-mathml` 上 ——
   那是 `clip:rect(1px,1px,1px,1px)` 的隐藏副本，**用户什么都看不见**。

**修法**：
- `projOf(root)` 建「**可见文本投影**」（跳过 `.katex-mathml` / `annotation` / `script` 的子树），
  **存与找都走它** —— 一条笔记的 `quote`/`prefix` 由 `canon(sec, range)` 统一从投影里取，
  不再用 `Range.toString()`。副作用是抽屉里显示的摘录也变干净了
  （`20.50` 只出现一次，不再是 `20.5020.5020.50`）。
- `locate()` 分层匹配：`T1` 压缩空白(prefix+quote) → `T2` 压缩空白(quote) →
  `T3` 去空白(prefix+quote) → `T4` 去空白(quote)；
  每层收集**全部**出现位置，再用 `rankRange()` 挑「起止落在同一个块内」的候选
  （分数 0 优先，涉及表格/列表的候选排最后）。
- **自愈**：命中 `T3/T4`（或旧记录兼容层）后，用 `canon()` 把 `quote/prefix` 重写回规范形式存好，
  下次就能在 `T1` 一次命中。
- **旧记录兼容层** `locateLegacy()`：老版本存下来的 quote 混着隐藏副本，
  在「含隐藏副本」的空间里再找一遍，找到后把边界 **吸附到可见文本**（`snap()`）——
  这样既救回旧笔记，又不会把标记打在 1px 的隐藏副本上。
  实测：4 条旧格式笔记（跨格 / 含公式 / 单段 / 跨段）**全部救回**，且 quote 被自动改写成规范形式。

**排查手法**：写个探针把三种文本空间逐字符打出来（`charCodeAt` 转 `U+xxxx`），
一眼就能看出是谁多插了 `\t`、谁多算了一份公式。


### 28. 重叠的标记会嵌套（正常现象，别当 bug 修）

**现象**：`audit()` 里某条笔记 `nested: true`，DOM 里出现 `<mark><mark>…</mark></mark>`。

**原因**：新标记的选区与已有标记重叠，而 `wrapRange` 只跳过「**同一条笔记**已经标过」的片段
（`mark.hl[data-nid="自己"]`），不同笔记之间的重叠按嵌套处理。

**为什么保留**：如果直接跳过所有已标记片段，新笔记可能一个 mark 都建不出来 →
抽屉里立刻显示「定位失效」，那才是真的 bug。嵌套的代价很小：
背景渐变相同、视觉上看不出，`unwrap()` 会先移出子节点再删自身，所以嵌套层级安全。
**要盯的是 `blockInsideMark`，不是 `nested`。**


### 29. 没有页码的区块：笔记显示「P？」，甚至根本标不了（用户实际踩到的）

**症状**：在「本节概述」卡、封面说明、速查表这类**没有页码**的内容上划词，笔记卡片上的位置徽标
显示 `P？`（小字号下很像 `P7`，一开始还以为是页码错了）；更早的版本里，「这份文档怎么用」这张卡
**点了「标记」只弹一句「这里的内容不在讲解正文里，标记不了」**。

**根因（两条）**：
1. 徽标直接写 `'P' + (m.page || '?')`，而 `m.page` 取自 `section[data-page]` —— 概述卡没有这个属性。
2. `markSelection` 用 `closest('section[data-page], section[id]')` 找宿主区块，而有些卡片
   （`<section class="card howto">`）**连 id 都没有**，于是取不到 `pid`，直接判为不可标记。

**修法**：
- `locOf(sec)`：有 `data-page` → `原文件 P12`；有 `.ov-kicker` → `本节概述 · 第二节（P9–P39）`
  （页码区间从 `.ov-range` 里抠）；其它卡片 → 自己的 `h2`/`h3`（去掉 `<em>` 副标题，超 18 字截断）；
  兜底 `#id`。徽标改用 `.ni-loc` 样式（单行省略），完整位置放 `title` 悬停提示。
- `ensureSectionIds()`：boot 时给没有 id 的 `section` 按文档序补 `sec-<n>` —— 文档是静态的，
  每次加载编号一致，所以能当稳定 `pid`。
- **位置在渲染时重算**，不依赖存下来的字段 → 老笔记自动补上正确位置（实测把 6 条笔记的 `loc`
  字段删掉再 `restoreAll()`，标签仍是 `本节概述 · 第二节（P9–P39）` / `原文件 P11` / `这份文档怎么用`）。
- 导出 Markdown 的小标题也换成位置标签（原来是 `原文件 P？ · ov2` 这种）。

**顺带踩的坑（写探针/harness 时注意）**：造 Range 时 `setEnd(node, len + tail)` 会抛
`IndexSizeError`，**异常会中断整个定时回调**，表现是「截图里什么都没有」——
一开始还以为是抽屉没打开。`tail` 一定要夹紧在节点长度内。
另外 `shot.py --section X` 会把其它区块设成 `display:none`，
被隐藏区块里的选区 `getBoundingClientRect()` 全是 0 → 浮层工具条不会出现，
**所以「一次标记多个区块」的 harness 不能只截一个区块**。

### 30. HTML 注释里的「字面标签」会骗过构建与体检（套件自检时踩到的）

**症状**：三个检查同时报错，指向三个看似无关的方向 ——

```
③ 标签配对：不平衡 → section: open=6 close=12
⑥ 缩略图 0 / 逐页区块 6 / PDF深链 6  ⚠ 数量不一致
probe_doc: 逐页区块 / 缩略图 / 深链: 6 / 0 / 6  ✘ 不一致
```

产物 HTML 里 `grep -c 'class="thumb"'` 明明是 6，浏览器里却一个都查不到。

**根因**：模板 `20_page.html` 末尾的注释里写了**字面**收尾标签：

```html
<!-- 缩略图由 build.py 自动插入到 </section> 之前，不要手写 -->
```

而 `build.py` 注入缩略图用的是**非贪婪**匹配：

```python
re.subn(r'<section class="pg" id="p\d+" data-page="\d+">.*?</section>', inject, body, flags=re.S)
```

`.*?` 撞上注释里那个假 `</section>` 就提前收尾 → 缩略图被插进**注释内部** →
① 注释被撑破（`-->` 之前的 `</section>` 让注释提前闭合），② 缩略图落在注释里不成为 DOM 节点，
③ 真正的收尾标签变成游离标签（所以 6 个区块数出 12 个 `</section>`）。
一处模板 bug，同时点亮三盏红灯。

**修法（两层，都要做）**：

1. **模板层**：注释里不写任何字面标签。要说明「插到收尾标签之前」就写「本区块收尾标签之前」。
   这条要当成模板编写规范 —— 注释里出现 `<xxx>` / `</xxx>` 都是雷。
2. **脚本层（更保险）**：所有「先匹配整段再改写」的地方，**先把注释整体挖走再匹配**：

```python
_c = []
def _mask(m):
    _c.append(m.group(0)); return '\x00CMT%d\x00' % (len(_c) - 1)
masked = re.sub(r'<!--[\s\S]*?-->', _mask, body)
masked, n = re.subn(r'<section class="pg" ...>.*?</section>', inject, masked, flags=re.S)
body = re.sub(r'\x00CMT(\d+)\x00', lambda m: _c[int(m.group(1))], masked)
```

`build.py`（注入缩略图）、`init_project.py`（`--no-extras` 删 primer 段）、
`check_math.js`（标签配对）三处都已按这个模式加固。
`check_math.js` 现在还会打印「已排除 N 段注释」，方便确认它真的生效了。

**同类隐患**：`check_ui.py` 曾经用「`#pdfB64` 容器是否存在」判断「是否启用了内嵌 PDF」——
但该容器在两种模式下**都存在**（非内嵌时内容为空串），于是默认模式被误判成 4 项 FAIL。
判据要选**只在该模式下出现**的东西（这里是正文里的 `data-embed-page` 属性）。

### 31. 标记回归探针在「骨架期 / 纯图课件」上会自灭

**症状**：`probe_marks.js` 输出 `cases: []` + `FATAL: 没找到可测的选区`，
退出码却是 0 —— 于是上游脚本判不出「其实没测」。

**根因**：探针的四个用例（跨格 / 跨段 / 跨公式 / 单段）都要从 `.pg-text` 里**现找**
「相邻两段文字」「≥3 列的表格」「段内的加粗」。骨架期整篇都是「待补」卡片，
纯图课件压根没有文字层，于是用例集为空。

**修法**：用例集为空时，探针**自己往第一个 `.pg-text` 里造一组**
（两段相邻文字 + 一个 3 列表格 + 一段加粗），并把自造后的结构纳入指纹基准 `fp0`。
这样「划线只加元素」的断言依然有效，且对任何文档都成立。
**凡是「探针依赖被测文档恰好长成某样」都是隐患 —— 让它自给自足。**

### 32. 套件里写死本机路径 → 整体打包迁移后全废（用户要求「方便整体打包迁移」）

**症状**：把技能目录拷到别的机器/别的用户名下，`run_all.py` 直接找不到 node、
`shot.py` / `probe.py` 找不到浏览器，文档里的示例命令也全是别人的路径。

**根因**：几处把本机环境写进了代码与文档 ——

```
scripts/run_all.py:  r'C:/Users/<用户名>/.workbuddy/binaries/node/versions/22.22.2-3/node.exe'
scripts/shot.py:     r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
scripts/probe.py:    同上
SKILL.md / init_project.py 生成的 README: PY="C:/Users/<用户名>/.../python.exe"
```

其中 node 那处最脆：**版本号目录名（`22.22.2-3`）会随运行时升级而变**，
换个环境必然失效；写死用户名则换个 Windows 账户就废。

**修法（统一收口到 `scripts/kitpath.py`）**：

- 新增 `scripts/kitpath.py`，只依赖标准库，提供 `python_exe()` / `node_exe()` /
  `browser_exe()` / `report()`。探测顺序一律是
  **① 环境变量（`KIT_NODE` / `KIT_BROWSER`）→ ② `shutil.which` 走 PATH
  → ③ 常见安装位置**。
- **托管运行时目录要「列目录 + 版本号倒序」而不是写死版本号**：

```python
for d in reversed(_glob_dirs(os.path.join(home, '.workbuddy', 'binaries', 'node', 'versions'), '*')):
    cands.append(os.path.join(d, 'node.exe'))
```

- `shot.py` / `probe.py` / `run_all.py` 的 `find_browser()` / `node_exe()` 改成
  一行委托给 `kitpath`，并删掉原来的 `CANDIDATES` 常量（留着是死代码，会误导）。
- 文档与生成的 README 改用 `PY="$(command -v python || command -v python3)"` +
  `<套件目录>` 占位；`init_project.py` 生成 README 时填入**当前** `KIT` 路径，
  并注明「套件搬走后改这一行即可」。
- `browser_exe()` 找不到时抛 `SystemExit` 并列出**三种可操作解法**，不崩栈。

**验证方式（改动后必做）**：把套件整体拷到一个新目录并**改名**，
从新位置跑 `scripts/selftest.py` —— 仍应 `PASS`。
这能一次性覆盖「脚本是否还依赖原路径」「模板/资源是否按相对位置找到」。
自查命令：`python scripts/kitpath.py` 打印四个路径；

**补记（同一次整理中发现）**：迁移时**外部程序之外还有一层依赖** ——
Python 第三方包。`init_project.py` / `prepare_pdf.py` / `selftest.py` 顶部直接
`import pymupdf`（`prepare_pdf.py` 还要 `from PIL import Image`），
换台机器跑就是一句光秃秃的 `ModuleNotFoundError: No module named 'pymupdf'`，
**看不出该装什么、装到哪个解释器里**（本机就踩过：托管 python 3.13.12 没有 pymupdf，
而 venv `binaries/python/envs/default` 里有 —— 用错解释器就报这个错）。
修法：

- `kitpath.py` 增加 `PY_DEPS` 清单 + `dep_status()` + `require_deps(*mods)`；
- 三个脚本改成 `import kitpath` → `kitpath.require_deps('pymupdf')` → 再 `import pymupdf`，
  顺序不能反（要在 `import` 之前拦）；
- `require_deps` 抛 `SystemExit`，内容包含**包名 + 用途 + 可直接照抄的 pip 命令 + 当前解释器路径**；
- `kitpath.py` 自查输出增加「Python 依赖」一段，缺包时退出码为 1。

```python
# 脚本顶部固定写法
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kitpath                                    # noqa: E402
kitpath.require_deps('pymupdf')                   # 缺包 → 给 pip 命令，不抛 ModuleNotFoundError
import pymupdf                                    # noqa: E402
```

### 33. 零宽字符让跨公式划线产生「宽度 0 的 mark」（2026-09-24 修，用户实际踩到的）

**症状**：`probe_marks.js` 报 `C_acrossFormula: FAIL … zeroWidth=2`，
其它断言全绿、`RESULT: FAIL`。肉眼完全看不出问题 —— 因为那两条 `<mark>`
包住的是**零宽字符**，宽高都是 0，用户不可能看到任何高亮。

**定位手段**（值得复用）：写一个临时探针，把零宽 mark 的 `outerHTML` 打出来 ——

```js
$$('mark.hl').filter(function (m) { return m.getBoundingClientRect().width <= 0; })
  .forEach(function (m) { T('zw', m.outerHTML + ' parent=' + m.parentNode.className); });
```

实测输出：`<mark class="hl" …>​</mark> parent=SPAN.vlist-s` ——
内容是 `\u200B`（零宽空格），父节点是 **KaTeX 的 `span.vlist-s`**。

**根因**：KaTeX 渲染 `\frac` 时会在 `.vlist-s` 这类结构里插入真实的
**U+200B**（分式线的定位就靠它）。而 `wrapRange()` 里两处空白判定用的是
`/^\s*$/` —— **JS 的 `\s` 不匹配 U+200B**，于是这个「看不见的字符」被当成
可见文字收进 `segs`，`wrapOne()` 顺手把它包成 `<mark>`。
只要一段选区跨过含 `\frac` 的公式，就必然踩到。

**修法**（`assets/site.js`，共 6 处，**存与找必须同改**）：

1. 新增统一的零宽集合，并把它并入空白：

```js
var INVIS_RE = /[\s\u200b-\u200f\u202a-\u202e\u2060\ufeff]/;
var INVIS_G  = /[\s\u200b-\u200f\u202a-\u202e\u2060\ufeff]/g;
function isBlankStr(s) { return !String(s == null ? '' : s).replace(INVIS_G, '').length; }
```

2. `wrapRange()` 的两处 `/^\s*$/` 判定 → `isBlankStr(...)`（这是直接止血的一处）；
3. `squash()` 的 `/\s/.test(c)` → `INVIS_RE.test(c)`（投影空间也把零宽当空白，
   这样 `quote` 里不会混进不可见字符）；
4. `canon()` 与 `candidates()` 的 `normQuote/normPre/tightQuote/tightPre` 归一化
   前面各加一次 `.replace(INVIS_G, ' ')` / `''`；
5. `captureSelection()` / `markSelection()` 里 `sel.toString()` 的归一化同理。

**为什么第 4、5 条不能省**：改 ②③ 之后投影串里不再有零宽字符，但**旧记录
的 `quote` 里还带着它们**。存（canon）与找（candidates）两端都做一次剥离，
老笔记才会在 T1 就近命中；只改一端会让老笔记落到 T4 兜底甚至失效。

**验证**：`probe_marks.js` → `RESULT: PASS`（`zeroWidth=0`）；
再跑 `selftest.py` 确认套件本身仍 `PASS`（两条都要，前者证明 bug 修掉、
后者证明没改坏别的东西）。

### 34. 正文里用组合箭头 U+20D7 表示矢量 → 渲染成方框（用户实际踩到的，2026-09-24）

**症状**：公式（KaTeX 渲染的）里的矢量箭头完全正常，**但正文里全是方框**。
用户原话：「在 latex 公式以外的地方，矢量符号无法正常显示，会变成一个方框」。
具体出现在三处：段落正文、表格单元格、**左侧目录标签**。

**根因**：`U+20D7 COMBINING RIGHT ARROW ABOVE` 属于
「符号用组合附加记号」区块（U+20D0–U+20FF）。
**中文字体栈（PingFang SC / Microsoft YaHei / Source Han Sans / Noto CJK）
普遍没有这个字形**，`var(--sans)` 整条链上谁都没有 → 浏览器回退不到任何字体 → 方框。
KaTeX 公式区不受影响，因为它在自己的字体里画 `\vec` 的箭头（用的是几何/`→`，不是 U+20D7）
—— **所以「公式里正常、正文里方框」是这个 bug 的典型指纹。**

**判定方法（别猜，实测）**：用套件自带的探针把文档里用到的**全部非中文符号**
用文档自己的字体栈渲染成一页，肉眼扫方框：

```bash
python scripts/glyph_probe.py "<成品.html>" "_extract"
python scripts/shot.py "_extract/glyph_probe.html" "_extract/glyph_probe.png" --height 2800 --width 1000
# 然后 Read 那张 png 看有没有方框
```

（`glyph_probe.py` 会用 `:root` 里的 `--sans`、逐字符 `×3` 排表，
并在发现 U+20D0–U+20FF 时直接把退出码置 1、红底标出那几行。）
本项目实测 72 种非中文符号，**只有 U+20D7 是方框**；下面这些都正常，可以放心用：

```
U+0302 n̂   U+0304 t̄   U+27E8 ⟨  U+27E9 ⟩   U+2212 −   U+2192 →   U+21D2 ⇒
U+2197 ↗   U+2630 ☰（收起按钮）  U+2714 ✔   U+2718 ✘   U+27F9 ⟹   U+27FA ⟺
∮ U+222E   ∬ U+222C   ∭ U+222D   ∯ U+222F   ∇ U+2207   ∂ U+2202   ∝ U+221D
∥ U+2225   ≪ U+226A   ⊥ U+22A5   ①②③④⑤⑥ U+2460–2465   希腊字母 σρρτεφ Ω Δ
```

**修法**：

1. `assets/site.css` 新增矢量样式（`font-style:inherit` 让它在 `<em>` 里自动变粗斜体）：

```css
.vec{font-weight:700;font-style:inherit}
```

2. 正文与目录标签统一改写成 `<b class="vec">`：
   `<em>J⃗</em>` → `<em><b class="vec">J</b></em>`、`⟨v⃗⟩` → `⟨<em><b class="vec">v</b></em>⟩`。
   **只改「文本节点」，不动标签与属性** —— 否则会砸坏 `title="…"` 之类的属性值。
   一个可靠的批量做法见本仓库那次用的脚本：先按 `<script type="math/tex…">` 切块跳过公式，
   再按 `<[^>]*>` 切标签，只对标签外的纯文本跑 `([A-Za-z])⃗` 替换，
   最后断言「文件里 U+20D7 计数为 0」。
3. **`config.json` 的目录标签也要改**（`build.py` 原样注入标签文本，HTML 能生效），
   但 **JSON 字符串本身是双引号包的，所以那里的属性必须用单引号**
   （`"<b class='vec'>J</b>"`）。用双引号会直接把 JSON 截断 —— 这个坑当场踩过一次。
4. 没有加粗样式时，`.vec` 会退化成普通 `<b>`，仍然可读，不会更糟。

**防回归（两个检查都已加）**：

- `scripts/check_math.js` 新增 **⑧ 正文缺字体检**：挖掉 math/tex 区块后统计
  `[\u20d0-\u20ff]`，**>0 即硬性失败**并列出码位与次数。
- `templates/probe_doc.js` 新增两行：`正文缺字风险`（按区块定位，跳过 `.katex` 子树）
  与 `非法命名实体`。后者是顺手加的同类问题：`&oiint;` `&iint;` `&iiint;` `&oint;`
  只存在于 MathML/LaTeX，**不在 HTML5 实体表里**，浏览器不解码、原样显示成
  「&oiint;」这串字面文本。判定办法最可靠：把这段字面文本塞进 `innerHTML` 试一次，
  `textContent` 没变就说明解析器不认识它。

**写这两个检查时当场踩的坑：探针会「自己命中自己」。**
`probe.py` 是把探针 JS **注入成页面的 `<script>`** 再跑的，于是：

- `document.body.textContent` / `documentElement.innerHTML` 里**含有探针自己的源码**。
  我在 `probe_doc.js` 的注释里写了 `&oiint;`、`TODO` 当例子 → 检查立刻报
  「非法命名实体: &oiint; &iint;」「TODO 残留: 6 处」，而产物里其实一个都没有。
  同类误报还有第三个来源：**内嵌 PDF 的 base64 payload 里随机拼出过 1 次 `TODO`**。
- 所以两个检查现在都只走**用户看得见的文字节点**，`acceptNode` 里拒掉
  `script, style, .katex-mathml, annotation`（`.katex-mathml` 是 KaTeX 的隐藏副本，
  公式只要用到 `\oiint` / `\iint`，那一份里就会出现字面实体）。
- `check_math.js` 侧的 TODO 检查则在源码层面 `replace(/<script[\s\S]*?<\/script>/g,'')`
  之后计数 —— 一次把「探针源码」和「base64 payload」两个来源都挖掉。
- **通用教训**：在「会把自己也算进去的容器」里做体检，先想清楚
  「这段扫描代码本身在哪里」，否则检查永远不可能变绿。

**另一个配套的坑：`run_all.py` 的摘要白名单会吞掉新增的体检项。**
`run_all.py` 不是原样透传探针输出，而是**按前缀白名单挑几行**再打印：
`parse_probe()` 只认 `RESULT / 结构指纹 / 重开后 / 逐页区块 / …`，
`parse_check_math()` 只认 `^[①-⑦]`。
于是出现一种很迷惑的现象：**直接跑 `probe.py` / `check_math.js` 能看到新检查，
走 `run_all.py` 却什么都看不到**（本次新增的「正文缺字风险」「非法命名实体」
「TODO 残留」和 `⑧ 正文缺字体检` 全中招）。
- 修法：`parse_probe()` 的白名单批量补上新前缀；`parse_check_math()` 的序号
  从 `⑦` 放宽成 `[\u2460-\u2469]`（①–⑩，U+2460 起连续），以后加 ⑨ ⑩ 都不用再改。
- **纪律：给探针加一行体检，同步给 `run_all.py` 的白名单加一个前缀。**

### 35. 自检「看起来卡死」其实是全程静默（用户实际反馈的，2026-09-24）

**症状**：用户报「最终套件自检卡住了」。实际去查：**自检 1 分 33 秒后
`PASS`，退出码 0，套件完全健康。**

**根因**：`selftest.py` 原来是

```python
r = subprocess.run(cmd, capture_output=True, text=True, timeout=...)
print(out)          # ← 跑完才打印
```

`capture_output=True` 期间**一个字都不输出**。流水线要 1~2 分钟，
期间调用方看到的永远是空输出 —— 观感与「卡死」没有区别；
真卡住时也完全看不出卡在哪一步。**这是纯粹的可用性缺陷，不是性能问题。**

**排查过程中另外踩到的两件事**（记下来免得重复浪费时间）：

1. **别用 shell 的 `&` 起后台任务做长实验。** 本机 Bash 工具在工具调用返回时
   会回收后台子进程，于是日志永远停在某一截，看起来「卡在第 ⑥ 步」——
   我据此差点误判成 `probe.py` 卡住。实际单独跑 `probe_marks.js` 只要 **23 秒**且 PASS。
   **要跑长任务就用工具自带的 `run_in_background`，不要 `&`。**
2. **`tasklist | grep -ci msedge` 会吓人一跳。** 本机常驻 60+ 个
   `msedge.exe` / `msedgewebview2.exe`（用户自己的 Edge + IDE 的 WebView2），
   一眼看去像「残留 headless 进程占锁」。要判定得看**命令行**里有没有
   `--headless` / `--user-data-dir=…\lr-probe-*`，数量本身没有意义。

**修法**（`selftest.py`）：

- 改成 `Popen` + **逐行实时透传**，并给子进程加 `-u`（否则它的 print 在管道里是块缓冲的，
  实时性会打折）。
- 加**两级看门狗**：无新输出超过 `STALL_WARN=120` 秒 → 打印警告并点名当前步骤
  （从最后一行 `▶ …` 里抓）；总时长超过 `HARD_LIMIT=900` 秒 → `kill` 并报出停在哪一步。
  用后台线程读 `proc.stdout`，主线程只做计时，这样「读」不会被「等」阻塞。
- 顺带补一句耗时打印，便于日后对比是否变慢。

**结论**：`run_all.py` 本身就带步骤级反馈（每步先打印 `▶ 标题` + `$ 命令`），
所以「静默」的责任只在 `selftest.py` —— 现在两者一致了。

### 36. 探针结果元素要写「字面标签」；截图 harness 里绝不能滚动（2026-09-24 两条都实测踩到）

**症状 A（探针静默读不到结果）**：自己写的探针用 `probe.py` 跑，报
`!! 没拿到探针结果 (dom 22827532 bytes, rc=0)`，
而脚本逻辑明明执行了（换成 `probe_marks.js` 同一份文档就正常）。

**根因 A**：`probe.py` 用 `dom.rfind('<pre id="__r">')` 定位结果，匹配的是**字面串**。
用
```js
var p = document.createElement('pre'); p.id = '__r';
p.style.display = 'none'; document.body.appendChild(p);
```
造出来的元素，序列化后是 `<pre id="__r" style="display: none;">` ——
**`id` 和 `>` 之间多了属性，字面串匹配不上**，于是被判定「没拿到」。

`probe_marks.js` / `templates/probe_doc.js` 之所以一直正常，是因为它们收尾用的是
```js
document.body.innerHTML = '<pre id="__r">' + esc(out.join('\n')) + '</pre>';
```
写出**字面标签**（副作用是连注入的 `<script>` 自己一起清掉，DOM 里只剩一份，`rfind` 必中）。

**处理**：要回传给 `probe.py` 的结果，一律用 `body.innerHTML` 写法；
只想给人看、不喂给探针的结果才用 `createElement`。
`templates/harness_markshot.js` 里那个 `#__r` 属于后者，已在注释里标明「probe.py 读不到」。

**症状 B（截图是一张纯背景色空图）**：用 `templates/harness_markshot.js` 截
「标记 + 笔记抽屉」，得到 **8 KB 的空白 png**，退出码 0、stdout/stderr 都没有报错。
带不带 `--section` 都一样必现。

**根因 B**：harness 收尾那句 `mk.scrollIntoView({ block: 'center' })`。
无头截图（`--screenshot` + `--virtual-time-budget`）下滚动会把视口送到内容范围之外。
实测对照（同一份文档、同一个 harness，只改这一处）：

| 改动 | 产物 |
|---|---|
| 原样 `scrollIntoView({block:'center'})` | **8 KB 空图** |
| 换成 `window.scrollTo(0, 0)` | 205 KB 正常 |
| 手算 `scrollTo` 并夹紧到 `scrollHeight - innerHeight` | **8 KB 空图** |
| **完全去掉滚动** | 222 KB 正常 |

（`scrollTo(0,0)` 能出图是因为它把视口拉回顶部；「夹紧」那版仍空白，说明**只要发生滚动就不可信**，
不是夹紧算错的问题。）

**处理**：`templates/harness_markshot.js` 已删除滚动，并在原位留了注释说明原因。
配合 `shot.py --section`，目标区块本来就排在最前，不需要滚；
想看画面别处就**换一个 `--section` 重截一张**，不要靠滚动。

**通用教训**：在无头截图里，`scrollIntoView` / `scrollTo` / `scroll-behavior:smooth`
都是不可信操作（第 22 条已记过 smooth 一条，这里是更狠的「一切都别滚」）。
截图前的「页面状态」只应该通过 **CSS 隐藏 + DOM 变动** 来构造，
不要依赖任何滚动位置；一旦截图结果是「纯背景色」，先怀疑滚动。
