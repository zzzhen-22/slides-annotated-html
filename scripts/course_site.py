#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""由 `course.json` + `_course/*.json` 生成课程合集入口 `index.html`。

用法：
    python course_site.py <课程目录> [--out index.html] [--max-text 120]
                          [--full] [--force-full] [--stdout-size]

产物是**单文件、断网可开**（硬约束 C1）。五区块：

    ① 课程地图   每讲的标题 / 页数 / 状态，点进对应产物
    ② 要点总结   各讲 #keypoints 汇总成一张可过滤、可导出 Markdown 的总表   ← 本版核心
    ③ 跨讲检索   搜内联的全课程索引，命中 → 跳到那一讲的该页并高亮
    ④ 术语总表   glossary.json 渲染；「首见」可点
    ⑤ 学习进度   每讲的阅读位置与笔记数（读各讲 localStorage；写作进度未完时逐行标注）
                  —— 设计稿 §5.10。

**为什么索引必须内联、不能在运行时 fetch**：`file://` 是不透明源，
`fetch('_course/index.json')` 会被 CORS 拦死，用户双击打开就是空白页。见设计稿 §5.2。

**为什么内容在 Python 侧预渲染、而不是让前端拿 JSON 画**：
预渲染的话，断网、禁用 JS、乃至任何抓取工具都读得到全部内容；JS 只做增强（过滤 / 导出 / 检索）。
体检脚本也因此能对静态 DOM 下断言，而不是猜前端渲染的结果。

设计稿：docs/v2-course-collection.md §5.1–5.6
"""
import argparse
import html as html_mod
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import coursekit  # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

SHELL = os.path.join(KIT, 'assets', 'course-shell.html')
CSS_F = os.path.join(KIT, 'assets', 'course.css')
JS_F = os.path.join(KIT, 'assets', 'course.js')
KATEX_DIR = os.path.join(KIT, 'vendor', 'katex')

SECTIONS = [('map', '课程地图'), ('keypoints', '要点总结'), ('search', '跨讲检索'),
            ('glossary', '术语总表'), ('progress', '学习进度')]
STATUS_LABEL = {'done': '已完成', 'partial': '部分完成', 'skeleton': '骨架', 'pending': '待建'}

SIZE_LIMIT = 3 * 1024 * 1024      # 超过就自动降级正文长度（设计稿 §5.6）
MAX_TEXT_FLOOR = 60
FULL_GATE = (8, 400)              # --full 的闸门：讲次数 / 总页数（设计稿 §8 阶段 4）
SEEN_MAX = 5                      # 术语表「出现位置」超过这个条数就截断（课程 TODO T8②）


def e(s):
    """HTML 转义。所有来自 json / 用户内容的字符串都必须先过它。"""
    return html_mod.escape(str(s if s is not None else ''), quote=True)


def href_of(lec, course_dir=None):
    """某讲产物的相对 URL（已百分号编码）。空表示这一讲**没有可打开的产物**。

    ⚠ 必须同时满足「product 字段非空」与「文件真的存在」两条：
    product 字段是从 config 的 `out` 推出来的**预计路径**——骨架讲次（还没构建）也推得出来。
    只判字段非空的话，骨架讲次的标题会挂上一个指向不存在文件的 `<a>`，点进去 404；
    而这里原本就备好了沉底形态（`<span class="ltitle dim" title="这一讲还没有产物可打开">`），
    只是从来没被走到。清单是死的、文件是活的——**链接只发活着的**
    （2026-10-14 由 course_check.py 的「入口页链接必须可达」断言逮出并修掉）。
    """
    p = (lec or {}).get('product') or ''
    if not p:
        return ''
    if course_dir and not os.path.exists(os.path.join(course_dir, p)):
        return ''
    return coursekit.url_quote(p)


def page_no(page_id):
    """把 `p12` 之类的锚点变成给人看的页码 `12`。"""
    m = re.search(r'(\d+)', str(page_id or ''))
    return m.group(1) if m else str(page_id or '')


def pages_left(lec):
    """这一讲还剩多少页没写。要点区的占位文案与学习进度区两处共用 ——
    同一个数只算一处，改口径时不会漏改另一边（审查报告 C1）。"""
    return max(0, (lec.get('page_count') or 0) - (lec.get('done_pages') or 0))


def doc_ns_of(course_dir, lec):
    """从某讲**产物**里提取命名空间（`lr-doc:<h10>:`），供「学习进度」读取端使用。

    单一真源：产物里的 `var DOC_NS` 由 build.py 注入、site.js 用它隔离笔记 ——
    这里只**提取**、不从 config（title/out）重算（重算 = 两处算法，迟早漂移）。
    产物不存在 / 是旧版构建没注入过时返回 ''，课程页按「无 ns」降级（该讲不显示
    学习进度）；course_check.py 对「产物存在但提取不到 / 与内联值不一致」报红。
    """
    p = (lec or {}).get('product') or ''
    if not p:
        return ''
    fp = os.path.join(course_dir, p)
    if not os.path.exists(fp):
        return ''
    try:
        raw = open(fp, encoding='utf-8', errors='replace').read()
    except OSError:
        return ''
    m = re.search(r'var DOC_NS\s*=\s*"(lr-doc:[0-9a-f]+:)"', raw)
    return m.group(1) if m else ''


# ------------------------------------------------------------------ ① 课程地图
def render_map(lectures, course_dir):
    out = []
    for lec in lectures:
        lid = lec.get('id') or '?'
        st = lec.get('status') or 'pending'
        title = lec.get('title') or lid
        href = href_of(lec, course_dir)
        topics = ' '.join('#' + t for t in (lec.get('topics') or []))
        # meta 只放徽标里没有的信息 —— 状态已在 badge 上（带颜色），不再重复渲染第二遍
        meta = []
        if lec.get('page_count'):
            meta.append('%s 页' % lec['page_count'])
        if href:
            name = '<a class="ltitle" href="%s">%s</a>' % (e(href), e(title))
        else:
            name = '<span class="ltitle dim" title="这一讲还没有产物可打开">%s</span>' % e(title)
        # 段与段之间用**真空格**连接（而不是只靠 flex 的 gap）：gap 是纯视觉的、
        # 进不了文本流，复制这一行会得到「L01selftest-deck部分完成」这种粘连串。
        # 纯空白文本节点在 flex 容器里不生成匿名 flex item，所以视觉零影响。
        segs = ['<span class="lid">%s</span>' % e(lid), name,
                '<span class="badge %s">%s</span>' % (e(st), e(STATUS_LABEL.get(st, st)))]
        if topics:
            segs.append('<span class="ltopics">%s</span>' % e(topics))
        if meta:
            segs.append('<span class="lmeta">%s</span>' % e(' · '.join(meta)))
        out.append('<div class="lec" data-lec="%s">%s</div>' % (e(lid), ' '.join(segs)))
    if not out:
        return '<p class="dim">（这门课还没有登记任何讲次。）</p>'
    return '\n'.join(out)


# ------------------------------------------------------------------ ② 要点总结
def render_keypoints(lectures, kp_by_id, course_dir):
    out = []
    total = 0
    for lec in lectures:
        lid = lec.get('id') or '?'
        st = lec.get('status') or 'pending'
        title = lec.get('title') or lid
        href = href_of(lec, course_dir)
        kp = kp_by_id.get(lid) or {}
        pts = kp.get('points') or []
        total += len(pts)
        # 标题在「有产物」时做成链接：读完要点想打开这一讲，不用滚回地图。
        # 讲次名与徽标之间用 <span> 包住，避免 flex 的 gap 把「L01 · 标题」拆散。
        if href:
            tname = '<a class="ktitle" href="%s">%s</a>' % (e(href), e(title))
        else:
            tname = e(title)
        head = ('<summary><span>%s · %s</span> <span class="badge %s">%s</span>'
                '<span class="kmeta">%s</span></summary>'
                % (e(lid), tname, e(st), e(STATUS_LABEL.get(st, st)),
                   e('%d 条' % len(pts)) if pts else '尚无要点'))
        if pts:
            rows = []
            for p in pts:
                extra = ''
                at = (p.get('at') or '').strip()
                if at and href:
                    extra += ('<a class="kp-at" href="%s#%s" title="跳到这一讲的该页">→P%s</a>'
                              % (e(href), e(at), e(page_no(at))))
                tp = (p.get('topic') or '').strip()
                if tp:
                    extra += ('<a class="kp-topic" href="#glossary" title="在术语总表里看这个概念">⟡%s</a>'
                              % e(tp))
                # 要点正文用**富文本**渲染（保留公式标签）——换成转义后的 text 会让
                # 要点里的 σ / ρ / ‖w‖ 显示成占位符〔公式〕，那样主页就读不懂了。
                # 回退到转义的 text 是为了兼容旧索引（没有 html 字段时也不至于丢内容）。
                rich = p.get('html') or e(p.get('text') or '')
                rows.append('<li>%s%s</li>' % (rich, extra))
            body = '<ol class="kpl">\n%s\n</ol>' % '\n'.join(rows)
        else:
            # **未写完的讲次要显式占位，绝不静默省略** —— 空白会让人以为遗漏了，
            # 而「还没写」正是必须一眼看出来的信息（设计稿 §5.2）。
            if st == 'pending':
                why = '本讲还没有目录 —— 在 course_init.py 里登记后再同步。'
            elif st == 'skeleton':
                why = '本讲还没构建产物 —— 跑 run_all.py 生成 HTML 后重跑课程同步。'
            elif st == 'partial':
                why = '本讲还有 %d 页没写完，要点待补。' % pages_left(lec)
            else:
                why = '本讲产物里没有「本讲要点」卡（#keypoints）—— 补上它再同步。'
            body = '<div class="kp-hold">%s</div>' % e(why)
        out.append('<details class="klec" data-lec="%s" open>\n%s\n%s\n</details>'
                   % (e(lid), head, body))
    if not out:
        return '<p class="dim">（这门课还没有登记任何讲次。）</p>'
    return '\n'.join(out)


# ------------------------------------------------------------------ ④ 术语总表
def render_glossary(terms, lec_by_id, course_dir):
    if not terms:
        return ('<p class="dim">（还没有术语。各讲写完 <code>#glossary</code> 术语表、'
                '并给引入概念的那一行加上 <code>data-concept</code> 之后，这里会自动长出内容。）</p>')
    rows = []
    for t in terms:
        first = t.get('first') or ''
        lid, _, pid = first.partition(':')
        lec = lec_by_id.get(lid) or {}
        href = href_of(lec, course_dir)
        if href and pid:
            seen_link = '<a href="%s#%s">%s P%s</a>' % (e(href), e(pid), e(lid), e(page_no(pid)))
        else:
            seen_link = '<span class="dim">（未定位）</span>'
        alias = '、'.join(t.get('aliases') or [])
        conf = t.get('conflicts') or []
        # 术语名 / English / 释义三列都用**富文本**渲染（保留公式标签）。
        # 术语表里写公式是常见做法（本套件自带 demo 的术语表里就有 9 处），
        # 用转义后的纯文本会让它们全变成〔公式〕。回退到 text 兼容旧索引。
        zh_html = t.get('zh_html') or e(t.get('zh') or '')
        en_html = t.get('en_html') or e(t.get('en') or '')
        def_html = t.get('def_html') or e(t.get('def') or '')
        name = '<b>%s</b>' % zh_html
        if not t.get('zh'):
            name = '<b class="dim">（缺中文名）</b>'
        note = ''
        if alias:
            note += '<br><span class="dim">别名：%s</span>' % e(alias)
        if conf:
            note += '<br><span class="dim">⚠ 各讲说法不一致：%s</span>' % e('；'.join(conf))
        # 「出现位置」超长时截断：术语出现在很多讲时全列会把格子撑成多行、行高不齐。
        # 截断为「首个位置 等 N 处」，全部位置挪进 title 悬停可见（课程 TODO T8②）。
        seen_list = t.get('seen') or []
        if len(seen_list) > SEEN_MAX:
            see_txt = '%s 等 %d 处' % (seen_list[0], len(seen_list))
            see_title = ' title="%s"' % e('全部 %d 处：%s' % (len(seen_list), '、'.join(seen_list)))
        else:
            see_txt = '、'.join(seen_list) or '—'
            see_title = ''
        rows.append(
            '<tr data-concept="%s"><td>%s<br><span class="mono dim">%s</span></td>'
            '<td>%s</td><td>%s%s</td><td>%s</td>'
            '<td class="see"%s>%s</td></tr>'
            % (e(t.get('id') or ''), name, e(t.get('id') or ''), en_html,
               def_html, note, seen_link,
               see_title, e(see_txt)))
    return ('<table class="tbl"><thead><tr>'
            '<th style="width:19%%">术语</th><th style="width:15%%">English</th><th>一句话定义</th>'
            '<th style="width:11%%">首见</th><th style="width:19%%">出现位置</th>'
            '</tr></thead><tbody>\n%s\n</tbody></table>' % '\n'.join(rows))


# ------------------------------------------------------------------ ⑤ 学习进度
def render_progress(lectures):
    """⑤ 区块的**静态骨架**：讲次行 + 学习进度占位格（运行期由 course.js 填）。

    学习进度（阅读位置 / 笔记数）存在用户浏览器里，生成期读不到 ——
    所以这里只出「讲次 + 空单元格」，`.lp-cell` 交给前端按 cdata.ns 渲染（§5.10）。
    写作进度（待补 N/M）只在这门课**还有没写完的讲**时逐行标注；
    全部写完时收敛为一行小字 —— 状态信息不再在「地图 / 要点 / 看板」三处重复
    （审查 B6 / 课程 TODO T7）。
    """
    if not lectures:
        return '<p class="dim">（这门课还没有登记任何讲次。）</p>'
    all_done = all((lec.get('status') == 'done') for lec in lectures)
    rows = []
    for lec in lectures:
        lid = lec.get('id') or '?'
        st = lec.get('status') or 'pending'
        title = lec.get('title') or ''
        cells = ['<td class="lp-lec"><b class="lid">%s</b>%s</td>'
                 % (e(lid), e(' ' + title if title else ''))]
        cells.append('<td class="lp-cell"><span class="dim">—</span></td>')
        if not all_done:
            note = {  # 用「已经发生的事实」说话，别写「请检查」这种没有指向的话
                'done': '要点与正文都齐了。',
                'partial': '还有 %d 页没写。' % pages_left(lec),
                'skeleton': '产物还没构建（跑 run_all.py）。',
                'pending': '讲次目录不存在。',
            }.get(st, '')
            num = ''
            if lec.get('page_count'):
                num = ' <span class="mono dim">%s / %s</span>' % (
                    e(lec.get('done_pages') or 0), e(lec['page_count']))
            cells.append('<td class="lp-write"><span class="badge %s">%s</span> %s%s</td>'
                         % (e(st), e(STATUS_LABEL.get(st, st)), e(note), num))
        rows.append('<tr data-lec="%s">%s</tr>' % (e(lid), ''.join(cells)))
    head = ('<th style="width:36%%">讲次</th><th>学习进度</th>'
            + ('' if all_done else '<th style="width:26%%">写作进度</th>'))
    tail = ('<p class="lp-foot dim">本课程讲解已全部写完（%d 讲）。阅读痕迹只存在本机浏览器里，'
            '打开任一讲阅读后上面的进度会自动出现。</p>' % len(lectures)) if all_done else ''
    return ('<div class="lp-top" id="lpTop"></div>'
            '<table class="tbl lp-tbl"><thead><tr>%s</tr></thead><tbody>\n%s\n</tbody></table>%s'
            % (head, '\n'.join(rows), tail))


# ------------------------------------------------------------------ 主流程
def load_payload(course_dir, course, index, max_text, full):
    """给前端检索用的内联数据。**只放检索真正需要的东西**，别把索引整个塞进来。"""
    lecs = []
    by_id = {x.get('id'): x for x in (index.get('lectures') or [])}
    for lec in (course.get('lectures') or []):
        ent = by_id.get(lec.get('id')) or {}
        href = href_of(lec, course_dir)
        pages = []
        for p in (ent.get('pages') or []):
            t = p.get('text') or ''
            pages.append({'id': p.get('id') or '', 'page': p.get('page') or '',
                          'title': p.get('title') or '',
                          'text': t if full else t[:max_text]})
        lecs.append({'id': lec.get('id'), 'title': lec.get('title') or '',
                     'status': lec.get('status') or '', 'href': href, 'pages': pages,
                     'ns': doc_ns_of(course_dir, lec),
                     'pageCount': lec.get('page_count') or 0})
    return {'maxText': max_text, 'full': bool(full), 'lectures': lecs}


def notice_of(max_text, full, size_note):
    if full:
        base = ('本页内联的是<b>每页全文</b>，所以可以在一个框里搜遍全课程。'
                '文件因此偏大，低配机器打开会慢一些。')
    else:
        base = ('本页内联的是<b>每页正文的前 %d 字</b>。' % max_text)
    return (base + ' <b>索引里的公式只留占位符</b>（LaTeX 源码塞进索引没法读），'
            '所以搜不到公式本身 —— 但要点表与术语总表里的公式是正常渲染的。'
            ' 换句话说：<b>找不到不等于没有</b> —— 精确全文搜索请打开对应讲次，'
            '用它自己的搜索框（那一份是全量的）。' + (size_note or ''))


def load_katex():
    """从 `vendor/katex/` 取离线 KaTeX（字体已转 data URI），返回 (css, js)。

    **为什么课程主页也要内联 KaTeX**：要点表与术语总表里带着各讲产物里的公式
    （`<script type="math/tex">`）。不内联的话，这些公式在主页上会显示成
    LaTeX 源码，或者更糟 —— 显示成抽取时留下的占位符〔公式〕。
    `html_text` 生成的那个占位符是给**检索索引**用的（把 LaTeX 塞进摘要是灾难），
    首页要显示的是 `html_rich` 保留下的公式标签，两者分工不同、不可互替。

    体积代价：css + js 约 630 KB。首页正文索引本身只有约 160 KB，
    加完仍远低于 SIZE_LIMIT（3 MB），且换来的是「断网也能看公式」。
    文件缺失时**降级而不是报错**：公式渲染不了，但正文照样读得到。
    """
    css = os.path.join(KATEX_DIR, 'katex.offline.css')
    js = os.path.join(KATEX_DIR, 'katex.min.js')
    missing = [f for f in (css, js) if not os.path.exists(f)]
    if missing:
        print('  [warn] 缺 vendor/katex/%s —— 课程主页的公式将不会渲染。'
              '先跑 scripts/katex_offline.py 生成。' % '、'.join(os.path.basename(f) for f in missing))
        return '', ''
    c = open(css, encoding='utf-8').read()
    j = open(js, encoding='utf-8').read()
    # 这里也要拦一道：katex.min.js 里理论上不该出现闭合标签，出现了就是内联会炸。
    _assert_no_script_end('katex.min.js', j)
    return c, j


# 内联 JS 的**闭合标签护栏**。
#
# 为什么要单独做这个检查：`__JS__` / `__KATEX_JS__` 是把整个 .js 文件原样塞进
# `<script>…</script>` 里的。只要文件里**任何位置**（包括注释、字符串字面量）
# 出现闭合标签，HTML 解析器就会把它当成 script 元素的结尾 —— 后面全部代码降级成
# 页面文本，整页交互报废，而生成期一切正常、只有浏览器里才看得出来。
#
# 2026-10-15 真实事故：course.js 的注释里为了举例写了字面的起止标签（说明公式标签
# 长什么样），内联后把脚本提前截断；同一个字符串还让「挖 script」的正则非贪婪匹配
# 从假标签起算、配对错位，害得静态体检误报「正文里有〔公式〕占位符」。
RE_SCRIPT_END_ANY = re.compile(r'</\s*script', re.I)
# 允许的写法：转义后的 `<\/script`（JS 里的合法等价写法）。
RE_SCRIPT_END_ESCAPED = re.compile(r'<\\/script|\\u003c/script|\\x3c/script', re.I)


def _assert_no_script_end(name, text):
    """内联 JS 里出现未转义的闭合标签就报错 —— 它会静默截断整页脚本。"""
    bare = RE_SCRIPT_END_ESCAPED.sub('', text)
    if RE_SCRIPT_END_ANY.search(bare):
        raise SystemExit(
            '%s 含未转义的脚本闭合标签（裸的 "<" + "/script"）—— '
            '内联进 <script> 会提前闭合它，整页脚本报废。\n'
            '    改法：注释/字符串里写成 "<" + "\\" + "/script" 这种拆开的形式，'
            '或者用 \\u003c 替代那个 "<"，干脆不写字面标签更好。' % name)


def check_no_script_end_in_assets():
    """生成前先扫一遍待内联的资产（shell 本身除外，它要的就是真标签）。"""
    for f in (CSS_F, JS_F):
        _assert_no_script_end(os.path.basename(f), open(f, encoding='utf-8').read())


def build(course_dir, course, index, glossary, keypoints, max_text, full, katex=('', '')):
    lec_by_id = {x.get('id'): x for x in (course.get('lectures') or [])}
    kp_by_id = {x.get('id'): x for x in ((keypoints or {}).get('lectures') or [])}
    lectures = course.get('lectures') or []

    nav = ' '.join('<a href="#%s">%s</a>' % (sid, e(label)) for sid, label in SECTIONS)
    n_pages = sum((x.get('page_count') or 0) for x in lectures)
    meta = ' · '.join([x for x in [
        course.get('instructor') or '', course.get('term') or '',
        '%d 讲' % len(lectures), '共 %d 页' % n_pages] if x])
    n_kp = sum(len((kp_by_id.get(x.get('id')) or {}).get('points') or []) for x in lectures)
    n_term = len((glossary or {}).get('terms') or [])

    payload = load_payload(course_dir, course, index, max_text, full)
    data_json = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    # `<` 必须转义：万一正文里出现字面 "</script"，内联标签会被提前截断、整页脚本报废。
    data_json = data_json.replace('<', '\\u003c')

    # 待内联的两个 JS/CSS 资产先过一遍闭合标签护栏（见 _assert_no_script_end 的说明）。
    check_no_script_end_in_assets()

    repl = {
        '__COURSE__': e(course.get('name') or '课程合集'),
        '__SUBTITLE__': e(' · '.join(x for x in [course.get('instructor') or '',
                                                course.get('term') or ''] if x)),
        '__SUMMARY__': e(course.get('summary') or '（本课程的目标简介还没写）'),
        '__META__': e(meta),
        '__NAV__': nav,
        '__MAP__': render_map(lectures, course_dir),
        '__KEYPOINTS__': render_keypoints(lectures, kp_by_id, course_dir),
        '__GLOSSARY__': render_glossary((glossary or {}).get('terms') or [], lec_by_id, course_dir),
        '__PROGRESS__': render_progress(lectures),
        '__NOTICE__': notice_of(max_text, full, ''),
        '__DATA__': data_json,
        '__KATEX_CSS__': katex[0],
        '__KATEX_JS__': katex[1],
        '__CSS__': open(CSS_F, encoding='utf-8').read(),
        '__JS__': open(JS_F, encoding='utf-8').read(),
        '__FOOT__': '本页只做索引与聚合，正文仍归各讲的产物文件 —— 点课程地图里的讲次即可打开。',
        '__GENERATED__': ('由 pdf-slides-annotated-html 的 course_site.py 生成 ｜ '
                          '%d 讲 · %d 页 · %d 条要点 · %d 个术语 ｜ 索引已内联，断网可用'
                          % (len(lectures), n_pages, n_kp, n_term)),
    }
    html = open(SHELL, encoding='utf-8').read()
    for k, v in repl.items():
        html = html.replace(k, v)
    left = [k for k in repl if k in html]
    if left:
        raise SystemExit('还有未替换的占位符: %s' % left)
    check_script_tags_balanced(html)
    return html


def check_script_tags_balanced(html):
    """生成后数一遍 script 起止标签，不配对就**当场报错**。

    为什么不靠上面那道资产级护栏、还要再数一次：资产级只看 .js/.css 文件，
    而截断也可能来自别处（比如某个渲染函数把带标签的正文拼进了 script 里，
    或者将来有人在 shell 里写错）。**成品自检**是最后一道、也是最接近真相的一道。

    判据刻意选得简单：`<script` 出现次数 == `</script` 出现次数。
    唯一合法的例外是课程索引那段 —— 它内联的是 JSON，生成时已把 `<` 转成 \\u003c，
    所以那里的公式标签不会以裸 `<` 出现，不影响计数。
    """
    n_open = len(re.findall(r'<script\b', html, re.I))
    n_close = len(re.findall(r'</script\s*>', html, re.I))
    if n_open != n_close:
        raise SystemExit(
            '生成的 index.html 里 script 标签不配对（%d 个开 / %d 个闭）—— '
            '多半是有内联的内容里出现了未转义的脚本闭合标签，浏览器会在此提前闭合脚本。\n'
            '    排查：注释或字符串里写了字面的起止标签，把那个 "<" 转义掉即可。'
            % (n_open, n_close))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('course_dir')
    ap.add_argument('--out', default=None, help='默认写 <课程目录>/index.html')
    ap.add_argument('--max-text', type=int, default=120,
                    help='默认模式内联每页正文的前 N 字（默认 120）')
    ap.add_argument('--full', action='store_true', help='内联每页全文（体积大，见下方闸门）')
    ap.add_argument('--force-full', action='store_true', help='体积超闸门时仍然生成')
    a = ap.parse_args()

    course_dir = os.path.abspath(a.course_dir)
    course = coursekit.read_json(os.path.join(course_dir, 'course.json'))
    if not isinstance(course, dict):
        raise SystemExit('读不到 course.json —— 先跑 course_init.py')
    index = coursekit.read_json(os.path.join(course_dir, '_course', 'index.json'))
    if not isinstance(index, dict):
        raise SystemExit('读不到 _course/index.json —— 先跑 course_index.py')
    glossary = coursekit.read_json(os.path.join(course_dir, '_course', 'glossary.json')) or {}
    keypoints = coursekit.read_json(os.path.join(course_dir, '_course', 'keypoints.json')) or {}

    lectures = course.get('lectures') or []
    n_lec, n_pages = len(lectures), sum((x.get('page_count') or 0) for x in lectures)

    # ---- 体积闸门：C3 的语义是「不许**无意中**造出巨型文件」，不是「不许用户自己选」 ----
    if a.full and not a.force_full:
        if n_lec > FULL_GATE[0] or n_pages > FULL_GATE[1]:
            raise SystemExit(
                '--full 在 %d 讲 / %d 页的规模上会产出几十 MB 的单文件，浏览器打开会明显卡。\n'
                '  这门课超过了闸门（%d 讲 / %d 页）。\n'
                '  确实要的话加 --force-full；否则用默认模式（每页前 %d 字）。'
                % (n_lec, n_pages, FULL_GATE[0], FULL_GATE[1], a.max_text))

    max_text = max(20, a.max_text)
    katex = load_katex()
    html = build(course_dir, course, index, glossary, keypoints, max_text, a.full, katex)
    size = len(html.encode('utf-8'))
    downgraded = False
    if not a.full and size > SIZE_LIMIT and max_text > MAX_TEXT_FLOOR:
        # 自动降级 + 明示。体积这种指标不该只靠估算守住（设计稿 §5.6）。
        max_text = MAX_TEXT_FLOOR
        html = build(course_dir, course, index, glossary, keypoints, max_text, a.full, katex)
        size = len(html.encode('utf-8'))
        downgraded = True

    out = os.path.abspath(a.out or os.path.join(course_dir, 'index.html'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)

    print('课程  : %s' % (course.get('name') or '(未命名)'))
    print('讲次  : %d（共 %d 页）' % (n_lec, n_pages))
    print('模式  : %s' % ('每页全文（--full）' if a.full else '每页前 %d 字' % max_text))
    if downgraded:
        print('        ⚠ 产物超过 %.1f MB，已自动把正文长度从 %d 字降到 %d 字'
              % (SIZE_LIMIT / 1048576.0, a.max_text, max_text))
    print('产物  : %s  (%.2f MB)' % (out, size / 1048576.0))
    print()
    print('下一步：')
    print('  python scripts/course_check.py "%s"      # 课程层体检' % course_dir)
    print('  或在浏览器里打开上面那个产物，确认五区块都对。')


if __name__ == '__main__':
    main()
