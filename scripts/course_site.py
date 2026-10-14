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
    ⑤ 进度看板   每讲写到第几页

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

SECTIONS = [('map', '课程地图'), ('keypoints', '要点总结'), ('search', '跨讲检索'),
            ('glossary', '术语总表'), ('progress', '进度看板')]
STATUS_LABEL = {'done': '已完成', 'partial': '部分完成', 'skeleton': '骨架', 'pending': '待建'}

SIZE_LIMIT = 3 * 1024 * 1024      # 超过就自动降级正文长度（设计稿 §5.6）
MAX_TEXT_FLOOR = 60
FULL_GATE = (8, 400)              # --full 的闸门：讲次数 / 总页数（设计稿 §8 阶段 4）


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


# ------------------------------------------------------------------ ① 课程地图
def render_map(lectures, course_dir):
    out = []
    for lec in lectures:
        lid = lec.get('id') or '?'
        st = lec.get('status') or 'pending'
        title = lec.get('title') or lid
        href = href_of(lec, course_dir)
        topics = ' '.join('#' + t for t in (lec.get('topics') or []))
        meta = []
        if lec.get('page_count'):
            meta.append('%s 页' % lec['page_count'])
        meta.append(STATUS_LABEL.get(st, st))
        if href:
            name = '<a class="ltitle" href="%s">%s</a>' % (e(href), e(title))
        else:
            name = '<span class="ltitle dim" title="这一讲还没有产物可打开">%s</span>' % e(title)
        out.append(
            '<div class="lec" data-lec="%s">'
            '<span class="lid">%s</span>%s'
            '<span class="badge %s">%s</span>'
            '<span class="ltopics">%s</span>'
            '<span class="lmeta">%s</span>'
            '</div>' % (e(lid), e(lid), name, e(st), e(STATUS_LABEL.get(st, st)),
                        e(topics), e(' · '.join(meta))))
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
        head = ('<summary>%s · %s <span class="badge %s">%s</span>'
                '<span class="kmeta">%s</span></summary>'
                % (e(lid), e(title), e(st), e(STATUS_LABEL.get(st, st)),
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
                rows.append('<li>%s%s</li>' % (e(p.get('text') or ''), extra))
            body = '<ol class="kpl">\n%s\n</ol>' % '\n'.join(rows)
        else:
            # **未写完的讲次要显式占位，绝不静默省略** —— 空白会让人以为遗漏了，
            # 而「还没写」正是必须一眼看出来的信息（设计稿 §5.2）。
            if st == 'pending':
                why = '本讲还没有目录 —— 在 course_init.py 里登记后再同步。'
            elif st == 'skeleton':
                why = '本讲还没构建产物 —— 跑 run_all.py 生成 HTML 后重跑课程同步。'
            elif st == 'partial':
                why = '本讲还有 %d 页没写完，要点待补。' % max(
                    0, (lec.get('page_count') or 0) - (lec.get('done_pages') or 0))
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
        name = '<b>%s</b>' % e(t.get('zh') or '?')
        if not t.get('zh'):
            name = '<b class="dim">（缺中文名）</b>'
        note = ''
        if alias:
            note += '<br><span class="dim">别名：%s</span>' % e(alias)
        if conf:
            note += '<br><span class="dim">⚠ 各讲说法不一致：%s</span>' % e('；'.join(conf))
        rows.append(
            '<tr data-concept="%s"><td>%s<br><span class="mono dim">%s</span></td>'
            '<td>%s</td><td>%s%s</td><td>%s</td>'
            '<td class="see">%s</td></tr>'
            % (e(t.get('id') or ''), name, e(t.get('id') or ''), e(t.get('en') or ''),
               e(t.get('def') or ''), note, seen_link,
               e('、'.join(t.get('seen') or []) or '—')))
    return ('<table class="tbl"><thead><tr>'
            '<th style="width:19%%">术语</th><th style="width:15%%">English</th><th>一句话定义</th>'
            '<th style="width:11%%">首见</th><th style="width:19%%">出现位置</th>'
            '</tr></thead><tbody>\n%s\n</tbody></table>' % '\n'.join(rows))


# ------------------------------------------------------------------ ⑤ 进度看板
def render_progress(lectures, index_by_id):
    rows = []
    for lec in lectures:
        lid = lec.get('id') or '?'
        st = lec.get('status') or 'pending'
        pc = lec.get('page_count') or 0
        done = lec.get('done_pages') or 0
        pct = int(round(done * 100.0 / pc)) if pc else 0
        cls = 'pbar' + (' warn' if 0 < pct < 100 else (' none' if not pc else ''))
        note = {  # 用「已经发生的事实」说话，别写「请检查」这种没有指向的话
            'done': '要点与正文都齐了。',
            'partial': '还有 %d 页没写。' % max(0, pc - done),
            'skeleton': '产物还没构建（跑 run_all.py）。',
            'pending': '讲次目录不存在。',
        }.get(st, '')
        rows.append('<tr data-lec="%s"><td>%s · %s</td>'
                    '<td><span class="%s"><i style="width:%d%%"></i></span>'
                    '<span class="mono">%s / %s</span></td>'
                    '<td><span class="badge %s">%s</span></td><td>%s</td></tr>'
                    % (e(lid), e(lid), e(lec.get('title') or ''), cls, pct,
                       e(done), e(pc or '—'), e(st), e(STATUS_LABEL.get(st, st)), e(note)))
    if not rows:
        return '<p class="dim">（这门课还没有登记任何讲次。）</p>'
    return ('<table class="tbl"><thead><tr><th style="width:30%%">讲次</th>'
            '<th style="width:30%%">进度</th><th style="width:12%%">状态</th><th>说明</th>'
            '</tr></thead><tbody>\n%s\n</tbody></table>' % '\n'.join(rows))


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
                     'status': lec.get('status') or '', 'href': href, 'pages': pages})
    return {'maxText': max_text, 'full': bool(full), 'lectures': lecs}


def notice_of(max_text, full, size_note):
    if full:
        base = ('本页内联的是<b>每页全文</b>，所以可以在一个框里搜遍全课程。'
                '文件因此偏大，低配机器打开会慢一些。')
    else:
        base = ('本页内联的是<b>每页正文的前 %d 字</b>，且公式只保留占位符、不参与检索。' % max_text)
    return (base + ' 换句话说：<b>找不到不等于没有</b> —— 精确全文搜索请打开对应讲次，'
            '用它自己的搜索框（那一份是全量的）。' + (size_note or ''))


def build(course_dir, course, index, glossary, keypoints, max_text, full):
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

    repl = {
        '__COURSE__': e(course.get('name') or '课程合集'),
        '__SUBTITLE__': e(' · '.join(x for x in [course.get('instructor') or '',
                                                course.get('term') or ''] if x)),
        '__SUMMARY__': e(course.get('summary') or '（还没写课程目标：course.json 的 summary）'),
        '__META__': e(meta),
        '__NAV__': nav,
        '__MAP__': render_map(lectures, course_dir),
        '__KEYPOINTS__': render_keypoints(lectures, kp_by_id, course_dir),
        '__GLOSSARY__': render_glossary((glossary or {}).get('terms') or [], lec_by_id, course_dir),
        '__PROGRESS__': render_progress(lectures, None),
        '__NOTICE__': notice_of(max_text, full, ''),
        '__DATA__': data_json,
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
    return html


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
    html = build(course_dir, course, index, glossary, keypoints, max_text, a.full)
    size = len(html.encode('utf-8'))
    downgraded = False
    if not a.full and size > SIZE_LIMIT and max_text > MAX_TEXT_FLOOR:
        # 自动降级 + 明示。体积这种指标不该只靠估算守住（设计稿 §5.6）。
        max_text = MAX_TEXT_FLOOR
        html = build(course_dir, course, index, glossary, keypoints, max_text, a.full)
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
