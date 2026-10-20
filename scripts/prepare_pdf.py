#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PDF / PPT 课件 → 逐页缩略图 + 文字层 + 单页大图（供人工核对）。

用法：
    python prepare_pdf.py <pdf> <输出目录> [缩略图宽度] [缩略图质量]

    位置参数按上面的顺序解析（`init_project.py` 生成的重建命令依赖它，
    所以永远是 `pdf outdir [宽] [质]`，不要调换）。`--help` 里有完整说明。

产物（输出目录下）：
    page-01.png ...            逐页整图渲染，**给 agent 自己逐页看**（这一步不能省）
    thumb_01.jpg ...           压缩后的缩略图，build.py 会 base64 内嵌
    raw.txt                    每页文字层，用 ==== PAGE n ==== 分隔
    chroma.txt                 每页图片对象数量（判断哪些页是纯图页）
    report.txt                 概览：页数、缩略图体积、疑似纯图页

为什么还要 page-*.png？
    PPT 导出的 PDF 常把公式做成图片或分行文本，文字层里符号会乱码
    （例如 ¡ 其实是减号、¼ 其实是 π）。**只看 get_text() 会讲错内容**，
    必须渲染成图逐页目视确认。这里一次性把图准备好，避免反复调用。
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kitpath  # noqa: E402

kitpath.require_deps('pymupdf', 'PIL')   # 缺包时给出 pip 命令，而不是 ModuleNotFoundError

import pymupdf  # noqa: E402
from PIL import Image  # noqa: E402


def main():
    ap = kitpath.arg_parser(
        'prepare_pdf.py',
        description='把课件 PDF 渲染成「逐页大图 + 内嵌缩略图 + 文字层」，供逐页目视核对。',
        epilog='产物：page-NN.png（逐页大图）/ thumb_NN.jpg（内嵌用）/ raw.txt / chroma.txt / report.txt\n'
               '位置参数顺序固定为 pdf outdir [宽] [质]（init_project.py 生成的重建命令依赖它）。')
    ap.add_argument('pdf', metavar='课件.pdf')
    ap.add_argument('outdir', metavar='输出目录')
    ap.add_argument('thumb_w', nargs='?', type=int, default=860, metavar='缩略图宽度',
                    help='缩略图宽度像素（默认 860；影响产物体积）')
    ap.add_argument('quality', nargs='?', type=int, default=75, metavar='JPEG质量',
                    help='缩略图 JPEG 质量（默认 75）')
    a = ap.parse_args()

    pdf = os.path.abspath(a.pdf)
    outdir = os.path.abspath(a.outdir)
    thumb_w, quality = a.thumb_w, a.quality
    if not os.path.exists(pdf):
        kitpath.die('找不到课件文件：%s' % pdf,
                    '路径不对，或文件已经被挪走/改名。',
                    '确认路径后重跑：python scripts/prepare_pdf.py "<课件.pdf>" "<输出目录>"')
    os.makedirs(outdir, exist_ok=True)

    doc = pymupdf.open(pdf)
    n = doc.page_count
    texts, chroma, sizes, blobs = [], [], [], []

    for i, page in enumerate(doc):
        num = i + 1
        # 整页图（供目视核对）
        pix = page.get_pixmap(dpi=160)
        pix.save(os.path.join(outdir, 'page-%02d.png' % num))

        # 缩略图（供内嵌）
        img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        h = int(round(pix.height * thumb_w / pix.width))
        img = img.resize((thumb_w, h), Image.LANCZOS)
        tp = os.path.join(outdir, 'thumb_%02d.jpg' % num)
        img.save(tp, 'JPEG', quality=quality, optimize=True, progressive=True)
        sizes.append(os.path.getsize(tp))

        texts.append('===== PAGE %d =====\n%s' % (num, page.get_text().rstrip()))
        # 图片对象数：0 通常意味着纯文字页，>=1 要多留意
        try:
            chroma.append(len(page.get_images(full=True)))
        except Exception:  # noqa: BLE001
            chroma.append(-1)

    open(os.path.join(outdir, 'raw.txt'), 'w', encoding='utf-8').write('\n'.join(texts))
    open(os.path.join(outdir, 'chroma.txt'), 'w', encoding='utf-8').write(
        '\n'.join('P%d\t%d' % (i + 1, c) for i, c in enumerate(chroma)))

    total = sum(sizes)
    lines = [
        '源文件      : %s' % pdf,
        '总页数      : %d' % n,
        '图片对象>0  : %s' % ', '.join('P%d(%d)' % (i + 1, c)
                                       for i, c in enumerate(chroma) if c > 0) or '(无)',
        '缩略图宽度  : %dpx  quality=%d' % (thumb_w, quality),
        '缩略图总体积: %.2f MB  →  base64 后约 %.2f MB' % (total / 1048576, total * 1.34 / 1048576),
        '最大/最小   : %.1f KB / %.1f KB' % (max(sizes) / 1024, min(sizes) / 1024),
        '',
        '【下一步】打开 page-01.png … 逐页看一遍，把每页的公式与图示记成笔记，',
        '         然后再动笔写讲解。**不要只依赖 raw.txt。**',
    ]
    report = '\n'.join(lines)
    open(os.path.join(outdir, 'report.txt'), 'w', encoding='utf-8').write(report)
    print(report)
    # 顺便探测 pdftotext 是否可用（备选抽取通道，一般用不上）
    try:
        subprocess.call(['pdftotext', '-v'], stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
    except Exception:  # noqa: BLE001
        pass


if __name__ == '__main__':
    main()
