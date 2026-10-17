#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""重建仓库里的在线 demo：两份单讲（`docs/demo/`、`docs/demo-en/`）+ 一份课程合集（`docs/demo-course/`）。

**为什么要有这个脚本**：这两份 demo 是项目门面，README 与 Releases 页都在引用它们。
门面比正文旧（少了后来加的交互）是访客最容易被误导的地方，而「手工重做一遍」
既不可复现、也一定会忘。demo 的**源工程**因此入了库：

    examples/demo/
      ├─ _thumbs/thumb_01..08.jpg  ← 原页图（**源资产，不是派生物**，理由见下）  ✅ 入库
      ├─ zh/                       ← 中文 demo 的源
      └─ en/                       ← 英文 demo 的源
           ├─ config.json          ← 标准 v1 项目配置（out 指向 docs/demo[-en]/index.html） ✅ 入库
           ├─ content/*.html       ← 逐页讲解分片（人工写的那部分，唯一的真源）           ✅ 入库
           └─ _katex/              ← 从 vendor/katex 复制                              ❌ 生成物

**为什么原页图是源资产而不是派生物**：demo 用的那份课件 PDF（一份机器学习讲义）
**并未随仓库分发**（版权原因，见 TODO 第 10 条）。所以这 8 张图没有可再生的上游，
只能作为源入库；zh / en 两份 bytes 完全相同，共享 `_thumbs/` 一份。
（对比之下，`examples/sample-lecture.pdf` 是另一份物理讲义，只服务于「三步上手」与
`selftest.py`，**与 demo 无关**——别把它当成 demo 的上游。）

用法：
    python scripts/build_demo.py            # 两份单讲 demo + 课程 demo，全部重建
    python scripts/build_demo.py zh         # 只重建中文单讲 demo
    python scripts/build_demo.py course     # 只重建课程 demo（它依赖两份单讲 demo 已是最新）
    python scripts/build_demo.py --check    # 只校验：重建到临时文件，与已入库的产物比对

`--check` 比对**目录（nav）与正文（wrap，含原页图）**：两者必须与已入库的 demo
逐字节一致——它们都来自源工程，重建不该改动它们。**只有外壳（CSS/JS/顶栏/页脚）
与 `DOC_NS` 会变，那是预期的**：前者正是「用当前版本重建」的目的，
后者在脚本区、不在比对范围内。

**课程 demo（`docs/demo-course/`）为什么也归这个脚本管**：它是另一条产物链
（`course_init → course_index → course_site → course_check`），手工拼一次就再也复现不了；
而且单讲 demo 一更新，课程 demo 里的讲次副本就悄悄落后——这与「门面必须能被源工程
忠实重建」是同一条纪律。它的讲次是**预构建产物**（把两份单讲 demo 复制过去，
并注入「← 返回课程主页」链接 —— 与构建期的 course_home 注入**共用同一个函数**，§5.9）：
课程层消费的只是各讲产物 HTML，`coursekit` 既不启浏览器也不读 PDF，所以这样做是充分的。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)

sys.path.insert(0, HERE)
from build import inject_course_home  # noqa: E402  （与构建注入共用同一实现，杜绝两处漂移）

DEMOS = [('zh', 'demo', '中文'), ('en', 'demo-en', '英文')]
OUTDIR = {lang: outdir for lang, outdir, _ in DEMOS}
THUMBS = os.path.join(KIT, 'examples', 'demo', '_thumbs')

# ── 课程 demo：把上面两份单讲 demo 当成一门课的两讲，再生成课程入口页 ──────────
COURSE_DIR = os.path.join(KIT, 'docs', 'demo-course')
COURSE_NAME = '逻辑回归 · 课程合集 Demo'
COURSE_SUMMARY = ('一门两讲示例课程：L01 中文精解 + L02 英文精解，演示课程主页的五个区块'
                  ' —— 课程地图、要点总结、跨讲检索、术语总表、学习进度。')
# (讲次目录名, 源 demo 的 lang, 课程地图上显示的标题)
# 标题取自讲次 config.json 的 `brand`（见 coursekit.lecture_meta 的优先级：
# outline.cover.title → config.brand → 目录名）—— 两份 demo 的产物与外壳**一个字节都不改**，
# 只在课程层给它们起一个能彼此区分的名字（否则两讲都叫 "Logistic Regression"，地图上看不出谁是谁）。
COURSE_LECTURES = [
    ('lecture-01-zh', 'zh', '逻辑回归 · 中文精解'),
    ('lecture-02-en', 'en', 'Logistic Regression · English walkthrough'),
]
# 课程层产物：重建后必须与已入库的这些文件逐字节一致
COURSE_FILES = ['index.html', 'course.json',
                '_course/index.json', '_course/glossary.json', '_course/keypoints.json']

COURSE_CFG_NOTE = (
    '本讲是**预构建产物**：index.html 由 docs/%s/index.html 复制并注入'
    '「返回课程主页」链接而来（见 scripts/build_demo.py），'
    '源工程在 examples/demo/%s/。本 config.json 只为课程层（course_init / course_index）'
    '提供 title / brand / pages / out，**不用于重新构建** —— 要改这一讲的正文，'
    '请改 examples/demo/%s/ 再跑 scripts/build_demo.py。'
)


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    if r.returncode != 0:
        raise SystemExit('命令失败（退出码 %d）：\n%s\n%s\n%s'
                         % (r.returncode, ' '.join(cmd), r.stdout, r.stderr))
    return (r.stdout or '') + (r.stderr or '')


def prep(lang, force):
    """备齐 `_katex/`（从 vendor 复制）。原页图是源资产，只检查、不生成。"""
    src = os.path.join(KIT, 'examples', 'demo', lang)
    cfg = json.load(open(os.path.join(src, 'config.json'), encoding='utf-8'))
    katex = os.path.join(src, cfg.get('katex_dir', '_katex'))
    os.makedirs(katex, exist_ok=True)
    for f in ('katex.min.js', 'katex.offline.css'):
        dst = os.path.join(katex, f)
        want = os.path.join(KIT, 'vendor', 'katex', f)
        if force or not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(want):
            shutil.copy2(want, dst)
    n = len([f for f in os.listdir(THUMBS) if f.endswith('.jpg')]) \
        if os.path.isdir(THUMBS) else 0
    if n < 1:
        raise SystemExit(
            '找不到原页图：%s\n'
            '  它们是**源资产**（demo 用的课件 PDF 未随仓库分发），不能靠脚本生成。\n'
            '  若确实缺失，只能从历史上某次提交的 docs/demo/index.html 里把\n'
            '  <figure class="thumb"> 的 base64 解回来（见 examples/demo/README.md）。' % THUMBS)
    return src


def build(src, out=None):
    cmd = [sys.executable, os.path.join(HERE, 'build.py'),
           os.path.join(src, 'config.json')]
    if out:
        cmd += ['--out', out]
    return sh(cmd)


def parts_of(path):
    """取一份产物的「目录 + 正文」，用于重建前后的忠实性比对。"""
    s = open(path, encoding='utf-8').read()
    nav = s[s.find('<nav'):s.find('</nav>')]
    i, j = s.find('<div class="wrap">'), s.find('<footer class="doc-foot">')
    return nav, s[i:j]


# ─────────────────────────────── 课程 demo ───────────────────────────────
def lecture_config(lang, brand):
    """讲次副本的 config.json：拿源工程的改几个字段。

    为什么不手写一份精简的：`pages` 必须是**与源工程同形的列表**
    （`coursekit` 用 `len(cfg['pages'])` 算页数），手写很容易写成 `8` 这种数字而静默出错。
    复制源配置则天然同形，只有下面几个字段需要改。
    """
    p = os.path.join(KIT, 'examples', 'demo', lang, 'config.json')
    cfg = json.load(open(p, encoding='utf-8'))
    cfg['out'] = 'index.html'                       # 产物就在讲次目录里
    cfg['brand'] = brand                            # → 课程地图上显示的标题
    # 讲次副本里没有 _thumbs / _katex（产物已预构建），路径指回源工程，至少是**能解析**的
    cfg['thumb_dir'] = '../../../examples/demo/_thumbs'
    cfg['katex_dir'] = '../../../examples/demo/%s/_katex' % lang
    cfg['_note'] = COURSE_CFG_NOTE % (OUTDIR[lang], lang, lang)
    return cfg


def build_course():
    """组装 `docs/demo-course/`：两讲副本（带返回入口）+ course.json + _course/ + index.html。"""
    os.makedirs(COURSE_DIR, exist_ok=True)
    for lcdir, lang, brand in COURSE_LECTURES:
        src_prod = os.path.join(KIT, 'docs', OUTDIR[lang], 'index.html')
        if not os.path.exists(src_prod):
            raise SystemExit('先把单讲 demo 建出来，课程 demo 要用它当讲次：%s' % src_prod)
        dst_dir = os.path.join(COURSE_DIR, lcdir)
        os.makedirs(dst_dir, exist_ok=True)
        # 复制**并注入「课程返回入口」**（设计稿 §5.9）——调用的是 build.py 的同一个
        # 注入函数（构建期的 course_home 注入），所以副本里讲次顶栏带「← 返回课程主页」，
        # 课程 demo 形成「主页 → 讲次 → 主页」完整闭环。
        # 读/写都用字节等价的方式（newline='' 不做行尾转换）：除注入点外，副本与
        # 单讲 demo 逐字节相同 —— check_course 的断言 ① 就是这么比对的。
        raw = open(src_prod, 'rb').read().decode('utf-8')
        text = inject_course_home(raw, '../index.html')
        with open(os.path.join(dst_dir, 'index.html'), 'w',
                  encoding='utf-8', newline='') as f:
            f.write(text)
        with open(os.path.join(dst_dir, 'config.json'), 'w', encoding='utf-8') as f:
            f.write(json.dumps(lecture_config(lang, brand), ensure_ascii=False, indent=2) + '\n')
        print('  讲次 %s ← docs/%s/index.html（标题：%s）+ 返回入口' % (lcdir, OUTDIR[lang], brand))
    sh([sys.executable, os.path.join(HERE, 'course_init.py'), COURSE_DIR,
        '--name', COURSE_NAME, '--summary', COURSE_SUMMARY])
    sh([sys.executable, os.path.join(HERE, 'run_course.py'), COURSE_DIR, '--sync', '--no-probe'])
    print('  ✔ 课程入口已生成：docs/demo-course/index.html')


def check_course(fails):
    """课程 demo 的两条忠实性断言。

    ① 讲次副本 == 当前单讲 demo **经同一注入转换后**（逐字节）—— 防「单讲更新了、
       课程 demo 还停在上一次」；转换 = `inject_course_home(…, '../index.html')`
       （与 build_course / build.py 共用同一实现，所以它的行为本身也被这条锁住）；
    ② 课程层五个产物能由「讲次副本 + course.json」重跑出来、逐字节一致 ——
       可比是因为 `long_path` 会把临时目录的 8.3 短名展开（否则 relpath 两侧一长一短，
       `course.json` 里的 outline 路径会算出 `../../../../SHENYU~1/...` 而假红）。
    """
    for lcdir, lang, _ in COURSE_LECTURES:
        a = os.path.join(KIT, 'docs', OUTDIR[lang], 'index.html')
        b = os.path.join(COURSE_DIR, lcdir, 'index.html')
        want = inject_course_home(open(a, 'rb').read().decode('utf-8'),
                                  '../index.html').encode('utf-8') \
            if os.path.exists(a) else b''
        same = (os.path.exists(a) and os.path.exists(b)
                and want == open(b, 'rb').read())
        print('  讲次副本 == docs/%s/index.html（经返回入口注入）: %s'
              % (OUTDIR[lang], '✔' if same else '✘'))
        if not same:
            fails.append('course/' + lcdir)

    bad = []
    tmp = tempfile.mkdtemp(prefix='coursedemo-')
    try:
        dst = os.path.join(tmp, 'course')
        shutil.copytree(COURSE_DIR, dst)
        sh([sys.executable, os.path.join(HERE, 'run_course.py'), dst, '--sync', '--no-probe'])
        for rel in COURSE_FILES:
            pa, pb = os.path.join(COURSE_DIR, rel), os.path.join(dst, rel)
            if not (os.path.exists(pa) and os.path.exists(pb)):
                bad.append(rel + '（缺文件）')
            elif open(pa, 'rb').read() != open(pb, 'rb').read():
                bad.append(rel)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('  课程层五产物可重建且逐字节一致: %s%s'
          % ('✔' if not bad else '✘', '' if not bad else '　不一致：' + '、'.join(bad)))
    if bad:
        fails.append('course（%d 个文件不一致）' % len(bad))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    force = '--force' in sys.argv
    check = '--check' in sys.argv
    want = [d for d in DEMOS if not args or d[0] in args]
    want_course = (not args) or ('course' in args)
    if not want and not want_course:
        raise SystemExit(__doc__)

    fails = []
    if want:
        print('原页图: %s（%d 张）' % (THUMBS, len(os.listdir(THUMBS))))
    for lang, outdir, label in want:
        print('\n=== %s demo（examples/demo/%s → docs/%s/）===' % (label, lang, outdir))
        src = prep(lang, force)
        target = os.path.join(KIT, 'docs', outdir, 'index.html')
        if check:
            tmp = os.path.join(KIT, '_selftest', 'demo-%s.html' % lang)
            os.makedirs(os.path.dirname(tmp), exist_ok=True)
            build(src, tmp)
            o_nav, o_body = parts_of(target)
            n_nav, n_body = parts_of(tmp)
            ok_nav, ok_body = (o_nav == n_nav), (o_body == n_body)
            print('  目录 nav  与已入库 demo 一致: %s' % ('✔' if ok_nav else '✘'))
            print('  正文 wrap 与已入库 demo 一致: %s（含原页图）' % ('✔' if ok_body else '✘'))
            if not (ok_nav and ok_body):
                fails.append(lang)
        else:
            for l in build(src).splitlines():
                if l.startswith(('注入缩略图', '命名空间', '输出:', '大小:', '  [warn]')):
                    print('  %s' % l)

    if check:
        if want_course:
            print('\n=== 课程 demo（docs/demo-course/ ← 两份单讲 demo）===')
            check_course(fails)
        print('\n结果：%s' % ('✔ 单讲与课程 demo 都能被重建到与已入库一致' if not fails
                            else '✘ 重建结果与已入库不一致：%s' % '、'.join(fails)))
        sys.exit(1 if fails else 0)

    if want_course:
        print('\n=== 课程 demo（docs/demo-course/ ← 两份单讲 demo）===')
        build_course()

    print('\n完成。产物：docs/demo/index.html、docs/demo-en/index.html、docs/demo-course/index.html')
    print('下一步（改过 assets/ 后必做）：')
    print('  node scripts/check_math.js "docs/demo/index.html" "examples/demo/zh/_katex/katex.min.js"')
    print('  python scripts/check_ui.py "docs/demo/index.html"')
    print('  python scripts/probe.py "docs/demo/index.html" templates/probe_find.js')
    print('  python scripts/probe.py "docs/demo-course/index.html" templates/probe_course.js')
    print('  python scripts/shoot_previews.py            # 预览图要跟着 demo 一起更新')
    print('  python scripts/build_demo.py --check        # 最后确认可重建')


if __name__ == '__main__':
    main()
