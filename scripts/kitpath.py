#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""套件内的**可迁移路径探测**——所有「外部程序在哪」的问题都问这里。

为什么要有这个文件：
    套件原本在几处写死了本机绝对路径
    （`C:/Users/<用户名>/.workbuddy/binaries/node/...`、`C:/Program Files/.../msedge.exe`），
    一旦把套件目录整体拷到别的机器/别的用户名下，那些路径就全废。
    现在统一改成「**先按环境变量、再按 PATH、最后才按常见安装位置猜**」，
    并把每个候选的探测结果缓存起来，便于 `--print-env` 自查。

约定：
    · 本模块**只依赖标准库**，可被任何脚本 `import kitpath`。
    · 所有探测函数返回**绝对路径字符串或 None**，不抛异常（由调用方决定怎么报错）。
    · 不假设 Windows —— 非 Windows 走 PATH / 常见 Unix 位置。
"""
import os
import shutil
import sys

IS_WIN = (os.name == 'nt')
HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)


# ----------------------------------------------------------------- 通用小工具
def _env(*names):
    """按顺序取第一个非空环境变量。"""
    for n in names:
        v = os.environ.get(n)
        if v and os.path.exists(v):
            return v
    return None


def _first_existing(paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def _glob_dirs(base, pattern='*'):
    """列出 base 下匹配 pattern 的子目录（不存在就返回空列表）。"""
    try:
        import glob as _g
        return sorted(_g.glob(os.path.join(base, pattern)))
    except Exception:  # noqa: BLE001
        return []


# ----------------------------------------------------------------- Python
def python_exe():
    """当前解释器。脚本本来就跑在某个 python 里，直接用它最可靠。"""
    return sys.executable


# ----------------------------------------------------------------- Node
def node_exe():
    """找 node：环境变量 → PATH → WorkBuddy 托管目录（按版本号倒序）→ 常见安装位置。"""
    hit = _env('KIT_NODE', 'NODE_EXE')
    if hit:
        return hit
    hit = shutil.which('node')
    if hit:
        return hit

    home = os.path.expanduser('~')
    cands = []
    # WorkBuddy 托管运行时（版本号会变，所以列目录而不是写死 22.22.2-3）
    for base in (os.path.join(home, '.workbuddy', 'binaries', 'node', 'versions'),
                 os.path.join(home, '.workbuddy', 'binaries', 'node')):
        for d in reversed(_glob_dirs(base, '*')):
            cands.append(os.path.join(d, 'node.exe' if IS_WIN else 'node'))
            cands.append(os.path.join(d, 'bin', 'node'))
    if IS_WIN:
        cands += [r'C:\Program Files\nodejs\node.exe',
                  r'C:\Program Files (x86)\nodejs\node.exe',
                  os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'),
                               'nodejs', 'node.exe')]
    else:
        cands += ['/usr/local/bin/node', '/usr/bin/node', '/opt/homebrew/bin/node']
    return _first_existing(cands)


# ----------------------------------------------------------------- 浏览器
def _browser_candidates():
    """常见安装位置（按「优先 Edge」的顺序）。"""
    c = []
    if IS_WIN:
        pf = os.environ.get('ProgramFiles', r'C:\Program Files')
        pf86 = os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')
        local = os.environ.get('LOCALAPPDATA', '')
        c += [
            os.path.join(pf86, r'Microsoft\Edge\Application\msedge.exe'),
            os.path.join(pf, r'Microsoft\Edge\Application\msedge.exe'),
            os.path.join(pf, r'Google\Chrome\Application\chrome.exe'),
            os.path.join(pf86, r'Google\Chrome\Application\chrome.exe'),
        ]
        if local:                       # Chrome 用户级安装
            c += [os.path.join(local, r'Google\Chrome\Application\chrome.exe')]
    else:
        c += ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
              '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
              '/usr/bin/google-chrome', '/usr/bin/chromium',
              '/usr/bin/chromium-browser', '/usr/bin/microsoft-edge']
    return c


def browser_exe(required=True):
    """找 Chromium 系浏览器：环境变量 KIT_BROWSER → PATH → 常见安装位置。"""
    hit = _env('KIT_BROWSER', 'CHROME_PATH', 'BROWSER_EXE')
    if hit:
        return hit
    for name in ('msedge', 'chrome', 'chromium', 'chromium-browser', 'google-chrome'):
        hit = shutil.which(name)
        if hit:
            return hit
    hit = _first_existing(_browser_candidates())
    if hit:
        return hit
    if required:
        raise SystemExit(
            '没找到 Edge/Chrome。请任选一种方式指定：\n'
            '  ① 设环境变量 KIT_BROWSER=<浏览器 exe 绝对路径>\n'
            '  ② 把浏览器加进 PATH\n'
            '  ③ 确认已安装 Microsoft Edge 或 Google Chrome')
    return None


# ----------------------------------------------------------------- Python 依赖
# 套件用到的第三方包（标准库之外）。换机器时最容易漏的就是这两个 ——
# 缺了会直接抛 ModuleNotFoundError，看不出「到底该装什么」，所以自查里一并报出来。
PY_DEPS = [
    ('pymupdf', 'pip install pymupdf', '读 PDF / 渲染逐页图（init_project、prepare_pdf、selftest）'),
    ('PIL', 'pip install pillow', '缩略图降采样（prepare_pdf）'),
]


def dep_status():
    """检查第三方依赖是否可导入。返回 [(模块名, 是否可用, 安装命令, 用途), ...]。"""
    import importlib.util
    rows = []
    for mod, cmd, why in PY_DEPS:
        try:
            ok = importlib.util.find_spec(mod) is not None
        except (ImportError, ValueError):
            ok = False
        rows.append((mod, ok, cmd, why))
    return rows


def require_deps(*mods):
    """缺依赖时给出可直接照抄的安装命令，而不是干巴巴的 ModuleNotFoundError。

    用法（放在脚本顶部 import 之前）：
        import kitpath
        kitpath.require_deps('pymupdf', 'PIL')
    """
    missing = [r for r in dep_status() if not r[1] and (not mods or r[0] in mods)]
    if not missing:
        return
    lines = ['缺少运行所需的 Python 包：', '']
    for mod, _ok, cmd, why in missing:
        lines.append('  · %-10s %s' % (mod, why))
        lines.append('    安装：%s' % cmd)
    lines += ['', '当前解释器：%s' % python_exe(),
              '（建议装进套件专用虚拟环境，避免污染系统 Python）']
    raise SystemExit('\n'.join(lines))


# ----------------------------------------------------------------- 自查
def report():
    """打印所有探测结果，便于换机器后先跑一次确认环境。"""
    rows = [
        ('套件目录 KIT', KIT),
        ('python', python_exe()),
        ('node', node_exe()),
        ('浏览器', browser_exe(required=False)),
    ]
    print('=== 套件路径自查 ===')
    for k, v in rows:
        print('  %-14s %s' % (k, v or '✘ 未找到'))
    print('  （可用环境变量覆盖：KIT_NODE / KIT_BROWSER）')

    print('=== Python 依赖 ===')
    deps = dep_status()
    for mod, ok, cmd, why in deps:
        print('  %-14s %s' % (mod, '✔ 已安装' if ok else '✘ 缺失 → %s' % cmd))
    bad_dep = [d for d in deps if not d[1]]
    if bad_dep:
        print('  提示：缺依赖时 init_project / prepare_pdf / selftest 会直接退出。')

    return all(v for _, v in rows) and not bad_dep


if __name__ == '__main__':
    sys.exit(0 if report() else 1)
