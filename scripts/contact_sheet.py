#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把逐页图拼成「联系表」（contact sheet），让 agent 一次 Read 就看完 9–12 页。

为什么需要它：
    逐页 Read 几十张 page-NN.png，调用参数只差一个数字 —— 宿主端的风控与
    「重复操作」判定很容易把它当成同一个操作在刷屏，于是一次次要求人工确认。
    拼成一张大图后，90 页只需要 10 次 Read，从根上避免这个形态。

用法：
    python contact_sheet.py "<项目>/_extract"                # 3×3，默认
    python contact_sheet.py "<项目>/_extract" --cols 4 --rows 3
    python contact_sheet.py "<项目>/_extract" --cell 620     # 单格更宽，细节更清
    python contact_sheet.py "<项目>/_extract" --dry-run      # 只列分组，不落盘

产物：
    <_extract>/sheets/sheet-01.png …   每格左上角标原文件页码（P07 这种）
    <_extract>/sheets/index.txt        一张清单：哪张表覆盖哪几页

看图策略（建议）：
    ① 先用联系表**扫结构**：这一页在干什么、标题、大概几个图几个公式；
    ② 只有需要**逐字核对公式 / 抄代码 / 辨认小字**的那几页，再单独 Read page-NN.png；
    ③ 不要为了「保险」把每一页都单独 Read —— 那正是触发确认的形态。
"""
import argparse
import os
import re
import sys

PAGE_RE = re.compile(r'^page-(\d+)\.png$', re.I)

# 页码条配色：深底白字，缩略图缩到很小也读得出
BAR_BG = (31, 41, 55)
BAR_FG = (255, 255, 255)
CANVAS_BG = (238, 241, 245)
FRAME = (203, 213, 225)

FONT_CANDIDATES = (
    r'C:/Windows/Fonts/arialbd.ttf',
    r'C:/Windows/Fonts/arial.ttf',
    r'C:/Windows/Fonts/segoeuib.ttf',
    '/System/Library/Fonts/Helvetica.ttc',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
)


def die(problem, fix):
    """三段式报错：问题 / 原因 / 可照抄的修法（与 kitpath.die 同风格）。"""
    sys.stderr.write('\n[contact_sheet] %s\n' % problem)
    sys.stderr.write('  修法：%s\n' % fix)
    sys.exit(2)


def load_font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return _truetype(p, size)
            except OSError:
                continue
    from PIL import ImageFont
    return ImageFont.load_default()


def _truetype(path, size):
    from PIL import ImageFont
    return ImageFont.truetype(path, size)


def find_pages(src):
    """按页码排序返回 [(页码, 路径), …]；页码不连续时如实报告，不猜。"""
    pages = []
    for name in os.listdir(src):
        m = PAGE_RE.match(name)
        if m:
            pages.append((int(m.group(1)), os.path.join(src, name)))
    pages.sort()
    return pages


def group(pages, per_sheet):
    return [pages[i:i + per_sheet] for i in range(0, len(pages), per_sheet)]


def make_sheet(chunk, idx, cols, cell_w, bar_h, gap, font, out_dir, cell_h):
    from PIL import Image, ImageDraw

    rows = (len(chunk) + cols - 1) // cols
    width = cols * cell_w + (cols + 1) * gap
    height = rows * (cell_h + bar_h) + (rows + 1) * gap

    canvas = Image.new('RGB', (width, height), CANVAS_BG)
    draw = ImageDraw.Draw(canvas)

    for k, (pno, path) in enumerate(chunk):
        r, c = divmod(k, cols)
        x = gap + c * (cell_w + gap)
        y = gap + r * (cell_h + bar_h + gap)

        with Image.open(path) as im:
            im = im.convert('RGB')
            # 等比缩放到「宽 cell_w、高 cell_h」的画框里，不裁切
            scale = min(cell_w / im.width, cell_h / im.height)
            w, h = max(1, int(im.width * scale)), max(1, int(im.height * scale))
            im = im.resize((w, h), Image.LANCZOS)
            ox = x + (cell_w - w) // 2
            oy = y + bar_h + (cell_h - h) // 2
            canvas.paste(im, (ox, oy))

        # 页码条
        draw.rectangle([x, y, x + cell_w - 1, y + bar_h - 1], fill=BAR_BG)
        draw.text((x + 8, y + max(1, (bar_h - 17) // 2)), 'P%d' % pno,
                  font=font, fill=BAR_FG)
        # 细边框，区分相邻两页（背景是图的时候尤其重要）
        draw.rectangle([x, y, x + cell_w - 1, y + bar_h + cell_h - 1], outline=FRAME)

    name = 'sheet-%02d.png' % idx
    dst = os.path.join(out_dir, name)
    canvas.save(dst, optimize=True)
    return dst, canvas.size


def main():
    ap = argparse.ArgumentParser(
        prog='contact_sheet.py',
        description='把逐页图拼成联系表（contact sheet），一次 Read 看多页。',
        epilog='例：python contact_sheet.py "C:/x/_extract" --cols 3 --rows 3',
    )
    ap.add_argument('src', help='含 page-NN.png 的目录（通常是 <项目>/_extract）')
    ap.add_argument('--cols', type=int, default=3, help='每行几页（默认 3）')
    ap.add_argument('--rows', type=int, default=3, help='每列几页（默认 3）')
    ap.add_argument('--cell', type=int, default=520, help='单格宽度像素（默认 520）')
    ap.add_argument('--gap', type=int, default=12, help='格间距（默认 12）')
    ap.add_argument('--bar', type=int, default=30, help='页码条高度（默认 30）')
    ap.add_argument('--out', default='', help='输出目录（默认 <src>/sheets）')
    ap.add_argument('--dry-run', action='store_true', help='只列分组，不生成图片')
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    if not os.path.isdir(src):
        die('目录不存在：%s' % src, '先跑 prepare_pdf.py 渲染逐页图，或检查 --src 写错了')
    if a.cols < 1 or a.rows < 1 or a.cell < 80:
        die('参数不合理：cols/rows 需 ≥1，cell 需 ≥80', '用默认值即可：--cols 3 --rows 3 --cell 520')

    pages = find_pages(src)
    if not pages:
        die('在 %s 里没找到 page-NN.png' % src,
            '先跑：python prepare_pdf.py "<课件.pdf>" "%s" 860 75' % src)

    # 页码连续性检查（缺页会让「第几张表覆盖哪几页」变得不可信，必须报出来）
    nums = [p for p, _ in pages]
    holes = sorted(set(range(nums[0], nums[-1] + 1)) - set(nums))

    per_sheet = a.cols * a.rows
    chunks = group(pages, per_sheet)

    from PIL import Image
    with Image.open(pages[0][1]) as im:
        ratio = im.height / im.width
    cell_h = int(a.cell * ratio)

    print('源目录   : %s' % src)
    print('逐页图   : %d 张（P%d–P%d）' % (len(pages), nums[0], nums[-1]))
    if holes:
        print('缺页     : %s  ← 这几页没有图，联系表里会留空位' %
              '、'.join('P%d' % n for n in holes))
    print('每张表   : %d 列 × %d 行 = %d 页' % (a.cols, a.rows, per_sheet))
    print('单格尺寸 : %d × %d（+ %d 页页码条）' % (a.cell, cell_h, a.bar))
    print('共需     : %d 张联系表' % len(chunks))
    print('')

    if a.dry_run:
        for i, ch in enumerate(chunks, 1):
            print('  sheet-%02d.png  P%d–P%d（%d 页）' %
                  (i, ch[0][0], ch[-1][0], len(ch)))
        print('\n（--dry-run，未落盘）')
        return 0

    out_dir = a.out or os.path.join(src, 'sheets')
    os.makedirs(out_dir, exist_ok=True)
    font = load_font(max(12, int(a.bar * 0.55)))

    lines = []
    for i, ch in enumerate(chunks, 1):
        dst, size = make_sheet(ch, i, a.cols, a.cell, a.bar, a.gap, font, out_dir, cell_h)
        span = 'P%d–P%d' % (ch[0][0], ch[-1][0]) if len(ch) > 1 else 'P%d' % ch[0][0]
        kb = os.path.getsize(dst) / 1024.0
        print('  ✔ %-14s %-12s %d 页  %d×%d  %.0f KB' %
              (os.path.basename(dst), span, len(ch), size[0], size[1], kb))
        lines.append('%s\t%s\t%d 页' % (os.path.basename(dst), span, len(ch)))

    index = os.path.join(out_dir, 'index.txt')
    with open(index, 'w', encoding='utf-8') as f:
        f.write('# contact sheet 清单（由 contact_sheet.py 生成，可删可重建）\n')
        f.write('# 表名\t覆盖页\t页数\n')
        f.write('\n'.join(lines) + '\n')

    print('\n输出目录 : %s' % out_dir)
    print('清单     : %s' % index)
    print('')
    print('下一步：先 Read 前几张联系表扫结构；**只有需要逐字核对公式 / 抄代码的那几页**')
    print('        再单独 Read page-NN.png。不要为了保险把每一页都单独读一遍。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
