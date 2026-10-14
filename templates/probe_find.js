/* ============================================================================
   正文搜索回归探针（通用，不依赖具体课件内容）

   覆盖「正文搜索」功能（Find 模块 + #qres 结果面板 + mark.q-hit 临时高亮）：
     · 索引惰性建、覆盖全部有文字的 section
     · 查询命中 → 结果面板打开、行数 = 命中处数、片段里带 mark.q-hit
     · 点击/Enter 跳转 → 正文里出现 mark.q-hit，且**笔记的 mark.hl 一个都没被碰**
     · 跳转只加元素不改结构（块级元素计数不变、文字一个字都没多没少）
     · 多词是「且」关系；查不到时目录交还给用户（.toc-nav 不带 .off）
     · Esc 清空 → 面板关闭、mark.q-hit 归零、正文文字与最初逐字相同

   为什么「不依赖课件内容」：本轮测试的词是**运行时从正文里现抓**的
   （取第一段连续 4 个汉字），不写死任何课文词。踩过的坑见 pitfalls 第 39 条：
   探针一旦依赖「被测文档恰好长成某样」，换个课件它就会自灭。

   用法：
     python probe.py <输出.html> templates/probe_find.js
   ========================================================================== */
window.addEventListener('load', function () { setTimeout(run, 700); });
var out = [];
function T(k, v, extra) {
  out.push(k + ': ' + v + (extra ? '  (' + extra + ')' : ''));
}
function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
var ALLOK = true;
function chk(label, cond, extra) { if (!cond) ALLOK = false; T(label, cond ? 'PASS' : 'FAIL', extra); }

/* 从正文里现抓一个测试词。**必须在单个文字节点内部命中**：
   跨节点的词在正文高亮时会套不上 mark（wrapTextHits 只在节点内动手），
   拿它去断言「跳转后有 mark.q-hit」就会假红。所以用 TreeWalker 逐节点找。
   三级兜底，最后一级自造词插进正文 —— 探针绝不依赖被测文档恰好长成某样
   （英文产物没有汉字，就是这条兜底在 2026-10-14 实测救回来的，见 pitfalls 第 39 条）。 */
function pickWord() {
  var SKIP = '.katex-mathml, annotation, script, style, noscript, svg, mark.q-hit';
  var secs = document.querySelectorAll('.pg-text, .card');
  var i, j, n, t, m;
  var cands = [];
  for (i = 0; i < secs.length; i++) {
    var w = document.createTreeWalker(secs[i], NodeFilter.SHOW_TEXT, {
      acceptNode: function (x) {
        if (!x.nodeValue || x.nodeValue.length < 5) return NodeFilter.FILTER_REJECT;
        if (x.parentNode && x.parentNode.closest && x.parentNode.closest(SKIP)) {
          return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    while ((n = w.nextNode())) cands.push(n.nodeValue);
    if (cands.length > 400) break;                 // 够用了，别把整篇走完
  }
  // ① 连续 ≥5 个汉字 → 取中间 4 个（中文产物）
  for (j = 0; j < cands.length; j++) {
    m = cands[j].match(/[\u4e00-\u9fa5]{5,}/);
    if (m) return m[0].slice(1, 5);
  }
  // ② ≥5 个拉丁字母的整词前缀（英文产物）
  for (j = 0; j < cands.length; j++) {
    m = cands[j].match(/[A-Za-z]{5,}/);
    if (m) return m[0].slice(0, 5);
  }
  // ③ 兜底：自造一个词写进正文，再让索引重建
  var host = document.querySelector('.pg-text') || document.querySelector('section[id]');
  if (!host) return '';
  t = 'qprobe' + Math.floor(Math.random() * 1e6);
  host.appendChild(document.createTextNode(' ' + t + ' '));
  window.__doc.find.idx = null;
  return t;
}
function pickAbsent() { return 'zzq' + Math.floor(Math.random() * 1e6) + 'qzz'; }
function q() { return document.getElementById('q'); }
function box() { return document.getElementById('qres'); }
function fire(el, type, key) {
  var ev = key
    ? new KeyboardEvent(type, { key: key, bubbles: true, cancelable: true })
    : new Event(type, { bubbles: true });
  el.dispatchEvent(ev);
}
function setQuery(v) { var i = q(); i.value = v; fire(i, 'input'); }
/* 块级结构 + 文字快照：跳转高亮「只该加元素」，两样都不该变 */
function snap(id) {
  var s = document.getElementById(id);
  if (!s) return null;
  return {
    blocks: s.querySelectorAll('p,div,table,td,tr,th,li,ul,ol,h3,blockquote').length,
    text: (s.textContent || '').replace(/\s+/g, ' ')
  };
}

function run() {
  try {
    var d = window.__doc;
    if (!d || !d.find) { T('FATAL', 'window.__doc.find 不存在（旧产物？）'); return dump(); }
    var F = d.find;

    chk('#q 与 #qres 都在', !!(q() && box()));
    if (!q() || !box()) return dump();

    /* ---- ① 初始：面板关闭、无临时高亮 ---- */
    chk('初始：面板关闭、无 mark.q-hit',
      !box().classList.contains('on') && document.querySelectorAll('mark.q-hit').length === 0);

    /* ---- ② 建索引 ---- */
    var idx = F.idx && F.idx.length ? F.idx : F.build();
    chk('索引建起来（≥3 节）', idx.length >= 3, 'indexed=' + idx.length);
    chk('索引跳过空节（每节都有文字）',
      idx.every(function (e) { return (e.text || '').length > 0; }));

    /* ---- ③ 单查一个真实存在的词 ---- */
    var word = pickWord();
    chk('能从正文里抓到测试词', !!word, 'word=' + word);
    if (!word) return dump();

    var beforeAll = document.querySelectorAll('mark.hl').length;
    setQuery(word);
    var st = F.stat();
    chk('查询后：面板打开', st.open === true, 'rows=' + st.rows);
    chk('查询后：命中 ≥1 且行数 = min(命中, MAX)', st.rows >= 1 && st.shown === Math.min(st.rows, F.MAX_ROWS),
      'rows=' + st.rows + ' shown=' + st.shown);
    chk('片段里有 mark.q-hit（结果面板内高亮）',
      box().querySelectorAll('mark.q-hit').length >= 1,
      'n=' + box().querySelectorAll('mark.q-hit').length);
    chk('搜索不动笔记：mark.hl 数量不变',
      document.querySelectorAll('mark.hl').length === beforeAll,
      'before=' + beforeAll + ' now=' + document.querySelectorAll('mark.hl').length);

    /* ---- ④ 跳转：正文高亮 + 结构只增不改 ---- */
    var tgt = F.items[0].e.id;
    var s0 = snap(tgt);
    var okGo = F.goto(0);
    var tgtEl = document.getElementById(tgt);
    var inBody = tgtEl ? tgtEl.querySelectorAll('mark.q-hit').length : 0;
    chk('跳转成功且正文里出现 mark.q-hit', okGo === true && inBody >= 1, 'pid=' + tgt + ' n=' + inBody);
    var s1 = snap(tgt);
    chk('跳转只加元素：块级元素计数不变', !!s0 && !!s1 && s0.blocks === s1.blocks,
      'blocks ' + (s0 && s0.blocks) + ' → ' + (s1 && s1.blocks));
    chk('跳转不改文字：textContent 逐字相同', !!s0 && !!s1 && s0.text === s1.text);

    /* ---- ⑤ 键盘：↓ 选择、Enter 跳转 ---- */
    F.on = -1;
    fire(q(), 'keydown', 'ArrowDown');
    chk('ArrowDown 选中第一行', F.on === 0 && box().querySelectorAll('.qhit.on').length === 1,
      'on=' + F.on);
    fire(q(), 'keydown', 'ArrowUp');
    chk('ArrowUp 不会越界到负数', F.on === 0, 'on=' + F.on);
    fire(q(), 'keydown', 'Enter');
    chk('Enter 跳转后仍有正文高亮', document.querySelectorAll('mark.q-hit').length >= 1);
    chk('键盘操作也不碰笔记', document.querySelectorAll('mark.hl').length === beforeAll);

    /* ---- ⑥ 多词 = 「且」 ---- */
    var w2 = word.slice(0, 2);
    setQuery(w2 + ' ' + word);
    chk('多词 AND：同节同时含两词 → 有命中', F.stat().rows >= 1, 'rows=' + F.stat().rows);
    setQuery(word + ' ' + pickAbsent());
    var st3 = F.stat();
    chk('多词 AND：含不存在的词 → 0 命中', st3.rows === 0, 'rows=' + st3.rows);
    chk('0 命中时把目录交还给用户（.toc-nav 不带 off）',
      !document.querySelector('.toc-nav').classList.contains('off'));

    /* ---- ⑦ Esc 清空：彻底还原 ---- */
    setQuery(word);                       // 先回到有命中的状态（此刻上一批高亮已被清掉）
    var tgt2 = F.items[0].e.id;
    var sBefore = snap(tgt2);
    F.goto(0);
    fire(q(), 'keydown', 'Escape');
    var st4 = F.stat();
    chk('Esc 后：输入框空、面板关闭', q().value === '' && st4.open === false);
    chk('Esc 后：mark.q-hit 归零', st4.hits === 0, 'hits=' + st4.hits);
    chk('Esc 后：目录恢复显示（无 off）',
      !document.querySelector('.toc-nav').classList.contains('off'));
    var sAfter = snap(tgt2);
    chk('Esc 后：正文文字与最初逐字相同（高亮干净拆掉）',
      !!sBefore && !!sAfter && sBefore.text === sAfter.text);
    chk('Esc 后：块级元素计数也回到最初', !!sBefore && !!sAfter && sBefore.blocks === sAfter.blocks);
    chk('全程不碰笔记', document.querySelectorAll('mark.hl').length === beforeAll);

    T('RESULT', ALLOK ? 'PASS' : 'FAIL');
    return dump();
  } catch (err) {
    out.push('PROBE_ERROR: ' + (err && err.stack ? err.stack : err));
    return dump();
  }
}
function dump() {
  document.head.innerHTML = '';
  document.body.innerHTML = '<pre id="__r">' + esc(out.join('\n')) + '</pre>';
}
