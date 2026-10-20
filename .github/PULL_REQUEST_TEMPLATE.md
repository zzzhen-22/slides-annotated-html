## 改了什么

<!-- 一句话。为什么改比改了什么更重要 —— 改了什么看 diff 就知道。 -->

## 动了哪条链

- [ ] 单讲（`run_all.py` 链路）
- [ ] 课程层（`run_course.py` / 课程主页）
- [ ] 套件自身（文档、体检、CI、发布）
- [ ] 只改文档 / 注释

## 跑了什么

<!-- 把关键几行贴上来，不要只写「都过了」。改文档就跑 check_docs，改代码就跑 selftest。 -->

- [ ] `python scripts/check_docs.py` → `结果: ALL PASS`
- [ ] `python scripts/selftest.py` → `自检结果: PASS`
- [ ] 改了 `assets/` 或 demo：`build_demo.py` → `shoot_previews.py` → `build_demo.py --check`
- [ ] 改了课程层：`python scripts/run_course.py <课程目录>`

```
（贴关键输出）
```

## 新增的检查有没有配反向注入

- [ ] 不适用（没有新增检查）
- [ ] 有：把代码改坏 → 确认报红 → 已还原（把注入方式写在这里）

## 文档同步

- [ ] 不需要
- [ ] 已同步：<!-- 列出改了哪几份（README / README.en / SKILL / workflow / TODO / CHANGELOG） -->

## 破坏性改动

<!-- 有就写清影响谁、怎么迁移；没有写「无」。 -->
无
