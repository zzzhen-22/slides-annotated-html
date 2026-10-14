#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""重建仓库里的两份在线 demo（`docs/demo/` 与 `docs/demo-en/`）。

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
    python scripts/build_demo.py            # 两份都重建
    python scripts/build_demo.py zh         # 只重建中文
    python scripts/build_demo.py --check    # 只校验：重建到临时文件，与已入库的 demo 比对

`--check` 比对**目录（nav）与正文（wrap，含原页图）**：两者必须与已入库的 demo
逐字节一致——它们都来自源工程，重建不该改动它们。**只有外壳（CSS/JS/顶栏/页脚）
与 `DOC_NS` 会变，那是预期的**：前者正是「用当前版本重建」的目的，
后者在脚本区、不在比对范围内。
"""
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)

DEMOS = [('zh', 'demo', '中文'), ('en', 'demo-en', '英文')]
THUMBS = os.path.join(KIT, 'examples', 'demo', '_thumbs')


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


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    force = '--force' in sys.argv
    check = '--check' in sys.argv
    want = [d for d in DEMOS if not args or d[0] in args]
    if not want:
        raise SystemExit(__doc__)

    print('原页图: %s（%d 张）' % (THUMBS, len(os.listdir(THUMBS))))
    fails = []
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
        print('\n结果：%s' % ('✔ 两份 demo 都能被源工程忠实重建' if not fails
                            else '✘ 重建结果与已入库 demo 不一致：%s' % '、'.join(fails)))
        sys.exit(1 if fails else 0)
    print('\n完成。两份产物已写回 docs/demo/index.html 与 docs/demo-en/index.html。')
    print('下一步（改过 assets/ 后必做）：')
    print('  node scripts/check_math.js "docs/demo/index.html" "examples/demo/zh/_katex/katex.min.js"')
    print('  python scripts/check_ui.py "docs/demo/index.html"')
    print('  python scripts/probe.py "docs/demo/index.html" templates/probe_find.js')


if __name__ == '__main__':
    main()
