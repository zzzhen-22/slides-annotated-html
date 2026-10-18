#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""课程层（多讲课程合集）的公共解析与状态判定 —— 供 course_*.py / run_course.py 共用。

用法（被 import，不单独执行）：
    import coursekit

它管五件事。**为什么要收进一个共用模块**：这几个判据会被 4 个脚本用到
（course_init / course_index / course_check / course_site），各写一份必然漂移 ——
那正是 references/pitfalls.md 第 43 条治的病（「同一个事实抄在 6 个文件里」）。

    ① 「逐页区块」的识别：section 开标签的匹配式（见下 PG_TAG_SRC）
    ② 讲次状态判定：pending / skeleton / partial / done（**纯静态，不依赖浏览器**）
    ③ 产物 HTML 的读取与注释剥离（pitfalls 第 18 条的纪律：先挖注释再匹配）
    ④ 讲次字段派生：从 config.json / _plan/outline.json 推出 title / page_count / product
    ⑤ 路径工具：相对课程目录的 posix 路径、URL 编码（跨讲链接必须编码）

────────────────────────── 关于 PG_TAG_SRC ──────────────────────────
v1 的 build.py 用的是**死抠属性顺序**的正则：

    <section class="pg" id="p\\d+" data-page="\\d+">      ← 要求 data-page 后立刻闭合

v2 给 section 追加了 data-concepts / data-pays-off / data-forward，这条正则**一条都匹配不上**
（缩略图一个都不注入）。所以这里改用下面这条**只看属性、不看顺序**的匹配式：

    <section(?=[^>]*\\bclass="pg")(?=[^>]*\\bdata-page="\\d+")[^>]*>

实测（Python 与 Node 两侧逐例对齐过）：v1 原样 ✓／属性追加在后 ✓／属性换序 ✓／
class 不在最前 ✓／概述卡 ✘／无 data-page ✘／class="pg-extra" ✘／class="pg-head" ✘。

**同一个匹配式在三处必须保持一致**（改一处就要改三处，否则体检会互相打架）：
    · scripts/build.py       （注入缩略图，另有 `>.*?</section>` 收尾）
    · scripts/coursekit.py   （本文件，课程层抽取）
    · scripts/check_math.js  （⑥ 数量一致性）
    · scripts/check_ui.py    （① 目录组）
"""
import hashlib
import json
import os
import re
import unicodedata
import urllib.parse

# ---------------------------------------------------------------- ① 区块匹配
PG_TAG_SRC = r'<section(?=[^>]*\bclass="pg")(?=[^>]*\bdata-page="\d+")[^>]*>'
RE_PG_TAG = re.compile(PG_TAG_SRC)
# 整个区块（含收尾）。**先挖注释再用**，否则注释里的字面 </section> 会提前收尾。
RE_PG_BLOCK = re.compile(PG_TAG_SRC + r'.*?</section>', re.S)

RE_COMMENT = re.compile(r'<!--[\s\S]*?-->')
RE_STYLE = re.compile(r'<style[\s\S]*?</style>', re.I)
# 骨架的占位卡长这样：<div class="note"><b>待补：</b>…</div>
RE_NOTE_OPEN = re.compile(r'<div class="note"[^>]*>')


# ---------------------------------------------------------------- ③ 读与挖注释
def read_text(path):
    """读 UTF-8 文本；文件不存在返回 None（调用方自己决定是报错还是降级）。"""
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read()


def strip_comments(html):
    """挖掉 HTML 注释。

    必须做：本套件的注释里大量出现**字面标签**（「缩略图由 build.py 插到 </section> 之前」
    这类说明），不挖掉的话非贪婪匹配会提前收尾。见 pitfalls 第 18 条。
    """
    return RE_COMMENT.sub('', html or '')


def body_html(html):
    """只留「正文标记」：挖掉 `<script>` / `<style>` 与 HTML 注释。

    专供「在页面里找元素、找链接」的检查用（course_check.py 的 .xref / 链接扫描、
    course_index.py 的「属性字样出现但没抽到」探测）。**不要**拿它去做正文抽取 ——
    正文抽取要把 `<script type="math/tex">` 变成〔公式〕占位符（见 html_text），
    这里是一刀全挖掉，用途不同。

    为什么要连 `<style>` 一起挖：本套件的 **CSS 注释里带着用法示例** ——
    `site.extra.css` 里就有一个字面的 `<div class="xref">…<a href="../…/x.html#p09">`，
    不挖的话「找 .xref 卡片」会把这个示例当真实链接去校验、直接误报。
    这是 pitfalls 第 18/46/47 条的老教训：挖噪声要按**类别**想全（注释、脚本、样式、
    一切 base64 载荷），而不是按它出现过的位置枚举。
    """
    s = RE_SCRIPT.sub('', html or '')
    s = RE_STYLE.sub('', s)
    return strip_comments(s)


def page_blocks(html):
    """产出全部「逐页区块」的完整 HTML（已挖注释）。"""
    return RE_PG_BLOCK.findall(strip_comments(html))


def count_page_sections(html):
    """数「逐页区块」的**开标签**数量（与 build.py 的注入数、check_math.js 的 ⑥ 同口径）。"""
    return len(RE_PG_TAG.findall(strip_comments(html)))


# ---------------------------------------------------------------- ② 完成度判定
def note_texts(block):
    """取一个区块里所有 `<div class="note">…</div>` 的文本（不跨过第一个 </div>）。

    为什么盯 .note 而不是整块搜「待补」：probe_doc.js 判「待补页面」时走的就是
    `.pg-text .note` 里含「待补」这条判据。两边判据必须同源，否则课程地图上的
    完成度会和单讲体检报的数字打架。
    """
    out = []
    for m in RE_NOTE_OPEN.finditer(block):
        rest = block[m.end():]
        end = rest.find('</div>')
        out.append(rest[:end] if end >= 0 else rest)
    return out


def is_placeholder(block):
    """这个区块是不是还没写（占位卡还在）。"""
    return any('待补' in t for t in note_texts(block))


def count_done_pages(html):
    """数「已写完」的页数 = 逐页区块总数 − 仍带占位卡的区块数。"""
    blocks = page_blocks(html)
    return sum(1 for b in blocks if not is_placeholder(b)), len(blocks)


def lecture_status(lecture_dir):
    """判定一个讲次目录的状态。返回 (status, done_pages, page_count)。

    四态（设计稿 §3.1）：
        pending   目录不存在
        skeleton  目录在，但没有 config.json 或没有产物 HTML
        partial   产物在，0 < 已写页数 < 总页数
        done      已写页数 == 总页数

    **纯静态**：不启动浏览器。probe_doc.js 才是权威的浏览器探针，但它一次只能看一份产物，
    N 讲就是 N 次 Chromium 启动，而 pitfalls 第 29 条记着浏览器会静默失灵 ——
    课程地图这种基础信息不该押在最不稳的一环上。
    """
    d = lecture_dir
    if not d or not os.path.isdir(d):
        return 'pending', 0, 0
    cfg_path = os.path.join(d, 'config.json')
    cfg = read_json(cfg_path)
    if cfg is None:
        return 'skeleton', 0, 0
    page_count = len(cfg.get('pages') or [])
    product = product_path(d, cfg)
    html = read_text(product) if product else None
    if html is None:
        return 'skeleton', 0, page_count
    done, total = count_done_pages(html)
    if page_count <= 0:
        page_count = total          # config 没给 pages 时退化成用产物的区块数
    if page_count and done >= page_count:
        return 'done', done, page_count
    return 'partial', done, page_count


# ---------------------------------------------------------------- ④ 字段派生
def read_json(path):
    """读 JSON；不存在或解析失败返回 None（调用方给告警，不要静默当空）。"""
    txt = read_text(path)
    if txt is None:
        return None
    try:
        return json.loads(txt)
    except ValueError:
        return None


def product_path(lecture_dir, cfg):
    """由 config.json 的 `out` 推出产物 HTML 的绝对路径。"""
    out = (cfg or {}).get('out') or ''
    if not out:
        return None
    return out if os.path.isabs(out) else os.path.normpath(os.path.join(lecture_dir, out))


def lecture_meta(lecture_dir, course_dir=None):
    """从一个讲次目录推出 course.json 需要的字段（全部可派生，不让用户手写）。

    返回 dict，含：title / page_count / product / outline / pdf / status / done_pages。
    取不到的值一律给空串或 0 —— **不猜**，让 course_check.py 去报「缺什么」。
    """
    cfg = read_json(os.path.join(lecture_dir, 'config.json')) or {}
    outline_path = os.path.join(lecture_dir, '_plan', 'outline.json')
    outline = read_json(outline_path)

    # 标题优先级：outline.cover.title（语义名，人写的）→ config.brand（PDF 文件名）→ 目录名
    # 一律用 _clean_soft：这三个来源都是作者原意，只折叠空白，不做 NFKC。
    title = ''
    if isinstance(outline, dict):
        cov = outline.get('cover') or {}
        title = _clean_soft(cov.get('title') or '')
    if not title:
        title = _clean_soft(cfg.get('brand') or '')
    if not title:
        title = os.path.basename(os.path.normpath(lecture_dir))

    page_count = len(cfg.get('pages') or [])
    if not page_count and isinstance(outline, dict):
        page_count = int(outline.get('page_count') or 0)

    prod = product_path(lecture_dir, cfg)
    status, done, pc = lecture_status(lecture_dir)
    if not page_count:
        page_count = pc

    # PDF：课程目录内 → 相对课程目录的路径（可迁移）；目录外 → 只留文件名（身份信息）
    pdf_raw = cfg.get('pdf') or ''
    pdf = ''
    if pdf_raw:
        abs_pdf = pdf_raw if os.path.isabs(pdf_raw) else os.path.normpath(
            os.path.join(lecture_dir, pdf_raw))
        pdf = rel_posix(abs_pdf, course_dir) if course_dir else os.path.basename(abs_pdf)
        if pdf.startswith('..') or os.path.isabs(pdf):
            pdf = os.path.basename(abs_pdf)

    return {
        'title': title,
        'page_count': page_count,
        'done_pages': done,
        'status': status,
        'product': rel_posix(prod, course_dir) if (prod and course_dir) else (prod or ''),
        'outline': rel_posix(outline_path, course_dir) if course_dir else outline_path,
        'pdf': pdf,
    }


def course_name_hint(course_dir, dirs):
    """从任一讲次的 outline.cover.course / config.course 里捞课程名，给 --name 做默认值。

    为什么值得做：init_project.py 早在 v2.0 就把课程名写进 config.json 的 `course` 字段了
    （来自 outline.cover.course）。让用户再手打一遍课程名，就是「同一事实抄两份」。
    """
    for name in dirs:
        for rel in ('_plan/outline.json', 'config.json'):
            obj = read_json(os.path.join(course_dir, name, rel))
            if not isinstance(obj, dict):
                continue
            if rel.endswith('outline.json'):
                val = (obj.get('cover') or {}).get('course') or ''
            else:
                val = obj.get('course') or ''
            val = _clean_soft(val)
            if val:
                return val
    return ''


# ---------------------------------------------------------------- ⑤ 路径与文本
# ---------------------------------------------------------------- ⑥ 产物抽取
RE_CARD_OPEN = r'<section(?=[^>]*\bid="%s")[^>]*>'
RE_SCRIPT = re.compile(r'<script[\s\S]*?</script>', re.I)
# 公式的承载标签 `<script type="math/tex">行内</script>`。html_rich 要把它留下来 ——
# 课程主页要**显示**公式，而 html_text 按设计换成占位符（那是给检索索引与摘要用的）。
RE_MATH_SCRIPT = re.compile(
    r'<script\b[^>]*\btype="math/tex[^"]*"[^>]*>[\s\S]*?</script>', re.I)
RE_THUMB = re.compile(r'<figure class="thumb">[\s\S]*?</figure>', re.I)
RE_TAG = re.compile(r'<[^>]+>')
RE_ATTR = re.compile(r'\bdata-([a-z-]+)="([^"]*)"')
# 概念 id 的字符集。**中文不要作 id**：它会在 URL / JSON / 文件名三处惹麻烦。
RE_CONCEPT_ID = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
RE_KP_LI = re.compile(r'<li\b([^>]*)>([\s\S]*?)</li>', re.I)


def card_html(html, card_id):
    """取 `<section … id="卡片id" …>…</section>` 的内部 HTML；找不到返回 ''。

    id 允许出现在任意属性位置（与逐页区块一样，不看属性顺序）。
    """
    m = re.search(RE_CARD_OPEN % re.escape(card_id), html or '')
    if not m:
        return ''
    rest = (html or '')[m.end():]
    end = rest.find('</section>')
    return rest[:end] if end >= 0 else rest


def html_text(fragment):
    """把一段 HTML 变成「人读得懂的纯文本」，用于课程页的检索与摘要。

    必须先挖掉的三类（顺序不能反）：
      ① 注释 —— 本套件的注释里大量出现字面标签与说明文字（pitfalls 第 18 条）
      ② `<script>` —— 公式源码（`<script type="math/tex">`）与内嵌载荷；
         公式保留成占位符〔公式〕，因为把 LaTeX 源码塞进摘要既难读又占地方
      ③ `<figure class="thumb">` —— **缩略图的 base64**，一份 82 页课件有 2.5 MB，
         不挖掉会让索引体积爆炸、检索结果里滚出一屏乱码
    """
    s = strip_comments(fragment or '')
    s = RE_SCRIPT.sub('〔公式〕', s)
    s = RE_THUMB.sub('', s)
    s = s.replace('<br>', ' ').replace('<br/>', ' ').replace('<br />', ' ')
    s = RE_TAG.sub(' ', s)
    s = (s.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>')
          .replace('&amp;', '&').replace('&quot;', '"'))
    return re.sub(r'\s+', ' ', s).strip()


# html_rich 允许放行的行内标签白名单（**不含 div/section/table 这类块级标签**）：
# 只保留「强调 + 公式 + 换行」，其余一律转成纯文本。这样即便将来某个卡片里混进
# 表格或脚本，也不会把主页结构撕开。
RICH_KEEP = {'b', 'strong', 'em', 'i', 'code', 'sub', 'sup', 'br', 'span', 'mark'}


def html_rich(fragment):
    """把一段 HTML 变成「安全、可显示公式」的 HTML 片段 —— 供课程主页**显示**用。

    **与 html_text 的分工**（两者不可互替，这是本函数存在的全部理由）：
      · html_text  → 纯文本，公式塌成占位符〔公式〕。给**检索索引与摘要**用：
        把 LaTeX 源码塞进索引既难读又占地方，且检索「〔公式〕」本来就没意义。
      · html_rich  → 保留公式标签与行内强调。给**页面显示**用：
        课程主页的要点表与术语表要让人看见 `ρ=2min_i r_i`，而不是「〔公式〕」。

    做法：
      ① 挖注释（同 html_text —— 注释里有字面标签，不挖会漏进输出）
      ② 挖掉非公式的 `<script>`；**公式 `<script type="math/tex">` 原样保留**
      ③ 挖掉缩略图 base64
      ④ 只放行白名单内的行内标签，其余标签**剥壳留文**（不整段丢弃，避免静默丢内容）
      ⑤ 中和危险属性：剥掉所有 `on*=` 事件与 `href="javascript:"`（产物来自本地、可信度中等，
         但主页是要给别人打开的，成本几乎为零的加固没有理由不做）

    ⚠ 调用方必须知道：本函数**不负责** HTML 转义 —— 它的输入是**本套件自己生成的产物**，
    不是用户输入。所以只做「标签白名单 + 危险属性剥离」这层净化，不 escape 文本。
    """
    s = strip_comments(fragment or '')
    # ② 先摘出公式标签占位，再挖 script，最后还原 —— 否则公式会被 RE_SCRIPT 一起吃掉
    math_parts = []

    def _stash(m):
        math_parts.append(m.group(0))
        return '\x00MATH%d\x00' % (len(math_parts) - 1)

    s = RE_MATH_SCRIPT.sub(_stash, s)
    s = RE_SCRIPT.sub('', s)
    s = RE_THUMB.sub('', s)

    # ④ 标签白名单：逐个标签判定，放行白名单，其余剥壳
    def _tag(m):
        raw = m.group(0)
        name = (m.group(1) or '').lower()
        if name in RICH_KEEP:
            if raw.startswith('</'):
                return '</%s>' % name
            # 保留标签但只留下**无害属性**（这里只需 class / data-* 都不需要，
            # 索性只保留标签名本身 —— 主页的样式按标签选，不按 class 选）
            return '<%s>' % name
        return ''                      # 其余标签剥掉壳，内容自然留下

    s = re.sub(r'</?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>', _tag, s)
    # ⑤ 兜底：万一有属性残留（上面已剥光，这里是双保险）
    s = re.sub(r'\son[a-z]+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', '', s, flags=re.I)
    s = re.sub(r'(href|src)\s*=\s*("|\')\s*javascript:[^"\']*\2', '', s, flags=re.I)

    # 还原公式标签
    def _unstash(m):
        i = int(m.group(1))
        return math_parts[i] if 0 <= i < len(math_parts) else ''

    s = re.sub(r'\x00MATH(\d+)\x00', _unstash, s)
    return s.strip()



def _attrs(attr_text):
    out = {}
    for k, v in RE_ATTR.findall(attr_text or ''):
        out['data-' + k] = v
    return out


def _ids(raw):
    """把 `data-concepts="a,b"` 拆成 id 列表（去空、去重、保序）。"""
    out = []
    for t in str(raw or '').split(','):
        t = t.strip()
        if t and t not in out:
            out.append(t)
    return out


def page_entries(html):
    """抽每个逐页区块：id / 页码 / 标题 / 正文纯文本 / 三个 data-* 声明。"""
    out = []
    for blk in page_blocks(html):
        tag = RE_PG_TAG.search(blk)
        a = _attrs(tag.group(0)[tag.group(0).find(' '):] if tag else '')
        pid_m = re.search(r'\bid="([^"]+)"', blk[:blk.find('>') + 1])
        page_m = re.search(r'\bdata-page="(\d+)"', blk[:blk.find('>') + 1])
        h3 = re.search(r'<h3[^>]*>([\s\S]*?)</h3>', blk, re.I)
        body = re.search(r'<div class="pg-text">([\s\S]*)</div>', blk, re.I)
        out.append({
            'id': pid_m.group(1) if pid_m else '',
            'page': page_m.group(1) if page_m else '',
            'title': html_text(h3.group(1)) if h3 else '',
            'text': html_text(body.group(1)) if body else '',
            'concepts': _ids(a.get('data-concepts')),
            'pays_off': _ids(a.get('data-pays-off')),
            'forward': _ids(a.get('data-forward')),
        })
    return out


def keypoint_entries(html):
    """抽 `#keypoints` 卡里的要点条目：{text, at, topic}。

    这是课程主页「要点总结页」的唯一真源 —— 设计上刻意不另立 JSON 文件，
    否则就有了第二真源（产物改了 JSON 没改 → 漂移），而且单讲被单独拷走时要点会丢。
    """
    card = card_html(html, 'keypoints')
    if not card:
        return []
    ol = re.search(r'<ol class="kpl"[^>]*>([\s\S]*?)</ol>', card, re.I)
    if not ol:
        return []
    out = []
    for m in RE_KP_LI.finditer(ol.group(1)):
        a = _attrs(m.group(1))
        text = html_text(m.group(2))
        if not text:
            continue
        at = a.get('data-at', '').lstrip('#')
        # `html` 是给**主页显示**的：保留公式标签，这样要点里的 σ、ρ、‖w‖ 能真的渲染出来，
        # 而不是显示成占位符〔公式〕。`text` 仍然保留，用于检索 / 过滤 / 导出 Markdown。
        out.append({'text': text, 'html': html_rich(m.group(2)),
                    'at': at, 'topic': a.get('data-topic', '')})
    return out


def glossary_entries(html):
    """抽 `#glossary` 术语表里带 data-concept 的行：{id, zh, en, def}。

    zh / en / def **直接读这一行的三个单元格**，不猜、不抓标题、不留空 ——
    这张表的列头在 v1 就固定是「术语 ｜ English ｜ 一句话解释」，
    且 content-quality.md 已把它列为必写项。现成的结构化资产，不该再从别处推。

    每列同时给出两个版本：
      · `zh` / `en` / `def`              —— 纯文本（公式塌成〔公式〕），给术语冲突比对用
      · `zh_html` / `en_html` / `def_html` —— 保留公式标签，给课程主页**显示**用
    两版必须**同源**（同一次正则扫出），否则术语冲突检测会和页面显示打架。
    """
    card = card_html(html, 'glossary')
    if not card:
        return []
    out = []
    for tr in re.findall(r'<tr\b([^>]*)>([\s\S]*?)</tr>', card, re.I):
        a = _attrs(tr[0])
        cid = a.get('data-concept', '').strip()
        if not cid:
            continue
        cells = re.findall(r'<td\b[^>]*>([\s\S]*?)</td>', tr[1], re.I) + ['', '', '']
        out.append({
            'id': cid,
            'zh': html_text(cells[0]), 'en': html_text(cells[1]), 'def': html_text(cells[2]),
            'zh_html': html_rich(cells[0]), 'en_html': html_rich(cells[1]),
            'def_html': html_rich(cells[2]),
        })
    return out


def file_hash(path):
    """产物内容的短哈希，用于课程层的**增量**：没变就不重抽。

    **换行归一化（\\r\\n → \\n）后再 hash**：产物 HTML 由生成脚本在 Windows 文本
    模式写出是 CRLF，而 git 以 LF 存 blob（`core.autocrlf=input`）、Linux 上 checkout
    出来是 LF。若按原始字节 hash，同一份产物在 Windows / Linux 会算出两个哈希 →
    课程层增量缓存在 Linux 上必然不命中 → 强制重抽 → 新哈希写进 index.json /
    keypoints.json → 「课程层五产物可重建且逐字节一致」在 CI 的 ubuntu 上红
    （2026-10-18 实测 build_demo --check 抓到的正是 index/keypoints 两个文件，
    而 glossary.json 没有 hash 字段、恰好不红）。归一化后「仅换行符不同」的文件
    共享同一哈希，跨平台增量稳定。一次性读入：产物 HTML 最多几十 MB，无内存之忧，
    且省掉了「分块 replace 的跨块 \\r\\n 边界」这个坑。
    """
    if not path or not os.path.exists(path):
        return ''
    with open(path, 'rb') as f:
        data = f.read()
    return hashlib.sha1(data.replace(b'\r\n', b'\n')).hexdigest()[:12]


def long_path(p):
    """把 Windows 8.3 短路径展开成完整路径（非 Windows、路径不存在或失败时原样返回）。

    为什么需要：本机 `tempfile.gettempdir()` 会返回 `SHENYU~1` 这类短名，而
    **Chromium 不接受短路径** —— 截图 / 探针会「退出码 0、无 stdout、不生成文件」，
    极难排查（见 pitfalls 第 29 条）。课程页里的链接最终要交给浏览器打开，
    所以在**路径写进 course.json 之前**就把它展开掉，而不是等浏览器那边哑掉。

    为什么不能只调一次 `GetLongPathNameW` 就完事：它**只认整条路径都存在**的情形，
    中间任何一段缺失就整串原样返回。而这里要展开的常常是**还不存在的文件** ——
    例如 `course.json` 里记的 `lecture-01-zh/_plan/outline.json`，那个 `_plan`
    目录可能压根还没建。这时若 `rel_posix` 的两端一个展开了、一个没展开，
    `os.path.relpath` 就找不出公共前缀，会算出
    `../../../../SHENYU~1/AppData/...` 这种又长又错位的相对路径
    （2026-10-16 在临时目录里重建课程 demo 时实测到）。

    做法：**从最长的「存在」前缀往下退**，把能展开的那一截展开，剩余部分原样拼回。
    """
    if not p or os.name != 'nt':
        return p
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        k32.GetLongPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        k32.GetLongPathNameW.restype = wintypes.DWORD

        def expand_once(q):
            buf = ctypes.create_unicode_buffer(32768)
            if k32.GetLongPathNameW(str(q), buf, 32768):
                return buf.value or q
            return q

        s = os.path.abspath(str(p))
        full = expand_once(s)
        # 整条能展开（含「本来就是长名」的情形）：直接给它
        if full != s or os.path.exists(s):
            return full
        # 整条展不开：逐级上退，找到最长的存在前缀再拼回去
        head, tail = s, ''
        while True:
            parent, name = os.path.split(head)
            if not name or parent == head:            # 退到盘符根了，放弃
                return s
            tail = (name + '\\' + tail) if tail else name
            if os.path.exists(parent):
                return expand_once(parent) + '\\' + tail
            head = parent
    except Exception:                                   # noqa: BLE001
        pass
    return p


def rel_posix(path, base):
    """把 path 转成相对 base 的 **posix** 路径（反斜杠一律换正斜杠）。

    跨讲引用一律相对路径（硬约束 C4）。目录名可迁移，绝对路径换台机器就废。
    两端都先过 long_path：这几个路径最终会变成课程页里的 `href`，短名会让浏览器哑掉。
    """
    if not path:
        return ''
    try:
        rel = os.path.relpath(long_path(os.path.abspath(path)),
                              long_path(os.path.abspath(base)))
    except ValueError:
        return long_path(path).replace('\\', '/')
    return rel.replace('\\', '/')


def url_quote(path):
    """URL 编码（只保留 `/` 与 `:`），供课程页生成跨讲链接。

    必须做：产物文件名取自 PDF 文件名，**普遍带空格**（例：`3-Deep Learning-I-逐页精解.html`）。
    href 里出现裸空格时浏览器行为不一致，`file://` 下可能跳不过去。

    ⚠ safe 集合**刻意只放 `/:`**，与 build.py 生成 file:// 深链时用的完全一致。
    不要把 `#` `?` `&` 放进去 —— 它们在 URL 里是**结构字符**（片段 / 查询 / 参数分隔），
    放行会让「文件名里恰好有 #」变成「链接被截断成另一条 URL」。
    """
    return urllib.parse.quote(str(path or ''), safe='/:')


def url_unquote(path):
    """`url_quote` 的逆运算，给 course_check.py 查「链接指向的文件在不在」用。

    查文件前必须解码：链接下来可能是 %E6%AE%8B（中文）或 %20（空格），
    拿编码后的串去 os.path.exists 会永远找不到 —— 那不是断链，是我们自己没解码。
    """
    if not path:
        return ''
    try:
        return urllib.parse.unquote(str(path))
    except Exception:                                   # noqa: BLE001
        return str(path)


def natural_key(s):
    """自然排序键：lecture-2 排在 lecture-10 前面（普通字符串排序会反过来）。"""
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r'(\d+)', str(s))]


def _clean(s):
    """给人看的字符串做 **NFKC** 归一化 + 折叠空白。

    只用在「从 PDF 文字层/产物 HTML 里刮出来的」字符串上：那里同一个字可能有多个码位
    （康熙部首 U+2E80–U+2FDF 等），不归一化会出现「看着一样、比着不同」。见 pitfalls 第 10 条。
    """
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', str(s or ''))).strip()


def _clean_soft(s):
    """只折叠空白，**不做 NFKC**。

    用在「人（或 agent）亲手写进 config.json / outline.json」的字符串上 ——
    那些值是作者的原意，归一化会把它改掉（实测：`CNN 基础（一）` 会被折成 `CNN 基础(一)`，
    全角括号变半角，中文排版上就错了）。
    """
    return re.sub(r'\s+', ' ', str(s or '')).strip()
