#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""结构信号巡读器：只「看结构」，不「写内容」，产出一份 outline 草案。

用法：
    python plan_outline.py <课件.pdf> [--out _plan/outline.json]
        [--pages _extract]        # 若已有逐页图，顺带报告哪些页是纯图页
        [--force]                 # 覆盖已存在的 outline

它做什么
    这是「先定结构、再写内容」这条路线的第一步。它把**脚本能可靠判断的部分**
    全部做完，把**必须靠读图/读语义判断的部分**留成 TODO 交给 agent：

    ① 书签信号：doc.get_toc() 有条目 -> 直接作为最高置信度的分段依据
    ② 编号信号：页标题带「1. 」「2.1 」「一、」这类前缀 -> 按编号跳变切段
                  （PPT 的作者常把章节编号写进标题，这是免费的段标记）
    ③ 封面清单：首页出现「连续多行都以 数字. 开头」的块 -> 抽为「权威段名名单」
    ④ 一致性校验：③ 抽到 N 条、② 切出 M 段 -> N≠M 时打醒目警告
    ⑤ 存疑报告：列出所有「可能抓错了」的页标题，供人一眼复核

    三路信号都拿不到时，退化为「按页数切」并在 warnings 里明确写出来。

它**不**做什么
    · 不写 content/，不建骨架（那是 init_project.py --outline 的事）
    · 不替 agent 定「每段叫什么」「每页标题怎么写」—— 草案里留 placeholder
    · 不渲染逐页图（那是 prepare_pdf.py 的事）

产出 outline 草案的结构见 init_project.py 的模块文档（schema: outline/v1）。
草案产出后的动作：
    1. agent 逐页看图，把 sections[].name / page_titles / toc_label 改成语义标题，
       并复核 warnings 里列出的存疑页；
    2. 拿给用户确认（这一步是硬闸门，见 SKILL.md「第 1 遍巡读」）；
    3. init_project.py <pdf> --out <dir> --outline _plan/outline.json
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)

sys.path.insert(0, HERE)
import kitpath  # noqa: E402

kitpath.require_deps('pymupdf')   # 缺包时给出 pip 命令

import pymupdf  # noqa: E402

# 复用骨架脚本里的归一化与启发式，避免两处规则漂移
from init_project import (  # noqa: E402
    clean_title, looks_like_formula, norm_unicode,
    strip_section_prefix, page_titles,
)

# 「1. 」「2.1 」「一、」「（三）」这类章节编号前缀
_NUMBER_PREFIX = re.compile(
    r'^\s*(?:'
    r'(?P<arabic>\d+(?:\.\d+)*)\s*[.、．)）]'      # 1. / 2.1 / 3)
    r'|(?P<cjk>[一二三四五六七八九十]+)\s*[、.．]'   # 一、 / 二.
    r')\s*(?P<rest>\S.*)?$'
)
# 装饰性版式字符（PPT 的提示条常用 ✿ ❖ ● 等开头，不是标题）
_DECOR = re.compile(r'^[\u2700-\u27bf\u2600-\u26ff\u2b00-\u2bff\u25a0-\u25ff\u2764\u2740\u2741]')


def raw_page_lines(doc):
    """逐页取「原始文字层」的合格候选行 —— 编号信号必须从这里读。

    **不能用 init_project.page_titles()**：它内部过 clean_title()，而
    clean_title 会把开头的「1. 」「2. 」当噪音 lstrip 掉（那是为了让页标题
    好看）。于是「编号」这个免费的分段信息在抵达本脚本前就已经被销毁了 ——
    实测症状是：页标题明明是「1. 物理问题的极值描述」，编号探测却报「无」。
    这里直接取原始行、只做归一化与公式/页码过滤，把编号完整保留下来。
    """
    out = []
    for page in doc:
        txt = norm_unicode(page.get_text() or '')
        cands = []
        for ln in txt.splitlines():
            s = re.sub(r'\s+', ' ', ln).strip()
            if len(s) < 2:
                continue
            if re.fullmatch(r'[\d\s/]+', s):        # 页码行
                continue
            if _DECOR.match(s):                     # 版式装饰提示条
                continue
            if looks_like_formula(s):
                continue
            cands.append(s)
        out.append(cands)
    return out


def numbered_headings(doc, skip_pages=(1,)):
    """扫描全书页标题，返回 [(页号, 编号字符串, 去掉编号后的文字), ...]。

    只收「看起来真的是章节编号」的行：
      · 编号在开头     · 去掉编号后还有像样的中文说明文字
      · **跳过封面页** —— 封面自带一份目录清单，那里的「1. 2. 3. 4.」
        是清单条目的编号，不是正文页的章节归属（实测会误报成「1(P1)」）
    这是 ② 号信号的核心 —— PPT 作者常把「1. 物理问题的极值描述」直接写在
    每页标题里，即使 PDF 没书签，这也是一份作者亲手标注的分段依据。
    """
    out = []
    for n, cands in enumerate(raw_page_lines(doc), 1):
        if n in skip_pages:
            continue
        for s in cands:
            if _DECOR.match(s):
                continue
            m = _NUMBER_PREFIX.match(s)
            if not m:
                continue
            rest = (m.group('rest') or '').strip()
            # 去掉编号后要有中文说明；纯数字/符号不算（那些是公式或页眉）
            if len(re.findall(r'[\u4e00-\u9fff]', rest)) < 2:
                continue
            # 单页里有多个带编号的行时，取「编号最小的那条」——
            # PPT 的页眉提示条常带编号，正文标题编号更小更靠前
            out.append((n, m.group('arabic') or m.group('cjk'), rest))
            break                                # 每页只取第一个带编号的行
    return out


def cover_parts(doc):
    """从首页抽出「作者列出的部分清单」。

    首页常有一段连续多行都以「数字.」开头（正是课件自己的目录）。
    返回 (parts, cover_meta)：
        parts      —— ['物理问题的极值描述', '再看极值', ...]
        cover_meta —— {'course':…, 'title':…, 'subtitle':…} 尽力而为，可为空
    """
    try:
        raw = norm_unicode(doc[0].get_text() or '')
    except Exception:  # noqa: BLE001
        return [], {}
    lines = [x.strip() for x in raw.splitlines() if x.strip()]

    # 连续编号行成块（允许中间没有空行，PPT 文字层一般就是连续的）
    parts, run = [], []
    for ln in lines:
        m = re.match(r'^\s*(\d+)\s*[.、．]\s*(.+)$', ln)
        if m:
            run.append((int(m.group(1)), strip_section_prefix(ln).strip()))
        else:
            # 遇到非编号行：已攒够 2 条以上就收成一个块，否则丢弃重来
            if len(run) >= 2:
                parts = run
                break
            run = []
    if len(run) >= 2 and not parts:
        parts = run
    parts = [t for _, t in parts]

    # 封面元信息尽力而为：取「编号块之前」的行
    meta = {}
    if parts:
        idx = next((i for i, ln in enumerate(lines)
                    if re.match(r'^\s*1\s*[.、．]\s*', ln)), None)
        head = lines[:idx] if idx else lines[:3]
        cands = [x for x in head if len(x) >= 2 and not looks_like_formula(x)]
        if cands:
            # PPT 封面第一行常是课程名（字号最大/在左上），最后一行常是课件名
            meta['course'] = cands[0][:40]
            if len(cands) >= 2:
                meta['title'] = cands[-1][:60]
            if len(cands) >= 3:
                meta['subtitle'] = cands[1][:80]
    return parts, meta


def groups_from_numbering(headings, n_pages, cover_pages=(1,)):
    """把编号信号切成段。返回 [(段名, [页号...]), ...] 或 []。

    **按编号归并，而不是按编号变化切段。** 这是实测得来的一条：PPT 里同一
    部分的页常常编号交替（本课件 P10/P11 标 3.、P12 标 4.、P13 又回 3.），
    如果一遇编号变化就切段，一个部分会被切成三四段 —— 实测把 4 个部分切成
    了 6 段，正是这个原因。

    正确规则：
      · 同一编号出现的所有页归为一段（不看它们是否连续）；
      · 段的先后顺序 = 各编号**首次出现**的页序；
      · 段内页码升序排列；
      · 未编号的页（引子、小结、作业等）先留出，由调用方决定归属。
    """
    if not headings:
        return []

    by_num = {}
    order = []
    for n, num, rest in headings:
        if n in cover_pages:
            continue
        if num not in by_num:
            by_num[num] = {'pages': [], 'first_text': rest}
            order.append(num)
        by_num[num]['pages'].append(n)
    if not order:
        return []

    out = []
    for num in order:
        info = by_num[num]
        text = re.sub(r'\s*[—\-–]\s*.*$', '', info['first_text']).strip()
        text = text or ('第 %s 部分' % num)
        out.append(('%s. %s' % (num, text), sorted(set(info['pages']))))
    return out


def _run_of_numbered_toc(parts, headings):
    """③ 号信号与 ② 号信号的一致性判据。返回 (ok, message)。"""
    if not parts:
        return None, '首页未发现部分清单（封面可能没有目录，或格式不是「数字. 名称」）'
    # ② 号信号切出的编号集合
    nums = {num for _, num, _ in headings}
    if not nums:
        return None, ('首页列了 %d 个部分，但正文页标题里找不到任何编号前缀；'
                      '分段只能靠语义判断' % len(parts))
    if len(nums) != len(parts):
        return False, ('首页列了 %d 个部分（%s），但正文只探测到 %d 个编号（%s）——'
                       '两者不一致，**必须人工确认**（可能是某部分在正文里没编号，'
                       '或编号被版式遮挡）'
                       % (len(parts), '、'.join(parts), len(nums),
                          '、'.join(sorted(nums))))
    return True, '首页部分清单（%d 条）与正文编号（%d 组）一致 ✔' % (
        len(parts), len(nums))


def suspect_titles(doc):
    """列出「可能抓错了」的页标题，供人复核。

    判定依据（都是实测踩过的）：
      · 以版式装饰字符开头（✿）—— 提示条，不是标题
      · 长度过短（<4 字）且不含章节编号 —— 可能是人名 / 图形标注
      · 疑似公式片段 —— 公式框浮在标题上方时会被抓走

    注意读的是**原始候选行**而非 page_titles 的输出：后者已经过 clean_title
    的 lstrip，看不出「这行原本有没有编号前缀」，判据会失准。
    """
    flagged = []
    for n, cands in enumerate(raw_page_lines(doc), 1):
        s = (cands[0] if cands else '').strip()
        reasons = []
        if not s:
            reasons.append('取不到合格候选行（可能是纯图页）')
        else:
            if _DECOR.match(s):
                reasons.append('以版式装饰字符开头（提示条？）')
            if len(s) < 4 and not _NUMBER_PREFIX.match(s):
                reasons.append('过短且无编号（人名 / 图形标注？）')
            if looks_like_formula(s):
                reasons.append('疑似公式')
        if reasons:
            flagged.append((n, s or '(空)', '；'.join(reasons)))
    return flagged


def template_scan(pages_dir):
    """可选：若已有逐页图，报告纯图页（这些页必须靠看图讲解，文字层帮不上忙）。"""
    if not pages_dir or not os.path.isdir(pages_dir):
        return None
    pngs = [f for f in os.listdir(pages_dir) if re.match(r'page-\d+\.png$', f)]
    txt = os.path.join(pages_dir, 'raw.txt')
    empty_pages = []
    if os.path.exists(txt):
        raw = open(txt, encoding='utf-8').read()
        for m in re.finditer(r'===== PAGE (\d+) =====\n(.*?)(?=\n===== PAGE |\Z)',
                             raw, re.S):
            body = norm_unicode(m.group(2)).strip()
            if len(re.sub(r'[\s\d]', '', body)) < 8:
                empty_pages.append(int(m.group(1)))
    return {'pngs': len(pngs), 'text_empty': empty_pages}


def span_str(pages):
    """把页码列表渲染成人看的字符串。

    **不要只写「P首–P尾」** —— 编号归并出的段页码常常不连续
    （本课件第 3 段是 [10,11,13]，写「P10–P13」会让人以为含 P12，
    而 P12 其实归在第 4 段。实测就被这个假象误导过一次）。
    连续就用区间，不连续就逐页列出。
    """
    if not pages:
        return ''
    if len(pages) == 1:
        return 'P%d' % pages[0]
    if pages == list(range(pages[0], pages[-1] + 1)):
        return 'P%d–P%d' % (pages[0], pages[-1])
    return 'P%s' % '、'.join(str(p) for p in pages)


def build_draft(pdf, doc):
    """三路信号汇总，产出 outline 草案。"""
    n_pages = doc.page_count
    titles = page_titles(doc)
    toc = []
    try:
        toc = doc.get_toc(simple=True) or []
    except Exception:  # noqa: BLE001
        toc = []

    parts, cover_meta = cover_parts(doc)
    headings = numbered_headings(doc)
    warnings = []

    # ---- 分段：书签 > 编号 > 兜底 ----
    sections = []
    if toc:
        src = 'bookmarks'
        warnings.append('使用 PDF 书签大纲切段（%d 条）' % len(toc))
        lvl1 = [(int(t[2]), clean_title(t[1], 40)) for t in toc if t[0] == 1] or \
               [(int(t[2]), clean_title(t[1], 40)) for t in toc]
        marks = sorted({max(1, min(n_pages, p)) for p, _ in lvl1})
        for i, st in enumerate(marks, 1):
            en = (marks[i] if i < len(marks) else n_pages + 1) - 1
            name = next((nm for p, nm in lvl1 if max(1, min(n_pages, p)) == st), '')
            sections.append({'key': 's%d' % i, 'name': name or ('第 %d 段' % i),
                             'pages': list(range(st, en + 1)), 'origin': 'bookmarks'})
    else:
        grp = groups_from_numbering(headings, n_pages,
                                    cover_pages=(1,) if parts or cover_meta else (1,))
        if grp:
            src = 'numbered'
            for i, (name, pages) in enumerate(grp, 1):
                sections.append({'key': 's%d' % i, 'name': name,
                                 'pages': pages, 'origin': 'numbering'})
        else:
            src = 'fallback'
            size = 8
            idx = 0
            for i in range(0, n_pages, size):
                if i == 0:
                    continue                      # 首页当封面
                chunk = list(range(i + 1, min(i + size, n_pages) + 1))
                idx += 1
                sections.append({'key': 's%d' % idx,
                                 'name': '第 %d 段' % idx,
                                 'pages': chunk, 'origin': 'fallback'})
            warnings.append('未探测到书签，也未探测到章节编号 —— 已退化为「每 %d 页一段」，'
                            '**必须人工按语义重新分段**' % size)

    # ---- 补齐未编号页：按「位置」分段，而不是全塞进一个桶 ----
    # 未编号页通常有两类：正文之前的引子/前言，以及正文之后的小结/作业。
    # 它们各自成段比混在一个「未归类」桶里更接近真实结构。
    covered = {n for s in sections for n in s['pages']}
    loose = [n for n in range(2, n_pages + 1) if n not in covered]
    if loose:
        first_num_pg = min((s['pages'][0] for s in sections if s['pages']),
                           default=n_pages + 1)
        last_num_pg = max((s['pages'][-1] for s in sections if s['pages']), default=1)
        head = [n for n in loose if n < first_num_pg]
        tail = [n for n in loose if n > last_num_pg]
        mid = [n for n in loose if n not in head and n not in tail]
        new_secs = []
        if head:
            new_secs.append({'name': '（开头未编号页 — 待人工命名，多为引子/前言）',
                             'pages': head, 'origin': 'unassigned'})
        if mid:
            new_secs.append({'name': '（中间未编号页 — 待人工判断归属）',
                             'pages': mid, 'origin': 'unassigned'})
        if tail:
            new_secs.append({'name': '（结尾未编号页 — 待人工命名，多为小结/作业）',
                             'pages': tail, 'origin': 'unassigned'})
        # 插到正确位置：head 在最前，tail 在最后，mid 追加在末尾前
        head_secs = [s for s in new_secs if s['name'].startswith('（开头')]
        tail_secs = [s for s in new_secs if s['name'].startswith('（结尾')]
        mid_secs = [s for s in new_secs if s['name'].startswith('（中间')]
        sections = head_secs + sections + mid_secs + tail_secs
        warnings.append('这些页没有编号前缀，已按位置单独成段，'
                        '**请人工命名并确认归属**：%s' % loose)

    # 重排 key（前面插入过新段）
    for i, s in enumerate(sections, 1):
        s['key'] = 's%d' % i

    # ---- 一致性校验（③ vs ②）----
    ok, msg = _run_of_numbered_toc(parts, headings)
    if ok is False:
        warnings.append('一致性校验未通过：%s' % msg)
    elif ok is True:
        warnings.append('一致性校验通过：%s' % msg)
    else:
        warnings.append('一致性校验跳过：%s' % msg)

    # ---- 存疑标题 ----
    sus = suspect_titles(doc)
    if sus:
        warnings.append('以下页标题疑似抓取有误，请逐页看图后改写（%d 条）' % len(sus))
        for n, t, why in sus:
            warnings.append('  P%d「%s」— %s' % (n, t, why))

    # ---- 存疑编号：同编号内「文字分歧」——正文里的清单被当成了章节标题 ----
    # 实测典型：某页写着「1. 如何将物理问题表述成数学上的极值问题 / 2. 如何求极值」，
    # 那是页内的**问题清单**（引子页的提问），却因为带「1.」前缀而被算进第 1 章。
    # 判据：同一编号下出现两种明显不同的文字，且其中一种带疑问语气 —— 必属误判。
    by_num = {}
    for n, num, rest in headings:
        by_num.setdefault(num, []).append((n, rest))
    for num, items in sorted(by_num.items()):
        texts = {re.sub(r'\s+', '', rest) for _, rest in items}
        if len(texts) <= 1:
            continue
        # 找出「少数派」文字：只在单页出现的那条
        for n, rest in items:
            same = sum(1 for _, r in items if re.sub(r'\s+', '', r) == re.sub(r'\s+', '', rest))
            if same == 1 and len(items) > 1:
                if re.search(r'如何|怎样|什么|为什么|是否|介绍|说明', rest):
                    warnings.append(
                        '  P%d 的编号「%s」紧接着一段像**页内问题清单**的文字'
                        '（「%s」），与同编号其它页的标题不同 —— 请看图确认它是否'
                        '真的属于第 %s 章，还是该并入前一段' % (n, num, rest[:36], num))

    # ---- 组装草案 ----
    page_titles_all = {}
    for n in range(1, n_pages + 1):
        t = titles[n - 1] if n - 1 < len(titles) else ''
        page_titles_all[str(n)] = t or ''
    # 封面页标题：用 cover_meta 里的课件名，或首行
    if cover_meta.get('title'):
        page_titles_all['1'] = (cover_meta.get('course', '') + ' · '
                                + cover_meta['title']).strip(' ·') or page_titles_all['1']

    for i, s in enumerate(sections, 1):
        s['part_index'] = None
        s['toc_label'] = ''                       # ← 留给 agent 填语义标签
        if s['pages']:
            s['page_titles'] = {str(n): page_titles_all.get(str(n), '')
                                for n in s['pages']}

    draft = {
        'schema': 'outline/v1',
        'pdf': os.path.abspath(pdf),
        'page_count': n_pages,
        'source': src,
        'confidence': {'bookmarks': 0.9, 'numbered': 0.7, 'fallback': 0.2}.get(src, 0.3),
        'confirmed': False,
        'confirmed_by': '',
        'confirmed_at': '',
        'cover_pages': [1],
        'cover': cover_meta,
        'parts_on_cover': parts,
        'warnings': warnings,
        'sections': sections,
        'page_titles_all': page_titles_all,
        '_todo': [
            'sections[].name —— 改成让人一眼看懂的语义段名（不要照抄编号）',
            'sections[].toc_label —— 填目录行标签，格式「N · 段名（P起–P止）」',
            'page_titles_all / sections[].page_titles —— 逐页看图后改写为人话',
            'warnings 里列出的存疑页标题 —— 必须逐页看图复核',
            'cover.* —— 核对课程名 / 课件名 / 副标题',
            '填完后把 confirmed 置 true，confirmed_by 写确认人，再跑 init_project --outline',
        ],
    }
    return draft


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('--out', default='_plan/outline.json',
                    help='草案输出路径（默认 _plan/outline.json）')
    ap.add_argument('--pages', default='_extract',
                    help='逐页图目录（可选，用于报告纯图页）')
    ap.add_argument('--force', action='store_true', help='覆盖已存在的 outline')
    a = ap.parse_args()

    pdf = os.path.abspath(a.pdf)
    if not os.path.exists(pdf):
        raise SystemExit('找不到 PDF: %s' % pdf)
    out = os.path.abspath(a.out)
    if os.path.exists(out) and not a.force:
        raise SystemExit('已存在 %s（用 --force 覆盖）\n'
                         '  注意：outline 一旦人工改过，重新生成会覆盖掉那些改动。' % out)

    doc = pymupdf.open(pdf)
    draft = build_draft(pdf, doc)

    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w', encoding='utf-8').write(
        json.dumps(draft, ensure_ascii=False, indent=2) + '\n')

    # ---------- 人看的报告 ----------
    n_pages = draft['page_count']
    print('课件  : %s' % pdf)
    print('页数  : %d' % n_pages)
    print('信号源: %s（置信度 %s）' % (draft['source'], draft['confidence']))
    print()
    print('【结构性信号】')
    toc_n = len(pymupdf.open(pdf).get_toc() or [])
    hs = numbered_headings(doc)
    print('  ① PDF 书签            : %s' % ('%d 条' % toc_n if toc_n else '无'))
    print('  ② 正文章节编号        : %s'
          % ('、'.join('%s(P%s)' % (num, n) for n, num, _ in hs) or '无'))
    print('  ③ 封面部分清单        : %s'
          % ('｜'.join(draft.get('parts_on_cover') or []) or '无'))
    print()
    print('【分段草案】%d 段' % len(draft['sections']))
    for i, s in enumerate(draft['sections'], 1):
        pg = s['pages']
        span = span_str(pg)
        print('  %d) %-30s %-12s ← %s' % (i, s['name'], span, s['origin']))
    print()
    print('【警告与待复核】%d 条' % len(draft['warnings']))
    for w in draft['warnings']:
        print('  · %s' % w)
    scan = template_scan(a.pages)
    if scan:
        print()
        print('【逐页图】已有 %d 张 page-NN.png' % scan['pngs'])
        if scan['text_empty']:
            print('         文字层几乎为空（纯图页，必须看图讲解）: %s'
                  % scan['text_empty'])
    print()
    print('=' * 68)
    print('草案已写入: %s' % out)
    print('下一步（缺一不可）：')
    print('  1) 逐页看图，把草案里的 _todo 项全部改写成语义标题；')
    print('  2) 把 warnings 里列出的存疑页逐页复核；')
    print('  3) 把草案拿给用户确认（硬闸门），确认后置 confirmed=true；')
    print('  4) init_project.py "%s" --out <项目目录> --outline "%s"'
          % (pdf.replace('\\', '/'), out.replace('\\', '/')))
    print('=' * 68)


if __name__ == '__main__':
    main()
