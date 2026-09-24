#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「讲解正文分片 + KaTeX 离线资源 + 页面缩略图」组装成单文件 HTML。

用法：
    python build.py [config.json] [--out 输出路径]

产物自带的交互（逻辑在 assets/site.js，样式在 assets/site.css，骨架在 assets/shell.html）：
    · 目录两级折叠（.toc-group 递归 + 状态记忆 + 搜索过滤 + 展开/折叠全部）
    · 侧栏整栏收起（body.nav-hidden），收起后缩略图列自动由 268px 放宽到 400px
    · 选中正文任意文字 → 浮动工具条 → 加入标记笔记；右侧抽屉支持备注、定位、导出 Markdown
    · 缩略图灯箱、滚动高亮、进度条、快捷键（J/K 翻页 · B 侧栏 · T 缩略图 · N 笔记）

config.json 关键字段
    groups  两级目录（递归）：
            [ [组名, 子项...], ... ]
            子项 = ["#锚点", "文字"]              叶子
                 | ["子组名", 子项, 子项, ...]      下级分组
    pages   [[页码, 标题], ...]
    shards  ["content/00_intro.html", ...]   按顺序拼接；最后一个分片应是纯 <section>
    pdf     原 PDF 路径，用于生成 file:// 深链（#page=N）
"""
import base64
import hashlib
import json
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, '..', 'assets')

# 占位符 → 允许出现次数的校验
REQUIRED = ['__KATEX_CSS__', '__CSS__', '__KATEX_JS__', '__TITLE__', '__BRAND__',
            '__SIDEBAR_TITLE__', '__SIDEBAR_SUB__', '__SEARCH_PH__', '__NAV_FOOT__',
            '__TOPBAR_TITLE__', '__PDF_LINE__', '__PDFURL__', '__DOC_NS__', '__JS__',
            '__TOC__', '__BODY__', '__FOOT1__', '__FOOT2__',
            '__PDF_NAME__', '__PDF_B64__']


def b64(path):
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode('ascii')


# ============================================================ 目录树渲染
# groups 结构（递归）：
#   [ [组名, 子项列表], ... ]
#   子项 = ["#锚点", "文字"]           叶子
#        | ["子组名", 子项列表]       下级分组
def count_pages(node):
    """统计一个分组下有多少个「页码链接」（#pNN），用于 .gcount"""
    n = 0
    for kid in node[1]:
        if isinstance(kid[1], str):
            if re.match(r'#p\d+$', kid[0]):
                n += 1
        else:
            n += count_pages(kid)
    return n


def render_group(node, ctr):
    gid = 'g%d' % next(ctr)
    name = node[0]
    cnt = count_pages(node)
    head = ('<div class="toc-head"><button class="toc-toggle" type="button" aria-expanded="true">'
            '<span class="chev"></span><span class="gt">%s</span></button>%s</div>'
            % (name, '<span class="gcount">%d</span>' % cnt if cnt else ''))
    inner = []
    for kid in node[1]:
        if isinstance(kid[1], str):
            href, label = kid[0], kid[1]
            m = re.match(r'#p(\d+)$', href)
            if m:
                inner.append('<a href="%s"><span class="num">%02d</span>'
                             '<span class="t">%s</span></a>' % (href, int(m.group(1)), label))
            else:
                inner.append('<a href="%s" class="group-link"><span class="num">·</span>'
                             '<span class="t">%s</span></a>' % (href, label))
        else:
            inner.append(render_group(kid, ctr))
    return ('<div class="toc-group" data-gid="%s">\n%s\n<div class="toc-items">\n%s\n</div></div>'
            % (gid, head, '\n'.join(inner)))


def build_toc(cfg):
    groups = cfg.get('groups') or []
    if not groups:
        raise SystemExit('config 缺少 groups（两级目录）')
    ctr = iter(range(1, 10000))
    body = '\n'.join(render_group(g, ctr) for g in groups)
    return '\n      ' + body + '\n  '


def collect_anchors(cfg):
    out = []

    def walk(node):
        for kid in node[1]:
            if isinstance(kid[1], str):
                if kid[0].startswith('#'):
                    out.append(kid[0][1:])
            else:
                walk(kid)

    for g in cfg.get('groups') or []:
        walk(g)
    return out


# ============================================================ 主流程
def main():
    args = list(sys.argv[1:])
    out_override = None
    if '--out' in args:
        i = args.index('--out')
        out_override = args[i + 1]
        del args[i:i + 2]
    cfg_path = os.path.abspath(args[0] if args else 'config.json')
    root = os.path.dirname(cfg_path)
    cfg = json.load(open(cfg_path, encoding='utf-8'))
    # 命名空间种子用「配置里的输出路径」而不是 --out 覆盖值，
    # 这样试构建（--out 到临时文件）与正式构建共享同一份笔记。
    ns_seed = (cfg.get('title', '') + '|' + cfg['out']).encode('utf-8')
    if out_override:
        cfg['out'] = out_override

    def rp(p):
        return p if os.path.isabs(p) else os.path.normpath(os.path.join(root, p))

    # ---------- 资源 ----------
    shell = open(os.path.join(ASSETS, 'shell.html'), encoding='utf-8').read()
    # 样式分两片：site.css 是基础版式，site.extra.css 是「目录折叠 / 侧栏收起 /
    # 本节概述 / 标记笔记」这几个交互功能的追加样式。拆开便于单独维护。
    css_files = ['site.css', 'site.extra.css']
    site_css = '\n'.join(open(os.path.join(ASSETS, f), encoding='utf-8').read()
                         for f in css_files if os.path.exists(os.path.join(ASSETS, f)))
    site_js = open(os.path.join(ASSETS, 'site.js'), encoding='utf-8').read()
    katex_dir = rp(cfg.get('katex_dir', '_katex'))
    katex_css = open(os.path.join(katex_dir, 'katex.offline.css'), encoding='utf-8').read()
    katex_js = open(os.path.join(katex_dir, 'katex.min.js'), encoding='utf-8').read()
    for nm, txt in (('katex.min.js', katex_js), ('site.js', site_js)):
        if '</script' in txt.lower():
            raise SystemExit('%s 含 </script，内联前必须转义' % nm)

    # ---------- 正文 ----------
    body = '\n'.join(open(rp(s), encoding='utf-8').read() for s in cfg['shards'])

    # 封面 id（若分片里没写）
    body = body.replace('<section class="cover">', '<section class="cover" id="cover">', 1)

    # ---------- 自动补齐目录锚点 ----------
    # #xyz 在正文里找不到 id="xyz" 时，就在 class 里含 xyz 的 <section> 上补 id
    anchors = collect_anchors(cfg)
    auto, missing = [], []
    for aid in anchors:
        if ('id="%s"' % aid) in body:
            continue
        mm = re.search(r'<section class="([^"]*\b%s\b[^"]*)">' % re.escape(aid), body)
        if mm:
            body = body.replace(mm.group(0),
                                '<section class="%s" id="%s">' % (mm.group(1), aid), 1)
            auto.append(aid)
        else:
            missing.append(aid)
    if auto:
        print('自动补 id: %s' % ', '.join(auto))
    if missing:
        print('  [warn] 目录锚点无对应元素: %s' % ', '.join(missing))

    # ---------- 注入缩略图 ----------
    thumb_dir = rp(cfg.get('thumb_dir', '_extract'))
    pattern = cfg.get('thumb_pattern', 'thumb_{n:02d}.jpg')

    def inject(m):
        block = m.group(0)
        num = int(re.search(r'data-page="(\d+)"', block).group(1))
        img = os.path.join(thumb_dir, pattern.format(n=num))
        if not os.path.exists(img):
            print('  [warn] 缺缩略图 %s' % img)
            return block
        fig = ('\n  <figure class="thumb"><img src="data:image/jpeg;base64,%s" '
               'data-cap="原文件第 %d 页" alt="原文件第 %d 页">\n'
               '    <figcaption>原文件 P%d · 点击放大</figcaption></figure>\n'
               % (b64(img), num, num, num))
        return block[:block.rfind('</section>')] + fig + '</section>'

    # 先把 HTML 注释整体挖走，再匹配区块 —— 否则注释里一旦出现字面 </section>
    # （很常见：「缩略图会插到 </section> 之前」这类说明），非贪婪 .*? 会提前收尾，
    # 缩略图被塞进注释内部、注释损坏、真收尾标签变游离标签。
    # 症状极隐蔽：产物里图片“在”，但 DOM 里查不到。见 references/pitfalls.md 第 30 条。
    _comments = []

    def _mask(m):
        _comments.append(m.group(0))
        return '\x00CMT%d\x00' % (len(_comments) - 1)

    masked = re.sub(r'<!--[\s\S]*?-->', _mask, body)
    masked, n_pg = re.subn(r'<section class="pg" id="p\d+" data-page="\d+">.*?</section>',
                           inject, masked, flags=re.S)
    body = re.sub(r'\x00CMT(\d+)\x00', lambda m: _comments[int(m.group(1))], masked)
    print('注入缩略图区块: %d' % n_pg)

    # ---------- PDF 深链 ----------
    # 两种模式：
    #   A. 默认 —— 链接指向本机的原始 PDF（绝对路径 file://…#page=N），只能在本机用；
    #   B. embed_pdf=true —— 把原 PDF 以 base64 内嵌进本文件，链接改为打开内嵌副本，
    #      于是文件拷到任何设备都能打开原文件（代价是体积 + 约 1.34 倍 PDF 大小）。
    embed = bool(cfg.get('embed_pdf'))
    pdf_name = os.path.basename(cfg['pdf']) if cfg.get('pdf') else ''
    pdf_url = ''
    pdf_b64 = ''
    if cfg.get('pdf'):
        pdf_url = 'file:///' + urllib.parse.quote(rp(cfg['pdf']).replace('\\', '/'), safe='/:')
    if embed:
        if not pdf_url:
            raise SystemExit('embed_pdf=true 但 config 没给 pdf 路径')
        pdf_b64 = b64(rp(cfg['pdf']))
        pdf_line = '原文件已内嵌 · 点每页的「打开原文件该页」即可对照'
    else:
        pdf_line = ('对照原文件：<a href="%s" target="_blank" rel="noopener">%s</a>'
                    % (pdf_url, pdf_name)) if pdf_url else ''

    # 把链接写进 HTML（不依赖 JS 也能点；内嵌模式下由 site.js 接管）
    if embed:
        body = re.sub(r'<a class="pdf-link" data-page="(\d+)">(.*?)</a>',
                      lambda m: '<a class="pdf-link" href="#" data-embed-page="%s" '
                                'role="button">%s</a>' % (m.group(1), m.group(2)),
                      body)
    elif pdf_url:
        body = re.sub(r'<a class="pdf-link" data-page="(\d+)">(.*?)</a>',
                      lambda m: '<a class="pdf-link" href="%s#page=%s" target="_blank" '
                                'rel="noopener">%s</a>' % (pdf_url, m.group(1), m.group(2)),
                      body)

    # ---------- 命名空间：file:// 下所有本地页面共享同一 localStorage 域，
    #            必须按文档隔离，否则不同讲解文档的笔记会串在一起 ----------
    doc_ns = 'lr-doc:' + hashlib.md5(ns_seed).hexdigest()[:10] + ':'

    f1, f2 = (cfg.get('footer') or ['', ''])
    nav_foot = cfg.get('nav_foot',
                       '快捷键：<b>J</b>/<b>K</b> 翻页 · <b>M</b> 标记选中 · <b>B</b> 侧栏 · <b>T</b> 缩略图 · <b>N</b> 笔记')

    repl = {
        '__KATEX_CSS__': katex_css,
        '__CSS__': site_css,
        '__KATEX_JS__': katex_js,
        '__JS__': site_js,
        '__TOC__': build_toc(cfg),
        '__BODY__': body,
        '__TITLE__': cfg.get('title', '逐页精解'),
        '__BRAND__': cfg.get('brand', ''),
        '__SIDEBAR_TITLE__': cfg.get('sidebar_title', ''),
        '__SIDEBAR_SUB__': cfg.get('sidebar_sub', ''),
        '__SEARCH_PH__': cfg.get('search_placeholder', '搜索页码或标题'),
        '__NAV_FOOT__': nav_foot,
        '__TOPBAR_TITLE__': cfg.get('topbar_title', ''),
        '__PDF_LINE__': pdf_line,
        '__PDFURL__': pdf_url,
        '__DOC_NS__': doc_ns,
        '__FOOT1__': f1,
        '__FOOT2__': f2,
        '__PDF_NAME__': pdf_name,
        '__PDF_B64__': pdf_b64,
    }
    html = shell
    for k, v in repl.items():
        html = html.replace(k, v)

    left = [k for k in REQUIRED if k in html]
    if left:
        raise SystemExit('还有未替换的占位符: %s' % left)

    out = rp(cfg['out'])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w', encoding='utf-8').write(html)
    print('命名空间: %s' % doc_ns)
    print('输出: %s' % out)
    print('大小: %.2f MB' % (os.path.getsize(out) / 1048576))


if __name__ == '__main__':
    main()
