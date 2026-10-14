# 在线 demo 的源工程

这个目录是仓库里两份在线 demo 的**源**：

| 源 | 产物 | 在线地址 |
|---|---|---|
| `zh/` | `docs/demo/index.html` | <https://zzzhen-22.github.io/slides-annotated-html/demo/> |
| `en/` | `docs/demo-en/index.html` | <https://zzzhen-22.github.io/slides-annotated-html/demo-en/> |

内容是完整版《逻辑回归 · 逐页精解》（63 页）里节选的 P1–P8。

## ⚠ 上游课件不在仓库里

demo 用的那份课件 PDF（一份机器学习讲义）**未随仓库分发**（版权原因，见 `TODO.md` 第 10 条）。
所以：

- **`_thumbs/` 里的 8 张原页图是「源资产」，不是派生物**——它们没有可再生的上游，
  只能作为源入库。zh / en 两份 bytes 完全相同，共享 `_thumbs/` 一份。
- **别拿 `../sample-lecture.pdf` 当它们的上游**。那是另一份**物理讲义**，
  只服务于「三步上手」与 `selftest.py`，与 demo 无关。（这个坑 2026-10-14 真踩过：
  按文件名想当然地重新渲染了一遍，结果 demo 里每页讲解旁边贴的是物理课的幻灯片。）

万一 `_thumbs/` 丢了，只能从历史上某次提交的 `docs/demo/index.html` 里解回来：

```bash
git show <某个提交>:docs/demo/index.html      # 取 <figure class="thumb"> 里的 base64 解码
```

## 怎么重建

```bash
python scripts/build_demo.py            # 两份都重建
python scripts/build_demo.py en         # 只重建英文
python scripts/build_demo.py --check    # 只校验：重建到临时文件，与已入库的 demo 比对
python scripts/build_demo.py --force    # 连 _katex/ 也重新复制
```

改过 `assets/`（外壳 / 样式 / 交互）之后**必须重建**，否则门面会停在旧版本上——
README 与 Releases 页都在引用这两份产物，门面比正文旧是访客最容易被误导的地方。

## 目录里有什么、什么不入库

```
examples/demo/
├─ _thumbs/thumb_01..08.jpg  ← 原页图（**源资产**，见上）        ✅ 入库
├─ zh/  en/
│   ├─ config.json           ← 标准 v1 项目配置                  ✅ 入库
│   ├─ content/*.html        ← 逐页讲解分片，**唯一的真源**       ✅ 入库
│   ├─ _katex/               ← 从 vendor/katex 复制             ❌ 生成物
│   └─ _extract/             ← 未使用（原页图走 _thumbs/）        ❌ 生成物
└─ README.md                  ← 本文件                          ✅ 入库
```

`_katex/` 与 `_extract/` 由 `build_demo.py` 按需生成（`.gitignore` 已挡掉）。

## 重建时会变的两件事，别当成 bug

1. **外壳**（CSS / JS / 顶栏 / 页脚提示）——这正是「用当前版本重建」的目的。
2. **`DOC_NS`**（localStorage 命名空间）——它由 `title|out` 派生。重构源工程时
   `out` 从「作者机器上的绝对路径」改成了**相对路径**，于是种子变了。
   好处是任何人、任何机器重建都得到同一个命名空间；代价是 demo 里老访客的笔记不再可见
   ——demo 没有这个负担。

`build_demo.py --check` 比对**目录（nav）与正文（wrap，含原页图）**：
它们都来自源工程，重建不该改动它们，所以必须逐字节一致。上面两样不在比对范围内。

## 源工程是怎么来的

这两份 demo 最早是手工产的，源工程没入库。2026-10-14 重建时，从当时已入库的产物
**反向导出**了 `config.json` 与 `content/`（切分点按 `<section>` 的字符区间算，
保证分片拼接能逐字节还原原文），原页图则从产物里的 base64 解回 `_thumbs/`。
随后用 `build_demo.py --check` 验证：重建产物的 nav 与 wrap（含原页图）与旧产物
**逐字节一致**。此后 `content/` 与 `_thumbs/` 就是真源，不必再反向导出。
