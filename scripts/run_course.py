#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""课程级流水线：把「一门课」同步到「合集入口能用 + 体检全绿」。

用法：
    python run_course.py <课程目录> [--add 讲次目录] [--brief L07]
                         [--no-probe] [--force] [--no-check]

三种典型用法：
    # ① 日常：写完/改完某一讲之后同步一次（这就是「每加一讲就更新」的那条命令）
    python run_course.py D:/课程/深度学习 --sync

    # ② 新加了一讲（骨架已建好）：登记 + 出它的前序知识简报 + 全量同步
    python run_course.py D:/课程/深度学习 --add lecture-07-attention

    # ③ 只想拿某一讲的简报来读
    python run_course.py D:/课程/深度学习 --brief L07

流程（每步都打印 ✔ / ⚠，最后给总结）：
    course_init   登记 / 刷新 course.json（派生字段重算，手写字段保留）
    course_index  扫各讲产物 → _course/index.json + glossary/keypoints（按哈希增量）
    course_brief  为指定讲次产出「前序知识简报」（仅 --add / --brief 时）
    course_site   生成课程合集入口 index.html（五区块，索引内联）
    course_check  课程层体检（**阶段 3 才写**，不存在时自动跳过并提示）
    probe_course  浏览器行为探针（地图/要点表/检索/术语/进度/导出/过滤）

**为什么单开一个入口、而不并进 `run_all.py`**：`run_all.py` 是**单讲**流水线
（签名 `<课件.pdf> [--out …]`，只产出一份产物，根本产不出合集入口）。
把课程探针挂进去 = 每跑一次单讲都要去检查一个不存在的 index.html，单讲用户必报错。
见 docs/v2-course-collection.md §7「已否决的方案」。

设计稿：docs/v2-course-collection.md §5.2 / §6.1 / §8 阶段 2
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import coursekit  # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')


class Runner(object):
    """与 run_all.py 同款：逐步打印、留下结果、最后给总结。"""

    def __init__(self, py):
        self.py = py
        self.results = []

    def step(self, label, script, args, fatal=True, show=0):
        path = os.path.join(HERE, script)
        if not os.path.exists(path):
            print('\n' + '-' * 72)
            print('▶ %s' % label)
            print('  ⚠ 跳过：%s 还不存在' % script)
            self.results.append((label, None, False))
            return None
        print('\n' + '-' * 72)
        print('▶ %s' % label)
        cmd = [self.py, path] + args
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        out = (r.stdout or '') + (('\n' + r.stderr) if r.stderr else '')
        if show and (r.returncode == 0):
            for line in out.strip().splitlines()[-show:]:
                print('  %s' % line)
        ok = (r.returncode == 0)
        if not ok:
            print('  ✘ 退出码 %d，输出尾部：\n%s'
                  % (r.returncode, '\n'.join(out.strip().splitlines()[-14:])))
        self.results.append((label, ok, fatal))
        print('  %s %s' % ('✔' if ok else '⚠', label))
        return ok

    def probe(self, label, html, js, fatal=True):
        return self.step(label, 'probe.py', [html, js], fatal=fatal, show=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('course_dir')
    ap.add_argument('--sync', action='store_true',
                    help='（默认动作）init → index → site → check → probe')
    ap.add_argument('--add', default=None, metavar='讲次目录',
                    help='新加了一讲：登记它、出它的简报，然后全量同步')
    ap.add_argument('--brief', default=None, metavar='LNN', help='只为这一讲出前序知识简报')
    ap.add_argument('--no-check', action='store_true', help='跳过课程层体检')
    ap.add_argument('--no-probe', action='store_true', help='跳过浏览器探针')
    ap.add_argument('--force', action='store_true', help='索引不做增量，全部重抽')
    a = ap.parse_args()

    course_dir = os.path.abspath(a.course_dir)
    if not os.path.isdir(course_dir):
        raise SystemExit('找不到课程目录: %s' % course_dir)
    cj = os.path.join(course_dir, 'course.json')
    if not os.path.exists(cj):
        raise SystemExit(
            '还没有 course.json。先用 course_init.py 建一次：\n'
            '  python scripts/course_init.py "%s" --name "课程名"' % course_dir)

    py = sys.executable
    R = Runner(py)
    print('套件 : %s' % KIT)
    print('课程 : %s' % course_dir)
    print('python: %s' % py)

    idx_args = [course_dir] + (['--force'] if a.force else [])
    # ① 登记 / 刷新。--add 时也要跑：它靠「已记录 + 新扫到」的合并把新讲次纳进来
    R.step('① 登记/刷新 course.json   course_init.py', 'course_init.py',
           [course_dir], fatal=True, show=6)
    # ② 扫描各讲产物
    R.step('② 扫产物建索引            course_index.py', 'course_index.py',
           idx_args, fatal=True, show=10)

    # ③ 简报（只有明确要的时候才出 —— 它是给「动笔前」用的，不是每次同步都要）
    want_brief = []
    if a.add:
        data = coursekit.read_json(cj) or {}
        lec = next((x for x in (data.get('lectures') or [])
                    if (x.get('dir') or '') == a.add), None)
        if not lec:
            print('\n[warn] course.json 里没有 %s —— 确认它是个含 config.json 的讲次目录，'
                  '且在课程目录之下' % a.add)
        else:
            want_brief.append(lec.get('id'))
    if a.brief:
        want_brief.append(a.brief)
    for lid in want_brief:
        if lid:
            R.step('③ 前序知识简报 %s          course_brief.py' % lid, 'course_brief.py',
                   [course_dir, '--for', lid], fatal=False, show=5)

    # ④ 生成合集入口
    R.step('④ 生成课程入口 index.html  course_site.py', 'course_site.py',
           [course_dir], fatal=True, show=6)

    html = os.path.join(course_dir, 'index.html')
    # ⑤ 课程层体检（阶段 3 才写；不存在时 step 会自己跳过并说清楚）
    if not a.no_check:
        R.step('⑤ 课程层体检              course_check.py', 'course_check.py',
               [course_dir], fatal=True)

    # ⑥ 浏览器行为探针
    if not a.no_probe:
        R.probe('⑥ 课程入口行为探针        probe_course.js', html,
                os.path.join(KIT, 'templates', 'probe_course.js'), fatal=True)

    # ---- 总结 ----
    print('\n' + '=' * 72)
    hard = [x for x in R.results if x[1] is False and x[2]]
    soft = [x for x in R.results if x[1] is False and not x[2]]
    skip = [x for x in R.results if x[1] is None]
    for label, ok, _ in R.results:
        print('  %s %s' % ('✔' if ok else ('·' if ok is None else '⚠'), label))
    print('=' * 72)
    if hard:
        print('结果：✘ 有关键步骤失败，先修它们：')
        for label, _, _ in hard:
            print('   - %s' % label)
        sys.exit(1)
    print('结果：✔ 课程层全绿。')
    if skip:
        print('      跳过（尚未实现）：%s' % '、'.join(x[0].split()[1] for x in skip))
    if soft:
        print('      以下不是致命项，但值得看一眼：%s' % '、'.join(x[0] for x in soft))
    print()
    print('入口：%s' % html)
    print('      双击打开即可（断网也可用）。「要点总结」随讲次自动生长：')
    print('      写完一讲 → 再跑一次本命令 → 要点表多一块。')


if __name__ == '__main__':
    main()
