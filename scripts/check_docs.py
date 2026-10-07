#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""套件自身的**文档口径体检**（不依赖浏览器、不依赖产物、不依赖 node）。

用法：
    python check_docs.py          # 静默跑完，只报PASS / FAIL
    python check_docs.py -v       # 额外打印派生出的口径明细（调口径时用）

它查六件事，全是「人眼容易漏、机器一次查完」的：
    ① 文件存在性：文档里提到的脚本/资产/目录是不是真的存在（删了没改文档）
    ② 数字口径：「N 类交互」在五处文档 + check_ui.py docstring 里是不是同一个 N
    ③ 关键功能名：check_ui 声明的每一项交互，功能名在中文文档里能不能找到
    ④ 步骤编号：run_all.py 的 ④–⑧ 各步所引用的脚本，README 校验表是否都列了
    ⑤ pitfalls 编号：1..N 连续无空洞，全仓库「第 N 条」引用都指向存在的条目，
      以及「pitfalls.md（N 条」的散文裸总数等于真实条数
    ⑥ 目录树：README 目录树里列的文件真实存在，且 scripts/ templates/ 下
       新增的 .py/.js 都被列进去了

为什么要它：2026-10-03 加字号功能时，代码改了、README 顶部 bullet 改了，
但 README 中段 3 处 + SKILL.md + workflow.md + run_all.py 注释**共 6 处仍写「四类交互」**，
英文 README 干脆没提这个功能。**根因不是忘了改，是口径散在 6 个文件、没有单一真源。**
（背景见 references/pitfalls.md 第 43 条）

设计原则：**宁可漏报，不可误报。** 任何一个断言在正常仓库上必须恒为真，
否则会被当成噪音关掉 —— 一个会误报的体检比没有体检更糟。
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)

# 中文数字 → int（只覆盖 1–10，够用；写多了反而是负担）
CN_NUM = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
          '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
EN_NUM = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
          'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}

fails = []
notes = []


def chk(label, cond, detail=''):
    print('%-54s %s %s' % (label, 'PASS' if cond else 'FAIL', detail))
    if not cond:
        fails.append(label)


def read(rel):
    p = os.path.join(KIT, rel)
    if not os.path.exists(p):
        return ''
    return open(p, encoding='utf-8').read()


def to_int(tok):
    """把 '五' / 'Five' / '5' 统一成int；认不出返回 None。"""
    tok = (tok or '').strip()
    if tok.isdigit():
        return int(tok)
    if tok in CN_NUM:
        return CN_NUM[tok]
    if tok.lower() in EN_NUM:
        return EN_NUM[tok.lower()]
    return None


# ────────────────────────────────────────────────────────────── ① 文件存在性
DOCS = ['README.md', 'README.en.md', 'SKILL.md', 'docs/workflow.md']

# **只校验带路径分隔符的引用**（scripts/x.py、templates/y.js…）。
# 为什么不校验裸文件名：文档里大量裸文件名是「概念名」而非仓库文件
# （README.en.md、Node.js、config.json、outline.json、requirements.txt…），
# 逐个加白名单会让这条断言变成维护负担，然后被无视——那比没有更糟。
# 裸文件名的存在性交给 ⑥（目录树 ↔ 实际文件）覆盖。
CODE_REF = re.compile(r'\b((?:scripts|templates|assets|references|docs|examples|vendor)/'
                      r'[A-Za-z0-9_][A-Za-z0-9_./-]*'
                      r'\.(?:py|js|md|html|css|json|txt))\b')


def check_files_exist():
    print()
    print('=== ① 文档提到的带路径文件都真实存在 ===')
    missing = []
    for doc in DOCS:
        for name in sorted(set(CODE_REF.findall(read(doc)))):
            if not os.path.exists(os.path.join(KIT, name)):
                missing.append('%s → %s' % (doc, name))
    chk('四份文档提到的带路径文件全部存在', not missing,
        '%d 处缺失' % len(missing))
    for m in missing[:12]:
        print('      ✘ %s' % m)
    if len(missing) > 12:
        print('      …… 还有 %d 处' % (len(missing) - 12))


# ────────────────────────────────────────────────────── ② 数字口径：N 类交互
# 单一真源 = check_ui.py 的 docstring（「检查五项交互功能的"接线"是否正确」）
# 其它文档一律向它对齐。谁写了新交互而忘了改别人，就在这里被抓出来。
SRC = 'scripts/check_ui.py'
DOC_TARGETS = ['README.md', 'SKILL.md', 'docs/workflow.md', 'scripts/run_all.py']
EN_TARGETS = ['README.en.md']

RE_CN_CNT = re.compile(r'([一二三四五六七八九十\d]+)\s*类交互')
RE_EN_CNT = re.compile(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+interactions?\b', re.I)
RE_CN_ITEM = re.compile(r'^\s*[①-⑳]\s*([^：\n]{2,12})[：]', re.M)


def read_interaction_items():
    """从 check_ui.py docstring 的 ①..⑳ 列表里取出每项的功能名。"""
    m = re.search(r'"""(.*?)"""', read(SRC), re.S)
    return [x.strip() for x in RE_CN_ITEM.findall(m.group(1))] if m else []


def check_counts():
    print()
    print('=== ② 「N 类交互」各处一致（真源 = check_ui.py docstring）===')
    m = re.search(r'检查\s*([一二三四五六七八九十\d]+)\s*项交互', read(SRC))
    base = to_int(m.group(1)) if m else None
    chk('能从 check_ui.py docstring 解析出交互项数', base is not None,
        'N = %s' % base)
    if base is None:
        notes.append('真源解析失败，② 后续与③ 跳过')
        return None

    for doc in DOC_TARGETS:
        found = [to_int(x) for x in RE_CN_CNT.findall(read(doc))]
        bad = [x for x in found if x is not None and x != base]
        chk('%-32s 写的都是「%d 类交互」' % (doc, base), found and not bad,
            '出现 %d 处%s' % (len(found), ('，其中错：%s' % bad) if bad else ''))
    for doc in EN_TARGETS:
        found = [to_int(x) for x in RE_EN_CNT.findall(read(doc))]
        bad = [x for x in found if x is not None and x != base]
        chk('%-32s 写的都是「%d interactions」' % (doc, base), found and not bad,
            '出现 %d 处%s' % (len(found), ('，其中错：%s' % bad) if bad else ''))
    return base


# ──────────────────────────────────── ③ 关键功能名能在中文文档里找到（弱校验）
# 弱在哪：只查「功能名里稳定的一个双字词」，不查完整措辞。
# 强在：新增一项交互忘了写进 README 特性列表，一定会命中。
#
# 为什么不逐项维护「别名表」：那等于把「同一个功能该叫什么」的知识又抄一份到脚本里，
# 那就是第 43 条要治的病。改为**从功能名里自动取一个有区分度的双字词**——
# 优先取后两个字（「目录逐级折叠」→ 「折叠」；「本节概述」→「概述」），
# 因为中文功能名的后缀比前缀稳定（「本节」可以叫「每节」，「概述」不会变）。
STRICT_DOCS = ['README.md', 'SKILL.md', 'docs/workflow.md']
# 这些词太泛，用作片段会误判为「提到了」，故排除
GENERIC = ('功能', '交互', '支持', '其它', '其他')


def pick_keywords(name):
    """从交互功能名里挑一个有区分度的双字词。"""
    if name in GENERIC or len(name) < 2:
        return [name]
    tail = name[-2:]
    head = name[:2]
    return [tail] if tail not in GENERIC else [head]


def check_feature_names():
    print()
    print('=== ③ 每项交互的功能名在中文文档里都找得到 ===')
    items = read_interaction_items()
    chk('能从 check_ui.py 解析出各交互的功能名', bool(items),
        '%d 项：%s' % (len(items), '、'.join(items)))
    if not items:
        return
    miss = {}
    for doc in STRICT_DOCS:
        txt = read(doc)
        for it in items:
            if not any(k in txt for k in pick_keywords(it)):
                miss.setdefault(doc, []).append(
                    '%s(关键词 %s)' % (it, '/'.join(pick_keywords(it))))
    for doc in STRICT_DOCS:
        bad = miss.get(doc, [])
        chk('%-32s 提到全部 %d 项' % (doc, len(items)), not bad,
            '缺：%s' % '、'.join(bad) if bad else '')

    # 英文侧只查字号功能的标志性字样（逐项对译表维护成本高于收益，只锁死这一个）
    en = read('README.en.md')
    chk('英文 README 提到正文字号调节',
        'body text size' in en, '关键词 body text size')


# ───────────────────────────── ④ 流水线④–⑧ 各步引用的脚本，README 校验表都列了
RE_STEP = re.compile(r'^\s*([④-⑳]b?)\s+(\S+\.(?:py|js))', re.M)


def check_pipeline_coverage():
    print()
    print('=== ④ 流水线验证步骤引用的脚本，README 校验表都列了 ===')
    run_all = read('scripts/run_all.py')
    steps = RE_STEP.findall(run_all)
    chk('能从 run_all.py docstring 解析出④–⑧ 各步', len(steps) >= 5,
        ' '.join('%s=%s' % s for s in steps))

    zh = read('README.md')
    en = read('README.en.md')
    # README 的校验表从「三重校验」标题到「自检」小节之间
    def section(txt, start, end=None):
        i = txt.find(start)
        if i < 0:
            return ''
        j = txt.find(end, i) if end else -1
        return txt[i:j] if j > 0 else txt[i:]
    zh_tbl = section(zh, '## 三重校验', '\n### ')
    en_tbl = section(en, '## Verification', '\n---')
    chk('找到中文 README 的校验表小节', bool(zh_tbl), '%d 字符' % len(zh_tbl))
    chk('找到英文 README 的校验表小节', bool(en_tbl), '%d 字符' % len(en_tbl))

    for num, script in steps:
        base = os.path.basename(script)
        chk('%-14s 列在中文校验表里' % base, base in zh_tbl)
        chk('%-14s 列在英文校验表里' % base, base in en_tbl)


# ─────────────────────────── ⑤ pitfalls 编号连续性 + 全仓库引用有效性
RE_PIT_NUM = re.compile(r'^###\s+(\d+)\.', re.M)
RE_PIT_HEAD = re.compile(r'^##\s+([A-Z])\.', re.M)
# 「第 18 条」「第 29、36 条」「第 2 条」都算
RE_REF = re.compile(r'第\s*(\d+(?:\s*[、,]\s*\d+)*)\s*条')
REF_GLOBS = [('scripts', '.py'), ('scripts', '.js'), ('templates', '.js'),
             ('templates', '.html'), ('examples', '.html')]
# 散文里的「裸总数」：「pitfalls.md（N 条」或「N 条…pitfalls.md」两种写法都算。
# 为什么单独查：上面的 ⑤ 只查「第 N 条」引用是否越界，不查这个总数——
# 2026-10-04 pitfalls 从 42 涨到 45 时，README.md 两处 + workflow.md 一处仍写「42 条」，
# 没有任何一条体检拦住（2026-10-07 接手时才发现）。这里把「总数口径」也纳入体检。
RE_PIT_COUNT = re.compile(
    r'pitfalls\.md[^\n]*?[（(]\s*\**(\d+)\s*条'
    r'|(\d+)\s*条[^\n]*?pitfalls\.md')


def check_pitfalls():
    print()
    print('=== ⑤ pitfalls 编号连续、引用有效 ===')
    txt = read('references/pitfalls.md')
    nums = [int(x) for x in RE_PIT_NUM.findall(txt)]
    chk('能解析出 pitfalls 条目编号', bool(nums), '%d 条' % len(nums))
    if not nums:
        return
    want = list(range(1, len(nums) + 1))
    chk('编号是 1..%d 的连续序列（无空洞 / 无重复）' % len(nums), nums == want,
        '' if nums == want else '实际：%s' % nums)

    heads = RE_PIT_HEAD.findall(txt)
    chk('分组字母递增且不重复（A..%s）' % (heads[-1] if heads else '?'),
        heads == sorted(set(heads), key=ord), ''.join(heads))

    # 全仓库引用：先收集每个被引用到的编号
    srcs = ['README.md', 'README.en.md', 'SKILL.md', 'docs/workflow.md', 'TODO.md']
    for d, ext in REF_GLOBS:
        dd = os.path.join(KIT, d)
        if not os.path.isdir(dd):
            continue
        srcs += [os.path.join(d, f) for f in sorted(os.listdir(dd))
                 if f.endswith(ext)]
    bad = []
    total = 0
    for rel in srcs:
        p = os.path.join(KIT, rel)
        if not os.path.exists(p):
            continue
        for grp in RE_REF.findall(open(p, encoding='utf-8').read()):
            for one in re.split(r'[、,]', grp):
                n = int(one)
                total += 1
                if not 1 <= n <= len(nums):
                    bad.append('%s → 第 %d 条' % (rel, n))
    chk('全仓库 %d 处「第 N 条」引用都指向存在的条目' % total, not bad,
        '' if not bad else '越界 %d 处' % len(bad))
    for b in bad[:10]:
        print('      ✘ %s' % b)

    # 裸总数口径：「pitfalls.md（N 条」的 N 都等于真实条数（含英文 README 的对应写法）
    count_bad = []
    for rel in ('README.md', 'README.en.md', 'SKILL.md', 'docs/workflow.md', 'TODO.md'):
        for m in RE_PIT_COUNT.finditer(read(rel)):
            n = int(m.group(1) or m.group(2))
            if n != len(nums):
                count_bad.append('%s → %d 条（实际 %d 条）' % (rel, n, len(nums)))
    chk('「pitfalls.md（N 条」的裸总数都等于真实条数', not count_bad,
        '' if not count_bad else '漂移 %d 处' % len(count_bad))
    for b in count_bad[:10]:
        print('      ✘ %s' % b)


# ─────────────────────────── ⑥ README 目录树 ↔ 实际文件
TREE_LINE = re.compile(r'^([│ ]*)([├└]─\s)(.+)$')
TREE_COMMENT = re.compile(r'\s*(?:←|//)\s*')
CODE_EXT = ('.py', '.js', '.md', '.html', '.css', '.json', '.txt', '.pdf')


def parse_tree(txt):
    """解析 README 目录树，返回 [(显示路径, 该行注释)]。"""
    out, stack = [], []
    for line in txt.splitlines():
        m = TREE_LINE.match(line)
        if not m:
            continue
        depth = len(m.group(1)) // 4
        name = TREE_COMMENT.split(m.group(3).strip())[0].strip()
        if not name:
            continue
        stack = stack[:depth]
        stack.append(name)
        out.append(('/'.join(stack), m.group(3)))
    return out


def check_tree():
    print()
    print('=== ⑥ README 目录树 ↔ 实际文件 ===')
    readme = read('README.md')
    i, j = readme.find('## 目录结构'), readme.find('## 三重校验')
    blk = readme[i:j] if 0 <= i < j else ''
    entries = parse_tree(blk)
    chk('能从 README 解析出目录树', len(entries) > 20, '%d 个条目' % len(entries))
    if not entries:
        return

    miss = [p for p, _ in entries
            if not p.endswith('/') and not os.path.exists(os.path.join(KIT, p))]
    chk('目录树列出的文件都存在', not miss, '%d 处缺失' % len(miss))
    for p in miss[:10]:
        print('      ✘ %s' % p)

    listed = {os.path.basename(p) for p, _ in entries}
    orphan = []
    for d in ('scripts', 'templates'):
        dd = os.path.join(KIT, d)
        if not os.path.isdir(dd):
            continue
        for f in sorted(os.listdir(dd)):
            if f.endswith(('.py', '.js')) and f not in listed:
                orphan.append('%s/%s' % (d, f))
    chk('scripts/ 与 templates/ 下的 .py/.js 都列进了目录树', not orphan,
        '%d 处漏列' % len(orphan))
    for o in orphan[:10]:
        print('      ✘ %s' % o)


def main():
    verbose = '-v' in sys.argv or '--verbose' in sys.argv
    if verbose:
        notes.append('check_ui 声明的交互：%s' % '、'.join(read_interaction_items()))
    print('套件文档口径体检 —— %s' % KIT)
    check_files_exist()
    check_counts()
    check_feature_names()
    check_pipeline_coverage()
    check_pitfalls()
    check_tree()
    print()
    if verbose:
        for n in notes:
            print('· %s' % n)
        print()
    print('结果:', 'ALL PASS' if not fails else ('FAILED: ' + '; '.join(fails)))
    sys.exit(0 if not fails else 1)


if __name__ == '__main__':
    main()
