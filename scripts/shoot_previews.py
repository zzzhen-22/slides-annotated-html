#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""重截 README 里那几张预览图（docs/images/*.png）。

**为什么要有这个脚本**：预览图是这个仓库的门面，它必须和 `docs/demo/` 的实际产物一致；
但这几张图一直是**手工截的**、没留脚本，于是悄悄过期了很久 —— 2026-10-16 重截时才发现
旧图里工具栏还没有字号按钮（A−/100%/A＋）、左侧目录也还没有「本讲要点」这一条。
把取景参数固化下来，重跑即可与当前产物对齐，不必再靠记忆还原构图。

用法：
    python scripts/shoot_previews.py              # 四张全截
    python scripts/shoot_previews.py hero notes   # 只截指定的几张
    python scripts/shoot_previews.py --list       # 只列出四张图与它们的取景参数

四张图（尺寸沿用旧图，README 的排版不用动）：

    hero.png      1500×1500  单讲 demo：p07 正文 + 左目录 + 右缩略图（`--section p07`）
    overview.png  1500×1250  单讲 demo：「本节概述」卡（`--section ov1`）
    notes.png     1500×1500  单讲 demo：p07 + 划词标记 → 笔记抽屉（注入两条示例笔记）
    course.png    1500×2030  课程合集 demo：五区块全貌（截全页后自动裁到内容底）

前置条件（与本机三条硬约束一致）：
    · 两份 demo 产物已存在：先跑 `python scripts/build_demo.py zh && ... en`；
      课程 demo 产物：`python scripts/run_course.py docs/demo-course --sync`
    · node 在 PATH、KIT_BROWSER 指向 Chrome（Edge 在无头下空转，见 pitfalls）

⚠ `course.png` 的注入脚本会把「要点总结」的讲次块**收起来**再截图 —— 这是课程页本来
   就有的交互（`.klec` 是 `details`），不是为截图造的假状态；不收起的话整页三米长，
   缩到 README 宽度后正文根本看不清。
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# ── 注入脚本：截图前先把页面调到一个「有代表性的稳定状态」 ──────────────────
# 笔记抽屉那张要注入两条真实笔记（空抽屉什么都说明不了）；课程页那张要收起要点块。
JS_NOTES = """\
/* 预览图用：造两条示例笔记并打开抽屉。
   必须走和真实入口同一条路 —— __doc.addNote() 内部就是 locate → canon → wrapRange，
   手搓 mark 会得到「测试绿、真实入口红」的假象（见 site.js 里那段注释）。 */
window.addEventListener('load', function () {
  setTimeout(function () {
    var D = window.__doc;
    if (!D || !D.addNote) return;
    try {
      D.addNote('p07', '还没看数据时，你认为哪个模型更可信',
                '分子是「数据下模型有多可信」，分母只是归一化用的证据。');
      D.addNote('p07', '贝叶斯法则在机器学习中的应用', '');
      D.notes.openDrawer(false);
    } catch (e) { /* 引文对不上就不画注释，别让截图悄悄变成别的样子 */ }
  }, 1200);
});
"""

JS_COURSE = """\
/* 预览图用：把「要点总结」的讲次块收起来，让五个区块能在一屏里同时看到。 */
window.addEventListener('load', function () {
  setTimeout(function () {
    var ds = document.querySelectorAll('details.klec');
    for (var i = 0; i < ds.length; i++) ds[i].open = false;
    window.scrollTo(0, 0);
  }, 1200);
});
"""

SHOTS = [
    dict(name='hero', src='docs/demo/index.html', w=1500, h=1500,
         section='p07', js=None, trim=False,
         desc='单讲 demo：逐页对照（p07 正文 + 左目录 + 右缩略图）'),
    dict(name='overview', src='docs/demo/index.html', w=1500, h=1250,
         section='ov1', js=None, trim=False,
         desc='单讲 demo：「本节概述」卡（本节主线 / 必记记号 / 易混点 / 自检）'),
    dict(name='notes', src='docs/demo/index.html', w=1500, h=1500,
         section='p07', js=JS_NOTES, trim=False,
         desc='单讲 demo：划词标记 → 笔记抽屉（带备注、跳转、导出 Markdown）'),
    dict(name='course', src='docs/demo-course/index.html', w=1500, h=2200,
         section=None, js=JS_COURSE, trim=True,
         desc='课程合集 demo：五区块全貌（地图 / 要点 / 检索 / 术语 / 进度）'),
]


def trim_bottom(png, tol=18, min_gap=2):
    """把截图底部多出来的背景裁掉 —— 截全页时给的 --height 是个"够高就行"的估值，
    直接用会在图底留一大片空背景。这里从下往上找最后一个"与背景不同"的行。"""
    try:
        from PIL import Image
    except ImportError:
        print('    （没装 Pillow，跳过裁剪）')
        return None
    im = Image.open(png).convert('RGB')
    bg = im.getpixel((5, im.height - 5))
    last = -1
    px = im.load()
    for y in range(im.height - 1, -1, -1):
        hit = 0
        for x in range(0, im.width, 7):
            p = px[x, y]
            if abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2]) > tol:
                hit += 1
                if hit > 3:
                    break
        if hit > 3:
            last = y
            break
    if last < 0:
        return None
    h = min(im.height, last + min_gap + 1)
    if h >= im.height:
        return im.size
    im.crop((0, 0, im.width, h)).save(png)
    return (im.width, h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('names', nargs='*', help='要重截的图名（不带 .png）；不给就全截')
    ap.add_argument('--list', action='store_true', help='只列出取景参数，不截')
    ap.add_argument('--out', default=os.path.join(KIT, 'docs', 'images'),
                    help='输出目录（默认 docs/images）')
    ap.add_argument('--wait', type=int, default=9000, help='透传给 shot.py 的 --wait')
    a = ap.parse_args()

    todo = [s for s in SHOTS if not a.names or s['name'] in a.names]
    unknown = [n for n in a.names if n not in {s['name'] for s in SHOTS}]
    if unknown:
        raise SystemExit('不认识的图名：%s（可选：%s）'
                         % (', '.join(unknown), ', '.join(s['name'] for s in SHOTS)))

    if a.list:
        for s in SHOTS:
            print('%-9s %-26s %4d×%-5d %s' % (
                s['name'] + '.png', s['src'], s['w'], s['h'], s['desc']))
        return

    os.makedirs(a.out, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='previewshoot-')
    rc_all = 0
    try:
        for s in todo:
            src = os.path.join(KIT, s['src'])
            if not os.path.exists(src):
                print('✘ %s：源产物不存在 → %s' % (s['name'], s['src']))
                print('    先重建 demo（见本脚本 docstring 的前置条件）')
                rc_all = 1
                continue
            out = os.path.join(a.out, s['name'] + '.png')
            cmd = [sys.executable, os.path.join(HERE, 'shot.py'), src, out,
                   '--width', str(s['w']), '--height', str(s['h']),
                   '--wait', str(a.wait)]
            if s['section']:
                cmd += ['--section', s['section']]
            if s['js']:
                jsp = os.path.join(tmp, s['name'] + '.js')
                open(jsp, 'w', encoding='utf-8').write(s['js'])
                cmd += ['--script', jsp]
            print('▶ %-9s %s' % (s['name'] + '.png', s['desc']))
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0 or not os.path.exists(out):
                print('  ✘ 截图失败：%s' % ((r.stdout or '') + (r.stderr or ''))[-400:])
                rc_all = 1
                continue
            if s['trim']:
                size = trim_bottom(out)
                # 注意：size 是 (w, h) 元组，直接 '%s' % size 会被当成多参数 → TypeError
                print('  裁剪后尺寸：%s' % ((size or '（未裁）'),))
            from PIL import Image
            iw, ih = Image.open(out).size
            print('  ✔ %d×%d  %.0f KB' % (iw, ih, os.path.getsize(out) / 1024.0))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print('结果：%s' % ('✔ 全部完成' if rc_all == 0 else '✘ 有失败项'))
    sys.exit(rc_all)


if __name__ == '__main__':
    main()
