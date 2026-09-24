#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""无 GUI 验证本地 HTML 的渲染效果：用系统自带 Edge/Chrome 无头截图。

用法：
    python shot.py <html> <out.png> [--section p52] [--width 1500] [--height 1180]
                   [--wait 9000] [--script run.js] [--full]

    --section  只显示该 id 的区块（其余内容 display:none），
               用来绕过「无头截图里 #fragment 不生效」这个坑。
    --script   在 </body> 前注入一段脚本，用来触发交互后再截图
               （例如 window.__doc.openDrawer() 打开笔记抽屉）。
    --full     截整页（配合 --height 给一个很大的值即可，一般不用）

要点（都是踩过的坑）：
    · 必须带 --user-data-dir + --no-first-run，否则截到 Edge 首次运行隐私弹窗
    · URL 必须是 file:///D:/... （三个斜杠），盘符冒号不能变成 %3A
    · agent-browser 未安装时这是性价比最高的验证手段：零安装、不弹窗
    · 注入了 --script 时，页面状态在截图前才变化，建议 --wait 给足（≥9000）
"""
import argparse
import glob
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
    """浏览器探测统一交给 kitpath：环境变量 KIT_BROWSER → PATH → 常见安装位置。
    不再依赖写死的 Program Files 路径，方便整套目录拷到别的机器。"""
    return kitpath.browser_exe()


def long_path(p):
    """把 8.3 短路径（如 C:\\Users\\SHENYU~1\\...）展开成长路径。

    实测：Chromium 在 8.3 短路径的 --user-data-dir 下会**静默失败**
    （退出码 0、无任何输出、不生成截图）。tempfile.gettempdir() 在部分
    Windows 环境下恰好返回短路径，所以要在这里兜一层。
    """
    if os.name != 'nt':
        return p
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(32768)
        n = ctypes.windll.kernel32.GetLongPathNameW(str(p), buf, 32768)
        if 0 < n < 32768:
            return buf.value
    except Exception:  # noqa: BLE001
        pass
    return p


def build_cmd(browser, prof, out, url, size, wait, mode):
    return [
        browser,
        '--headless=' + mode, '--disable-gpu', '--no-sandbox',
        '--no-first-run', '--no-default-browser-check', '--disable-sync',
        '--disable-crash-reporter', '--disable-breakpad',
        '--user-data-dir=%s' % prof,
        '--hide-scrollbars',
        '--virtual-time-budget=%d' % wait,
        '--window-size=%s' % size,
        '--screenshot=%s' % out,
        url,
    ]


def selftest(browser):
    """确认浏览器还能用：dump-dom about:blank 应该有输出。"""
    import tempfile as _tf
    d = long_path(_tf.mkdtemp(prefix='shotselftest-'))
    try:
        r = subprocess.run([browser, '--headless=new', '--no-sandbox', '--disable-gpu',
                            '--no-first-run', '--user-data-dir=%s' % os.path.join(d, 'p'),
                            '--dump-dom', 'about:blank'],
                           capture_output=True, text=True, timeout=90)
        got = len((r.stdout or '').strip())
        print('自检: 退出码=%s 输出字节=%d %s' % (r.returncode, got,
                                            '✔ 浏览器可用' if got else '✘ 浏览器无响应'))
        return got > 0
    except Exception as e:  # noqa: BLE001
        print('自检异常: %s' % e)
        return False
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('html', nargs='?')
    ap.add_argument('out', nargs='?')
    ap.add_argument('--section', default=None)
    ap.add_argument('--width', type=int, default=1500)
    ap.add_argument('--height', type=int, default=1180)
    ap.add_argument('--wait', type=int, default=9000)
    ap.add_argument('--selftest', action='store_true', help='只检测浏览器是否可用')
    ap.add_argument('--script', default=None,
                    help='把一个 .js 文件注入到 </body> 前再截图，用来触发交互'
                         '（如点击 #navToggle、调用 window.__doc.openDrawer()）。'
                         '脚本里请用 window.addEventListener("load", ...) + setTimeout 包一层，'
                         '确保晚于页面自身的 boot() 执行。')
    ap.add_argument('--profile', default=None,
                    help='复用固定的浏览器 profile（测试 localStorage 持久化时用）。'
                         '传"名字"即可，会固定落在系统临时目录下：'
                         'lr-shotprof-<名字>。⚠ profile 目录**不要**放在项目盘/工作盘上，'
                         'Chromium 可能静默失败。')
    a = ap.parse_args()

    browser = find_browser()
    if a.selftest:
        sys.exit(0 if selftest(browser) else 1)
    if not a.html or not a.out:
        raise SystemExit('用法: python shot.py <html> <out.png> [--section id] [--profile 名字]')

    html = os.path.abspath(a.html)
    out = os.path.abspath(a.out)
    reuse = a.profile
    if reuse:
        # 说明：实测 Chromium 在非系统盘上创建 user-data-dir 会静默失败，
        # 因此名字形式统一落在系统临时目录；绝对路径则原样使用（自担风险）。
        base = reuse if os.path.isabs(reuse) else \
            os.path.join(long_path(tempfile.gettempdir()), 'lr-shotprof-' + reuse)
        base = long_path(base)
        os.makedirs(base, exist_ok=True)
        tmp = base
        prof = os.path.join(base, 'ud')
    else:
        tmp = long_path(tempfile.mkdtemp(prefix='shotprof-'))
        prof = os.path.join(tmp, 'profile')
    target = html

    try:
        if a.section or a.script:
            s = open(html, encoding='utf-8').read()
            if a.section:
                sid = a.section.lstrip('#')
                css = ('<style>.card:not(#%s){display:none!important}'
                       '.pg:not(#%s){display:none!important}'
                       '.cover{display:none!important}</style>' % (sid, sid))
                s = s.replace('</head>', css + '\n</head>', 1)
            if a.script:
                js = open(os.path.abspath(a.script), encoding='utf-8').read()
                s = s.replace('</body>', '<script>\n' + js + '\n</script>\n</body>', 1)
            target = os.path.join(tmp, 'isolated.html')
            open(target, 'w', encoding='utf-8').write(s)

        url = 'file:///' + urllib.parse.quote(target.replace('\\', '/'), safe='/:')
        size = '%d,%d' % (a.width, a.height)
        ok = False
        for mode in ('new', 'old'):          # new 失败则退回 old，两条代码路径
            cmd = build_cmd(browser, prof, out, url, size, a.wait, mode)
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            except subprocess.TimeoutExpired:
                print('  headless=%s 超时' % mode)
                continue
            if os.path.exists(out):
                print('已生成 %s  (%.0f KB, headless=%s)' % (out, os.path.getsize(out) / 1024, mode))
                ok = True
                break
            print('  headless=%s 未出图：退出码=%s stdout=%r stderr=%r'
                  % (mode, r.returncode, (r.stdout or '')[-300:], (r.stderr or '')[-300:]))
        if not ok:
            print()
            print('  ⚠ 浏览器"空转"（退出码 0 且完全无输出、不生成截图）时的排查顺序：')
            print('    1) python shot.py --selftest            # 先确认浏览器本身是否可用')
            print('    2) 换一个 profile 名字再试               # 排除脏 profile')
            print('    3) 确认 profile 不在工作盘、路径不含 8.3 短名（如 SHENYU~1）')
            print('    4) 本机 Edge 若正开着，长时间批量调用后可能整体失灵 ——')
            print('       实测失效后 --dump-dom / --version 也全部无输出，需等 Edge')
            print('       自身恢复或重启系统。此时改用静态检查脚本兜底，不要反复重试。')
            print('    5) 切勿直接 taskkill msedge —— 用户自己的浏览器也是同名进程，')
            print('       先用 Win32_Process 查 CommandLine 过滤 headless 再动。')
            raise SystemExit('截图失败')
    finally:
        if not reuse:
            shutil.rmtree(tmp, ignore_errors=True)
        # 顺手清掉可能残留的临时副本
        for f in glob.glob(os.path.join(tempfile.gettempdir(), 'isolated.html')):
            try:
                os.remove(f)
            except OSError:
                pass


if __name__ == '__main__':
    main()
