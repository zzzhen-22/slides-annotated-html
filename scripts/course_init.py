#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""初始化 / 更新一门课的 `course.json` 与 `_course/`（v2「多课件课程合集」的阶段 0）。

用法：
    python course_init.py <课程目录> [--name "课程名"] [--dir 讲次目录]...
                          [--instructor X] [--term Y] [--summary Z]
                          [--dry-run]

三种典型用法：
    # ① 第一次：让脚本自己去课程目录里找讲次（目录下含 config.json 的子目录）
    python course_init.py D:/课程/深度学习 --name "清华大学 · 深度学习"

    # ② 讲次目录不在课程目录里，或想指定顺序：显式给 --dir（可重复）
    python course_init.py D:/课程/深度学习 --name "…" --dir lecture-01-why-dl --dir lecture-02-cnn

    # ③ 写完一讲之后：再跑一次，状态与页数自动刷新（幂等，不覆盖手写字段）
    python course_init.py D:/课程/深度学习

────────────────────────────────────────────────────────────────────────
设计原则（照着 v1 的 check_docs.py「单一真源」那套来）：

**派生得出来的字段就不要手写。** 讲次的 title / page_count / 产物路径 / 状态，全部能从
该讲自己的 `config.json` 与 `_plan/outline.json` 推出来。course.json 只留两张手写的东西：
课程名/教师/学期/课程目标，以及讲次目录列表。

**写两遍必然漂移** —— 这正是 v1 的 check_docs.py 第 43 条要治的病：同一个事实抄在多个
文件里，改一处忘一处。所以每次跑本脚本，派生字段一律**重新算、直接覆盖**；
手写字段一律**原样保留**。由此得到：

    · 讲次标题想改 → 改那一讲的 outline/config，不要改 course.json（改了也会被覆盖）
    · 讲次顺序想改 → 改 --dir 的给法，或删掉 course.json 重建

**幂等**：连跑两遍，输出逐字节一致（`created` 只在首建时写一次，状态是静态扫描出来的）。

**状态判定不依赖浏览器**：见 coursekit.lecture_status 的说明。这里是「课程地图」的地基，
不能押在会静默失灵的浏览器探针上（pitfalls 第 29 条）。
"""
import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import coursekit  # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

SCHEMA = 'course/v1'
STATUS_LABEL = {
    'pending':  '待建',
    'skeleton': '骨架',
    'partial':  '未写完',
    'done':     '已完成',
}


# ------------------------------------------------------------------ 扫描讲次
def find_lecture_dirs(course_dir, explicit, recorded):
    """决定这门课有哪些讲次目录。

    三种情况：
      · 给了 --dir      → **就是这些**（顺序即课程顺序）。这是「我要重排/裁剪」的明确表态。
      · 没给 --dir      → **已记录的 + 新扫到的**，合并去重。
        为什么不是「只扫」：讲次 id 是外键（glossary / index.json / briefing 到处在引用它），
        目录一旦被改名，纯扫描会让它换一个 id，全身断链；合并则把它留成 `pending` 并告警，
        让人自己决定是改回来还是重排。宁可留下一条显眼的告警，也不要静默换 id。
      · 扫不到任何目录 → 报错（见调用方），别写一份空课程覆盖掉原有记录。

    扫描的判据：子目录里有 `config.json`（init_project.py 的产物标志）。
    自然排序，保证 lecture-2 排在 lecture-10 前面。
    """
    if explicit:
        return list(dict.fromkeys(explicit))          # 去重且保序
    found = []
    if os.path.isdir(course_dir):
        for name in sorted(os.listdir(course_dir), key=coursekit.natural_key):
            d = os.path.join(course_dir, name)
            if os.path.isdir(d) and os.path.exists(os.path.join(d, 'config.json')):
                found.append(name)
    if not found:
        return list(recorded)                          # 扫不到就保留原记录（可能是路径写错了）
    out = list(recorded)
    for name in found:
        if name not in out:
            out.append(name)
    return out


def assign_ids(old_lectures, dirs):
    """给每个讲次目录分配稳定 id（L01…）。

    已存在的按 dir 复用（**不许重排** —— 讲次 id 是 glossary/briefing/index.json
    里到处在引用的外键，重排一次全身断链）；新目录取下一个空闲编号。
    """
    by_dir = {}
    used = set()
    for lec in old_lectures:
        d = lec.get('dir') or ''
        i = lec.get('id') or ''
        if d and i and i not in used:
            by_dir[d] = i
            used.add(i)
    out = {}
    n = 0
    for d in dirs:
        if d in by_dir:
            out[d] = by_dir[d]
            continue
        while True:
            n += 1
            cand = 'L%02d' % n
            if cand not in used:
                break
        used.add(cand)
        out[d] = cand
    return out


# ------------------------------------------------------------------ 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('course_dir', help='课程目录（讲次的父目录；也是产物 index.html 的落点）')
    ap.add_argument('--name', default=None, help='课程名。首次建 course.json 时必需')
    ap.add_argument('--dir', action='append', default=None,
                    help='讲次目录（相对课程目录；可重复）。不给则自动扫描')
    ap.add_argument('--instructor', default=None)
    ap.add_argument('--term', default=None)
    ap.add_argument('--summary', default=None, help='课程目标一句话（课程页顶部展示）')
    ap.add_argument('--dry-run', action='store_true', help='只打印将要写什么，不落盘')
    a = ap.parse_args()

    course_dir = os.path.abspath(a.course_dir)
    os.makedirs(course_dir, exist_ok=True)
    course_json = os.path.join(course_dir, 'course.json')

    old = coursekit.read_json(course_json)
    if old is None and os.path.exists(course_json):
        raise SystemExit('course.json 存在但不是合法 JSON，先修好它：%s' % course_json)
    old = old or {}
    old_lectures = old.get('lectures') or []

    dirs = find_lecture_dirs(course_dir, a.dir, [x.get('dir') for x in old_lectures if x.get('dir')])
    if not dirs:
        raise SystemExit(
            '在 %s 下没找到任何讲次目录。\n'
            '  讲次目录的标志是「目录里有 config.json」（由 init_project.py 生成）。\n'
            '  讲次在别处时用 --dir 显式指定。' % course_dir)

    missing = [d for d in dirs if not os.path.isdir(os.path.join(course_dir, d))]
    ids = assign_ids(old_lectures, dirs)

    # 课程名：显式 > 已有 course.json > 从讲次 config/outline 里捞
    name = a.name or old.get('name') or coursekit.course_name_hint(course_dir, dirs)

    print('课程目录: %s' % course_dir)
    print('讲次数  : %d（%s）' % (len(dirs), '、'.join(dirs)))
    print()
    print('%-5s %-26s %-7s %-8s %s' % ('id', 'dir', '页数', '状态', '标题'))
    print('-' * 96)

    lectures = []
    unknowns = []
    for d in dirs:
        lec_dir = os.path.join(course_dir, d)
        m = coursekit.lecture_meta(lec_dir, course_dir)
        lid = ids[d]
        row = {
            'id': lid,
            'dir': d,
            'title': m['title'],
            'pdf': m['pdf'],
            'page_count': m['page_count'],
            'status': m['status'],
            'done_pages': m['done_pages'],
            'topics': [],
            'outline': m['outline'],
            'product': m['product'],
        }
        # 手写字段：原样保留（topics 是给人分类用的，派生不出来）
        prev = next((x for x in old_lectures if (x.get('dir') or '') == d), None)
        if prev is not None and isinstance(prev.get('topics'), list):
            row['topics'] = prev['topics']
        lectures.append(row)

        print('%-5s %-26s %-7s %-8s %s' % (
            lid, d[:26], m['page_count'] or '—',
            STATUS_LABEL.get(m['status'], m['status']), m['title'][:40]))
        if m['status'] == 'pending':
            unknowns.append('%s：目录不存在' % lid)
        elif m['status'] == 'skeleton':
            if not m['product']:
                unknowns.append('%s：config.json 里没有 out，推不出产物路径' % lid)
            else:
                unknowns.append('%s：产物 HTML 还没构建（跑 run_all.py）' % lid)
        if not m['outline'] or not os.path.exists(os.path.join(course_dir, m['outline'])):
            unknowns.append('%s：还没有 _plan/outline.json' % lid)
        if m['product'].startswith('..'):
            # 产物落在课程目录之外：路径能算对，但「课程目录整体搬走」会断链。
            # 正常布局下产物就在 `<课程目录>/<讲次>/` 里，不会出现这一条。
            unknowns.append('%s：产物在课程目录之外 —— 课程目录整体搬家会断链（%s）'
                            % (lid, m['product']))

    print()
    if not name:
        print('[warn] 课程名还没定。加 --name "课程名" 补上（首次建 course.json 时必需）。')
        unknowns.append('课程名未定（--name）')
    for field, label in (('instructor', '教师'), ('term', '学期'), ('summary', '课程目标')):
        val = {'instructor': a.instructor, 'term': a.term, 'summary': a.summary}[field]
        if not val and not old.get(field):
            unknowns.append('%s未填（--%s）' % (label, field))

    data = {
        'schema': SCHEMA,
        'name': name or '',
        'instructor': a.instructor if a.instructor is not None else (old.get('instructor') or ''),
        'term': a.term if a.term is not None else (old.get('term') or ''),
        'summary': a.summary if a.summary is not None else (old.get('summary') or ''),
        'created': old.get('created') or datetime.date.today().isoformat(),
        'lectures': lectures,
        'unknowns': unknowns,
    }

    if a.dry_run:
        print('[dry-run] 没有写盘。以下是将要写入的内容：')
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if not data['name']:
        raise SystemExit('课程名是必需的：加 --name "课程名"，或先给讲次补上 outline.cover.course')

    os.makedirs(os.path.join(course_dir, '_course'), exist_ok=True)
    with open(course_json, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

    print('已写入: %s' % course_json)
    print('课程  : %s' % data['name'])
    print('讲次  : %d 个（已完成 %d / 未写完 %d / 骨架 %d / 待建 %d）' % (
        len(lectures),
        sum(1 for x in lectures if x['status'] == 'done'),
        sum(1 for x in lectures if x['status'] == 'partial'),
        sum(1 for x in lectures if x['status'] == 'skeleton'),
        sum(1 for x in lectures if x['status'] == 'pending'),
    ))
    print('派生目录: %s' % os.path.join(course_dir, '_course'))
    if unknowns:
        print()
        print('待补（%d 条，已记进 course.json 的 unknowns）：' % len(unknowns))
        for u in unknowns[:12]:
            print('  · %s' % u)
        if len(unknowns) > 12:
            print('  …… 还有 %d 条' % (len(unknowns) - 12))
    print()
    print('下一步：')
    print('  python scripts/course_index.py "%s"   # 扫各讲产物 → _course/index.json' % course_dir)
    print('  python scripts/course_brief.py "%s" --for L07   # 写某讲之前先取一份前序知识简报' % course_dir)


if __name__ == '__main__':
    main()
