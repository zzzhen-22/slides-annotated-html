/* ============================================================================
   标记功能回归探针（通用，不依赖具体课件内容）

   覆盖 2026-09-24 修掉的两个 bug：
     ① 跨块/跨格划线把块级元素（<p>/<td>）克隆进 <mark> → 标记处多出换行 + 不再高亮
     ② 重新进入页面后标记全部「定位失效」

   用法（配合 scripts/probe.py）：
     python probe.py <输出.html> scripts/probe_marks.js

   断言的不变量（对任何课件都成立）：
     · 划线**只加元素**：块级元素数量、每个区块的可见文本必须一字不变
     · 任何 <mark> 里不得出现 p/div/table/tr/td/th/li/ul/ol
     · 每条笔记至少 1 个 <mark>，且宽度 > 0（宽度 0 = 标在隐藏副本上，用户看不见）
     · 拆掉所有 mark 再 restoreAll（等价于重新打开页面）后，以上仍然成立
   ========================================================================== */
window.addEventListener('load', function () { setTimeout(run, 900); });
var out = [];
function T(k, v) { out.push(k + ': ' + (typeof v === 'string' ? v : JSON.stringify(v))); }
function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function $$(s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); }
function norm(t) { return String(t).replace(/\s+/g, ' ').trim(); }

/* ---------- 结构指纹 ---------- */
var BLOCK = 'p,div,table,tr,td,th,li,ul,ol,h3,blockquote';
function fingerprint() {
  return $$('section[id]').map(function (s) {
    return s.id + ':' + s.querySelectorAll(BLOCK).length +
      ':' + s.querySelectorAll('tr').length +
      ':' + s.querySelectorAll('td,th').length +
      ':' + norm(s.textContent).length;
  }).join('|');
}
function marksBroken() {
  return $$('mark.hl').filter(function (m) {
    return !!m.querySelector(BLOCK);
  }).length;
}
function zeroWidthMarks() {
  return $$('mark.hl').filter(function (m) {
    return m.getBoundingClientRect().width <= 0;
  }).length;
}

/* ---------- 真实入口：造选区 → mouseup → 点浮出的「✎ 标记」 ---------- */
function reset() {
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
}
function realMark(range) {
  reset();
  var sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
  document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
  var btn = document.querySelector('.selbar.on button[data-act="mark"]');
  if (!btn) return 'NO_SELBAR';
  btn.click();
  return 'ok';
}
/* 只挑「可见的」文字节点当锚点 —— 用户不可能选中 .katex-mathml 里那份隐藏副本，
   而第一版探针正是因为它才误判（NO_SELBAR）。 */
function collectTexts(el) {
  var vis = [];
  var w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null), n;
  while ((n = w.nextNode())) {
    if (!norm(n.nodeValue)) continue;
    if (n.parentNode && n.parentNode.closest &&
      n.parentNode.closest('.katex-mathml, annotation')) continue;
    vis.push(n);
  }
  return vis;
}
function firstTextWithText(el, min) {
  min = min || 2;
  var t = collectTexts(el), i;
  for (i = 0; i < t.length; i++) if (norm(t[i].nodeValue).length >= min) return t[i];
  return null;
}
function lastTextWithText(el, min) {
  min = min || 2;
  var t = collectTexts(el), i;
  for (i = t.length - 1; i >= 0; i--) if (norm(t[i].nodeValue).length >= min) return t[i];
  return null;
}

/* ---------- 自动找四个典型选区（全部限定在逐页讲解区 .pg-text 内） ---------- */
function cases() {
  var res = [], i;

  // A. 跨表格单元格（同一行的第 1 格 → 第 3 格）
  var rows = $$('.pg-text table.tbl tr').filter(function (tr) {
    return tr.querySelectorAll('td').length >= 3;
  });
  for (i = 0; i < rows.length; i++) {
    var tds = rows[i].querySelectorAll('td');
    var a = firstTextWithText(tds[0]), b = lastTextWithText(tds[2]);
    if (a && b) { res.push({ name: 'A_crossCell', a: a, b: b }); break; }
  }

  // B. 跨段落（相邻的两个 <p>）
  var ps = $$('.pg-text > p').filter(function (p) { return norm(p.textContent).length >= 20; });
  for (i = 0; i + 1 < ps.length; i++) {
    if (ps[i].nextElementSibling !== ps[i + 1]) continue;
    var a2 = lastTextWithText(ps[i], 6), b2 = firstTextWithText(ps[i + 1], 4);
    if (a2 && b2) { res.push({ name: 'B_crossBlock', a: a2, b: b2 }); break; }
  }

  // C. 横跨内联公式（KaTeX）：选一整段（段里除公式外还有别的字）
  //    注意：内联公式的父节点是 renderMath 造的那个裸 <span>，里面只有公式，
  //    所以要往上找到段落级宿主，否则会误判成「找不到」。
  var khost = null;
  $$('.pg-text .katex').forEach(function (k) {
    if (khost) return;
    var p = k.closest('p, li, td, .note, .tip, .flag');
    if (p && p.textContent.length > k.textContent.length + 4) khost = p;
  });
  if (khost) {
    var a3 = firstTextWithText(khost, 2), b3 = lastTextWithText(khost, 2);
    if (a3 && b3 && a3 !== b3) res.push({ name: 'C_acrossFormula', a: a3, b: b3 });
  }

  // D. 单段内（对照组，必须永远成功）
  var bolds = $$('.pg-text p b').filter(function (b) { return norm(b.textContent).length >= 4; });
  if (bolds.length) {
    var t = firstTextWithText(bolds[0], 4);
    if (t) res.push({ name: 'D_singleBlock', a: t, b: t });
  }
  return res;
}

/* ---------- 兜底：文档里没有可测结构时临时造一个 ----------
   骨架期（整篇都是「待补」卡）、纯图课件、或讲解只写在 .note 里的文档，
   都可能一个用例都凑不出来。这时往第一个 .pg-text 里塞入
   「两段相邻文字 + 一个 3 列表格 + 一段加粗」，让四个用例都能成立。
   自造结构会先纳入结构指纹基准（fp0），所以「划线只加元素」的断言依然有效。 */
function injectProbeFixture() {
  var host = document.querySelector('.pg-text');
  if (!host) {
    var pg = document.querySelector('section.pg');
    if (!pg) return false;
    host = document.createElement('div');
    host.className = 'pg-text';
    pg.appendChild(host);
  }
  var p1 = document.createElement('p');
  p1.innerHTML = '探针自造段落一：用来验证跨块划线不会把块级元素搬进<b>标记内部</b>。';
  var p2 = document.createElement('p');
  p2.textContent = '探针自造段落二：与上一段相邻，构成跨段落选区。';
  var tb = document.createElement('table');
  tb.className = 'tbl';
  tb.innerHTML = '<tr><td>甲格文字内容</td><td>乙格文字内容</td><td>丙格文字内容</td></tr>';
  host.appendChild(p1); host.appendChild(p2); host.appendChild(tb);
  T('（文档里没有可测结构，已自造一组测试段落/表格）', 'fixture');
  return true;
}

function run() {
  try {
    try { localStorage.clear(); } catch (e) {}
    var d = window.__doc;
    if (!d) { T('FATAL', 'window.__doc 不存在（页面没跑起来？）'); return dump(); }

    var fp0 = fingerprint();
    var cs = cases();
    if (!cs.length && injectProbeFixture()) {
      fp0 = fingerprint();          // 自造结构纳入基准，之后的断言才有意义
      cs = cases();
    }
    T('cases', JSON.stringify(cs.map(function (c) { return c.name; })));
    /* 某个用例没被找到时，先看这里（例如公式那个用例要求段落里除公式外还有别的字） */
    T('katex_hosts', JSON.stringify($$('.pg-text .katex').slice(0, 3).map(function (k) {
      var p = k.closest('p, li, td, .note, .tip, .flag');
      return (p ? p.tagName + '.' + String(p.className).slice(0, 12) : '-') +
        ' k=' + k.textContent.length + ' host=' + (p ? p.textContent.length : 0);
    })));
    if (!cs.length) { T('FATAL', '没找到可测的选区'); return dump(); }

    var allOk = true;
    cs.forEach(function (c) {
      var r = document.createRange();
      r.setStart(c.a, 0);
      r.setEnd(c.b, c.b.nodeValue.length);
      var before = d.notes.items.length;
      var ret = realMark(r);
      var note = d.notes.items.length > before ? d.notes.items[d.notes.items.length - 1] : null;
      var ms = note ? $$('mark.hl[data-nid="' + note.id + '"]') : [];
      var ok = ret === 'ok' && ms.length > 0 && marksBroken() === 0 && zeroWidthMarks() === 0;
      allOk = allOk && ok;
      T('  ' + c.name, (ok ? 'PASS' : 'FAIL') +
        ' ret=' + ret + ' marks=' + ms.length +
        ' broken=' + marksBroken() + ' zeroWidth=' + zeroWidthMarks() +
        ' sec=' + ((c.a.parentNode && c.a.parentNode.closest('section[id]')) ?
          c.a.parentNode.closest('section[id]').id : '-') +
        ' a=「' + norm(c.a.nodeValue).slice(0, 10) + '」' +
        ' b=「' + norm(c.b.nodeValue).slice(-10) + '」' +
        ' quote=' + JSON.stringify((note ? note.quote : '').slice(0, 24)));
    });

    T('结构指纹不变（划线只加元素）', (fingerprint() === fp0 ? 'PASS' : 'FAIL'));
    allOk = allOk && fingerprint() === fp0;

    /* ---- 等价于「重新打开页面」：拆掉所有 mark 再 restoreAll ---- */
    $$('mark.hl').forEach(function (m) { d.notes.unwrap(m); });
    var res = d.notes.restoreAll();
    var aud = d.audit();
    var stale = aud.perNote.filter(function (p) { return p.stale; }).length;
    var broken = aud.perNote.filter(function (p) { return p.blockInsideMark || p.inHidden; }).length;
    var zw = aud.perNote.filter(function (p) { return p.marks > 0 && p.width <= 0; }).length;
    T('重开后 restoreAll', JSON.stringify(res) + ' stale=' + stale +
      ' 结构损坏=' + broken + ' 零宽=' + zw);
    T('重开后结构指纹不变', (fingerprint() === fp0 ? 'PASS' : 'FAIL'));
    T('重开后无定位失效/结构损坏/零宽',
      (stale === 0 && broken === 0 && zw === 0 ? 'PASS' : 'FAIL'));
    allOk = allOk && stale === 0 && broken === 0 && zw === 0 && fingerprint() === fp0;

    T('audit', JSON.stringify(aud));
    T('RESULT', allOk ? 'PASS' : 'FAIL');
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
