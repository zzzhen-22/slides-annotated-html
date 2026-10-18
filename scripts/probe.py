#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""无头跑一段探针 JS 并把**结果读回来**（shot.py 只能出图，这个读 DOM）。

用法：
    python probe.py <输出.html> <探针.js> [--profile 名字] [--wait 20000] [--keep]

    --profile  复用同一个浏览器 profile（**测 localStorage 持久化 / 重新打开页面**时必须用）：
               第 1 跑写数据，第 2 跑换一个探针读数据，两次都要传同一个名字。
    --wait     --virtual-time-budget 值（毫秒），默认 20000。
    --keep     保留中间产物（isolated.html）便于人工打开排查。

约定：探针脚本自己在结束时把页面清空，只留
      <pre id="__r">要回传的文本</pre>
      （直接改 document.head/body 的 innerHTML 即可，见 references/pitfalls.md 第 23 条）。
      **判定回传**：探针以 `RESULT: PASS` / `RESULT: FAIL` 收尾（probe_doc.js 例外，
      它只报数据不打判定）；出现 `RESULT: FAIL` 时本脚本退出码为 **1** —— 这样
      run_all / run_course 等按退出码判步骤的调用方，才能真正看见探针红了
      （2026-10-17 实测的假绿：课程探针在真实大课件上 FAIL，run_course 却照报 ✔）。

为什么需要它：截图只能看「长得对不对」，看不了「结构有没有被改坏」（例如
划线把 <td> 搬进 <mark>、表格 tr/td 数量变化）。DOM 断言必须靠这个。

坑：
    · 必须带 --user-data-dir + --no-first-run，否则截到 Edge 首次运行弹窗
    · profile 目录要落在系统临时目录（Chromium 在工作盘上创建 profile 会静默失败）
    · 取结果必须 **rfind** 而不是 find —— 注入的 <script> 源码在 DOM dump 里
      不会被转义，若探针抛异常没来得及清空 body，find 会从脚本源码里抠出一段垃圾
    · 命令行里带中文文件名会偶发触发沙箱异常 → 路径尽量由脚本内部给出
    · 浏览器输出**必须落临时文件，不许走管道**（2026-10-17 实测：Chrome 的幽灵
      子进程占住 stdout 管道不松手时，capture_output 的读端在超时杀进程后仍等
      EOF，整体挂死 7m20s；改文件后读端永远不被谁卡住，见 pitfalls 第 54 条）
"""
import argparse
import ctypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kitpath  # noqa: E402


def find_browser():
    """浏览器探测统一交给 kitpath：环境变量 KIT_BROWSER → PATH → 常见安装位置。"""
    return kitpath.browser_exe()


def long_path(p):
    """展开 8.3 短路径 —— Chromium 在短路径 profile 下会静默失败（退出码 0、无输出）。"""
    if os.name != 'nt':
        return p
    try:
        buf = ctypes.create_unicode_buffer(32768)
        n = ctypes.windll.kernel32.GetLongPathNameW(str(p), buf, 32768)
        if 0 < n < 32768:
            return buf.value
    except Exception:  # noqa: BLE001
        pass
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('html')
    ap.add_argument('probe')
    ap.add_argument('--profile', default=None)
    ap.add_argument('--wait', type=int, default=20000)
    ap.add_argument('--keep', action='store_true')
    ap.add_argument('--hash', default=None,
                    help='打开时附带的 URL hash（不含 #），用来测深链，如 --hash "q=残差&p=p51"')
    a = ap.parse_args()

    src = os.path.abspath(a.html)
    js = open(os.path.abspath(a.probe), encoding='utf-8').read()
    html = open(src, encoding='utf-8').read()
    html = html.replace('</body>', '<script>\n' + js + '\n</script>\n</body>', 1)

    if a.profile:
        base = long_path(os.path.join(tempfile.gettempdir(), 'lr-probe-' + a.profile))
        os.makedirs(base, exist_ok=True)
        prof = long_path(os.path.join(base, 'ud'))
        tmp = base
    else:
        tmp = long_path(tempfile.mkdtemp(prefix='lrprobe-'))
        prof = os.path.join(tmp, 'ud')

    target = os.path.join(tmp, 'isolated.html')
    open(target, 'w', encoding='utf-8').write(html)
    url = 'file:///' + urllib.parse.quote(target.replace('\\', '/'), safe='/:')
    if a.hash:
        # hash 里的中文/空格要编码，但 `&` `=` 是参数分隔符，必须原样留下
        url += '#' + urllib.parse.quote(str(a.hash).lstrip('#'), safe='&=%/:')

    cmd = [find_browser(), '--headless=new', '--disable-gpu', '--no-sandbox',
           '--no-first-run', '--no-default-browser-check', '--disable-sync',
           '--disable-crash-reporter', '--disable-breakpad',
           '--user-data-dir=%s' % prof,
           '--virtual-time-budget=%d' % a.wait,
           '--window-size=1500,1180']
    # 去提权开关（Windows 必需，理由见 kitpath.browser_flags 的注释：
    # 不加的话 Chromium 会派生去提权子进程、父进程立刻退出，
    # 我们只能抓到「退出码 0 + 0 字节」的假象）。
    cmd += kitpath.browser_flags(find_browser())
    cmd += ['--dump-dom', url]

    # —— 浏览器输出落临时文件，不走管道 ——
    # 管道版（capture_output=True）的坑：Chromium 主进程退出后，它派生的幽灵
    # 子进程可能仍握着 stdout 的写端不关；Python 的读端在等 EOF，于是连
    # 「timeout=300 杀掉子进程」之后读端也照样堵——实测整体挂死 7m20s（2026-10-17）。
    # 落文件后不存在这个问题：浏览器写它的文件，我们结束后打开读就是了，
    # 谁占着句柄都堵不到读取端。文件放在 tmp（isolate.html 同目录），
    # 随 --keep / profile 的既有清理策略一起走，不另留垃圾。
    out_path = os.path.join(tmp, 'dom.txt')
    err_path = os.path.join(tmp, 'stderr.txt')
    rc = None
    try:
        with open(out_path, 'w', encoding='utf-8') as fo, \
                open(err_path, 'w', encoding='utf-8') as fe:
            r = subprocess.run(cmd, stdout=fo, stderr=fe, timeout=300)
            rc = r.returncode
    except subprocess.TimeoutExpired:
        raise SystemExit('探针超时（300s；已产出的部分输出在 %s）' % out_path)

    with open(out_path, encoding='utf-8', errors='replace') as f:
        dom = f.read()
    stderr_tail = ''
    if os.path.exists(err_path):
        with open(err_path, encoding='utf-8', errors='replace') as f:
            stderr_tail = f.read()[-800:]
    key = '<pre id="__r">'
    i = dom.rfind(key)                      # 一定用 rfind，理由见文件头
    if i < 0:
        print('!! 没拿到探针结果 (dom %d bytes, rc=%s)' % (len(dom), rc))
        print('stderr tail:', stderr_tail)
        sys.exit(3)
    j = dom.find('</pre>', i)
    body = dom[i + len(key):j]
    for x, y in (('&lt;', '<'), ('&gt;', '>'), ('&amp;', '&'), ('&quot;', '"')):
        body = body.replace(x, y)
    print(body)

    # 判定行必须反映到退出码：调用方（run_all / run_course 的步骤判定）看的就是它。
    # 只有 RESULT 行首锚定的 FAIL 才算 —— 探针正文里提到这个词不会误解。
    if re.search(r'^RESULT:\s*FAIL\b', body, re.M):
        sys.exit(1)

    if not a.profile and not a.keep:
        shutil.rmtree(tmp, ignore_errors=True)
    elif a.keep:
        print('\n[keep] %s' % target)


if __name__ == '__main__':
    main()
