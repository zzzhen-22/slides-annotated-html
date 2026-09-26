#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把一个课件 PDF 变成「项目骨架」——**生成完就能 build、能打开**，讲解文字留待逐页补写。

用法：
    python init_project.py <课件.pdf> [--out 项目目录]
        [--title 标题] [--group-size 8] [--group-by bookmarks|auto|flat]
        [--outline _plan/outline.json]
        [--extras/--no-extras] [--embed-pdf/--no-embed-pdf] [--force]

两种分段来源（第三条优先）：
    ① 有书签大纲 -> 按书签切
    ② 无书签 -> 按固定页数切（--group-size）
    ③ **--outline 给了一份语义大纲 -> 完全按它切**（推荐；见下）

什么是 outline.json
    「先读整份课件、由内容语义决定分节」这条路线产出的中间产物。
    它把「几段、每段叫什么、边界在第几页、每页标题是什么」显式写下来，
    于是**脚本不再需要靠文字层去猜结构**——这正是「页标题抓到公式/人名、
    四个部分被 8 页硬切成三段」这类问题的根源（见 pitfalls 第 40 条）。

    结构（schema: outline/v1）：
        {
          "pdf": "...", "page_count": 17,
          "source": "semantic", "confidence": 0.95, "confirmed": true,
          "cover": {"course": "...", "title": "...", "subtitle": "...", "parts": [...]},
          "warnings": ["..."],
          "sections": [
            {"key": "s1", "name": "物理问题的极值描述",
             "pages": [4,5,6,7], "origin": "numbering", "part_index": 1,
             "toc_label": "1 · 物理问题的极值描述（P4–P7）",
             "page_titles": {"4": "...", "5": "..."}}
          ],
          "page_titles_all": {"1": "...", "2": "..."}
        }
    · sections 就是目录的一级分组，顺序即目录顺序；
    · pages 必须覆盖 1..page_count（缺页会报错，防止漏贴）；
    · toc_label 直接作为目录行文字，不再经任何启发式加工；
    · page_titles / page_titles_all 直接作为页头标题，不再从文字层猜；
    · cover.* 覆盖封面元信息（课程名 / 主标题 / 副标题 / 首页所列部分清单）。

它会做这些事：
    1. 决定分段：读 outline（若给了）／读 PDF 书签／按页数切
    2. 决定每页标题：outline 给的就用，否则取首个非空文本行
    3. 生成 content/ 分片：00_intro（封面/使用说明/脉络/前置）+ 每段 概述卡 + 逐页骨架 + 90_outro
    4. 生成 config.json（字段齐全，可直接跑 build.py）
    5. 把套件自带的离线 KaTeX 复制进项目 _katex/（**不需要联网**）
    6. 写一份 README-项目.md：重建命令、目录说明、待补清单

**不**做的事（有意留给 run_all.py / 人工）：
    · 渲染逐页大图与缩略图（run_all.py 会调 prepare_pdf.py）
    · 写讲解内容（这是这个套件唯一不能自动化的部分，质量靠 references/content-quality.md）

产出后：
    python run_all.py <课件.pdf> --out <同一个目录> --skip-init   # 一键：渲染+构建+三项体检+截图
"""
import argparse
import json
import os
import re
import shutil
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)

sys.path.insert(0, HERE)
import kitpath  # noqa: E402

kitpath.require_deps('pymupdf')   # 缺包时给出 pip 命令，而不是 ModuleNotFoundError

import pymupdf  # noqa: E402

TPL = os.path.join(KIT, 'templates')
SKEL = os.path.join(TPL, 'content-skeleton')

PAGE_TPL = '20_page.html'
OV_TPL = '10_overview.html'
INTRO_TPL = '00_intro.html'
OUTRO_TPL = '90_outro.html'
# 注：config 不用模板文件 —— 本脚本用 json.dumps 直接生成（字段更可控、不会漏替换）


# --------------------------------------------------------------------- 语义大纲
def load_outline(path):
    """读一份 outline.json 并做一致性校验。返回 dict 或 None。

    校验是刻意严格的：outline 是「结构确认后即锁死」的东西，
    宁可在这里报错，也不要让它带着漏洞进到骨架里（残缺的 pages
    会在成品里表现为「某一页凭空消失」，非常难查）。
    """
    if not path:
        return None
    p = os.path.abspath(path)
    if not os.path.exists(p):
        raise SystemExit('找不到 outline: %s' % p)
    try:
        outline = json.load(open(p, encoding='utf-8'))
    except json.JSONDecodeError as e:
        raise SystemExit('outline 不是合法 JSON（%s）:\n  %s' % (p, e))

    if not isinstance(outline.get('sections'), list) or not outline['sections']:
        raise SystemExit('outline 缺少 sections[]，或为空: %s' % p)
    outline['_path'] = p

    # 页码覆盖性：sections 的 pages 并集必须是 1..page_count，不缺不重
    seen = []
    for i, sec in enumerate(outline['sections'], 1):
        pages = sec.get('pages')
        if not isinstance(pages, list) or not pages:
            raise SystemExit('outline 第 %d 个 section 缺 pages[]: %s'
                             % (i, sec.get('key') or sec.get('name')))
        if pages != sorted(pages):
            raise SystemExit('outline 第 %d 个 section 的 pages 未按升序: %s'
                             % (i, pages))
        seen.extend(pages)
    dup = sorted({n for n in seen if seen.count(n) > 1})
    if dup:
        raise SystemExit('outline 里这些页被重复分配: %s' % dup)
    return outline


def check_outline_coverage(outline, n_pages):
    """核对 outline 覆盖了全部页码（封面页除外），且与 PDF 实际页数一致。

    封面页是特例：它由 00_intro.html 的封面卡承载，不进 sections，
    所以允许它落在覆盖范围之外 —— 但也仅限「首页」，其余任何页都不许漏。
    """
    seen = sorted(n for sec in outline['sections'] for n in sec['pages'])
    allow = set(outline.get('cover_pages') or [1])
    want = [n for n in range(1, n_pages + 1) if n not in allow]
    missing = [n for n in want if n not in seen]
    extra = [n for n in seen if n not in range(1, n_pages + 1)]
    if missing:
        raise SystemExit('outline 漏了这些页（PDF 共 %d 页）: %s\n'
                         '  除封面页 %s 外，每一页都必须归属于某个 section，\n'
                         '  否则成品里会凭空少一页。'
                         % (n_pages, missing, sorted(allow)))
    if extra:
        raise SystemExit('outline 多出这些页（PDF 只有 %d 页）: %s' % (n_pages, extra))
    declared = outline.get('page_count')
    if declared is not None and declared != n_pages:
        print('  [warn] outline.page_count=%s 与 PDF 实际页数 %d 不符，以 PDF 为准'
              % (declared, n_pages))


def groups_from_outline(outline):
    """把 outline.sections 转成 split_groups 的返回格式 [(组名, [页号...]), ...]。"""
    return [(sec.get('name') or ('第 %d 段' % i), list(sec['pages']))
            for i, sec in enumerate(outline['sections'], 1)]


def titles_from_outline(outline, n_pages, doc):
    """按 outline 决定每页标题：page_titles_all 优先，其次各 section 的 page_titles，
    都没有就退回文字层启发式（page_titles）。返回长度 = n_pages 的列表。"""
    fallback = None                      # 惰性调用，避免白白解析文字层
    out = []
    per_all = outline.get('page_titles_all') or {}
    for n in range(1, n_pages + 1):
        t = per_all.get(str(n))
        if not t:
            for sec in outline['sections']:
                pt = sec.get('page_titles') or {}
                if str(n) in pt:
                    t = pt[str(n)]
                    break
        if not t:
            if fallback is None:
                fallback = page_titles(doc)
            t = fallback[n - 1] if n - 1 < len(fallback) else ''
            if not t:
                print('  [warn] P%d 在 outline 里没有标题，且文字层也取不到' % n)
        out.append(t or '')
    return out


def outline_label_of(outline, n):
    """从 outline 里取第 n 页的标题（供 toc_label 的 raw 参数）。"""
    per_all = outline.get('page_titles_all') or {}
    if str(n) in per_all:
        return per_all[str(n)]
    for sec in outline['sections']:
        pt = sec.get('page_titles') or {}
        if str(n) in pt:
            return pt[str(n)]
    return ''


def print_outline_report(outline, n_pages):
    """把 outline 的结构摘要打出来 —— 让执行者与用户一眼看到「拿什么依据切段」。"""
    print('  语义大纲: %s' % outline['_path'])
    print('  依据: %s   置信度: %s   已确认: %s'
          % (outline.get('source', '?'), outline.get('confidence', '?'),
             '是' if outline.get('confirmed') else '否'))
    if outline.get('warnings'):
        for w in outline['warnings']:
            print('  [note] %s' % w)
    print('  分段:')
    for i, sec in enumerate(outline['sections'], 1):
        pages = sec['pages']
        span = ('P%d' % pages[0] if len(pages) == 1
                else 'P%d–P%d' % (pages[0], pages[-1]))
        part = sec.get('part_index')
        print('    %d) %-22s %-12s %s%s'
              % (i, sec.get('name', '?'), span,
                 ('（首页第 %s 部分）' % part) if part else '（非编号部分）',
                 ('  ← %s' % sec['origin']) if sec.get('origin') else ''))
    print('  合计 %d 段 / %d 页' % (len(outline['sections']), n_pages))


# --------------------------------------------------------------------- 小工具
def load(name):
    return open(os.path.join(name), encoding='utf-8').read()


def fill(text, mapping):
    for k, v in mapping.items():
        text = text.replace('{{%s}}' % k, str(v))
    return text


def norm_unicode(s):
    """把 PDF 里常见的「形近异码」字符折回标准码位。

    PPT 导出的 PDF 文字层里，汉字常来自数学/符号字体，导出后变成
    康熙部首（CJK Radicals Supplement, U+2E80–U+2FDF）或全角形式，
    肉眼与正常汉字一模一样、码位却不同。后果是：
      · 目录与正文标题「看着是同一个字、其实不是」；
      · 浏览器为两种码位回退到不同字体 -> 表现为「中文字体不统一」；
      · 按标题做匹配/去重时对不上。
    这里统一做 NFKC 归一化（会把 U+2F12 ⼒ 折成 U+529B 力 等），
    另外把几个 NFKC 管不到的空白/连字符类字符也一并规整。
    """
    if not s:
        return ''
    s = unicodedata.normalize('NFKC', s)
    # NFKC 不处理的零宽字符与各类不间断空格
    s = s.replace('\u200b', '').replace('\ufeff', '')
    s = re.sub(r'[\u00a0\u2000-\u200a\u202f\u205f\u3000]', ' ', s)
    # 各种连字符统一成 ASCII 减号，避免视觉上的「字体不一致」
    s = re.sub(r'[\u2010-\u2015\u2212\uff0d]', '-', s)
    # 标题里的装饰性符号（PPT 常用的花饰/圆点标记）去掉，免得挤进目录
    s = re.sub(r'^[\u2700-\u27bf\u2600-\u26ff\u2b00-\u2bff\u25a0-\u25ff\u2764\u2740\u2741]\s*', '', s)
    return s


def clean_title(s, maxlen=42):
    s = norm_unicode(s)
    s = re.sub(r'\s+', ' ', (s or '')).strip()
    s = s.lstrip('•·-—–*0123456789.、 ').strip()
    if len(s) > maxlen:
        s = s[:maxlen - 1] + '…'
    return s


# 该行是否「像公式 / 像纯符号」，而不是一个正常的页面标题
_FORMULA_HINT = re.compile(
    r'[=＋+×÷^∑∫∮√≈≠≤≥∞∂∇]'          # 明显的数学运算符
    r'|\b(?:sin|cos|tan|log|ln|exp|dx|dy|dt|max|min|const)\b'
)
def looks_like_formula(s):
    """判断一行文本是不是公式/公式片段（用来避免把公式当成页面标题）。"""
    if not s:
        return True
    body = s.strip()
    # 以等号、运算符结尾 -> 几乎一定是被截断的公式
    if re.search(r'[=+\-×÷^]\s*$', body):
        return True
    # 含数学运算符且不含中文 -> 视为公式
    if _FORMULA_HINT.search(body) and not re.search(r'[\u4e00-\u9fff]', body):
        return True
    # 字母/数字/符号占比过高（中文少于 2 字）且长度很短 -> 不像标题
    han = len(re.findall(r'[\u4e00-\u9fff]', body))
    if han == 0 and len(body) <= 20:
        return True
    return False


def strip_section_prefix(s):
    """把页面标题里的「1. 」「2.1 」「一、」这类编号前缀去掉，便于当段名。"""
    if not s:
        return ''
    s = re.sub(r'^\s*[\d一二三四五六七八九十]+(?:[.．]\d+)*\s*[.、．]?\s*', '', s)
    return s.strip()


def strip_english_parens(s):
    """剥掉末尾的英文括号副标题，例如「泛函 (function of function)」。"""
    return re.sub(r'\s*[（(][A-Za-z][^）)]*[）)]\s*$', '', s or '').strip()


def tidy_punct(s):
    """统一标点与空格观感：半角转全角、破折号规整、中英数之间补空格。

    目录标签与段名共用这一套，避免两处规则不一致（曾出现段名里
    留着半角「附录:作业」、而页面标签已是「附录：作业」的割裂）。
    """
    if not s:
        return ''
    s = s.replace(':', '：').replace(';', '；').replace(',', '，')
    s = re.sub(r'\s*-\s*', ' — ', s)          # 「有限变量 - 有限变量」-> 「—」
    s = re.sub(r'\s*：\s*', '：', s)           # 「例1 ： 斯涅尔」-> 「例1：斯涅尔」
    s = re.sub(r'\s*—\s*', ' — ', s)
    s = re.sub(r'\s{2,}', ' ', s).strip()
    # 中文与数字/字母之间补一个空格（「例1：」-> 「例 1：」），读起来更整齐
    s = re.sub(r'([\u4e00-\u9fff])(\d)', r'\1 \2', s)
    s = re.sub(r'(\d)([\u4e00-\u9fff])', r'\1 \2', s)
    return s


def toc_label(n, raw):
    """把一页的原始标题整理成目录里那一行标签。

    处理三件事：
      1. 剥离「English (副标题)」里的英文部分——中文目录里混一堆英文
         括号内容既长又乱，且英文部分常是 PPT 的模板副标题；
      2. 清掉公式碎片（前导的 =、运算符、孤立括号）；
      3. 空标题兜底成「第 N 页」，绝不出现空标签。
    """
    s = clean_title(raw or '', 44)
    s = strip_english_parens(s)
    s = tidy_punct(s)
    # 清掉首尾的公式碎片与孤立符号
    s = re.sub(r'^[\s=+\-×÷^、,，。;；:：]+', '', s)
    s = re.sub(r'[\s=+\-×÷^、,，;；:：]+$', '', s).strip()
    # 括号不配对（被截断）时丢掉末尾这段
    if s.count('（') != s.count('）'):
        s = re.sub(r'[（(][^（()）]*$', '', s).strip()
    if not s or looks_like_formula(s):
        s = '第 %d 页' % n
    return '%d. %s' % (n, s)


def page_titles(doc):
    """每页取首个「像标题」的非空行；返回标题字符串列表。

    原先的实现在「公式框浮在标题上方」的版式上会取错：它拿的是
    「首个长度>=2 的非空行」，于是一页里最上面的公式（例如
    ``F(x, y, y′) =``）会被当成标题。这里改为：跳过页码行、
    跳过疑似公式行，取首个合格行；都取不到就返回空串（由调用方
    显示「（待填标题）」提示人工补）。
    """
    out = []
    for page in doc:
        txt = norm_unicode(page.get_text() or '')
        lines = [clean_title(x) for x in txt.splitlines()]
        lines = [x for x in lines if len(x) >= 2]
        # 跳过 PPT 常见的「第 n 页 / 页码 / 页眉」这类噪音行
        cand = [x for x in lines if not re.fullmatch(r'[\d\s/]+', x)]
        # 再跳过疑似公式行，取第一个真正像标题的
        title = ''
        for x in cand:
            if not looks_like_formula(x):
                title = x
                break
        out.append(title)
    return out


def split_groups(doc, n_pages, titles, mode, size):
    """返回 [(组名, [页号...]), ...]。页号从 1 开始。"""
    if mode in ('bookmarks', 'auto'):
        toc = []
        try:
            toc = doc.get_toc(simple=True) or []
        except Exception:  # noqa: BLE001
            toc = []
        if toc:
            lvl1 = [(t[0], clean_title(t[1], 30), int(t[2])) for t in toc if t[0] == 1]
            flat = [(t[0], clean_title(t[1], 30), int(t[2])) for t in toc]
            if not lvl1:                      # 只有更深层的大纲 -> 全部当一级
                lvl1 = flat
            # 用「一级标题出现的位置」把页码切段
            marks = sorted(set(max(1, min(n_pages, p)) for _, _, p in lvl1))
            if len(marks) >= 2:
                groups = []
                for i, start in enumerate(marks):
                    end = (marks[i + 1] - 1) if i + 1 < len(marks) else n_pages
                    if end < start:
                        continue
                    name = [t[1] for t in lvl1 if max(1, min(n_pages, t[2])) == start][0]
                    groups.append((name, list(range(start, end + 1))))
                if groups and groups[0][1]:
                    return groups
            if mode == 'bookmarks':
                return [('全部页面（原文件未提供可用大纲）', list(range(1, n_pages + 1)))]
    # auto / flat：按固定页数切
    # 段名只描述「第几段」，**不带页码**——页码由调用方统一附加一次。
    # 历史上这里写成 '第 N 段（P#–P#）'，调用方又拼一遍页码，
    # 于是目录里出现「1 · 第 1 段（P1–P8）（P1–P8）」这种重复。
    # 另外：如果该段首页有可用的页面标题，就把标题并进段名，让目录一眼
    # 能看出这一段在讲什么（「第 2 段 · 再看极值」优于光秃秃的「第 2 段」）。
    groups = []
    for i in range(0, n_pages, size):
        chunk = list(range(i + 1, min(i + size, n_pages) + 1))
        name = '第 %d 段' % (len(groups) + 1)
        head = ''
        if titles and chunk[0] - 1 < len(titles):
            head = strip_section_prefix(titles[chunk[0] - 1] or '')
        if head:
            # 段名也要过一遍标点/公式规整，否则会出现「附录:作业」这类半角混排
            head = tidy_punct(strip_english_parens(head))
            name = '%s · %s' % (name, head[:24])
        groups.append((name, chunk))
    return groups


# --------------------------------------------------------------------- 骨架生成
def page_blocks(nums, titles):
    tpl = load(os.path.join(SKEL, PAGE_TPL))
    out = []
    for n in nums:
        t = titles[n - 1] if n - 1 < len(titles) else ''
        out.append(fill(tpl, {
            'nn': '%02d' % n, 'n': n,
            'title_en': t or '<!-- TODO 本页标题 -->',
            'title_cn': '<!-- TODO 中文副标题 -->',
        }))
    return '\n\n'.join(out)


def overview_block(idx, name, nums, titles):
    tpl = load(os.path.join(SKEL, OV_TPL))
    chips = ''.join('<a href="#p%02d">P%d</a>' % (n, n) for n in nums)
    minutes = max(10, int(round(len(nums) * 2.5 / 5.0) * 5))
    return fill(tpl, {
        'n': idx, 'label': re.sub(r'^第[一二三四五六七八九十]+[、.．]?\s*', '', name)[:24],
        'from': '%02d' % nums[0], 'to': '%02d' % nums[-1],
        'count': len(nums), 'minutes': minutes, 'chips': chips,
    })


def roadmap_rows(groups):
    rows = []
    for i, (name, nums) in enumerate(groups, 1):
        rows.append('      <tr><td><b>%d</b> %s</td><td>P%d–P%d</td>'
                    '<td><!-- TODO 这一段在讲什么（一到两句，看概述卡） --></td></tr>'
                    % (i, name, nums[0], nums[-1]))
    return '\n'.join(rows)


def guess_meta(pdf_path, doc, titles, outline=None):
    """推定封面用的 (文档名, 主标题行, 课程名)。

    文档名 = 产物文件名 / 品牌名，一律取 PDF 文件名（如「第 19 讲 变分法基础」），
    它才是这份产物的身份。**不要用课程名覆盖它** —— 同一门课有几十讲，
    全叫「课程名-逐页精解.html」会互相盖掉，也看不出是哪一讲。

    有 outline 时额外取 outline.cover.course 作为「课程名」kicker 单独返回；
    title 供封面副标题/主标题使用。
    """
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    first = ''
    try:
        lines = (doc[0].get_text() or '').strip().splitlines()
        first = clean_title(next((x for x in lines if len(x) >= 3), ''), 60)
    except Exception:  # noqa: BLE001
        first = ''
    course = ''
    if outline and outline.get('cover'):
        cov = outline['cover']
        course = clean_title(cov.get('course') or '', 60)
        title = clean_title(cov.get('title') or '', 60)
        if title:
            first = title
    return stem, first, course


# --------------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('--out', default=None, help='项目目录（默认：PDF 同级的 <文件名>-讲解/）')
    ap.add_argument('--title', default=None, help='文档标题（默认按文件名猜）')
    ap.add_argument('--group-size', type=int, default=8,
                    help='没有可用大纲时每段切多少页（默认 8）')
    ap.add_argument('--group-by', choices=['auto', 'bookmarks', 'flat'], default='auto',
                    help='auto=有大纲就用大纲，没有就按页数切；bookmarks=只用大纲；flat=只按页数切')
    ap.add_argument('--outline', default=None,
                    help='语义大纲 JSON（如 _plan/outline.json）；给了就完全按它切段与定页标题，'
                         '忽略 --group-by / --group-size')
    ap.add_argument('--no-extras', action='store_true', help='不生成 primer / roadmap 这两张卡')
    ap.add_argument('--embed-pdf', action='store_true', help='把原 PDF base64 内嵌进产物')
    ap.add_argument('--no-embed-pdf', action='store_true', help='（默认）只写本机绝对路径深链')
    ap.add_argument('--force', action='store_true', help='目录非空时也覆盖已有文件')
    a = ap.parse_args()

    pdf = os.path.abspath(a.pdf)
    if not os.path.exists(pdf):
        raise SystemExit('找不到 PDF: %s' % pdf)
    stem = os.path.splitext(os.path.basename(pdf))[0]
    out_dir = os.path.abspath(a.out) if a.out else os.path.join(
        os.path.dirname(pdf), stem + '-讲解')
    content = os.path.join(out_dir, 'content')
    for d in (out_dir, content, os.path.join(out_dir, '_extract'),
              os.path.join(out_dir, '_katex')):
        os.makedirs(d, exist_ok=True)

    def w(rel, text):
        p = os.path.join(out_dir, rel)
        if os.path.exists(p) and not a.force:
            print('  跳过（已存在）: %s' % rel)
            return
        open(p, 'w', encoding='utf-8').write(text)
        print('  写入: %-34s %6.1f KB' % (rel, len(text.encode('utf-8')) / 1024))

    doc = pymupdf.open(pdf)
    n_pages = doc.page_count
    outline = load_outline(a.outline)
    if outline is not None:
        check_outline_coverage(outline, n_pages)
        print_outline_report(outline, n_pages)
        titles = titles_from_outline(outline, n_pages, doc)
        groups = groups_from_outline(outline)
        src_desc = '语义大纲（%s）' % os.path.basename(outline['_path'])
    else:
        titles = page_titles(doc)
        groups = split_groups(doc, n_pages, titles, a.group_by, a.group_size)
        src_desc = ('来自 PDF 大纲' if a.group_by == 'bookmarks'
                    else ('按页数切（每段 %d 页）' % a.group_size
                          if a.group_by == 'flat' else '自动探测'))
    stem_name, first_line, course_name = guess_meta(pdf, doc, titles, outline)

    title = a.title or ('%s · 逐页精解 — %d 页对照讲解' % (stem_name, n_pages))
    cover_h1 = stem_name
    cover_h2 = '逐页精解'
    # 封面 kicker：有课程名（outline.cover.course）就把它放上去，否则用默认文案。
    # 课程名与文档名是两个独立字段 —— 课程名只进 kicker，绝不进 h1 / 文件名。
    cover_kicker = ('%s · 逐页对照讲解' % course_name) if course_name else '逐页对照讲解 · 中文'
    print('项目目录: %s' % out_dir)
    print('页数: %d   分段: %d 段（%s）' % (n_pages, len(groups), src_desc))
    if course_name:
        print('课程: %s   文档名: %s' % (course_name, stem_name))

    # ---------- 分片 ----------
    shards = ['content/00_intro.html']
    groups_cfg = []

    intro_start = [['#cover', '封面与使用说明'], ['#roadmap', '全文脉络']]
    if not a.no_extras:
        intro_start.insert(1, ['#primer', '阅读前必读（补充）'])
    cover_sub = '基于《%s》（%d 页课件）逐页编写' % (stem_name, n_pages)
    if outline and outline.get('cover', {}).get('subtitle'):
        cover_sub = clean_title(outline['cover']['subtitle'], 90)
    intro = fill(load(os.path.join(SKEL, INTRO_TPL)), {
        'cover_h1': cover_h1, 'cover_h2': cover_h2,
        'cover_kicker': cover_kicker,
        'cover_sub': cover_sub,
        'pdf_name': os.path.basename(pdf), 'page_count': n_pages,
        'roadmap_rows': roadmap_rows(groups),
    })
    if a.no_extras:
        # 先挖掉注释再匹配整段删除，避免注释里的字面标签干扰（pitfalls 第 30 条）。
        cmts = []

        def _mk(m):
            cmts.append(m.group(0))
            return '\x00C%d\x00' % (len(cmts) - 1)

        masked = re.sub(r'<!--[\s\S]*?-->', _mk, intro)
        masked = re.sub(r'<section class="card primer"[\s\S]*?</section>\s*$', '', masked)
        intro = re.sub(r'\x00C(\d+)\x00', lambda m: cmts[int(m.group(1))], masked)
    w('content/00_intro.html', intro)

    cfg_groups = [['开始', [[x[0], x[1]] for x in intro_start]]]

    def label_for(n):
        """一页在目录里那一行的文字。统一带「页码. 」前缀。

        （曾试图让段首页改用 outline 的 toc_label 覆盖，结果那一行变成
        「0 · 引子（P2–P3）」，与段内其它页的「3. xxx」格式割裂 ——
        toc_label 是**段标签**语义，只该喂组名，不该占页标签的位置。）
        """
        if outline:
            return toc_label(n, outline_label_of(outline, n))
        return toc_label(n, titles[n - 1])

    for gi, (gname, nums) in enumerate(groups, 1):
        ov_id = 'ov%d' % gi
        shards.append('content/%d0_ov%d.html' % (gi, gi))
        w('content/%d0_ov%d.html' % (gi, gi), overview_block(gi, gname, nums, titles))
        # 段内再按 group_size 切正文分片；只有一段就不带数字后缀
        pieces = [nums] if len(nums) <= a.group_size + 4 else \
            [nums[i:i + a.group_size] for i in range(0, len(nums), a.group_size)]
        sub = []
        for pi, piece in enumerate(pieces, 1):
            fname = 'content/%d%d_p%02d_p%02d.html' % (gi, pi, piece[0], piece[-1])
            shards.append(fname)
            w(fname, page_blocks(piece, titles))
            # 目录里逐页列出（每页一条），方便跳转
            for n in piece:
                sub.append(['#p%02d' % n, label_for(n)])
        # 段名：outline 给了 toc_label 就用它（语义标签，已含页码），
        # 否则在此处附加一次页码，避免与 split_groups 的段名重复
        sec_toc = ''
        if outline and gi - 1 < len(outline['sections']):
            sec_toc = (outline['sections'][gi - 1].get('toc_label') or '').strip()
        if sec_toc:
            gtitle = sec_toc
        else:
            parts = re.split(r'\s*（P\d+–P\d+）\s*$', gname)
            gname_clean = parts[0] if parts and parts[0] else gname
            gtitle = '%d · %s（P%d–P%d）' % (gi, gname_clean, nums[0], nums[-1])
        cfg_groups.append([gtitle, [[('#%s' % ov_id), '本节概述']] + sub])

    shards.append('content/90_outro.html')
    w('content/90_outro.html', fill(load(os.path.join(SKEL, OUTRO_TPL)), {
        'page_count': n_pages, 'last_n': n_pages, 'last_nn': '%02d' % n_pages,
    }))
    cfg_groups.append(['速查与说明', [
        ['#cheatsheet', '公式与要点速查'],
        ['#glossary', '术语速查表'],
        ['#about', '关于本文档'],
    ]])

    # ---------- config.json ----------
    pages = [[n, titles[n - 1] or '第 %d 页' % n] for n in range(1, n_pages + 1)]
    cfg = {
        'out': os.path.join(out_dir, '%s-逐页精解.html' % stem_name),
        'pdf': pdf,
        'embed_pdf': bool(a.embed_pdf and not a.no_embed_pdf),
        'title': title,
        'brand': stem_name,
        'course': course_name or '',
        'sidebar_title': ' 逐页精解',
        'topbar_title': '%s · 逐页精解' % stem_name,
        'shards': shards,
        'thumb_dir': '_extract',
        'thumb_pattern': 'thumb_{n:02d}.jpg',
        'katex_dir': '_katex',
        'pages': pages,
        'groups': cfg_groups,
        'footer': [
            '逐页精解 · 基于《%s》编写' % stem_name,
            '讲解部分为本文档新增内容；公式、图示与知识点归属原作者。',
        ],
    }
    if outline:
        # 溯源：config 从哪份 outline 来的、依据是什么、确认过没有。
        # 重建时若发现结构与 memory/负责人 记得的不一致，凭这三个字段就能定位。
        cfg['outline'] = {
            'path': os.path.relpath(outline['_path'], out_dir).replace('\\', '/')
                    if outline['_path'].startswith(out_dir) else outline['_path'],
            'source': outline.get('source', ''),
            'confidence': outline.get('confidence'),
            'confirmed': bool(outline.get('confirmed')),
            'warnings': outline.get('warnings') or [],
        }
    cfgtext = json.dumps(cfg, ensure_ascii=False, indent=2)
    w('config.json', cfgtext)

    # ---------- 离线 KaTeX（套件自带，免联网） ----------
    vk = os.path.join(KIT, 'vendor', 'katex')
    for f in ('katex.offline.css', 'katex.min.js'):
        src = os.path.join(vk, f)
        dst = os.path.join(out_dir, '_katex', f)
        if os.path.exists(src):
            if not os.path.exists(dst) or a.force:
                shutil.copy2(src, dst)
            print('  KaTeX: %-24s ← vendor/katex' % f)
        else:
            print('  [warn] 缺 vendor/katex/%s，请先跑 scripts/katex_offline.py 生成' % f)

    # ---------- 项目说明 ----------
    readme = '\n'.join([
        '# %s · 项目说明' % stem_name,
        '',
        '由 pdf-slides-annotated-html 套件的 `scripts/init_project.py` 生成。',
        '**当前状态：骨架已就绪，讲解文字待补。**',
        '',
        '## 重建（每次改完 content/ 都要跑）',
        '',
        '```bash',
        '# 套件位置：默认从本文件所在目录往上找不到时，改这一行即可',
        'KIT="%s"' % KIT.replace('\\', '/'),
        'PY="$(command -v python || command -v python3)"',
        '',
        '# 先自查环境（python / node / 浏览器 是否就位）',
        '"$PY" "$KIT/scripts/kitpath.py"',
        '',
        '# 一键（渲染逐页图 + 构建 + 四项体检 + 截图）',
        '"$PY" "$KIT/scripts/run_all.py" "%s" --out "%s" --skip-init' % (pdf, out_dir),
        '',
        '# 或分步',
        '"$PY" "$KIT/scripts/prepare_pdf.py" "%s" "_extract" 860 75' % pdf,
        '"$PY" "$KIT/scripts/build.py" config.json',
        'node  "$KIT/scripts/check_math.js" "%s-逐页精解.html" "_katex/katex.min.js"' % stem_name,
        '"$PY" "$KIT/scripts/check_ui.py"  "%s-逐页精解.html"' % stem_name,
        '"$PY" "$KIT/scripts/probe.py"    "%s-逐页精解.html" "$KIT/scripts/probe_marks.js"' % stem_name,
        '"$PY" "$KIT/scripts/probe.py"    "%s-逐页精解.html" "$KIT/templates/probe_doc.js"' % stem_name,
        '```',
        '',
        '> `KIT` 是套件目录。本文件生成时套件位于上面那个路径；',
        '> 把套件整个拷到别处后，把这一行改成新位置即可，其余命令都不用动。',
        '> 若 `node` / 浏览器不在 PATH 里，可用环境变量指定：`KIT_NODE` / `KIT_BROWSER`。',
        '',
        '## 目录',
        '',
        '| 路径 | 作用 |',
        '|---|---|',
        '| `content/00_intro.html` | 封面、使用说明、全文脉络、前置知识 |',
        '| `content/<段>0_ovN.html` | 每段的「本节概述」卡 |',
        '| `content/<段><片>_pXX_pYY.html` | 逐页讲解（只放 `<section>`） |',
        '| `content/90_outro.html` | 速查表 / 术语表 / 关于 |',
        '| `config.json` | build.py 的输入（目录结构、标题、深链） |',
        '| `_extract/` | `page-NN.png`（**逐页核对用**）、`thumb_NN.jpg`（内嵌用） |',
        '| `_katex/` | 离线 KaTeX（套件自带，无需联网） |',
        '',
        '## 待补清单（按顺序做）',
        '',
        '1. **逐页看图**：打开 `_extract/page-01.png … page-%d.png` 走一遍。' % n_pages,
        '   不要只看 `_extract/raw.txt` —— PPT 导出的 PDF 里数学符号字体映射常是坏的',
        '   （`¡`=减号、`¼`=π、`®`=w…），只读文字层必然讲错公式。',
        '2. 把每个 `content/*pXX*.html` 里的「待补」卡片换成真正的讲解：',
        '   **每页先说「这页在干什么」→ 结论前置 → 补原文跳过的推导（放 `.note`）→',
        '   指出原稿问题（放 `.flag`）→ 点出与前后页的伏笔关系**。',
        '3. 每段一张概述卡（`*_ovN.html`）：核心问题 / 读完应能 / 与前后节关系。',
        '4. `00_intro.html` 的 primer（前置知识）与 roadmap（脉络表后半段）。',
        '5. `90_outro.html` 的一页纸速查表与术语表。',
        '6. 交前跑一遍交付体检：`probe_doc.js` 里「待补页面」应为 0、TODO 注释应为 0。',
        '',
        '质量标准见套件的 `references/content-quality.md`；',
        '所有踩过的坑见 `references/pitfalls.md`。',
        '',
    ])
    w('README-项目.md', readme)

    print()
    print('=' * 68)
    print('骨架就绪。下一步：')
    print('  1) 一键跑通（会渲染逐页图 + 构建 + 体检 + 截图）：')
    print('     python "%s/scripts/run_all.py" "%s" --out "%s" --skip-init'
          % (KIT.replace('\\', '/'), pdf.replace('\\', '/'), out_dir.replace('\\', '/')))
    print('  2) 然后按 README-项目.md 的「待补清单」逐页写讲解。')
    print('=' * 68)


if __name__ == '__main__':
    main()
