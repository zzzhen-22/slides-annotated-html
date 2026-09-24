#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""正文符号探针：把成品里用到的**全部非中文符号**排成一页，用来肉眼查缺字（tofu）。

为什么需要它：**「公式里正常、正文里方框」是字体缺字的典型指纹。**
KaTeX 公式在自己的字体里画符号，永远不会缺；而正文走的是 `var(--sans)`
（PingFang SC / Microsoft YaHei / Source Han Sans / Noto CJK），
这一串中文 UI 字体**对「符号用组合附加记号」整段 U+20D0–U+20FF 都没有字形**。
实测最常踩的：拿 U+20D7（组合右箭头）当矢量符号写「J + U+20D7」→ 全是方框。
同类：`&oiint;` 这种非 HTML5 命名实体会原样显示成字面文本（那是另一回事，
`probe_doc.js` 会查）。

用法：
    python scripts/glyph_probe.py <成品.html> [输出目录，默认 _extract]
    # 然后用套件自带的截图工具把它渲染出来，肉眼扫一遍：
    python scripts/shot.py <输出目录>/glyph_probe.html <输出目录>/glyph_probe.png --height 2600 --width 1000

判定标准：**表格里凡显示为方框者，就是本机字体栈缺字**，必须改写：
矢量 → `<b class="vec">J</b>` 加粗；其它符号 → 换成有字形的等价写法或放进 KaTeX 公式。
详见 references/pitfalls.md 第 34 条。
"""
import argparse
import os
import re
import sys
import unicodedata

# 先挖掉所有 script（含 KaTeX 源码与内嵌 base64），再看剩下的可见文本
SCRIPT_RE = re.compile(r'<script[\s\S]*?</script>', re.I)
TAG_RE = re.compile(r'<[^>]*>')
# 中文字体必然支持、不必检查的区段
SKIP_RANGES = (
    (0x2E80, 0x9FFF),    # CJK 汉字
    (0x3000, 0x303F),    # CJK 标点（「」等）
    (0x3040, 0x30FF),    # 假名
    (0xFF00, 0xFFEF),    # 半角/全角形式
    (0xE000, 0xF8FF),    # 私用区
)

CSS = (
    '<style>'
    ':root{--sans:"PingFang SC","Microsoft YaHei","Hiragino Sans GB",'
    '"Source Han Sans SC","Noto Sans CJK SC",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;'
    '--serif:Georgia,"Times New Roman","Songti SC",serif;'
    '--mono:"Cascadia Mono",Consolas,monospace}'
    'body{margin:0;background:#fff;color:#1b2233;font-family:var(--sans);font-size:15px;padding:14px 18px}'
    'table{border-collapse:collapse;width:100%}'
    'td{border:1px solid #dde3ee;padding:3px 8px;vertical-align:middle}'
    '.cp{font-family:var(--mono);font-size:12px;color:#6b7488;white-space:nowrap}'
    '.nm{font-size:12px;color:#3d4759}'
    '.big{font-size:24px;line-height:1.1}'
    '.serif{font-family:var(--serif);font-size:24px}'
    '</style>'
)


def collect(html):
    """返回成品里用到的非中文符号集合（按码位排序）。"""
    txt = TAG_RE.sub('', SCRIPT_RE.sub('', html))
    found = set()
    for ch in txt:
        cp = ord(ch)
        if cp < 0x80:
            continue
        if any(lo <= cp <= hi for lo, hi in SKIP_RANGES):
            continue
        found.add(ch)
    return sorted(found, key=ord)


def build_page(chars, source):
    rows = []
    for ch in chars:
        name = unicodedata.name(ch, '?')[:34].replace('<', '&lt;')
        cp = 'U+%04X' % ord(ch)
        warn = ' style="background:#fdf0ee"' if 0x20D0 <= ord(ch) <= 0x20FF else ''
        rows.append(
            '<tr%s><td class="cp">%s</td><td class="nm">%s</td>'
            '<td class="big">%s</td><td class="big">%s%s</td></tr>'
            % (warn, cp, name, ch * 3, ch, ch)
        )
    return (
        '<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"><title>glyph probe</title>'
        + CSS + '</head><body>'
        '<p style="font-size:13px;color:#6b7488;margin:0 0 4px">'
        '正文符号探针 · 来源：' + source + '</p>'
        '<p style="font-size:13px;color:#6b7488;margin:0 0 10px">'
        '共 ' + str(len(chars)) + ' 种非中文符号（按码位排序）。每组左边连续 3 个、右边单看。'
        '<b>凡显示为方框者即为本机字体栈缺字</b>，必须改写；红底行是组合附加记号 U+20D0–U+20FF，'
        '整段都需要重点看。</p>'
        '<table>' + ''.join(rows) + '</table></body></html>'
    )


def main():
    ap = argparse.ArgumentParser(description='正文符号探针（查缺字 / tofu）')
    ap.add_argument('html', help='成品单文件 HTML')
    ap.add_argument('outdir', nargs='?', default='_extract', help='输出目录，默认 _extract')
    a = ap.parse_args()

    if not os.path.isfile(a.html):
        raise SystemExit('找不到文件：' + a.html)
    html = open(a.html, encoding='utf-8').read()
    chars = collect(html)
    if not chars:
        print('未发现任何非中文符号，无需检查。')
        return 0

    os.makedirs(a.outdir, exist_ok=True)
    out = os.path.join(a.outdir, 'glyph_probe.html')
    open(out, 'w', encoding='utf-8').write(build_page(chars, os.path.basename(a.html)))

    risky = [c for c in chars if 0x20D0 <= ord(c) <= 0x20FF]
    print('非中文符号 %d 种 → %s' % (len(chars), out))
    if risky:
        print('⚠ 其中 %d 种属于组合附加记号 U+20D0–U+20FF（中文 UI 字体普遍缺字形）：%s'
              % (len(risky), ' '.join('U+%04X' % ord(c) for c in risky)))
        print('  正文里表示矢量请改用 <b class="vec">J</b>，见 references/pitfalls.md 第 34 条。')
    else:
        print('✔ 没有组合附加记号（U+20D0–U+20FF）——这一类缺字风险已排除。')
    print('下一步（渲染出来肉眼扫一遍）：\n'
          '  python scripts/shot.py "%s" "%s" --height 2600 --width 1000'
          % (out, os.path.join(a.outdir, 'glyph_probe.png')))
    return 1 if risky else 0


if __name__ == '__main__':
    sys.exit(main())
