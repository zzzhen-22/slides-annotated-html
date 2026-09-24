#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 KaTeX 打包成「完全离线」的 CSS：字体全部转成 base64 data URI。

用法：
    python katex_offline.py <输出目录> [katex版本]

产物：
    <输出目录>/katex.offline.css   —— 字体已内嵌，无任何外部引用
    <输出目录>/katex.min.js        —— 渲染引擎，直接内联进 HTML
    <输出目录>/katex.src.json      —— 记录版本与校验信息

之后 build.py 会自动从这里取用。
"""
import base64
import json
import os
import re
import subprocess
import sys
import tarfile

MIRRORS = [
    'https://registry.npmmirror.com/katex/-/katex-%s.tgz',
    'https://registry.npmjs.org/katex/-/katex-%s.tgz',
]


def fetch(version, workdir):
    tgz = os.path.join(workdir, 'katex-%s.tgz' % version)
    if os.path.exists(tgz) and os.path.getsize(tgz) > 100000:
        print('[skip] 已存在 %s' % tgz)
        return tgz
    last = None
    for tpl in MIRRORS:
        url = tpl % version
        print('[get ] %s' % url)
        try:
            subprocess.check_call(['curl', '-sL', '--max-time', '120', '-o', tgz, url])
            if os.path.getsize(tgz) > 100000:
                return tgz
            last = '体积异常'
        except Exception as e:  # noqa: BLE001
            last = str(e)
    raise SystemExit('下载 KaTeX 失败：%s' % last)


def build(dist_dir, outdir):
    css_path = os.path.join(dist_dir, 'katex.min.css')
    css = open(css_path, encoding='utf-8').read()

    # ① src 列表里只保留 woff2（woff/ttf 会让体积翻四倍且没必要）
    css = re.sub(
        r'src:([^;}]*woff2[^;}]*)',
        lambda m: 'src:' + ','.join(p for p in m.group(1).split(',') if '.woff2' in p),
        css,
    )

    # ② woff2 → data URI
    names = sorted(set(re.findall(r'url\(fonts/([A-Za-z0-9_.-]+\.woff2)\)', css)))
    if not names:
        raise SystemExit('CSS 里没找到 woff2 引用，KaTeX 版本可能变了，请检查')
    for n in names:
        p = os.path.join(dist_dir, 'fonts', n)
        b64 = base64.b64encode(open(p, 'rb').read()).decode('ascii')
        css = css.replace('url(fonts/%s)' % n, 'url(data:font/woff2;base64,%s)' % b64)
    if 'fonts/' in css:
        raise SystemExit('仍有未内嵌的字体引用，请检查替换规则')

    out_css = os.path.join(outdir, 'katex.offline.css')
    open(out_css, 'w', encoding='utf-8').write(css)

    js_src = os.path.join(dist_dir, 'katex.min.js')
    js = open(js_src, encoding='utf-8').read()
    if '</script' in js.lower():
        raise SystemExit('katex.min.js 含 </script，内联前必须转义')
    out_js = os.path.join(outdir, 'katex.min.js')
    open(out_js, 'w', encoding='utf-8').write(js)

    meta = {'fonts': len(names), 'css_bytes': len(css), 'js_bytes': len(js)}
    json.dump(meta, open(os.path.join(outdir, 'katex.src.json'), 'w'), indent=2)
    print('[ok  ] %s  (字体 %d 个内嵌, CSS %.1f KB, JS %.1f KB)'
          % (out_css, meta['fonts'], len(css) / 1024, len(js) / 1024))


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    outdir = os.path.abspath(sys.argv[1])
    version = sys.argv[2] if len(sys.argv) > 2 else '0.16.11'
    os.makedirs(outdir, exist_ok=True)

    tgz = fetch(version, outdir)
    with tarfile.open(tgz) as tf:
        try:
            tf.extractall(outdir, filter='data')   # Python 3.12+，防路径穿越
        except TypeError:                          # 老版本没有 filter 参数
            tf.extractall(outdir)
    dist = os.path.join(outdir, 'package', 'dist')
    if not os.path.isdir(dist):
        raise SystemExit('解包后没找到 package/dist，请检查 tgz')
    build(dist, outdir)


if __name__ == '__main__':
    main()
