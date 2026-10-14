#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""产出某一讲的「前序知识简报」`_course/briefing-LNN.md`（A 侧的核心）。

用法：
    python course_brief.py <课程目录> --for L07 [--out 路径] [--threshold 0.34]

它是**给 agent 读的**（不是给人看的排版稿），固定五节：

    ① 前序讲次地图   每讲的标题、页数、语义段名 + 页码区间
    ② 术语权威表     已被前序讲次确立的 中/英/别名/首见位置 —— **必须沿用，不许新造译名**
    ③ 概念落点索引   「这个概念在前序哪讲的哪一页展开过」
    ④ 已讲预警       本讲大纲的每个语义段，与前序讲次哪一段高度重合（**带分数**）
    ⑤ 待回收的伏笔   前序讲次里标了 data-forward、至今没人 data-pays-off 的开放问题

为什么是 markdown 不是 JSON：agent 读 markdown 更省 token、也更不容易误读结构；
机器消费的部分（术语、落点）已经在 `_course/*.json` 里了。

────────────────────────── 关于第 ④ 节的分数 ──────────────────────────
**阈值刻意没有拍板。** 分数用「中文双字组 + 英文词」的 Jaccard 词面重合度算，
不用嵌入模型（那会引入依赖、还可能联网，违反「零依赖、可断网」的硬约束）。

但中文的 Jaccard 分布与英文差别很大，凭空定一个 0.34 很容易落到
「要么全亮、要么全不亮」—— 那就是「一个会误报的体检比没有体检更糟」。
所以本脚本**无论阈值多少，都把 top-N 的分数打出来**，让人在真实课程上先看几条，
再把 `--threshold` 定死。默认 0.34 只是占位，**不要当成已校准的值**。

还有一条纪律：**预警是提示，不是禁令。** 简报里写的是「前序已详述，建议回顾一句 + 指路」，
不是「禁止展开」—— 本讲确实需要换个角度重讲时，照写，只是别假装前序没讲过。
"""
import argparse
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import coursekit  # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# 拆词用的停用字：只用来丢掉「整段都是虚词」的双字组，不做真正的分词
STOP = set('的了和与及在是有对为以之等这那我你他它们个中上下前后则就都也很'
           '一二三四五六七八九十一页页第节讲章并其此由从到把被让给可会能要')


def tokens(s):
    """把一句话拆成可比较的词集合。

    中文没有空格，用**双字组**代替分词（不引入 jieba 之类依赖）：
    「残差连接」→ {残差, 差连, 连接}。英文按词切。整段是虚词的双字组丢掉。
    """
    s = unicodedata.normalize('NFKC', str(s or '')).lower()
    out = set(re.findall(r'[a-z][a-z0-9_-]{1,}', s))
    for run in re.findall(r'[\u4e00-\u9fff]+', s):
        if len(run) == 1:
            out.add(run)
        for i in range(len(run) - 1):
            g = run[i:i + 2]
            if not all(c in STOP for c in g):
                out.add(g)
    return out


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def read_outline(course_dir, lec):
    """读某讲的 _plan/outline.json（拿语义段名与页码区间）。没有就返回 None。"""
    rel = lec.get('outline') or ''
    if rel:
        d = coursekit.read_json(os.path.join(course_dir, rel))
        if isinstance(d, dict):
            return d
    # 兜底：按约定路径找
    d = coursekit.read_json(os.path.join(course_dir, lec.get('dir') or '', '_plan', 'outline.json'))
    return d if isinstance(d, dict) else None


# outline 里人填的 toc_label 按约定是「N · 段名（P起–P止）」，**页码已经含在里面**。
# 本脚本展示时要自己拼一次页码，比对时更要把页码剔掉 —— 否则：
#   ① 显示成「朴素贝叶斯分类器（P5–P8）（P5–P8）」（pitfalls 第 10 条的原症状）
#   ② 页码数字进词袋，让两段「页码区间相同但内容无关」的段白得相似度
RE_RANGE_PAREN = re.compile(r'\s*[（(]\s*P?\d+\s*[–—\-~至到]+\s*P?\d+\s*[）)]\s*$')
RE_RANGE_BARE = re.compile(r'\s*P\d+\s*[–—\-~]+\s*P?\d+\s*$')
# 开头的「一 · 」「1. 」「（三）」这类编号也剔掉：编号是结构顺序，不是内容
RE_LEAD_NUM = re.compile(r'^\s*(?:[（(]?\s*(?:\d+|[一二三四五六七八九十]+)\s*[）)]?\s*[·.、:：]\s*)+')


def strip_range(s):
    """去掉段名里已经写着的页码区间与开头编号，只留语义部分。"""
    s = coursekit._clean_soft(s)
    for _ in range(2):                       # 可能同时有「编号 + 区间」
        s2 = RE_RANGE_PAREN.sub('', s)
        s2 = RE_RANGE_BARE.sub('', s2)
        if s2 == s:
            break
        s = s2
    return RE_LEAD_NUM.sub('', s).strip()


def sections_of(outline):
    """从一个 outline 里取 [(段名, 起页, 止页, 页标题表)]。

    段名只留语义部分（见 strip_range）：页码由调用方拼，**只拼一次**。
    """
    out = []
    for s in (outline or {}).get('sections') or []:
        pages = s.get('pages') or []
        if not pages:
            continue
        raw = s.get('toc_label') or s.get('name') or ''
        out.append((strip_range(raw) or '(未命名)', min(pages), max(pages),
                    s.get('page_titles') or {}))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('course_dir')
    ap.add_argument('--for', dest='for_id', required=True, help='为哪一讲写简报，如 L07')
    ap.add_argument('--out', default=None, help='默认写 <课程目录>/_course/briefing-<id>.md')
    ap.add_argument('--threshold', type=float, default=0.34,
                    help='已讲预警的阈值（**占位值，先在真实课程上看分数再定**）')
    ap.add_argument('--top', type=int, default=8, help='第 ④ 节无论如何都列出前 N 对，便于校准阈值')
    a = ap.parse_args()

    course_dir = os.path.abspath(a.course_dir)
    course = coursekit.read_json(os.path.join(course_dir, 'course.json'))
    if not isinstance(course, dict):
        raise SystemExit('读不到 course.json —— 先跑 course_init.py')
    index = coursekit.read_json(os.path.join(course_dir, '_course', 'index.json'))
    if not isinstance(index, dict):
        raise SystemExit('读不到 _course/index.json —— 先跑 course_index.py')
    glossary = coursekit.read_json(os.path.join(course_dir, '_course', 'glossary.json')) or {}

    lecs = course.get('lectures') or []
    ids = [x.get('id') for x in lecs]
    if a.for_id not in ids:
        raise SystemExit('course.json 里没有讲次 %s（现有：%s）' % (a.for_id, '、'.join(ids)))
    pos = ids.index(a.for_id)
    prior, cur = lecs[:pos], lecs[pos]
    lname = {x.get('id'): (x.get('title') or '') for x in lecs}

    if not prior:
        print('提示：%s 是第一讲，没有前序知识可关联 —— 简报会是一份空壳。' % a.for_id)

    by_id = {e.get('id'): e for e in (index.get('lectures') or [])}
    cur_entry = by_id.get(a.for_id) or {}

    L = []
    L.append('# 前序知识简报 · %s（%s）' % (a.for_id, lname.get(a.for_id, '')))
    L.append('')
    L.append('> 这份文件是**给写讲解的 agent 读的**，不是给人看的排版稿。')
    L.append('> 写 %s 的讲解之前先读它，再动笔。' % a.for_id)
    L.append('>')
    L.append('> 三条纪律：**术语必须沿用**（第 ② 节给什么就用什么，不许新造译名）；')
    L.append('> **第 ④ 节的预警是提示不是禁令**（前序讲透的地方，回顾一句 + 指路即可，')
    L.append('> 确实需要换角度重讲就重讲，只是别假装前序没讲过）；')
    L.append('> **本讲首次引入的概念，要在本讲术语表补一行并加 data-concept**。')
    L.append('')

    # ---------------------------------------------- ① 前序讲次地图
    L.append('## ① 前序讲次地图')
    L.append('')
    if not prior:
        L.append('（本讲是第一讲，无前序。）')
    else:
        L.append('| 讲次 | 标题 | 页数 | 状态 | 语义段 |')
        L.append('|---|---|---|---|---|')
        for x in prior:
            ol = read_outline(course_dir, x)
            secs = sections_of(ol)
            desc = '；'.join('%s（P%d–P%d）' % (n or '(未命名)', s, e)
                             for n, s, e, _ in secs) or '（还没有 outline.json）'
            L.append('| %s | %s | %s | %s | %s |' % (
                x.get('id'), x.get('title') or '', x.get('page_count') or '—',
                x.get('status') or '', desc))
    L.append('')
    L.append('本讲大纲：')
    ol_cur = read_outline(course_dir, cur)
    secs_cur = sections_of(ol_cur)
    if secs_cur:
        for n, s, e, _ in secs_cur:
            L.append('- **%s**（P%d–P%d）' % (n or '(未命名)', s, e))
    else:
        L.append('- （还没有 `_plan/outline.json` —— 第 ④ 节的预警要等大纲定了才能算）')
    L.append('')

    # ---------------------------------------------- ② 术语权威表
    L.append('## ② 术语权威表（**必须沿用**）')
    L.append('')
    prior_ids = {x.get('id') for x in prior}
    terms = [t for t in (glossary.get('terms') or [])
             if (t.get('first') or '').split(':')[0] in prior_ids]
    if not terms:
        L.append('（前序讲次还没有确立任何术语。若本讲首次引入概念，记得在本讲术语表补一行。）')
    else:
        L.append('| 术语 | English | 一句话定义 | 首见 | 别名（历史说法） |')
        L.append('|---|---|---|---|---|')
        for t in terms:
            L.append('| %s | %s | %s | %s | %s |' % (
                t.get('zh') or '**(待补)**', t.get('en') or '',
                t.get('def') or '', t.get('first') or '',
                '、'.join(t.get('aliases') or [])))
        L.append('')
        L.append('> 上表里 `**(待补)**` 表示那一讲写术语表时漏了中文名 —— 本讲沿用时要补上，')
        L.append('> 并回头修那一讲的 `#glossary`（那里才是真源）。')
    L.append('')

    # ---------------------------------------------- ③ 概念落点索引
    L.append('## ③ 概念落点索引（前序在哪讲的哪一页展开过）')
    L.append('')
    if not terms:
        L.append('（无。）')
    else:
        for t in terms:
            seen = [s for s in (t.get('seen') or []) if s.split(':')[0] in prior_ids]
            if not seen:
                continue
            L.append('- **%s**（%s）：%s' % (t.get('zh') or t.get('id'), t.get('id'),
                                        '、'.join(seen)))
    L.append('')

    # ---------------------------------------------- ④ 已讲预警（带分数）
    L.append('## ④ 本讲大纲的「已讲预警」')
    L.append('')
    pairs = []
    prior_secs = []
    for x in prior:
        ol = read_outline(course_dir, x)
        for n, s, e, pt in sections_of(ol):
            # 段的词袋 = 段名 + 该段内所有页标题（页标题常常比段名更具体）
            bag = tokens(n)
            for v in pt.values():
                bag |= tokens(v)
            prior_secs.append((x.get('id'), n, s, e, bag))
    for n, s, e, pt in secs_cur:
        bag = tokens(n)
        for v in pt.values():
            bag |= tokens(v)
        for pid, pn, ps, pe, pbag in prior_secs:
            sc = jaccard(bag, pbag)
            if sc > 0:
                pairs.append((sc, n, s, e, pid, pn, ps, pe))
    pairs.sort(reverse=True, key=lambda x: x[0])

    if not secs_cur:
        L.append('（本讲还没有 outline.json，无法比对。）')
    elif not pairs:
        L.append('（没有检测到与前序讲次重合的段落 —— 都可能是新内容。）')
    else:
        hit = [p for p in pairs if p[0] >= a.threshold]
        L.append('阈值 `%.2f` 下命中 **%d** 处 —— 该阈值是**占位值，尚未校准**，'
                 '请对照下方「前 %d 对」的实际分数再定。' % (a.threshold, len(hit), a.top))
        L.append('')
        if hit:
            for sc, n, s, e, pid, pn, ps, pe in hit:
                L.append('- ⚠ 本讲「**%s**」（P%d–P%d）与 %s「%s」（P%d–P%d）高度重合（%.2f）'
                         % (n, s, e, pid, pn, ps, pe, sc))
                L.append('  → 建议写法：回顾一句 + 指路（「这一点 %s P%d–P%d 已讲过，'
                         '这里只补 XXX」），不要重新展开。' % (pid, ps, pe))
        else:
            L.append('（阈值为 %d 时无命中 —— 见下方「前 %d 对」的实际分数，据此调 `--threshold`。）'
                     % (a.threshold, a.top))
        L.append('')
        L.append('<details><summary>前 %d 对的分数（用来校准阈值，写讲解时不必细看）</summary>' % a.top)
        L.append('')
        L.append('| 分数 | 本讲段 | 前序段 |')
        L.append('|---|---|---|')
        for sc, n, s, e, pid, pn, ps, pe in pairs[:a.top]:
            L.append('| %.3f | %s（P%d–P%d） | %s · %s（P%d–P%d） |'
                     % (sc, n, s, e, pid, pn, ps, pe))
        L.append('')
        L.append('</details>')
    L.append('')

    # ---------------------------------------------- ⑤ 待回收的伏笔
    L.append('## ⑤ 待回收的伏笔（前序埋的、至今没人认领）')
    L.append('')
    claimed = set()
    for e in (index.get('lectures') or []):
        for p in (e.get('pages') or []):
            for v in (p.get('pays_off') or []):
                claimed.add(v)
    open_forwards = []
    for e in (index.get('lectures') or []):
        if e.get('id') not in prior_ids:
            continue
        for p in (e.get('pages') or []):
            for f in (p.get('forward') or []):
                key = '%s@%s:%s' % (f, e.get('id'), p.get('id'))
                if key in claimed:
                    continue
                open_forwards.append((e.get('id'), p.get('id'), f, key))
    zh = {t.get('id'): (t.get('zh') or '') for t in (glossary.get('terms') or [])}
    if not open_forwards:
        L.append('（前序没有留下未回收的伏笔 —— 要么没写 data-forward，要么都回收了。）')
    else:
        cur_bag = set()
        for n, s, e, pt in secs_cur:
            cur_bag |= tokens(n)
            for v in pt.values():
                cur_bag |= tokens(v)
        for lid, pid, f, key in open_forwards:
            name = zh.get(f) or ''
            rel = ''
            if tokens(f) & cur_bag or (name and tokens(name) & cur_bag):
                rel = '  ⭐ **与本讲大纲有交集，优先考虑在本讲回收**'
            L.append('- `%s`（%s%s）— 埋于 %s:%s%s'
                     % (f, name, '/' if name else '', lid, pid, rel))
        L.append('')
        L.append('> 在本讲回收时：给对应页加 `data-pays-off="%s"`，'
                 '并在正文里显式写「这一页回答了 %s %s 留下的问题」。'
                 % (open_forwards[0][3], open_forwards[0][0], open_forwards[0][1]))
    L.append('')

    # ---------------------------------------------- 新鲜度
    L.append('---')
    L.append('')
    L.append('## 附：本简报依据的产物版本（用来判断它是否过期）')
    L.append('')
    L.append('| 讲次 | 产物哈希 |')
    L.append('|---|---|')
    for x in prior + [cur]:
        e = by_id.get(x.get('id')) or {}
        L.append('| %s | `%s` |' % (x.get('id'), e.get('hash') or '(无产物)'))
    L.append('')
    L.append('若某讲的哈希变了，重跑 `course_index.py` 与 `course_brief.py` 再动笔。')

    text = '\n'.join(L) + '\n'
    out = a.out or os.path.join(course_dir, '_course', 'briefing-%s.md' % a.for_id)
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(text)

    print('简报已写入: %s' % out)
    print('  前序讲次 %d 个 ｜ 术语 %d 条 ｜ 候选重合对 %d 个（阈值 %.2f 命中 %d）'
          % (len(prior), len(terms), len(pairs), a.threshold,
             len([p for p in pairs if p[0] >= a.threshold])))
    print('  未回收伏笔 %d 条' % len(open_forwards))
    print()
    print('下一步：读这份简报，再动笔写 %s 的讲解。' % a.for_id)


if __name__ == '__main__':
    main()
