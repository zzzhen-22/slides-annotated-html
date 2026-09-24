#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""产出物的静态体检（不依赖浏览器）—— check_math.js 的补充。

用法：
    python check_ui.py <输出.html>

检查四项交互功能的"接线"是否正确：
    ① 目录逐级折叠：分组/按钮/计数徽标数量、各小节标题是否都在
    ② 本节概述：overview 卡数量与其锚点是否进目录
    ③ 侧栏收起：navToggle/thumbToggle 是否存在、收起后缩略图列宽是否真的变大
    ④ 标记与笔记：抽屉 DOM、选择工具条依赖的样式、localStorage 命名空间是否注入

浏览器失灵时（见 references/pitfalls.md 第 13 条）用它兜底，
能覆盖"结构对不对"，覆盖不了"长得对不对"。
"""
import os
import re
import sys

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
    chk('JS 有 filter（搜索兼容嵌套）', 'filter: function' in js)
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
        # 默认模式（只写本机绝对路径深链）：这里只做「有没有写对」的正面检查，
        # 不再报「没内嵌」为失败 —— 那是配置选择，不是缺陷。
        chk('深链指向本机原文件（file:///#page=N）',
            'file:///' in html and '#page=' in html)
        chk('未内嵌时不留 data-embed-page（模式一致）', 'data-embed-page=' not in html)
        chk('未内嵌时 pdfB64 容器为空', payload == '')
        print('  （embed_pdf=false：跳过硬性内嵌项）')

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
    print('=== 数量一致性 ===')
    pg = html.count('<section class="pg"')
    th = html.count('class="thumb"')
    pl = html.count('class="pdf-link"')
    chk('逐页区块 = 缩略图 = PDF深链', pg == th == pl and pg > 0, '%d / %d / %d' % (pg, th, pl))
    chk('目录链接数与页数不矛盾', len(re.findall(r'<a href="#', nav)) >= pg,
        '%d 条 / %d 页' % (len(re.findall(r'<a href="#', nav)), pg))
    print('  文件大小: %.2f MB' % (os.path.getsize(path) / 1048576))

    print()
    print('结果:', 'ALL PASS' if not fails else ('FAILED: ' + '; '.join(fails)))
    sys.exit(0 if not fails else 1)


if __name__ == '__main__':
    main()
