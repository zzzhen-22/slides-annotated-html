---
name: Bug 报告
about: 产物不对、体检报红、脚本崩溃或无输出 —— 附上环境自查输出能省一半来回
title: "[bug] "
labels: bug
---

## 发生了什么

<!-- 一句话说清现象。例如：「run_all.py 跑到 ④ 后退出，产物没生成」。 -->

## 复现步骤

1.
2.
3.

<!-- 能附一条最小复现命令最好（用 examples/sample-lecture.pdf 复现最佳）。 -->

## 期望 vs 实际

- **期望**：
- **实际**：

<!-- 有报错就把完整报错贴进来（含最后一行 traceback）；不要只截一句。 -->

## 环境自查输出（必填）

```bash
python scripts/kitpath.py --json
```

```
（把 JSON 输出整段贴在这里）
```

> 这一条能一次性回答「哪个平台、哪个浏览器、缺哪个包」。没有它，
> 维护者第一轮回复大概率只是问你要这个。

## 补充信息

- 平台（Windows / macOS / Linux）：
- 浏览器（Chrome / Edge / 其它）+ 版本：
- 有没有 `node`：
- 课件页数 / 产物体积（MB）：
- 是否改过 `assets/` 或 `content/`：
- 跑的是哪条链：`run_all.py` / `run_course.py` / 手工分步

<!-- ⚠ 不要上传有版权的课件原文件或含版权内容的产物截图；
     用仓库自带的 examples/sample-lecture.pdf 能复现就优先用它。 -->
