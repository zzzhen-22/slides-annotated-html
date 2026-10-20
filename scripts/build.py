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

# 强制 stdout/stderr 走 UTF-8：英文地区 Windows 默认编码 cp1252，print 中文会
# UnicodeEncodeError（GitHub Windows runner 上实测踩到，2026-10-07）。
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, '..', 'assets')
sys.path.insert(0, HERE)
import kitpath  # noqa: E402  统一的参数解析与三段式报错（见 kitpath.arg_parser / die）

# 占位符 → 允许出现次数的校验
REQUIRED = ['__KATEX_CSS__', '__CSS__', '__KATEX_JS__', '__TITLE__', '__BRAND__',
            '__SIDEBAR_TITLE__', '__SIDEBAR_SUB__', '__SEARCH_PH__', '__NAV_FOOT__',
            '__ABOUT_BODY__', '__ABOUT_PDF__', '__PDFURL__', '__DOC_NS__', '__JS__',
            '__TOC__', '__BODY__', '__FOOT1__', '__FOOT2__',
            '__PDF_NAME__', '__PDF_B64__']

# ------------------------------------------------------------ 「逐页区块」的匹配式
# **只看属性、不看顺序。**
#
# 为什么不能用 v1 的老写法 `<section class="pg" id="p\d+" data-page="\d+">`：
# 它要求开标签在 `data-page` 之后**立刻闭合**。v2 给 section 追加了 data-concepts /
# data-pays-off / data-forward 之后，这条正则**一条都匹配不上** —— 后果是缩略图全部不注入，
# 产物每页都缺原页图。实测：属性追加在后、属性换序、class 不在最前，老写法全部失配。
#
# ⚠ **同源拷贝**：coursekit.py / check_math.js / check_ui.py 里各有一份等价实现，
#   四处口径必须一致（改一处就要改四处），否则「缩略图 N / 逐页区块 M」会互相打架。
RE_PG_TAG = re.compile(r'<section(?=[^>]*\bclass="pg")(?=[^>]*\bdata-page="\d+")[^>]*>')
RE_PG_BLOCK = re.compile(RE_PG_TAG.pattern + r'.*?</section>', re.S)

# ============================================================ 代码块后处理
# 分片里写的形态（**只有源码，没有标题栏**）：
#
#   <div class="codeblk" data-lang="python" data-src="原文件 P24 · 模型定义">
#   <pre class="code">class ActorCritic(...)</pre>
#   </div>
#
# 构建期做三件事，把上面这段补成「能读、能抄、能复制」的完整代码块：
#   ① **着色**：注释 / 字符串 / 关键字 / 数字四类上色。**不用任何高亮库** ——
#      单文件产物要断网可用、不能引 CDN，所以自己在构建期扫一遍就够了。
#      为什么放在构建期而不是运行时：颜色跟着文件走，打印、另存、断网都还在。
#   ② **标题栏**：由 data-lang / data-src 生成语言标签、来源说明与「复制」按钮。
#      （分片里不手写标题栏，避免 20 个块各写一遍、改起来漏改。）
#   ③ **行高亮**：data-hl="12,18" 把指定行加底色，供正文点名某行时用。
#
# 两条纪律：
#   · 着色**只加 <span>、不动一个字符**。产物里的文字投影（标记与笔记的定位口径）
#     拼的是文字节点，切碎成多个 span 不影响它 —— 但一旦顺手改了字，笔记全失效。
#     所以下面有 decorate_codeblocks 的自证断言：剥掉 span 后必须与原码逐字相同。
#   · **幂等**：块里已经含 <span class="c/s/k/n"> 就整体跳过（尊重手工着色），
#     已含 .codeblk-head 就不再注入标题栏。
LANG_NAME = {'python': 'Python', 'py': 'Python', 'bash': 'Bash', 'sh': 'Bash',
             'shell': 'Bash', 'text': '运行输出', 'output': '运行输出', 'plain': '纯文本'}
# 只对「有语法」的语言着色；运行输出 / 纯文本不着色（给它们上色只会误导）。
COLOR_LANGS = ('python', 'py', 'bash', 'sh', 'shell')

PY_KW = frozenset((
    'import from as def class return if elif else for while in not and or is None '
    'True False with try except finally raise pass break continue lambda global '
    'nonlocal yield assert del async await print').split())
# print 严格说不是关键字，但它是这套代码里唯一高频出现的函数调用，
# 不染一下，整块代码看起来全黑、层次立不起来。
SH_KW = frozenset((
    'sudo apt-get apt pip pip3 conda python python3 echo cd export mkdir rm cp mv '
    'if then fi for do done while read source cat grep sed chmod systemctl').split())

# 实体往返：分片里的代码是**已转义**的（`>` 写成 &gt;），而着色必须按真实字符来扫，
# 否则 `&gt;` 会被当成字母串、`&` 会干扰；输出时再转义回去。往返恒等（已自证）。
_ENT = {'&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'", '&amp;': '&'}
_RE_UNESC = re.compile(r'&(?:lt|gt|quot|#39|amp);')


def _unesc(s):
    return _RE_UNESC.sub(lambda m: _ENT[m.group(0)], s)


def _esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _tokenize(src, kw):
    """把一整段代码切成 [(类别, 文字)]，类别 ∈ ''(本色) / c 注释 / s 字符串 / k 关键字 / n 数字。

    优先级：注释 > 字符串 > 关键字 > 数字。必须先认注释与字符串 ——
    否则字符串里的 `#` 会被当注释、`if` 会被从字符串中间切开。

    **对整段扫描而不是逐行扫描**：三引号文档字符串常常跨行
    （整理版脚本开头的模块 docstring 就是），逐行扫会把它的中间几行
    当普通代码着色，一片绿中间夹一段黑的，很难看。整段扫才能正确识别。
    单引号 / 双引号字符串按 Python 语义**不跨行**：行内没闭合就到此为止，
    免得一处笔误把后面整篇都染成字符串色。
    """
    out, buf, i, n = [], [], 0, len(src)

    def flush():
        if buf:
            out.append(('', ''.join(buf)))
            buf.clear()

    while i < n:
        ch = src[i]
        if ch == '\n':                              # 换行原样保留（不并入被着色的片段）
            flush()
            out.append(('', '\n'))
            i += 1
            continue
        if ch == '#':                               # 注释：到行尾为止
            j = src.find('\n', i)
            if j < 0:
                j = n
            flush()
            out.append(('c', src[i:j]))
            i = j
            continue
        if ch in '"\'':
            q = ch
            if src[i:i + 3] == q * 3:               # 三引号：可以跨行
                j = src.find(q * 3, i + 3)
                j = n if j < 0 else j + 3
            else:
                j = i + 1
                while j < n:
                    if src[j] == '\n':
                        break                       # 单引号/双引号不跨行
                    if src[j] == '\\':
                        j += 2
                        continue
                    if src[j] == q:
                        j += 1
                        break
                    j += 1
            flush()
            out.append(('s', src[i:j]))
            i = j
            continue
        if ch.isalpha() or ch == '_':
            j = i
            while j < n and (src[j].isalnum() or src[j] == '_'):
                j += 1
            w = src[i:j]
            if w in kw:
                flush()
                out.append(('k', w))
            else:
                buf.append(w)
            i = j
            continue
        if ch.isdigit():
            j = i
            while j < n and (src[j].isdigit() or src[j] == '.'):
                j += 1
            flush()
            out.append(('n', src[i:j]))
            i = j
            continue
        buf.append(ch)
        i += 1
    flush()
    return out


def _colorize(src, lang):
    """给一段（已转义的）源码着色。返回 (着色后的 HTML, 纯文字)。"""
    if lang not in COLOR_LANGS:
        return src, _unesc(src)
    kw = PY_KW if lang in ('python', 'py') else SH_KW
    plain = _unesc(src)
    html = ''.join(_esc(t) if k == '' else '<span class="%s">%s</span>' % (k, _esc(t))
                   for k, t in _tokenize(plain, kw))
    return html, plain


# 匹配一个代码块。**属性顺序不限**，class 允许带修饰（inline）。
RE_CODEBLK = re.compile(
    r'<div class="codeblk(?P<mods>[^"]*)"(?P<attrs>[^>]*)>\s*'
    r'<pre class="code">(?P<src>[\s\S]*?)</pre>\s*</div>')
RE_CODE_ATTR = re.compile(r'\bdata-(lang|src|hl|title)="([^"]*)"')


def _hl_lines(spec):
    """解析 data-hl="12, 18" → [12, 18]（非法项直接丢弃，不让一个手滑毁掉整个构建）"""
    out = []
    for x in re.split(r'[,\s]+', spec or ''):
        if x.isdigit() and int(x) > 0:
            out.append(int(x))
    return out


def decorate_codeblocks(body):
    """给所有 .codeblk 补「着色 + 标题栏 + 行高亮」。返回 (新正文, 处理块数)。"""
    # **先拦手写的标题栏**。RE_CODEBLK 要求 `<div class="codeblk...">` 后面紧跟
    # `<pre class="code">`；分片里若自己写了标题栏，正则就失配、整块被**静默跳过**
    # （不着色、不加按钮，而且不报错）—— 这种「悄悄不做」最难发现。
    # 与其让它漏到下游，不如在这里硬失败。见 pitfalls 第 44 条。
    n_pre_head = body.count('class="codeblk-head"')
    if n_pre_head:
        raise SystemExit(
            '分片里出现了 %d 处手写的 codeblk-head —— 标题栏由 build.py 统一注入，'
            '分片里只写 data-lang / data-src 即可。\n'
            '  手写的标题栏会让代码块正则失配（该块会被静默跳过），必须删掉。' % n_pre_head)

    stats = {'n': 0}

    def repl(m):
        mods, attrs, src = m.group('mods'), m.group('attrs'), m.group('src')
        a = dict(RE_CODE_ATTR.findall(attrs))
        lang = (a.get('lang') or '').lower()
        stats['n'] += 1

        colored, plain = src, _unesc(src)
        # 幂等：块里已经有手写的着色 span 就整体跳过，不改人家的手笔
        if '<span class="c"' not in src and '<span class="k"' not in src:
            colored, plain = _colorize(src, lang)

        hls = _hl_lines(a.get('hl'))
        if hls:
            lines = colored.split('\n')
            for n in hls:
                if 0 <= n - 1 < len(lines):
                    lines[n - 1] = '<span class="ln-hl">%s</span>' % lines[n - 1]
            colored = '\n'.join(lines)

        # 标题栏：语言 / 来源 / 复制。src 为空则只留语言与复制。
        name = a.get('title') or LANG_NAME.get(lang, lang or '代码')
        parts = ['<div class="codeblk-head"><b>%s</b>' % _esc(name)]
        if a.get('src'):
            parts.append('<span class="code-src">%s</span>' % _esc(a['src']))
        parts.append('<button class="code-copy" type="button" data-copy="1">复制</button>')
        parts.append('</div>')
        head = ''.join(parts)

        return ('<div class="codeblk%s"%s>%s\n<pre class="code">%s</pre>\n</div>'
                % (mods, attrs, head, colored))

    new = RE_CODEBLK.sub(repl, body)

    # ② 声明了 .codeblk 却一块都没被匹配到 —— 说明写法超出了 RE_CODEBLK 的容忍范围
    #    （例如中间夹了别的元素、属性里有换行、`pre` 的 class 不叫 `code`）。
    #    这种「悄悄不处理」最难发现：产物看起来有代码块，只是没颜色、没复制按钮。
    #    断言问的是「是不是我无法接受的样子」——代码块没被处理，就是不能接受。
    n_declared = len(re.findall(r'<div class="codeblk(?: inline)?"', body))
    if n_declared != stats['n']:
        raise SystemExit(
            '声明了 %d 个代码块，但只处理了 %d 个 —— 有块没被 RE_CODEBLK 匹配上。\n'
            '  代码块必须写成 <div class="codeblk" data-lang=".." data-src="..">\n'
            '  紧接 <pre class="code">…</pre> 再闭 div，中间不要插别的元素。\n'
            '  未被处理的块不会着色、也没有复制按钮，必须修掉。'
            % (n_declared, stats['n']))

    # ③ 自证：剥掉本函数注入的所有标签后，代码块里的文字必须与原码逐字相同。
    # 「着色只加 span、不动字」是笔记能否继续定位的前提，不能靠自觉。
    def strip_tags(s):
        return re.sub(r'</?(?:span|button|b|div|pre)\b[^>]*>', '', s)

    RE_SRC_INNER = re.compile(r'<pre class="code">([\s\S]*?)</pre>')
    before = [_unesc(x) for x in RE_SRC_INNER.findall(body)]
    after = [_unesc(strip_tags(x)) for x in RE_SRC_INNER.findall(new)]
    if before != after:
        raise SystemExit(
            '代码块着色改变了源码文字（%d 块 → %d 块）—— 着色只允许加 <span>。\n'
            '  这会让「选中代码 → 标记笔记」的定位全部失效，必须修掉。' % (len(before), len(after)))
    return new, stats['n']


# ============================================================ 课程返回入口（可选注入）
# 只有声明了 config.course_home 的讲次才有这个元素（课程场景的可选增强，
# 见 docs/v2-course-collection.md §5.9）。三条性质：
#   · 不默认 —— 没有字段时**一个字节都不碰顶栏**；
#   · 可选 —— 删字段重构建即移除；
#   · 不构成依赖 —— 注入物只是一个 <a>，讲次的全部功能都不读课程目录
#     （被单独拷走时链接失效，其余毫发无损）。
#
# 为什么用「锚点插入」而不是占位符：无痕天然成立（不注入 = 零接触），
# 而且「单讲 demo → 课程 demo 讲次副本」的注入（build_demo.py 的
# add_course_home）与本处的构建注入**共用同一实现** —— 两处各写一份的话，
# 锚点迟早漂移。锚点必须恰好出现 1 次，不满足即硬失败（pitfalls 第 44 条）。
RE_TOPBAR_ANCHOR = '<div class="topbar">'


def course_home_html(raw_href):
    """生成「← 返回课程主页」链接的 HTML。href 统一 URL 编码（§5.5 同款 safe 集合）。"""
    href = urllib.parse.quote(str(raw_href).strip(), safe='/:')
    # 箭头与文字各包一层 span、用 CSS gap 排版（site.css）：这样 ≤1024px
    # 隐藏文字时（只留箭头）不会剩下「← 」的尾随空格、虚线底也只覆盖箭头本身。
    return ('<a class="course-home" href="%s" title="回到这门课的课程主页">'
            '<span class="ch-arrow">←</span>'
            '<span class="ch-label">返回课程主页</span></a>' % href)


def inject_course_home(html, raw_href):
    """把返回入口插进顶栏最左。返回注入后的 HTML；不注入时请直接别调本函数。"""
    n = html.count(RE_TOPBAR_ANCHOR)
    if n != 1:
        raise SystemExit(
            '顶栏锚点 %r 在页面里出现 %d 次（应为 1）—— 骨架变了或页面结构异常，'
            '课程返回入口无法安全注入。' % (RE_TOPBAR_ANCHOR, n))
    return html.replace(RE_TOPBAR_ANCHOR, RE_TOPBAR_ANCHOR + course_home_html(raw_href), 1)


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
    ap = kitpath.arg_parser(
        'build.py',
        description='把「讲解正文分片 + 离线 KaTeX + 页面缩略图」组装成单个断网可用的 HTML。',
        epilog='例：\n'
               '    python build.py config.json\n'
               '    python build.py config.json --out /tmp/try.html   # 试构建，不动正式产物')
    ap.add_argument('config', nargs='?', default='config.json', metavar='config.json',
                    help='项目配置（默认 ./config.json；相对路径按当前目录解析）')
    ap.add_argument('--out', default=None, metavar='输出路径',
                    help='覆盖 config.out（试构建用；笔记命名空间仍按 config.out 算，'
                         '所以试构建不会丢笔记）')
    a = ap.parse_args()
    cfg_path = os.path.abspath(a.config)
    out_override = a.out
    if not os.path.exists(cfg_path):
        kitpath.die('找不到配置文件：%s' % cfg_path,
                    '路径不对，或还没建项目骨架（config.json 由 init_project.py 生成）。',
                    ['建骨架：python scripts/init_project.py <课件.pdf> --out <项目目录>',
                     '再构建：python scripts/build.py <项目目录>/config.json'])
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

    # ---------- 代码块：着色 + 标题栏 + 行高亮 ----------
    # 放在缩略图之前：这一步只动 .codeblk 内部，与逐页区块的注入互不干扰，
    # 但先做可以让后面所有环节（体检、探针、截图）看到的都是最终形态。
    body, n_code = decorate_codeblocks(body)
    if n_code:
        print('代码块后处理: %d 块（着色 / 标题栏 / 行高亮）' % n_code)

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
    # 症状极隐蔽：产物里图片“在”，但 DOM 里查不到。见 references/pitfalls.md 第 18 条。
    _comments = []

    def _mask(m):
        _comments.append(m.group(0))
        return '\x00CMT%d\x00' % (len(_comments) - 1)

    masked = re.sub(r'<!--[\s\S]*?-->', _mask, body)
    # 先数应注入多少块，注入完再核对。**不等就硬失败**，不留一个数字让人自己看 ——
    # 「区块正则在某类写法下失配」这个故障极隐蔽（产物里图片「在」，但 DOM 里查不到），
    # 与其让它以「缩略图 0 / 逐页区块 12」的形式漏到下游，不如在源头拦住。见 pitfalls 第 44 条：
    # 断言要问「是不是我无法接受的样子」，而不是「是不是我期望的样子」。
    n_expect = len(RE_PG_TAG.findall(masked))
    masked, n_pg = re.subn(RE_PG_BLOCK, inject, masked)
    if n_pg != n_expect:
        raise SystemExit(
            '缩略图注入区块数 %d ≠ 逐页区块数 %d —— build.py 的区块正则失配了。\n'
            '  多半是 section 开标签的写法超出了 RE_PG_TAG 的容忍范围。\n'
            '  逐页区块必须同时有 class="pg" 与 data-page="N"，缺一个就不算。\n'
            '  见 scripts/build.py 顶部 RE_PG_TAG 的注释。' % (n_pg, n_expect))
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
    else:
        # config 没给 pdf（例如本仓库的在线 demo：原始课件因版权不入库）。
        # 此时模板里的 <a class="pdf-link" data-page="N"> 会**原样留下**——它是个没有 href
        # 的悬空链接，点了没反应，看起来像坏了。**主动换成停用态 span**，
        # 让「这里本来就没有原文件可跳」变成明示，而不是让体检把它当成缺陷报出来。
        # 参见 references/pitfalls.md 第 44 条。
        body, n_disabled = re.subn(
            r'<a class="pdf-link" data-page="(\d+)">(.*?)</a>',
            lambda m: '<span class="pdf-link" aria-disabled="true" '
                      'title="本产物未包含原文件，无法跳转到对应页">%s</span>' % m.group(2),
            body)
        if n_disabled:
            print('[build] config 未给 pdf —— %d 处「打开原 PDF 该页」已置为停用态'
                  % n_disabled)

    # ---------- 命名空间：file:// 下所有本地页面共享同一 localStorage 域，
    #            必须按文档隔离，否则不同讲解文档的笔记会串在一起 ----------
    doc_ns = 'lr-doc:' + hashlib.md5(ns_seed).hexdigest()[:10] + ':'

    # ---------- 关于面板（顶栏「关于」→ 使用说明 + 生成工具）----------
    # 原顶栏的 pdf-line（「原文件已内嵌……」）与正文的「这份文档怎么用」卡都收到这里。
    # 文案按 config.lang 取 assets/about-<lang>.html（缺省 zh）——英文 demo 用 en。
    lang = str(cfg.get('lang') or 'zh').strip().lower()
    if lang not in ('zh', 'en'):
        lang = 'zh'
    about_path = os.path.join(ASSETS, 'about-%s.html' % lang)
    if not os.path.exists(about_path):
        raise SystemExit('缺 assets/about-%s.html（关于面板文案；config.lang=%r）'
                         % (lang, cfg.get('lang')))
    about_body = open(about_path, encoding='utf-8').read()

    def _esc(s):
        return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    if embed:
        about_pdf = (('Source file <b>%s</b> — embedded in this document. Use “Open this page in '
                      'the original PDF” on any page, or “Save original PDF” in the top bar.')
                     % _esc(pdf_name)) if lang == 'en' else (
                     '原文件 <b>%s</b> —— 已内嵌在本文档里。点每页的「打开原文件该页」即可对照，'
                     '或用顶栏的「另存原 PDF」导出。' % _esc(pdf_name))
    elif pdf_url:
        about_pdf = ('Source file: <a href="%s" target="_blank" rel="noopener">%s</a>'
                     if lang == 'en' else
                     '对照原文件：<a href="%s" target="_blank" rel="noopener">%s</a>'
                     ) % (pdf_url, _esc(pdf_name))
    else:
        about_pdf = ('The source file is not embedded — this document contains the annotations '
                     'and page screenshots only.' if lang == 'en'
                     else '本文档没有内嵌原文件（只含讲解与页面截图）。')

    f1, f2 = (cfg.get('footer') or ['', ''])
    nav_foot = cfg.get('nav_foot',
                       '快捷键：<b>J</b>/<b>K</b> 翻页 · <b>/</b> 搜索正文 · '
                       '<b>M</b> 标记选中 · <b>B</b> 侧栏 · <b>T</b> 缩略图 · <b>N</b> 笔记')

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
        '__SEARCH_PH__': cfg.get('search_placeholder', '搜索正文 · 标题 · 页码（/）'),
        '__NAV_FOOT__': nav_foot,
        '__ABOUT_PDF__': about_pdf,
        '__PDFURL__': pdf_url,
        '__DOC_NS__': doc_ns,
        '__FOOT1__': f1,
        '__FOOT2__': f2,
        '__PDF_NAME__': pdf_name,
        '__PDF_B64__': pdf_b64,
    }
    # 先把关于面板正文拼进外壳：about-*.html 里的 __ABOUT_PDF__ 等占位由下面的
    # repl 循环统一替换（顺序上必须先拼、后替换）。
    html = shell.replace('__ABOUT_BODY__', about_body)
    for k, v in repl.items():
        html = html.replace(k, v)

    left = [k for k in REQUIRED if k in html]
    if left:
        raise SystemExit('还有未替换的占位符: %s' % left)

    # ---------- 课程返回入口（可选注入，见设计稿 §5.9）----------
    # 没声明 course_home 就什么都不做 —— 产物与旧版除「用不到的 CSS 规则」外零差异。
    raw_home = cfg.get('course_home')
    if raw_home is not None and not isinstance(raw_home, str):
        raise SystemExit('config.course_home 必须是字符串（课程主页相对产物目录的路径），'
                         '当前是 %r' % (raw_home,))
    if (raw_home or '').strip():
        html = inject_course_home(html, raw_home)
        print('课程返回入口: ← %s' % raw_home.strip())

    out = rp(cfg['out'])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w', encoding='utf-8').write(html)
    print('命名空间: %s' % doc_ns)
    print('输出: %s' % out)
    print('大小: %.2f MB' % (os.path.getsize(out) / 1048576))


if __name__ == '__main__':
    main()
