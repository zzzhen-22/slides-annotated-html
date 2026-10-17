#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""课程层体检（静态断言，不依赖浏览器）—— 设计稿 §5.7 的七条 + 要点表断言 + 资源自检。

用法：
    python course_check.py <课程目录>

它回答的是**单讲那套体检答不了**的问题：一门课的各部分之间，还互相认不认得。
逐组：

    === 资源自身 ===            course-shell.html / course.css / course.js 的接线是否齐全
    ① course.json 与讲次目录     每个 dir 存在、config.json 可解析、done/partial 的产物在
    ② 课程入口 index.html        跨讲链接的文件与锚点都要可达、无裸空格、入口与 course.json 同步
    ③ 术语一致性                glossary.json 的 conflicts 必须为空（同一概念不许两讲两个名字）
    ④ 跨讲引用 .xref             卡片里的外链都要可达（课程目录完整时）
    ⑤ data-pays-off / forward   格式合法、概念在术语表、讲次与页都真实存在
    ⑥ 要点表                    #keypoints 的 data-at 必须指向本讲真实存在的页 id
    ⑦ 索引新鲜度                 产物哈希 vs index.json —— 不一致 = 该重跑 run_course --sync

为什么要它：以上每一条都对应一种「流水线全绿、但课程层悄悄坏掉」的故障 ——
改名断链、术语漂移、锚点被删、产物改了索引没跟上。设计稿 §8 阶段 3 的验收要求：
故意制造这几种错误，本脚本必须**逐条**报 FAIL（v1 的 pitfalls 第 44 条正是
「断言写错形态导致体检永远 PASS」的事故，所以这一步不许省）。

约定：FAIL 进退出码（0 = ALL PASS）；WARN 只提示，不拦。
"""
import argparse
import json
import os
import re
import sys
from html import unescape as html_unescape

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import coursekit  # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

MAX_KEYPOINTS = 10          # 与 course_index.py 同口径：超过它多半是在抄速查表
RE_PAYS_OFF = re.compile(r'^[a-z0-9-]+@L\d+:p?\d+$')   # 与 course_index.py 的 WARN 同源
RE_HREF = re.compile(r'''href\s*=\s*(?:"([^"]*)"|'([^']*)')''')
RE_ID = re.compile(r'\bid="([^"]+)"')

fails, warns = [], []


def chk(label, cond, detail=''):
    print('%-56s %s %s' % (label, 'PASS' if cond else 'FAIL', detail))
    if not cond:
        fails.append(label)


def warn(msg):
    warns.append(msg)


# ================================================================== 产物扫描
# 一个产物要参与四组检查（① 存在性 / ② 目标可达 / ④⑤⑥ 内容声明 / ⑦ 哈希），
# 但**只读一遍**：扫描结果按绝对路径缓存，读完不保留原文（一份产物可以到 10 MB，
# 14 讲全留在内存里是没必要的）。原文不进缓存，派生数据都很小。
_PROD_CACHE = {}


def scan_product(path):
    """把一个产物里课程层要用的东西一次性抽出来。

    只在**正文标记**上找元素 —— `body_html()` 先挖掉 script / style / HTML 注释：
      · CSS 注释里就带着 `.xref` 的用法示例（含字面 `<div class="xref">` 与假 href）
      · 骨架产物的注释里到处都是 `data-concepts` 字样
    不挖的话，示例会被当成真实链接去校验、字样会被当成真实声明（pitfalls 第 18/46/47 条）。
    """
    path = os.path.normpath(path)
    if path in _PROD_CACHE:
        return _PROD_CACHE[path]
    html = coursekit.read_text(path) or ''
    body = coursekit.body_html(html)
    d = {
        'ids': set(RE_ID.findall(body)),          # 正文里全部 id（查锚点用）
        'page_nums': set(),                       # 逐页区块的页码（int，查「这一页在不在」）
        'kps': [],                                # [(at, topic)]，含还没写文本的占位 li
        'xrefs': [],                              # [href]，.xref 卡里的外链
        'homes': [],                              # [href]，顶栏「课程返回入口」的外链（可选注入）
        'pays': [],                               # [(page_id, value)]
        'forwards': [],                           # [(page_id, value)]
        'has': {k: (k in body) for k in ('data-concepts', 'data-pays-off', 'data-forward')},
    }
    for p in coursekit.page_entries(html):
        for src in (p.get('page') or '', p.get('id') or ''):
            m = re.search(r'(\d+)', src)
            if m:
                d['page_nums'].add(int(m.group(1)))
        for v in p.get('pays_off') or []:
            d['pays'].append((p.get('id') or '', v))
        for v in p.get('forward') or []:
            d['forwards'].append((p.get('id') or '', v))

    # #keypoints 卡的 li：**连还没写文本的占位 li 一起收** ——
    # 它们的 data-at 同样必须有效（写错一个锚点，考点跳到 404 而不自知）
    card = coursekit.card_html(body, 'keypoints')
    ol = re.search(r'<ol class="kpl"[^>]*>([\s\S]*?)</ol>', card, re.I)
    if ol:
        for m in re.finditer(r'<li\b([^>]*)>', ol.group(1), re.I):
            a = dict(re.findall(r'\bdata-([a-z-]+)="([^"]*)"', m.group(1)))
            d['kps'].append((a.get('at', '').lstrip('#'), a.get('topic', '')))

    # .xref 卡里的 <a href>（div 到第一个 </div> 为止，与 coursekit.note_texts 同约定）
    for m in re.finditer(r'<div[^>]*\bclass="[^"]*\bxref\b[^"]*"[^>]*>([\s\S]*?)</div>', body, re.I):
        for a in RE_HREF.finditer(m.group(1)):
            d['xrefs'].append(a.group(1) if a.group(1) is not None else a.group(2))

    # 顶栏的「课程返回入口」（可选注入，设计稿 §5.9）：有就收，没就空 —— 不强制
    for m in re.finditer(r'<a\b[^>]*\bclass="[^"]*\bcourse-home\b[^"]*"[^>]*>', body, re.I):
        hm = RE_HREF.search(m.group(0))
        if hm:
            d['homes'].append(hm.group(1) if hm.group(1) is not None else hm.group(2))

    _PROD_CACHE[path] = d
    return d


def split_href(href):
    """把 href 拆成 (路径, 片段)。先做 HTML 实体反转义（`&amp;` 之类写进 href 是合法的）。"""
    h = html_unescape(href or '')
    path, _, frag = h.partition('#')
    return path, frag


def is_external(href):
    """外部链接 / 协议链接 —— 不是课程层要管的事。"""
    return bool(re.match(r'^(?:[a-z][a-z0-9+.-]*:|//)', href, re.I))


def resolve_link(base_dir, href):
    """把一个相对 href 解析成绝对路径；片段在这里剔除。

    返回 (绝对路径, 片段, 错误)。**必须先解码再查**：链接可能是 %E6%AE%8B（中文）
    或 %20（空格），拿编码后的串去 os.path.exists 会永远找不到 —— 那不是断链（§5.5）。
    """
    path, frag = split_href(href)
    if re.search(r'\s', path):
        return None, frag, 'href 含裸空白：%r（空格必须写成 %%20，见设计稿 §5.5）' % href
    if path.startswith('/') or re.match(r'^[a-zA-Z]:', path):
        return None, frag, '绝对路径 %r（跨讲引用一律相对路径，见硬约束 C4）' % href
    return os.path.normpath(os.path.join(base_dir, coursekit.url_unquote(path))), frag, ''


def anchor_missing(target_path, frag):
    """目标产物里有没有这个 id 对应的锚点。"""
    if not frag:
        return False
    sc = scan_product(target_path)
    frag = coursekit.url_unquote(frag)
    if frag in sc['ids']:
        return False
    return True


# ================================================================== 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('course_dir',
                    help='课程目录（讲次的父目录，里面有 course.json）')
    a = ap.parse_args()
    course_dir = os.path.abspath(a.course_dir)
    cj_path = os.path.join(course_dir, 'course.json')

    print('课程层体检 —— %s' % course_dir)

    # 前置诊断：这压根不是一门课的时候，先说清楚，别让人对着一串 FAIL 猜。
    # （「是课程目录、但 course.json 坏了」属于另一回事，留给 ① 组去报。）
    if not os.path.exists(cj_path):
        print()
        print('✘ 这里没有 course.json —— 它不是一门课的目录。')
        print('  课程层要的是**讲次的父目录**（里面放着 lecture-01-xxx/ 这样的若干讲）。')
        print('  第一次用先建一次：')
        print('    python scripts/course_init.py "%s" --name "<课程名>"' % course_dir)
        print('  只想体检**单讲**的话用另一条链（check_math.js / check_ui.py / probe_doc.js），'
              '见 README「三重校验」。')
        sys.exit(2)

    # ---------------------------------------------------------- 资源自身
    print()
    print('=== 资源自身（课程页三件套）===')
    css = coursekit.read_text(os.path.join(KIT, 'assets', 'course.css')) or ''
    js = coursekit.read_text(os.path.join(KIT, 'assets', 'course.js')) or ''
    shell = coursekit.read_text(os.path.join(KIT, 'assets', 'course-shell.html')) or ''
    chk('course.css 花括号平衡', css.count('{') == css.count('}'),
        '%d/%d' % (css.count('{'), css.count('}')))
    chk('course.js 花括号平衡', js.count('{') == js.count('}'),
        '%d/%d' % (js.count('{'), js.count('}')))
    chk('course.js 暴露无头测试入口 window.__course', 'window.__course' in js)
    chk('course.js 有导出 Markdown（kp.markdown）', 'markdown: function' in js)
    chk('course.js 的检索索引立刻建（不懒建，防探针读到假故障）', 'CFind.build();' in js)
    chk('course.js 会渲染公式（要点表/术语总表里的 KaTeX）', 'renderMath' in js and 'katex.render' in js)
    # 交互接线的「两端都在」检查：shell 里有控件、js 里有引用 —— 只查一端的话，
    # 「UI 加了但没人接线」与「逻辑写了但没挂 UI」两种半成品都会漏网。
    for wid in ('kpFilter', 'kpToggle', 'kpExport', 'glFilter', 'glTools', 'glSort'):
        chk('course-shell.html 的 #%s 有控件、course.js 有引用' % wid,
            ('id="%s"' % wid) in shell and ("'#%s'" % wid) in js)
    chk('course.js 有 scrollspy（顶栏当前区块高亮）',
        'function initSpy' in js and 'Spy.build' in js)
    chk('course.js 有 URL 状态同步（#sec=&kp=&find=&gl=）',
        'function initUrl' in js and "'sec='" in js)
    # 顺序断言要拿 **boot() 函数体内的调用处** 比，不能拿 `initKp()` 字面量 ——
    # 它首次出现是 `function initKp() {` 这个**定义**（在 renderMath 调用之前），
    # 用字面量找会把正确的代码误判成「顺序反了」。
    _m_boot = re.search(r'\bfunction\s+boot\s*\(\s*\)\s*\{', js)
    _ok_order = False
    if _m_boot:
        _tail = js[_m_boot.end():]
        _a = re.search(r'\brenderMath\s*\(\s*document\s*\)', _tail)
        _b = re.search(r'\binitKp\s*\(\s*\)', _tail)
        _ok_order = bool(_a and _b and _a.start() < _b.start())
    chk('course.js 渲染公式在 build 要点索引之前（顺序反了过滤会按源码匹配）', _ok_order,
        '' if _ok_order else 'boot() 里要先 renderMath(document) 再 initKp()')
    chk('course-shell.html 内联了 KaTeX 的 CSS 与 JS 两个占位符',
        '__KATEX_CSS__' in shell and '__KATEX_JS__' in shell)
    for sid in ('map', 'keypoints', 'search', 'glossary', 'progress'):
        chk('course-shell.html 含区块 #%s' % sid, ('id="%s"' % sid) in shell)

    # ---------------------------------------------------------- ① course.json
    print()
    print('=== ① course.json 与讲次目录 ===')
    course = coursekit.read_json(cj_path)
    chk('course.json 可解析且 schema=course/v1',
        isinstance(course, dict) and course.get('schema') == 'course/v1',
        '' if isinstance(course, dict) else '读不到或不是合法 JSON')
    if not isinstance(course, dict):
        summary(len([]), 0, 0, 0)
        return finish()
    lectures = [x for x in (course.get('lectures') or []) if isinstance(x, dict)]

    # 没写 summary 时 hero 区会显示一句给读者看的占位文案（「本课程的目标简介还没写」），
    # 页面不算坏、但作者多半是忘了 —— 给一条 WARN 把「忘了」和「故意不写」分开。
    if not (course.get('summary') or '').strip():
        warn('course.json 还没写课程目标简介（summary）—— 课程主页 hero 区会显示占位文案')

    ids = [x.get('id') or '' for x in lectures]
    chk('讲次 id 非空且不重复', all(ids) and len(set(ids)) == len(ids), '、'.join(ids) or '(无讲次)')

    missing_dirs, bad_cfg, missing_prod, prods = [], [], [], {}
    for lec in lectures:
        lid = lec.get('id') or '?'
        d = (lec.get('dir') or '').strip()
        full = os.path.join(course_dir, d) if d else ''
        if not d or not os.path.isdir(full):
            missing_dirs.append('%s(%s)' % (lid, d or '空'))
            continue
        if coursekit.read_json(os.path.join(full, 'config.json')) is None:
            bad_cfg.append(lid)
        rel = lec.get('product') or ''
        p = os.path.join(course_dir, rel) if rel else ''
        if rel and os.path.exists(p):
            prods[lid] = os.path.normpath(p)
        if (lec.get('status') or '') in ('done', 'partial') and not (rel and os.path.exists(p)):
            missing_prod.append('%s(%s)' % (lid, rel or 'product 字段为空'))
    chk('每个讲次的 dir 都存在', not missing_dirs, '缺：%s' % '、'.join(missing_dirs))
    chk('每个讲次目录里有可解析的 config.json', not bad_cfg, '坏：%s' % '、'.join(bad_cfg))
    chk('done / partial 的讲次产物文件存在', not missing_prod, '缺：%s' % '、'.join(missing_prod))

    # ---------------------------------------------------------- ② index.html
    print()
    print('=== ② 课程入口 index.html：跨讲链接必须可达 ===')
    n_links = 0
    raw = coursekit.read_text(os.path.join(course_dir, 'index.html'))
    chk('index.html 存在', raw is not None, '' if raw is not None else '先跑 course_site.py')
    if raw is not None:
        body = coursekit.body_html(raw)
        left = sorted(set(re.findall(r'__[A-Z][A-Z_]+__', body)))
        chk('没有未替换的占位符（__XXX__）', not left, '、'.join(left))

        hrefs = [html_unescape(m.group(1) if m.group(1) is not None else m.group(2))
                 for m in RE_HREF.finditer(body)]
        space_bad = [h for h in hrefs if re.search(r'\s', h)]
        chk('href 里没有裸空白（空格必须 %%20）', not space_bad,
            '例：%r' % space_bad[0] if space_bad else '%d 条链接' % len(hrefs))

        page_ids_here = set(RE_ID.findall(body))
        dead_files, dead_anchors, internal_bad = [], [], []
        for h in hrefs:
            if is_external(h):
                continue
            path, frag = split_href(h)
            if not path:
                if frag and coursekit.url_unquote(frag) not in page_ids_here:
                    internal_bad.append(h)
                continue
            target, frag2, err = resolve_link(course_dir, h)
            if err:
                dead_files.append(err)
                continue
            n_links += 1
            if not os.path.exists(target):
                dead_files.append('%s（文件不存在）' % h)
            elif frag2 and anchor_missing(target, frag2):
                dead_anchors.append('%s（目标产物里没有 #%s）' % (h, coursekit.url_unquote(frag2)))
        chk('每条相对链接的目标文件都存在', not dead_files, '；'.join(dead_files[:4]))
        chk('带锚点的链接在目标产物里都能找到该 id', not dead_anchors, '；'.join(dead_anchors[:4]))
        chk('页内锚点（#map 等）都存在', not internal_bad, '；'.join(internal_bad[:4]))

        # 反向：产物已存在的讲次，入口页必须有它的链接（否则入口页是旧的，跑 course_site.py）
        no_link = []
        for lec in lectures:
            lid = lec.get('id') or '?'
            if lid not in prods:
                continue
            want = coursekit.url_quote(lec.get('product') or '')
            if not any(h == want or h.startswith(want + '#') for h in hrefs):
                no_link.append(lid)
        chk('产物存在的讲次在入口页都有链接', not no_link,
            '缺链接：%s（跑 course_site.py 重新生成）' % '、'.join(no_link))

        # 内联数据与 course.json 同步（加了讲次没重跑 site → 入口页还停在旧世界）
        m = re.search(r'<script[^>]*\bid="cdata"[^>]*>([\s\S]*?)</script>', raw, re.I)
        n_site, ok_c = 0, False
        if m:
            try:
                n_site = len((json.loads(m.group(1)) or {}).get('lectures') or [])
                ok_c = True
            except ValueError:
                pass
        chk('入口页内联数据（cdata）可解析', ok_c)
        chk('入口页内联讲次数 = course.json 讲次数', ok_c and n_site == len(lectures),
            '%d vs %d' % (n_site, len(lectures)) if ok_c else '')

        # ---- 学习进度：内联的命名空间（cdata.ns）必须与产物实际 DOC_NS 一致 ----
        # 防漂移：主页按 ns 读各讲 localStorage 的阅读痕迹（设计稿 §5.10）。ns 由
        # course_site 从**产物**提取内联（单一真源）；产物重建后忘了重跑 course_site、
        # 或提取/注入环节被改坏，这里当场报红。与「返回入口」组同精神：只查
        # 「产物存在」的讲，产物不存在的讲不查。
        ns_bad, ns_checked = [], 0
        if ok_c:
            lecs_c = ((json.loads(m.group(1)) or {}).get('lectures')) or []
            for lc in lecs_c:
                lid = lc.get('id') or '?'
                fp = prods.get(lid)
                if not fp:
                    continue
                prod_raw = coursekit.read_text(fp) or ''
                mm = re.search(r'var DOC_NS\s*=\s*"(lr-doc:[0-9a-f]+:)"', prod_raw)
                actual = mm.group(1) if mm else ''
                ns_checked += 1
                if not actual:
                    ns_bad.append('%s：产物里找不到 DOC_NS（先重建该讲）' % lid)
                elif lc.get('ns') != actual:
                    ns_bad.append('%s：内联 %r ≠ 产物 %r（跑 course_site.py 重新生成）'
                                  % (lid, lc.get('ns'), actual))
        chk('学习进度的命名空间（cdata.ns）= 各讲产物实际值', not ns_bad, '；'.join(ns_bad[:4]))
        if ns_checked:
            print('  （核对了 %d 个讲次的命名空间）' % ns_checked)

        # 学习进度的静态骨架（lpTop 总览区 / lp-cell 每讲的格子）。有讲次就该有 ——
        # 运行期由 course.js 填充；静态层只保「骨架存在」（渲染正确性归探针 ⑭ 组）。
        if lectures:
            _sk_ok = 'id="lpTop"' in raw and 'class="lp-cell"' in raw
            chk('入口页含学习进度骨架（#lpTop / .lp-cell）', _sk_ok,
                '' if _sk_ok else '缺骨架（跑 course_site.py 重新生成）')

        # 公式能不能渲染 —— 防的具体事故（2026-10-15）：
        # 课程主页没内联 KaTeX，各讲汇总来的公式全显示成〔公式〕占位符。
        # 生成期断言全绿，只有人打开页面才看得见，所以必须在静态层也拦一道。
        n_math = len(re.findall(r'<script\b[^>]*\btype="math/tex', raw, re.I))
        has_katex = 'katex.min.js' in raw or 'katex.render' in raw
        chk('入口页内联了 KaTeX（公式才渲染得出来）', has_katex,
            '' if has_katex else 'index.html 里找不到 KaTeX —— 跑 course_site.py 重新生成')
        # 可见正文里不许出现占位符〔公式〕（那是给检索索引留的记号，不该显示）
        vis = coursekit.body_html(raw)
        ph = vis.count('〔公式〕')
        chk('可见正文里没有〔公式〕占位符', ph == 0,
            '%d 处（正文里有 %d 个待渲染公式）—— 抽取器把公式塌成了占位符，渲染链断了'
            % (ph, n_math) if ph else '%d 个公式已保留为可渲染标签' % n_math)

    # ---------------------------------------------------------- ③ 术语一致性
    print()
    print('=== ③ 术语一致性（_course/glossary.json）===')
    gl = coursekit.read_json(os.path.join(course_dir, '_course', 'glossary.json'))
    chk('glossary.json 可解析且 schema=glossary/v1',
        isinstance(gl, dict) and gl.get('schema') == 'glossary/v1',
        '' if isinstance(gl, dict) else '读不到或不是合法 JSON')
    terms = [t for t in ((gl or {}).get('terms') or []) if isinstance(t, dict)]
    conf = [t for t in terms if (t.get('conflicts') or [])]
    chk('没有术语冲突（同一概念在各讲译名一致）', isinstance(gl, dict) and not conf,
        '%d 个概念，冲突 %d 个' % (len(terms), len(conf)))
    for t in conf[:8]:
        print('      ✘ %s：%s' % (t.get('id'), '；'.join(t.get('conflicts') or [])))
    gloss_ids = {t.get('id') for t in terms if t.get('id')}
    for t in terms:
        if not (t.get('zh') or '').strip():
            warn('术语 %s 缺中文名（术语表那一行的第一格是空的）' % t.get('id'))

    # ---------------------------------------------------------- ④ .xref 外链
    print()
    print('=== ④ 跨讲引用 .xref 外链可达 ===')
    n_xref, xref_bad = 0, []
    for lid, p in sorted(prods.items()):
        sc = scan_product(p)
        base_dir = os.path.dirname(p)
        for h in sc['xrefs']:
            if re.search(r'\s', h):
                xref_bad.append('%s：href 含裸空白 %r' % (lid, h))
                continue
            if is_external(h) or h.startswith('#'):
                continue
            n_xref += 1
            target, frag, err = resolve_link(base_dir, h)
            if err:
                xref_bad.append('%s：%s' % (lid, err))
                continue
            if not os.path.exists(target):
                xref_bad.append('%s → %s（文件不存在）' % (lid, h))
            elif frag and anchor_missing(target, frag):
                xref_bad.append('%s → %s（目标产物里没有 #%s）' % (lid, h, coursekit.url_unquote(frag)))
    chk('每个 .xref 外链都可达（文件 + 锚点）', not xref_bad, '；'.join(xref_bad[:4]))
    if n_xref:
        print('  （检查了 %d 条 .xref 外链）' % n_xref)
    else:
        print('  （本课程还没有 .xref 跨讲卡）')

    # 课程返回入口（可选注入，设计稿 §5.9）：**有链接的讲**才查目标可达；
    # 没有链接的讲不查 —— 不声明 course_home 是合法形态，不能强制要求每个讲都有。
    home_bad, n_home = [], 0
    for lid, p in sorted(prods.items()):
        sc = scan_product(p)
        for h in sc['homes']:
            n_home += 1
            if re.search(r'\s', h):
                home_bad.append('%s：href 含裸空白 %r' % (lid, h))
                continue
            if is_external(h):
                continue
            target, _frag, err = resolve_link(os.path.dirname(p), h)
            if err:
                home_bad.append('%s：%s' % (lid, err))
            elif not os.path.exists(target):
                home_bad.append('%s → %s（目标文件不存在）' % (lid, h))
    chk('每个课程返回入口都指向存在的目标（有则必达）', not home_bad, '；'.join(home_bad[:4]))
    if n_home:
        print('  （检查了 %d 个课程返回入口）' % n_home)

    # ---------------------------------------------------------- ⑤ data-*
    print()
    print('=== ⑤ data-pays-off / data-forward 的格式与指向 ===')
    page_count = {}
    for lec in lectures:
        try:
            page_count[lec.get('id')] = int(lec.get('page_count') or 0)
        except (TypeError, ValueError):
            page_count[lec.get('id')] = 0
    pays_fmt, pays_ref, fwd_bad, pays_unresolved = [], [], [], []
    for lid, p in sorted(prods.items()):
        sc = scan_product(p)
        for pid, v in sc['pays']:
            where = '%s:%s' % (lid, pid or '?')
            if not RE_PAYS_OFF.match(v):
                pays_fmt.append('%s → %r（应为 概念id@L01:p77）' % (where, v))
                continue
            cid, _, ref = v.partition('@')
            tlec, _, tpage = ref.partition(':')
            n = int(re.sub(r'\D', '', tpage) or 0)
            if cid not in gloss_ids:
                pays_ref.append('%s → 概念 %r 不在术语表里' % (where, cid))
            if tlec not in ids:
                pays_ref.append('%s → 讲次 %s 不在课程里' % (where, tlec))
                continue
            tp = prods.get(tlec)
            if tp:
                if n not in scan_product(tp)['page_nums']:
                    pays_ref.append('%s → %s 没有第 %d 页' % (where, tlec, n))
            elif page_count.get(tlec) and n > page_count[tlec]:
                # 目标讲还没产物：退而求其次，按 course.json 的页数卡上界（设计稿 §4.3）
                pays_ref.append('%s → 超过 %s 的页数（%d 页）' % (where, tlec, page_count[tlec]))
            else:
                pays_unresolved.append('%s（目标讲 %s 还没有产物，暂无法验证）' % (where, tlec))
        for pid, v in sc['forwards']:
            for one in [x.strip() for x in v.split(',') if x.strip()]:
                if not coursekit.RE_CONCEPT_ID.match(one):
                    fwd_bad.append('%s:%s → %r（只允许小写字母/数字/连字符）' % (lid, pid or '?', one))
        if sc['has']['data-pays-off'] and not sc['pays']:
            warn('%s：产物里出现了 data-pays-off，但一个都没抽到 —— 属性可能挂错了位置' % lid)
        if sc['has']['data-forward'] and not sc['forwards']:
            warn('%s：产物里出现了 data-forward，但一个都没抽到 —— 属性可能挂错了位置' % lid)
    chk('data-pays-off 格式合法（概念id@LNN:pNN）', not pays_fmt, '；'.join(pays_fmt[:4]))
    chk('data-pays-off 指向真实存在的位置', not pays_ref, '；'.join(pays_ref[:4]))
    for u in pays_unresolved:
        warn('data-pays-off 暂时无法验证：%s' % u)
    for f in fwd_bad[:8]:
        warn('data-forward 不是合法概念 id：%s' % f)

    # ---------------------------------------------------------- ⑥ 要点表
    print()
    print('=== ⑥ 要点表（#keypoints）===')
    n_kp, at_bad, topic_bad, long_kp, no_kp = 0, [], [], [], []
    for lec in lectures:
        lid = lec.get('id') or '?'
        p = prods.get(lid)
        if not p:
            continue
        sc = scan_product(p)
        if not sc['kps']:
            if (lec.get('status') or '') == 'done':
                no_kp.append(lid)
            continue
        if len(sc['kps']) > MAX_KEYPOINTS:
            long_kp.append('%s（%d 条）' % (lid, len(sc['kps'])))
        for at, topic in sc['kps']:
            n_kp += 1
            if at:
                m = re.match(r'^p?(\d+)$', at)
                if not m or int(m.group(1)) not in sc['page_nums']:
                    at_bad.append('%s → #%s' % (lid, at))
            if topic and gloss_ids and topic not in gloss_ids:
                topic_bad.append('%s → %s' % (lid, topic))
    chk('每条的 data-at 都指向本讲真实存在的页', not at_bad,
        '；'.join(at_bad[:4]) if at_bad else '共 %d 条要点' % n_kp)
    if long_kp:
        warn('单讲要点超过 %d 条（建议 3–7，多半是在抄速查表）：%s'
             % (MAX_KEYPOINTS, '、'.join(long_kp)))
    if no_kp:
        warn('这些讲次标着 done 却没有「本讲要点」卡：%s（课程主页要点表会缺这一讲）'
             % '、'.join(no_kp))
    for t in topic_bad[:8]:
        warn('data-topic 不在术语表里，要点与术语的互链指不到东西：%s' % t)

    # ---------------------------------------------------------- ⑦ 索引新鲜度
    print()
    print('=== ⑦ 索引新鲜度（哈希一致性）===')
    cdir = os.path.join(course_dir, '_course')
    idx = coursekit.read_json(os.path.join(cdir, 'index.json'))
    kpj = coursekit.read_json(os.path.join(cdir, 'keypoints.json'))
    chk('index.json 可解析且 schema=index/v1',
        isinstance(idx, dict) and idx.get('schema') == 'index/v1',
        '' if isinstance(idx, dict) else '读不到或不是合法 JSON')
    chk('keypoints.json 可解析且 schema=keypoints/v1',
        isinstance(kpj, dict) and kpj.get('schema') == 'keypoints/v1',
        '' if isinstance(kpj, dict) else '读不到或不是合法 JSON')
    if isinstance(idx, dict):
        iids = [x.get('id') for x in (idx.get('lectures') or []) if isinstance(x, dict)]
        chk('index.json 的讲次与 course.json 一致', set(iids) == set(ids),
            '索引 %d 个 / 课程 %d 个' % (len(iids), len(ids)))
        stale = []
        for ent in (idx.get('lectures') or []):
            if not isinstance(ent, dict):
                continue
            rel = ent.get('product') or ''
            cur = coursekit.file_hash(os.path.join(course_dir, rel)) if rel else ''
            if (ent.get('hash') or '') != cur:
                stale.append('%s（索引记 %s，现场 %s）'
                             % (ent.get('id'), ent.get('hash') or '空', cur or '空'))
        chk('各讲产物与 index.json 的哈希一致', not stale,
            '；'.join(stale[:4]) if stale else '（不一致 = 产物改过还没重跑，先跑 run_course --sync）')
        if stale:
            print('      ✘ %s' % '；'.join(stale[:6]))

    # ---------------------------------------------------------- 收尾
    summary(len(lectures), n_links, len(terms), n_kp)
    finish()


def summary(n_lec, n_links, n_terms, n_kp):
    print()
    print('统计：%d 讲 ｜ %d 条入口链接 ｜ %d 个术语 ｜ %d 条要点' % (n_lec, n_links, n_terms, n_kp))


def finish():
    if warns:
        print()
        print('警告 %d 条（不影响 PASS/FAIL，但值得看一眼）：' % len(warns))
        for w in warns[:20]:
            print('  · %s' % w)
        if len(warns) > 20:
            print('  …… 还有 %d 条' % (len(warns) - 20))
    print()
    print('结果:', 'ALL PASS' if not fails else ('FAILED: ' + '; '.join(fails)))
    if fails:
        print('  修完后重跑：python scripts/run_course.py "<课程目录>" --sync')
    sys.exit(0 if not fails else 1)


if __name__ == '__main__':
    main()
