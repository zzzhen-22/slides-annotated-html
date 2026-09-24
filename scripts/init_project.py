#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把一个课件 PDF 变成「项目骨架」——**生成完就能 build、能打开**，讲解文字留待逐页补写。

用法：
    python init_project.py <课件.pdf> [--out 项目目录]
        [--title 标题] [--group-size 8] [--group-by bookmarks|auto|flat]
        [--extras/--no-extras] [--embed-pdf/--no-embed-pdf] [--force]

它会做这些事：
    1. 读 PDF 大纲（书签）→ 自动切段，生成目录 groups（两级）
    2. 每页取首个非空文本行当标题（供目录与页头用）
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


# --------------------------------------------------------------------- 小工具
def load(name):
    return open(os.path.join(name), encoding='utf-8').read()


def fill(text, mapping):
    for k, v in mapping.items():
        text = text.replace('{{%s}}' % k, str(v))
    return text


def clean_title(s, maxlen=42):
    s = re.sub(r'\s+', ' ', (s or '')).strip()
    s = s.lstrip('•·-—–*0123456789.、 ').strip()
    if len(s) > maxlen:
        s = s[:maxlen - 1] + '…'
    return s


def page_titles(doc):
    """每页取首个够长的非空行当标题；返回 (标题, 是否纯图页)。"""
    out = []
    for page in doc:
        txt = page.get_text() or ''
        lines = [clean_title(x) for x in txt.splitlines()]
        lines = [x for x in lines if len(x) >= 2]
        # 跳过 PPT 常见的「第 n 页 / 页码 / 页眉」这类噪音行
        cand = [x for x in lines if not re.fullmatch(r'[\d\s/]+', x)]
        out.append(cand[0] if cand else '')
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
    groups = []
    for i in range(0, n_pages, size):
        chunk = list(range(i + 1, min(i + size, n_pages) + 1))
        name = '第 %d 段（P%d–P%d）' % (len(groups) + 1, chunk[0], chunk[-1])
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


def guess_meta(pdf_path, doc, titles):
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    first = ''
    try:
        first = (doc[0].get_text() or '').strip().splitlines()
        first = clean_title(next((x for x in first if len(x) >= 3), ''), 60)
    except Exception:  # noqa: BLE001
        first = ''
    return stem, first


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
    titles = page_titles(doc)
    stem_name, first_line = guess_meta(pdf, doc, titles)
    groups = split_groups(doc, n_pages, titles, a.group_by, a.group_size)

    title = a.title or ('%s · 逐页精解 — %d 页对照讲解' % (stem_name, n_pages))
    cover_h1 = stem_name
    cover_h2 = '逐页精解'
    print('项目目录: %s' % out_dir)
    print('页数: %d   分段: %d 段（%s）' % (n_pages, len(groups),
                                        '来自 PDF 大纲' if a.group_by != 'flat' else '按页数切'))

    # ---------- 分片 ----------
    shards = ['content/00_intro.html']
    groups_cfg = []

    intro_start = [['#cover', '封面与使用说明'], ['#roadmap', '全文脉络']]
    if not a.no_extras:
        intro_start.insert(1, ['#primer', '阅读前必读（补充）'])
    intro = fill(load(os.path.join(SKEL, INTRO_TPL)), {
        'cover_h1': cover_h1, 'cover_h2': cover_h2,
        'cover_sub': '基于《%s》（%d 页课件）逐页编写' % (stem_name, n_pages),
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
            sub.append(['#p%02d' % piece[0],
                        '%d. %s' % (piece[0], titles[piece[0] - 1] or '（待填标题）')])
            # 目录里逐页列出（每页一条），方便跳转
            for n in piece:
                lbl = titles[n - 1] or '（待填标题）'
                if n != piece[0]:
                    sub.append(['#p%02d' % n, '%d. %s' % (n, lbl)])
        cfg_groups.append(['%d · %s（P%d–P%d）' % (gi, gname, nums[0], nums[-1]),
                           [[('#%s' % ov_id), '本节概述']] + sub])

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
