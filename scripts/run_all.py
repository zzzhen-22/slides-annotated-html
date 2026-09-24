#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一键流水线：把「一个课件 PDF」跑到「能打开的成品 + 全绿体检」。

用法：
    python run_all.py <课件.pdf> [--out 项目目录] [--skip-init] [--skip-prepare]
                      [--no-shot] [--embed-pdf] [--thumb-width 860] [--thumb-quality 75]

流程（每一步都会打印 PASS / FAIL，最后给总结）：
    ① init_project.py   建骨架（config.json + content/ + _katex/）—— 已存在时用 --skip-init
    ② prepare_pdf.py    逐页大图（供人/agent 逐页核对）+ 内嵌缩略图
    ③ build.py          组装单文件 HTML
    ④ check_math.js     公式语法 / CJK / 标签配对 / 目录锚点 / 数量一致性
    ⑤ check_ui.py       四类交互的接线（含标记上色的结构安全、笔记位置标签）
    ⑥ probe_marks.js    标记功能行为回归（真实入口 + DOM 结构断言）
    ⑦ probe_doc.js      交付体检（内容进度 / 缩略图一致性 / 断链）
    ⑧ shot.py ×3        首屏 / 首段概述卡 / 侧栏收起（截图失败只告警，不算失败）

注意：内容（讲解文字）**不会**被自动写出来 —— 这一份流水线负责把机械部分全部做完，
      并把「还差多少页没写」直接报出来（probe_doc.js 的「待补页面」）。
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import kitpath  # noqa: E402  （放在 sys.path 之后，便于脚本直接双击运行）


def node_exe():
    """node 的探测统一交给 kitpath（不再写死版本号与用户名）。"""
    return kitpath.node_exe()


class Runner(object):
    def __init__(self):
        self.results = []

    def step(self, label, cmd, cwd=None, parse=None, fatal=True):
        print('\n' + '-' * 72)
        print('▶ %s' % label)
        print('  $ %s' % ' '.join('"%s"' % c if ' ' in str(c) else str(c) for c in cmd))
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        out = (r.stdout or '') + (('\n' + r.stderr) if r.stderr else '')
        metrics = []
        if parse:
            metrics = parse(out)
            for m in metrics:
                print('  · %s' % m)
        ok = (r.returncode == 0)
        if not ok:
            tail = '\n'.join(out.strip().splitlines()[-18:])
            print('  ✘ 退出码 %d，输出尾部：\n%s' % (r.returncode, tail))
        self.results.append((label, ok, r.returncode == 0 or not fatal))
        print('  %s %s' % ('✔' if ok else '⚠', label))
        return ok, out


def parse_build(out):
    m = [l for l in out.splitlines() if l.startswith(('输出:', '大小:', '注入缩略图区块:', '命名空间:'))]
    warn = [l for l in out.splitlines() if '[warn]' in l]
    if warn:
        m.append('有 %d 条 warn（缺缩略图/锚点等），见上方输出' % len(warn))
    return m


def parse_check_math(out):
    m = []
    for l in out.splitlines():
        # 序号必须是「①–⑩」全段（U+2460–U+2469 连续），不能只写到 ⑦ ——
        # check_math.js 新增 ⑧ 时就被这条卡掉过：直接跑有输出、走 run_all 看不到。
        if re.match(r'^[\u2460-\u2469]', l.strip()) or '失败' in l or '一致' in l:
            m.append(l.strip())
    return m[:10]


def parse_check_ui(out):
    fails = [l for l in out.splitlines() if 'FAIL' in l]
    m = ['结果：' + ('ALL PASS' if not fails else 'FAILED %d 项：%s' % (len(fails), '; '.join(fails[:5])))]
    return m


def parse_probe(out):
    m = []
    for l in out.splitlines():
        s = l.strip()
        # 白名单前缀 —— 探针新增体检项时**记得同步加进来**，
        # 否则直接跑 probe.py 能看到、走 run_all 却被过滤掉（2026-09-24 踩过：
        # 「正文缺字风险 / 非法命名实体 / TODO 残留」三项就是这样被吞掉的）。
        if s.startswith(('RESULT', '结构指纹', '重开后', '逐页区块', '公式（', '内容进度',
                         '目录条目', '标记回归', '缺缩略图的页', '抽屉里的',
                         '正文缺字风险', '非法命名实体', 'TODO 残留')):
            m.append(s)
    # 探针的判定行（PASS/FAIL）务必透传，否则上游脚本没法据此判绿。
    if not any(x.startswith('RESULT') for x in m):
        verdict = [l.strip() for l in out.splitlines()
                   if re.search(r'(RESULT\s*:|判定|PASS|FAIL)', l)]
        m.extend(verdict[-2:])
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('--out', default=None)
    ap.add_argument('--skip-init', action='store_true')
    ap.add_argument('--skip-prepare', action='store_true')
    ap.add_argument('--no-shot', action='store_true')
    ap.add_argument('--embed-pdf', action='store_true')
    ap.add_argument('--group-size', type=int, default=8, help='传给 init_project.py')
    ap.add_argument('--group-by', default='auto',
                    choices=['auto', 'bookmarks', 'flat'], help='传给 init_project.py')
    ap.add_argument('--force', action='store_true', help='传给 init_project.py：覆盖已有分片')
    ap.add_argument('--thumb-width', type=int, default=860)
    ap.add_argument('--thumb-quality', type=int, default=75)
    a = ap.parse_args()

    pdf = os.path.abspath(a.pdf)
    if not os.path.exists(pdf):
        raise SystemExit('找不到 PDF: %s' % pdf)
    stem = os.path.splitext(os.path.basename(pdf))[0]
    out_dir = os.path.abspath(a.out) if a.out else os.path.join(os.path.dirname(pdf), stem + '-讲解')
    cfg_path = os.path.join(out_dir, 'config.json')
    py = sys.executable
    node = node_exe()
    R = Runner()

    print('套件 : %s' % KIT)
    print('课件 : %s' % pdf)
    print('项目 : %s' % out_dir)
    print('python: %s' % py)
    print('node  : %s' % (node or '✘ 没找到（check_math.js 会跳过）'))

    # ① 骨架
    if a.skip_init:
        if not os.path.exists(cfg_path):
            raise SystemExit('--skip-init 但找不到 %s，请先跑一次 init_project.py' % cfg_path)
        print('\n① 跳过 init（复用已有 config.json）')
    else:
        cmd = [py, os.path.join(HERE, 'init_project.py'), pdf, '--out', out_dir,
               '--group-size', str(a.group_size), '--group-by', a.group_by]
        if a.embed_pdf:
            cmd.append('--embed-pdf')
        if a.force:
            cmd.append('--force')
        R.step('① 建项目骨架 init_project.py', cmd, fatal=True)

    cfg = json.load(open(cfg_path, encoding='utf-8'))
    html = cfg['out'] if os.path.isabs(cfg['out']) else os.path.join(out_dir, cfg['out'])
    print('\n产物 : %s' % html)

    # ② 逐页图 + 缩略图
    if a.skip_prepare:
        print('\n② 跳过 prepare_pdf')
    else:
        R.step('② 渲染逐页图与缩略图 prepare_pdf.py',
               [py, os.path.join(HERE, 'prepare_pdf.py'), pdf,
                os.path.join(out_dir, '_extract'),
                str(a.thumb_width), str(a.thumb_quality)], fatal=True)

    # ③ 构建
    R.step('③ 构建单文件 build.py', [py, os.path.join(HERE, 'build.py'), cfg_path],
           parse=parse_build, fatal=True)

    # ④⑤⑥⑦ 体检
    if node:
        R.step('④ 公式体检 check_math.js',
               [node, os.path.join(HERE, 'check_math.js'), html,
                os.path.join(out_dir, '_katex', 'katex.min.js')], parse=parse_check_math)
    else:
        print('\n④ 跳过 check_math.js（没有 node）')
    R.step('⑤ 交互接线体检 check_ui.py', [py, os.path.join(HERE, 'check_ui.py'), html],
           parse=parse_check_ui, fatal=True)
    R.step('⑥ 标记功能回归 probe_marks.js',
           [py, os.path.join(HERE, 'probe.py'), html, os.path.join(HERE, 'probe_marks.js')],
           parse=parse_probe, fatal=True)
    R.step('⑦ 交付体检 probe_doc.js',
           [py, os.path.join(HERE, 'probe.py'), html,
            os.path.join(KIT, 'templates', 'probe_doc.js')], parse=parse_probe)

    # ⑧ 截图
    if a.no_shot:
        print('\n⑧ 跳过截图（--no-shot）')
    else:
        shots = os.path.join(out_dir, '_extract')
        R.step('⑧a 首屏截图', [py, os.path.join(HERE, 'shot.py'), html,
                              os.path.join(shots, 'v_home.png')], fatal=False)
        first_pg = cfg['pages'][0][0] if cfg.get('pages') else 1
        R.step('⑧b 首段概述卡/首屏页截图',
               [py, os.path.join(HERE, 'shot.py'), html, os.path.join(shots, 'v_p%02d.png' % first_pg),
                '--section', 'p%02d' % first_pg, '--script',
                os.path.join(KIT, 'templates', 'harness_nav.js')], fatal=False)

    # 总结
    print('\n' + '=' * 72)
    hard = [x for x in R.results if x[1] is False and x[2] is False]
    soft = [x for x in R.results if x[1] is False and x[2] is True]
    for label, ok, _fatal in R.results:
        print('  %s %s' % ('✔' if ok else '⚠', label))
    print('=' * 72)
    if hard:
        print('结果：✘ 有关键步骤失败，先修它们：')
        for label, _, _ in hard:
            print('   - %s' % label)
        sys.exit(1)
    print('结果：✔ 机械部分全绿。')
    if soft:
        print('      以下不是致命项，但值得看一眼：%s' % ', '.join(x[0] for x in soft))
    print('      下一步：按 %s 的「待补清单」逐页写讲解，' % os.path.join(out_dir, 'README-项目.md'))
    print('      再跑一次本脚本（加 --skip-init --skip-prepare）复检。')
    print('      内容进度看 ⑦ 的「内容进度：待补页面」——目标是 0。')


if __name__ == '__main__':
    main()
