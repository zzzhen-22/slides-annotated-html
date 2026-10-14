#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""扫描各讲产物 → `_course/index.json`（+ `glossary.json` / `keypoints.json`）。

用法：
    python course_index.py <课程目录> [--force] [--quiet]

它做四件事：
    ① 逐讲读产物 HTML，抽出每个逐页区块的 id / 页码 / 标题 / 正文纯文本 / 三个 data-*
    ② 抽出每讲的「本讲要点」（#keypoints）与「术语表」（#glossary 里带 data-concept 的行）
    ③ 汇总成课程级的术语权威表（谁先引入、在哪几页出现过、各讲说法有没有冲突）
    ④ 把上面全部写进 `_course/`，并把可疑之处打成告警

**索引只从「产物 HTML」抽，不从 content/ 抽。** 理由：产物是最终交付物，索引与它一致才有意义；
从 content/ 抽会出现「索引里有、产物里没有」（比如某分片没被加进 config.shards）。

**增量**：按产物内容的 sha1 判断。哈希没变就复用上一次的抽取结果，不重新解析 ——
14 讲规模下重跑是毫秒级，所以「每加一讲跑一次」是零负担的。

**不写时间戳**：产物是给人 diff 的，带时间戳会让每次重跑都全文件变化。

设计稿：docs/v2-course-collection.md §3 / §5.4 / §5.8
"""
import argparse
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

MAX_PAGE_TEXT = 4000        # 单页正文的存储上限（防病态页把索引撑爆）
MAX_KEYPOINTS = 10          # 超过就告警：要点不是速查表（设计稿 §5.8）


def load_prev(path):
    """读上一次的 index.json，用于增量复用。读不到就当没有。"""
    d = coursekit.read_json(path)
    if not isinstance(d, dict):
        return {}
    return {x.get('id'): x for x in (d.get('lectures') or []) if isinstance(x, dict)}


def extract(course_dir, lec, prev, force):
    """抽一个讲次的产物。返回 (entry, warnings)。"""
    lid = lec.get('id') or '?'
    warn = []
    prod_rel = lec.get('product') or ''
    prod = os.path.join(course_dir, prod_rel) if prod_rel else ''
    entry = {
        'id': lid,
        'dir': lec.get('dir') or '',
        'title': lec.get('title') or '',
        'status': lec.get('status') or '',
        'page_count': lec.get('page_count') or 0,
        'done_pages': lec.get('done_pages') or 0,
        'product': prod_rel,
        'hash': '',
        'pages': [],
        'keypoints': [],
        'glossary': [],
    }
    if not prod or not os.path.exists(prod):
        return entry, warn

    h = coursekit.file_hash(prod)
    entry['hash'] = h
    old = prev.get(lid) or {}
    if not force and old.get('hash') == h:
        return old, warn                      # 增量命中：原样复用

    html = coursekit.read_text(prod) or ''

    pages = coursekit.page_entries(html)
    for p in pages:
        if len(p['text']) > MAX_PAGE_TEXT:
            p['text'] = p['text'][:MAX_PAGE_TEXT]
    entry['pages'] = pages

    entry['keypoints'] = coursekit.keypoint_entries(html)
    entry['glossary'] = coursekit.glossary_entries(html)

    # ---- 告警：都是「流水线全绿、但索引悄悄少东西」的那一类 ----
    if not entry['keypoints']:
        if lec.get('status') == 'done':
            warn.append('%s：没有「本讲要点」卡（#keypoints）—— 课程主页的要点总结页会缺这一讲' % lid)
    elif len(entry['keypoints']) > MAX_KEYPOINTS:
        warn.append('%s：本讲要点有 %d 条（建议 3–7）—— 超过 %d 条多半是在抄速查表'
                    % (lid, len(entry['keypoints']), MAX_KEYPOINTS))

    # 概念 id 写错、或属性挂错了位置（挂到 h3 / 内层 div 上是抽取不到的）
    used = set()
    for p in pages:
        used.update(p['concepts'])
        for bad in [c for c in p['concepts'] if not coursekit.RE_CONCEPT_ID.match(c)]:
            warn.append('%s:%s 的 data-concepts 有非法 id %r（只允许小写字母/数字/连字符）'
                        % (lid, p['id'], bad))
        for v in p['pays_off']:
            if not re.match(r'^[a-z0-9-]+@L\d+:p?\d+$', v):
                warn.append('%s:%s 的 data-pays-off 格式不对：%r（应为 概念id@L01:p77）'
                            % (lid, p['id'], v))
    if 'data-concepts' in coursekit.body_html(html) and not used:
        warn.append('%s：产物里出现了 data-concepts，但一个都没抽到 —— '
                    '属性可能挂错了位置（必须写在逐页区块的开标签上，不是 h3/内层 div）' % lid)

    declared = {g['id'] for g in entry['glossary']}
    for miss in sorted(used - declared):
        warn.append('%s：概念 %r 在页面上用了，但术语表里没有对应行（tr 缺 data-concept）'
                    % (lid, miss))
    for extra in sorted(declared - used):
        warn.append('%s：术语表里的 %r 没有任何页面声明它（页面的 data-concepts 漏了）'
                    % (lid, extra))
    return entry, warn


def build_glossary(entries, prev_glossary):
    """把各讲的术语表汇总成课程级权威表。

    · first / seen 由 data-concepts 的分布自动算，不手写
    · zh / en / def 取自各讲的术语表那一行；**多讲不一致时记进 conflicts**，
      由 course_check.py 报 FAIL（术语漂移是必须拦住的，否则同一概念两讲两个名字）
    · aliases 是唯一的手写字段，从上一版 glossary.json 里原样带过来
    """
    alias = {}
    for t in (prev_glossary.get('terms') or []):
        if isinstance(t, dict) and t.get('id'):
            alias[t['id']] = t.get('aliases') or []

    order, terms = [], {}
    for e in entries:
        lid = e['id']
        for g in e['glossary']:
            cid = g['id']
            if cid not in terms:
                terms[cid] = {'zh': [], 'en': [], 'def': [], 'seen': []}
                order.append(cid)
            t = terms[cid]
            for key in ('zh', 'en', 'def'):
                v = (g.get(key) or '').strip()
                if v and v not in t[key]:
                    t[key].append(v)
            for p in e['pages']:
                if cid in p['concepts']:
                    ref = '%s:%s' % (lid, p['id'])
                    if ref not in t['seen']:
                        t['seen'].append(ref)

    out = []
    for cid in order:
        t = terms[cid]
        conflicts = []
        for key, label in (('zh', '中文'), ('en', '英文'), ('def', '释义')):
            if len(t[key]) > 1:
                conflicts.append('%s：%s' % (label, ' ／ '.join(t[key])))
        out.append({
            'id': cid,
            'zh': t['zh'][0] if t['zh'] else '',
            'en': t['en'][0] if t['en'] else '',
            'def': t['def'][0] if t['def'] else '',
            'aliases': alias.get(cid, []),
            'first': t['seen'][0] if t['seen'] else '',
            'seen': t['seen'],
            'conflicts': conflicts,
        })
    return {'schema': 'glossary/v1', 'terms': out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('course_dir')
    ap.add_argument('--force', action='store_true', help='忽略增量缓存，全部重抽')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()

    course_dir = os.path.abspath(a.course_dir)
    cj = os.path.join(course_dir, 'course.json')
    course = coursekit.read_json(cj)
    if not isinstance(course, dict):
        raise SystemExit('读不到 %s —— 先跑 course_init.py' % cj)

    cdir = os.path.join(course_dir, '_course')
    os.makedirs(cdir, exist_ok=True)
    prev = load_prev(os.path.join(cdir, 'index.json'))
    prev_glossary = coursekit.read_json(os.path.join(cdir, 'glossary.json')) or {}

    entries, warns, reused, scanned = [], [], 0, 0
    for lec in (course.get('lectures') or []):
        e, w = extract(course_dir, lec, prev, a.force)
        if e.get('hash'):
            if e is prev.get(e['id']):
                reused += 1
            else:
                scanned += 1
        entries.append(e)
        warns += w

    # 课程级告警
    ids = [e['id'] for e in entries]
    if len(set(ids)) != len(ids):
        warns.append('讲次 id 有重复：%s' % ids)
    for e in entries:
        if e['status'] in ('done', 'partial') and e['page_count'] and e['done_pages'] < e['page_count']:
            warns.append('%s：还有 %d 页没写完（%d/%d）'
                         % (e['id'], e['page_count'] - e['done_pages'], e['done_pages'], e['page_count']))

    index = {
        'schema': 'index/v1',
        'course': course.get('name') or '',
        'lectures': entries,
        'stats': {
            'lectures': len(entries),
            'pages': sum(len(e['pages']) for e in entries),
            'concepts': len({g['id'] for e in entries for g in e['glossary']}),
            'keypoints': sum(len(e['keypoints']) for e in entries),
        },
    }
    glossary = build_glossary(entries, prev_glossary)
    keypoints = {
        'schema': 'keypoints/v1',
        'lectures': [{
            'id': e['id'], 'title': e['title'], 'status': e['status'],
            'page_count': e['page_count'], 'done_pages': e['done_pages'],
            'hash': e['hash'], 'points': e['keypoints'],
        } for e in entries],
    }

    def w(name, obj):
        p = os.path.join(cdir, name)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
        return p

    w('index.json', index)
    w('glossary.json', glossary)
    w('keypoints.json', keypoints)

    if not a.quiet:
        st = index['stats']
        print('课程  : %s' % (course.get('name') or '(未命名)'))
        print('讲次  : %d（本次重抽 %d / 复用缓存 %d）' % (st['lectures'], scanned, reused))
        print('规模  : %d 页 ｜ %d 个概念 ｜ %d 条要点' % (st['pages'], st['concepts'], st['keypoints']))
        print()
        print('%-5s %-9s %-7s %-7s %s' % ('id', '状态', '页', '要点', '概念'))
        print('-' * 66)
        for e in entries:
            print('%-5s %-9s %-7s %-7s %s' % (
                e['id'], e['status'], '%d/%d' % (e['done_pages'], e['page_count']) if e['page_count'] else '—',
                len(e['keypoints']) or '—', len(e['glossary']) or '—'))
        print()
        print('写入  : _course/index.json / glossary.json / keypoints.json')
        conf = [t for t in glossary['terms'] if t['conflicts']]
        if conf:
            print()
            print('术语冲突（同一概念在不同讲里说法不一致，course_check.py 会判 FAIL）：')
            for t in conf[:8]:
                print('  · %s：%s' % (t['id'], '；'.join(t['conflicts'])))
        if warns:
            print()
            print('告警 %d 条：' % len(warns))
            for x in warns[:20]:
                print('  · %s' % x)
            if len(warns) > 20:
                print('  …… 还有 %d 条' % (len(warns) - 20))
        if not warns:
            print()
            print('告警：无。')


if __name__ == '__main__':
    main()
