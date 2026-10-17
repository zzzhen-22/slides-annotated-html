#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""产出物的静态体检（不依赖浏览器）—— check_math.js 的补充。

用法：
    python check_ui.py <输出.html>

检查六项交互功能的"接线"是否正确：
    ① 目录逐级折叠：分组/按钮/计数徽标数量、各小节标题是否都在
    ② 本节概述：overview 卡数量与其锚点是否进目录
    ③ 侧栏收起：navToggle/thumbToggle 是否存在、收起后缩略图列宽是否真的变大
    ④ 标记与笔记：抽屉 DOM、选择工具条依赖的样式、localStorage 命名空间是否注入
    ⑤ 正文字号调节：A−/A＋ 按钮、--fs 缩放变量、max-width 反向补偿、localStorage 键
    ⑥ 正文搜索：搜索框与结果面板、索引惰性建、临时高亮与笔记高亮的类名隔离、
       清空时拆除并 normalize、↑↓/Enter/Esc 键盘路径、搜索框是否真的接到 Find

（⑦–⑬ 是「结构安全 / 附加功能」类检查，不计入上面的「六项交互」——
   它们的编号延续历史顺序：⑦ 目录滚动、⑧ 标记上色、⑨ 位置标签、
   ⑩ 字号调节、⑪ 正文搜索的补充、⑫ 代码块的标题栏与复制按钮、
   ⑬ 课程返回入口（可选注入，无此元素是合法形态 → 整组 SKIP）、
   ⑭ 关于面板（顶栏入口 + 使用说明 + 生成工具；**非条件式**，每份产物都该有）。）

浏览器失灵时（见 references/pitfalls.md 第 29 条）用它兜底，
能覆盖"结构对不对"，覆盖不了"长得对不对"。
"""
import os
import re
import sys

# 强制 stdout/stderr 走 UTF-8：英文地区 Windows 默认编码 cp1252，print 中文会
# UnicodeEncodeError（GitHub Windows runner 上实测踩到，2026-10-07）。
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, '..', 'assets')


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    path = os.path.abspath(sys.argv[1])
    html = open(path, encoding='utf-8').read()
    css = '\n'.join(open(os.path.join(ASSETS, f), encoding='utf-8').read()
                    for f in ('site.css', 'site.extra.css')
                    if os.path.exists(os.path.join(ASSETS, f)))
    js = open(os.path.join(ASSETS, 'site.js'), encoding='utf-8').read()
    fails = []

    def chk(label, cond, detail=''):
        print('%-52s %s %s' % (label, 'PASS' if cond else 'FAIL', detail))
        if not cond:
            fails.append(label)

    print('=== 资源自身 ===')
    chk('site.css / site.extra.css 花括号平衡', css.count('{') == css.count('}'),
        '%d/%d' % (css.count('{'), css.count('}')))
    chk('site.js 花括号平衡', js.count('{') == js.count('}'),
        '%d/%d' % (js.count('{'), js.count('}')))
    chk('site.js 使用注入的命名空间', 'window.DOC_NS ||' in js)
    chk('HTML 已注入 DOC_NS', re.search(r'var DOC_NS = "[^"]+"', html) is not None)

    print()
    print('=== ① 目录逐级折叠 ===')
    nav_s, nav_e = html.find('<nav'), html.find('</nav>')
    nav = html[nav_s:nav_e] if nav_s >= 0 and nav_e > nav_s else ''
    groups = html.count('class="toc-group"')
    toggles = html.count('class="toc-toggle"')
    chk('存在目录 <nav>', bool(nav))
    chk('分组数 = 折叠按钮数', groups == toggles and groups > 0, '%d / %d' % (groups, toggles))
    chk('分组数 ≥ 2（说明确实是多级）', groups >= 2, str(groups))
    chk('计数徽标只出现在含页码的分组上', 0 < html.count('class="gcount"') <= groups,
        str(html.count('class="gcount"')))
    chk('有展开/折叠全部按钮', 'id="tocExpand"' in html and 'id="tocCollapse"' in html)
    chk('JS 有 filter（正文 0 命中时回退到目录标题过滤）', 'filter: function' in js)
    chk('JS 有 revealLink（滚动时自动展开所在组）', 'revealLink: function' in js)

    print()
    print('=== ② 本节概述 ===')
    ovs = re.findall(r'<section class="card overview" id="(ov\d+)"', html)
    chk('存在概述卡', len(ovs) >= 1, ', '.join(ovs))
    missing = [o for o in ovs if ('href="#%s"' % o) not in nav]
    chk('概述卡都已进入目录', not missing, ('缺: ' + ','.join(missing)) if missing else '')

    print()
    print('=== ③ 侧栏收起 / 缩略图放大 ===')
    chk('存在侧栏开关', 'id="navToggle"' in html)
    chk('存在缩略图开关', 'id="thumbToggle"' in html)
    m = re.search(r'body\.nav-hidden\s*\.pg\s*\{[^}]*minmax\(0,\s*1fr\)\s*(\d+)px', css)
    base = re.search(r'\.pg\s*\{[^}]*minmax\(0,\s*1fr\)\s*(\d+)px', css)
    chk('CSS 定义了收起后的大缩略图列', bool(m), (m.group(1) + ' px') if m else '')
    if m and base:
        chk('  收起后确实变大', int(m.group(1)) > int(base.group(1)),
            '%s px → %s px' % (base.group(1), m.group(1)))

    print()
    print('=== ④ 标记与笔记 ===')
    for el in ['id="notesBtn"', 'id="drawer"', 'id="drawerList"',
               'id="notesExport"', 'id="notesClear"', 'id="notesBtnCount"']:
        chk('  ' + el, el in html)
    for sel in ['mark.hl', '.selbar', '.note-item', '.note-input', '.ni-stale']:
        chk('  样式 %s' % sel, sel in css)
    for fn in ['function locate', 'function restore', 'Notes.render =',
               'Notes.restoreAll =', 'Notes.jump =', 'function buildSelBar']:
        chk('  JS %s' % fn, fn in js)

    print()
    print('=== ⑤ 选区工具条避让 / 多条标记入口 ===')
    # 背景：Edge 选中文本浮出的「迷你菜单」由浏览器 UI 层绘制，网页压不住它，
    # 所以必须：① 工具条避开（放下方）② 另有不依赖浮层的入口 ③ 有选区时接管右键。
    chk('存在顶栏「标记选中」入口', 'id="markBtn"' in html)
    chk('CSS 有形如 .selbar.below / .above 的方向样式',
        '.selbar.below' in css and '.selbar.above' in css)
    chk('CSS 有自绘右键菜单样式', '.ctxmenu' in css)
    chk('JS 有统一入口 markSelection', 'function markSelection' in js)
    chk('JS 有选区缓存（点击按钮时选区可能已被收起）', 'lastSel' in js)
    chk('JS 把工具条优先放到选区下方', 'useBelow' in js and 'r.bottom + 12' in js)
    chk('JS 有快捷键 M', "k === 'm'" in js)
    chk('JS 记住「标记选中」按钮的可用状态', 'markBtnState' in js)
    chk('JS 有选区时接管右键（preventDefault）', 'function buildCtx' in js and 'e.preventDefault()' in js)
    chk('JS 保留 Shift+右键 的逃生通道', 'e.shiftKey' in js)
    chk('JS 右键菜单里补了「复制」', "data-act=\"copy\"" in js or "data-act='copy'" in js)
    # 「先 render 后上色」会让卡片误判成定位失效 —— 上色之后必须再 render 一次
    chk('JS 上色后会重新渲染卡片（避免误报定位失效）',
        'wrapRange(r2, m.id);' in js and js.count('Notes.render();') >= 3)

    print()
    print('=== ⑧ 标记上色：结构安全 / 投影定位（2026-09-24 修的两个 bug）===')
    # 教训：「上色不许搬动结构」。跨元素选区曾被 surroundContents 的 extractContents 退路
    # 克隆进 <mark>，导致①标记处凭空多出换行且不再高亮 ②跨格划线把表格拆散。
    # 另一半教训是「存与找必须同源」：Selection.toString() 会在块/单元格边界插 \n \t，
    # 而 TreeWalker 拼接不带分隔符，两边不同源 → 重新打开后全部定位失效。
    chk('JS 上色绝不取内容再插回（不克隆元素进 mark）',
        'extractContents(' not in js)
    chk('JS 上色逐文字节点片段包围（单节点内必然成功）',
        'function wrapOne' in js and 'surroundContents' in js)
    chk('JS 按块级祖先分组 + 二分收敛', 'function wrapGroup' in js and 'blockAncestor' in js)
    chk('JS 跳过 KaTeX 隐藏副本（否则公式重复、且会标到看不见的 1px 副本上）',
        '.katex-mathml' in js and 'annotation' in js)
    chk('JS 有「投影空间」，存与找同源（projOf / canon）',
        'function projOf' in js and 'function canon' in js)
    chk('JS 定位分层：压缩空白 → 去空白兜底 → 旧记录兼容',
        'function squash' in js and 'tightQuote' in js and 'function locateLegacy' in js)
    chk('JS 一条笔记可对应多个 mark（删除/清空必须全量拆）',
        js.count("$$('mark.hl") >= 2)
    chk('JS 命中兜底层后把记录改写成规范形式（自愈）', 'm.quote = c.quote' in js)
    chk('JS 有标记体检入口（audit / structAudit / traceWrap）',
        'audit: function' in js and 'structAudit: function' in js and 'traceWrap' in js)

    print()
    print('=== ⑨ 笔记的「原文位置」标签（无页码的卡片不再显示 P？）===')
    # 用户反馈：标记「本节概述」等没有页码的内容时，笔记里显示「P？」，看不出标在哪。
    # 现在：页码页 -> P12；概述卡 -> "本节概述 · 第二节（P9–P39）"；其它卡片 -> 自己的标题。
    chk('JS 有 locOf（按区块算出可读的原文位置）', 'function locOf' in js)
    chk('JS 概述卡取 .ov-kicker + .ov-range 的页码区间',
        '.ov-kicker' in js and '.ov-range' in js)
    chk('JS 渲染时重算位置（老笔记没存 loc 也能补上）',
        'locOf(sec) || m.loc' in js)
    chk('JS 不再输出「P？」占位', "esc(m.page || '?')" not in js)
    chk('JS 给无 id 卡片补稳定 id（否则那些内容根本标不了）',
        'function ensureSectionIds' in js and "'sec-' +" in js)
    chk('CSS 有 .ni-loc 徽标样式（单行省略 + title 提示）',
        '.ni-loc' in css and 'text-overflow:ellipsis' in css)
    chk('JS 导出 Markdown 用位置标签当小标题', 'locTip(sec, locOf(sec))' in js)
    chk('JS 把 locOf 暴露给探针', 'locOf: function (pid)' in js)

    print()
    print('=== ⑥ 内嵌原文件（embed_pdf）===')
    # 注意：#pdfB64 容器在两种模式下都存在（非内嵌时内容为空串），
    # 所以不能拿「容器存在」当「已启用内嵌」的判据 —— 那会把默认模式误判成 4 项 FAIL。
    # 正确判据：正文里出现了内嵌专用属性 data-embed-page。
    mb = re.search(r'<script type="text/plain" id="pdfB64"[^>]*data-pdf-name="([^"]*)"[^>]*>([\s\S]*?)</script>', html)
    payload = (mb.group(2) or '').strip() if mb else ''
    embed_on = ('data-embed-page=' in html) or (len(payload) > 100000)
    if embed_on:
        chk('内嵌了原文件', len(payload) > 100000,
            '%d 字符 ≈ %.2f MB（原文件 %s）' % (len(payload), len(payload) * 0.75 / 1048576,
                                            mb.group(1) if mb else '?'))
        chk('base64 只含合法字符', re.fullmatch(r'[A-Za-z0-9+/=]*', payload) is not None)
        chk('深链已切到内嵌模式', 'data-embed-page=' in html)
        stale = [t for t in re.findall(r'<a class="pdf-link"[^>]*>', html) if 'file:///' in t]
        chk('没有残留本机绝对路径的深链', not stale, '%d 条' % len(stale))
        chk('存在「另存原 PDF」按钮', 'id="savePdf"' in html)
        chk('JS 有内嵌打开逻辑', 'function openEmbeddedPdf' in js and 'URL.createObjectURL' in js)
    else:
        # 非内嵌模式。这里有**两种合法形态**，不能一刀切要求 file:///：
        #   A. config 给了 pdf → 深链指向本机原文件（file:///#page=N）
        #   B. config 没给 pdf → 深链是**停用态**（<span class="pdf-link" aria-disabled>，
        #      由 build.py 主动降级生成，见 pitfalls 第 44 条）。本仓库的在线 demo 就是这一类：
        #      原始课件因版权不入库，所以产物里根本没有可跳的原文件。
        # 早先这里硬性要求 'file:///' in html，于是 B 类文档必然报 FAIL——
        # 而这不是缺陷，是配置选择。现在按形态分别断言。
        n_disabled = len(re.findall(r'<span class="pdf-link" aria-disabled', html))
        n_filelink = len(re.findall(r'<a class="pdf-link"', html))
        if n_disabled:
            chk('未提供原文件：深链已全部置为停用态', n_disabled and not n_filelink,
                '%d 处停用 / %d 处仍是<a>' % (n_disabled, n_filelink))
            chk('停用态不残留悬空<a class="pdf-link">（无 href 点不动）',
                'class="pdf-link" data-page=' not in html)
            chk('停用态有 aria-disabled 与 title 说明',
                html.count('aria-disabled="true"') >= n_disabled)
            print('  （config 未提供原文件：按「停用态」口径检查，不要求 file:/// 深链）')
        else:
            chk('深链指向本机原文件（file:///#page=N）',
                'file:///' in html and '#page=' in html)
            chk('未内嵌时不留 data-embed-page（模式一致）', 'data-embed-page=' not in html)
            print('  （embed_pdf=false：跳过硬性内嵌项）')
        chk('未内嵌时 pdfB64 容器为空', payload == '')

    print()
    print('=== ⑦ 目录滚动：长章节不能被整体钉住 ===')
    # .toc-group 是「包住整章的容器」（可能比视口高得多）。一旦它被设成粘性定位，
    # 章节的下半段就永远滚不出来，而且滚动条会动、内容不动，极难排查。
    plain = re.sub(r'/\*[\s\S]*?\*/', ' ', css)
    chk('没有把 .toc-group 本身设成粘性定位',
        not re.search(r'(^|[,\s])\.toc-group\s*\{[^}]*position:\s*sticky', plain))
    chk('有把 .toc-group 强制为 static 的兜底规则',
        bool(re.search(r'\.toc-nav\s+\.toc-group\s*\{\s*position:\s*static', plain)))
    chk('一级表头仍是粘性（长章节滚动时保留上下文）',
        bool(re.search(r'\.toc-nav>\s*\.toc-group>\s*\.toc-head\s*\{[^}]*position:\s*sticky', plain)))
    chk('JS 用真实表头高度而非写死的 44px',
        "nav.querySelector(':scope > .toc-group > .toc-head')" in js)

    print()
    print('=== ⑩ 正文字号调节（A−/A＋，存浏览器）===')
    # 功能：顶栏 A−/A＋ 按钮整体等比缩放正文（.wrap），档位写 localStorage。
    # 关键在「max-width 反向补偿」——只 zoom 不放宽 max-width 会导致放大字号时内容区变窄。
    # 这一组原本排在 ⑨ 之后、⑥ 之前，输出读起来「⑨→⑩→⑥」跳来跳去（TODO 第 11 条）。
    # 注意：**只搬顺序不改编号** —— 编号是历史形成的，⑤ 之后新增的组都插在 ⑨ 之后，
    # 重新编号会让「⑤ 之后是 ⑥」这个文档里的说法失效，得不偿失。
    chk('存在字号减小/增大按钮', 'id="fontMinus"' in html and 'id="fontPlus"' in html)
    chk('存在字号档位显示标签', 'id="fontSizeLabel"' in html)
    chk('CSS 定义了 --fs 缩放变量', '--fs:' in css)
    chk('CSS 正文容器应用 zoom 缩放', 'zoom:var(--fs)' in css or 'zoom: var(--fs)' in css)
    chk('CSS max-width 反向补偿（放大字号不缩窄）', 'calc(1000px / var(--fs))' in css)
    chk('JS 有字号存储键 FS_KEY', 'FS_KEY' in js and "'font-size'" in js)
    chk('JS 字号档位存 localStorage', 'LS.set(FS_KEY' in js)
    chk('JS 字号模块暴露给探针', 'font: Font' in js)

    print()
    print('=== ⑪ 正文搜索（#qres 结果面板 + mark.q-hit 临时高亮）===')
    # 功能：搜索框不只过滤目录标题，还搜正文；命中在左栏列出
    # 「页码 · 标题 · 上下文片段」，点一条跳到该页并把命中词高亮。
    # 高亮是**临时**的（mark.q-hit），与持久笔记（mark.hl）严格分开：
    # 笔记的 unwrapAll / audit / restoreAll 只认 mark.hl，两者永不互相误伤。
    # 这一组只查「接线」，真实行为由 ⑥c probe_find.js 在浏览器里回归。
    chk('存在搜索框 #q', 'id="q"' in html)
    chk('存在结果面板 #qres', 'id="qres"' in html)
    chk('CSS 定义了结果面板与 .on 态', '.qres' in css and '.qres.on' in css)
    chk('CSS 定义了临时命中高亮 mark.q-hit', 'mark.q-hit' in css)
    chk('CSS 让结果面板顶掉目录（.toc-nav.off）', '.toc-nav.off' in css)
    chk('CSS 定义了跨边界命中的块级闪烁 .q-flash', '.q-flash' in css)
    chk('JS 有 Find 模块', 'var Find = {' in js)
    chk('JS 索引惰性建（首次查询才建）', 'build: function' in js and 'this.idx || this.build()' in js)
    chk('JS 索引跳过 KaTeX 隐藏副本', 'SKIP_SEL' in js and 'projOf(sec).str' in js)
    chk('JS 高亮类名与笔记严格分开', "'q-hit'" in js and 'mark.hl[data-nid=' in js)
    chk('JS 清空时拆除高亮并 normalize', 'clearHits: function' in js and 'p.normalize' in js)
    chk('JS 支持 ↑↓ / Enter / Esc', 'ArrowDown' in js and 'ArrowUp' in js and
        "'Enter'" in js and "'Escape'" in js)
    chk('JS 把搜索框接到 Find（不再只过滤目录）', 'Find.run(q)' in js)
    chk('JS 支持「/」对焦搜索框', "k === '/'" in js)
    chk('JS 搜索模块暴露给探针', 'find: Find' in js)

    print()
    print('=== ⑫ 代码块：标题栏 / 语法着色 / 一键复制 ===')
    # 背景：课件后半段整页都是可运行源码，代码块必须能读（着色）、能抄（复制）。
    # 三件事的分工要说清楚，否则改错地方会「看起来改了但没生效」：
    #   · **着色与标题栏在构建期生成**（build.py 的 decorate_codeblocks）——
    #     颜色跟着文件走，打印、另存、断网都还在，且不必引高亮库（单文件要断网可用）。
    #   · **复制逻辑在运行时**（site.js 的 initCodeCopy），因为它要用剪贴板 API。
    #   · 分片里只写「data-lang / data-src + pre.code」，标题栏一律不手写（20 块会写漏）。
    # 计数必须用**精确**匹配：`'class="codeblk'` 这种前缀写法会把
    # `class="codeblk-head"` 也算成代码块（实测 20 块被数成 40）。
    # 这正是 pitfalls 第 44 条那类教训——断言要问「是不是我无法接受的样子」。
    RE_BLK = r'<div class="codeblk(?: inline)?"'
    n_blk = len(re.findall(RE_BLK, html))
    n_head = html.count('class="codeblk-head"')
    n_copy = html.count('class="code-copy"')
    # **课件里没有源码是完全合法的形态**（自检用的合成 PDF 就没有）。
    # 所以这一组整体是「条件式」：没有块就整组跳过，不能报 FAIL ——
    # 这正是 pitfalls 第 44 条：断言要问「是不是我无法接受的样子」，
    # 而不是「是不是我期望的样子」。早先写成 n_blk > 0 硬要求，
    # 结果 selftest 的合成课件被判 6 项 FAIL（2026-10-15 实测）。
    if n_blk == 0:
        print('%-52s %s %s' % ('（本文档没有代码块，本组跳过）', 'SKIP', '0 块'))
    else:
        chk('每块都有标题栏（构建期注入）', n_head == n_blk and n_head > 0,
            '%d 块 / %d 头部' % (n_blk, n_head))
        chk('每块都有复制按钮', n_copy == n_blk and n_copy > 0, '%d 个' % n_copy)
        # 「标题栏紧跟在块开标签之后」——查的是**注入位置**，不是数量（数量上一条已查）。
        # 分片里手写标题栏这件事在构建期就被拦了：build.py 的 RE_CODEBLK 要求开标签后
        # 紧跟 `<pre class="code">`，手写头部会让它失配，进而触发「声明 N 块只处理 M 块」
        # 的硬闸门直接 SystemExit。所以产物层只需确认「注入的头部在该在的地方」。
        # 注意 RE_BLK 以 `"` 收尾，后面还有 data-lang / data-src 等属性，必须补 `[^>]*`；
        # 早先漏了这一步，正则永远匹配 0 次，把一条正确的结构误报成 FAIL。
        chk('标题栏紧跟块开标签（构建期注入的位置正确）',
            len(re.findall(RE_BLK + r'[^>]*>\s*<div class="codeblk-head">', html)) == n_blk,
            '%d 块' % n_blk)
        # 四类着色：注释 / 字符串 / 关键字 / 数字。
        # 只查「至少各出现一次」——不着色时这几类一个都没有，一查就现形。
        for cls, name in [('c', '注释'), ('s', '字符串'), ('k', '关键字'), ('n', '数字')]:
            chk('  着色的 %s span' % name, ('<span class="%s">' % cls) in html)
    # 下面这些查的是**套件资产**（CSS / JS），与本文档有没有代码块无关，永远要查。
    chk('CSS 定义了四类着色与标题栏按钮样式',
        all(('.code .%s{' % c) in css for c in 'cskn') and '.code-copy{' in css)
    chk('CSS 的复制按钮含成功 / 失败两态', '.code-copy.done' in css and '.code-copy.fail' in css)
    chk('打印时隐藏复制按钮（纸上按不了）',
        re.search(r'@media print\{[\s\S]*?\.code-copy\{display:none', css) is not None)
    chk('JS 有 initCodeCopy', 'function initCodeCopy' in js)
    chk('JS 取的是 pre 的纯文本而不是 innerHTML（否则会把着色标记一起复制）',
        'pre.textContent' in js or 'pre .textContent' in js)
    chk('JS 复制有降级路径（剪贴板 API 不可用时用 execCommand）',
        'navigator.clipboard' in js and 'execCommand' in js)
    # 这条是实测踩出来的：`navigator.clipboard.writeText()` 在文档失焦时
    # **既不 resolve 也不 reject**（无头浏览器 100% 复现），没有超时兜底的话
    # 点按钮会毫无反馈 —— 按钮不变色、不弹提示，用户以为坏了。
    chk('JS 复制带超时兜底（防止 writeText 永久 pending 时点了没反应）',
        re.search(r'function copyText\([\s\S]{0,900}?setTimeout\(', js) is not None)
    chk('JS 把代码块模块暴露给探针（可断言「按下去会复制到什么」）',
        'initCodeCopy: initCodeCopy' in js and 'codeOf: function' in js)
    chk('JS 在 boot 里挂上了复制逻辑', 'initCodeCopy();' in js)
    # 顺手兜住 toast：site.js 历史上调用过 8 次 toast 却从未定义，
    # 那些分支一执行就 ReferenceError —— 补上之后这里守住它不再丢。
    chk('JS 定义了 toast（不再是有调用无实现）',
        'function toast(' in js and re.search(r'^\.toast\{', css, re.M) is not None)

    print()
    print('=== ⑬ 课程返回入口（可选注入 · 条件式）===')
    # 只有声明了 config.course_home 的讲次才有这个元素（课程场景的可选增强，
    # 见 docs/v2-course-collection.md §5.9）。**单讲产物没有它是合法形态** ——
    # 与 ⑫ 代码块组同一原则：没有就整组 SKIP，不能报 FAIL。
    n_home = len(re.findall(r'<a class="course-home"', html))
    if n_home == 0:
        print('%-52s %s %s' % ('（本文档没有课程返回入口，本组跳过）', 'SKIP', '0 个'))
    else:
        chk('恰好一个课程返回入口', n_home == 1, '%d 个' % n_home)
        mh = re.search(r'<a class="course-home" href="([^"]*)"', html)
        href = mh.group(1) if mh else ''
        chk('href 非空、无裸空白', bool(href) and not re.search(r'\s', href), href)
        chk('href 是相对路径（不带协议、不以 / 开头）',
            bool(href) and '://' not in href and not href.startswith('/'), href)
        tb_s = html.find('<div class="topbar">')
        tb_e = html.find('</div>', tb_s)
        a_s = html.find('<a class="course-home"')
        chk('位于顶栏容器内（顶栏最左）', 0 <= tb_s < a_s < tb_e)
        chk('CSS 定义了 .course-home 样式', '.course-home' in css)

    print()
    print('=== ⑭ 关于面板（顶栏入口 + 使用说明 + 生成工具）===')
    # 2026-10-17 增补：原顶栏的 pdf-line（「原文件已内嵌……」）与正文的「这份文档怎么用」
    # 卡都收进了这个面板 —— 使用说明随外壳走，正文不再重复。**非条件式**（与 ⑬ 相反）：
    # 每份产物都该有它；没有就是构建链出了问题。
    chk('存在顶栏「关于」入口', 'id="aboutBtn"' in html)
    chk('存在关于面板（#aboutMask / .ab-card）',
        'id="aboutMask"' in html and 'class="ab-card"' in html)
    m_ab = re.search(r'class="ab-list"([\s\S]*?)</ol>', html)
    n_howto = m_ab.group(1).count('<li>') if m_ab else 0
    chk('面板含使用说明条目（≥ 6 条）', n_howto >= 6, '%d 条' % n_howto)
    n_sec = html.count('class="ab-sec"')
    chk('面板分节（使用说明 + 生成工具 ≥ 2 节）', n_sec >= 2, '%d 节' % n_sec)
    chk('面板含生成工具说明（GitHub 链接）',
        'github.com/zzzhen-22/slides-annotated-html' in html)
    chk('顶栏不再有 pdf-line（已迁进关于面板）', 'class="pdf-line"' not in html)
    chk('面板带 modal 语义（role=dialog + aria-modal）',
        'role="dialog"' in html and 'aria-modal="true"' in html)
    chk('CSS 有关于面板样式（.ab-mask / .ab-card）',
        '.ab-mask' in css and '.ab-card' in css)
    chk('JS 有 About 模块（开 / 关 / Esc 接线）',
        'var About =' in js and 'About.isOpen()' in js and 'About.init();' in js)

    print()
    print('=== 数量一致性 ===')
    # 「逐页区块」的匹配式：**只看属性、不看顺序**，与 build.py / check_math.js / coursekit.py 同源。
    # v1 用字符串 `'<section class="pg"'` 计数，隐含要求 class 紧跟 `<section`；v2 给 section
    # 追加 data-* 之后，属性换序的写法会让这里少数、而 build.py 照样注入 —— 两边对不上。
    pg = len(re.findall(r'<section(?=[^>]*\bclass="pg")(?=[^>]*\bdata-page="\d+")[^>]*>', html))
    th = html.count('class="thumb"')
    # 深链计数要**按标签分别数**，不能只数 class="pdf-link" 字符串。
    # 早先用字符串计数，把停用态的 <span> 和活链 <a> 混在一起算——数字对上了，
    # 却掩盖了「一个是死链一个是活链」这个本质差别（见 pitfalls 第 44 条）。
    pl_a = len(re.findall(r'<a class="pdf-link"', html))
    pl_span = len(re.findall(r'<span class="pdf-link"', html))
    chk('逐页区块 = 缩略图 = 深链总数', pg == th == pl_a + pl_span and pg > 0,
        '%d / %d / %d（活链 %d + 停用 %d）' % (pg, th, pl_a + pl_span, pl_a, pl_span))
    chk('不会同时存在活链与停用态（降级要么全做要么不做）', not (pl_a and pl_span),
        '' if not (pl_a and pl_span) else '两种形态并存')
    chk('目录链接数与页数不矛盾', len(re.findall(r'<a href="#', nav)) >= pg,
        '%d 条 / %d 页' % (len(re.findall(r'<a href="#', nav)), pg))
    print('  文件大小: %.2f MB' % (os.path.getsize(path) / 1048576))

    print()
    print('结果:', 'ALL PASS' if not fails else ('FAILED: ' + '; '.join(fails)))
    sys.exit(0 if not fails else 1)


if __name__ == '__main__':
    main()
