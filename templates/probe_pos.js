/* ============================================================================
   阅读位置（学习进度）回归探针（通用，不依赖具体课件内容）

   覆盖 2026-10-17 新增的「阅读位置记录」（设计稿 §5.10）：
     · 换页时写入 lr-doc:<ns>:pos（{v,p,n,t}）
     · 同页反复滚动不重复写（节流 + 同页去重）
     · 页面隐藏（visibilitychange）时强制写
     · pagehide 兜底写
     · 换到第三页时更新（多页场景的「每页都记」）
     · 无页区块的产物（骨架等）SKIP —— 条件式原则：不假装验过，也不误报红

   用法（配合 scripts/probe.py）：
     python probe.py <输出.html> templates/probe_pos.js

   注：无头下原生 scroll 事件不一定派发（pitfalls 第 13 条同款教训），
   每次程序性滚动后手动补一发 scroll 事件。
   ========================================================================== */
window.addEventListener('load', function () { setTimeout(run, 900); });
var out = [];
function T(k, v) { out.push(k + ': ' + (typeof v === 'string' ? v : JSON.stringify(v))); }
function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function $$(s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); }
var KEY = (window.DOC_NS || 'lr-doc:') + 'pos';
function posOf() {
  try { return JSON.parse(localStorage.getItem(KEY) || 'null'); }
  catch (e) { return null; }
}
function scrollToEl(el) {
  window.scrollTo({ top: el.offsetTop - 74, behavior: 'instant' });
  window.dispatchEvent(new Event('scroll'));
}
function triggerHidden(flag) {
  /* stub document.hidden 再派发 visibilitychange —— 直接并真实地走页面里那条接线 */
  try {
    Object.defineProperty(document, 'hidden', {
      configurable: true, get: function () { return flag; }
    });
  } catch (e) {}
  document.dispatchEvent(new Event('visibilitychange'));
}

function run() {
  var allOk = true;
  try {
    var secs = $$('section.pg');
    if (secs.length < 3) {
      T('SKIP', '本产物页区块不足（section.pg=' + secs.length + '）—— 阅读位置不适用');
      T('RESULT', 'PASS');
      return dump();
    }
    localStorage.removeItem(KEY);          // 清掉环境残留，不把历史数据当结果
    var target = secs[1].id;

    scrollToEl(secs[1]);                   // ① 换页写（等 800ms 节流）
    setTimeout(function () {
      var o1 = posOf();
      var ok1 = !!o1 && o1.v === 1 && o1.p === target && o1.n > 0 && typeof o1.t === 'number';
      T('换页写入', (ok1 ? 'PASS' : 'FAIL') + ' → ' + JSON.stringify(o1) + ' 期望 p=' + target);
      allOk = allOk && ok1;

      /* 交叉验证：DOM 判定（__doc.pos.cur）与写入值一致 —— 防「写是写了、页判定错了」 */
      var cur = null;
      try { cur = window.__doc.pos.cur(); } catch (e) {}
      var okc = !!cur && cur.p === target;
      T('DOM 判定与写入一致', (okc ? 'PASS' : 'FAIL') + ' cur=' + JSON.stringify(cur));
      allOk = allOk && okc;

      var t0 = o1 && o1.t;
      window.scrollBy(0, 40);              // ② 同页滚动：t 不应变化
      window.dispatchEvent(new Event('scroll'));
      setTimeout(function () {
        var o2 = posOf();
        var ok2 = !!o2 && o2.t === t0 && o2.p === target;
        T('同页不重复写', (ok2 ? 'PASS' : 'FAIL') + ' t0=' + t0 + ' t=' + (o2 && o2.t));
        allOk = allOk && ok2;

        /* ③ 隐藏时强制写：t 先改成 0 作标记 → stub hidden → 派发 → t 应被刷新 */
        var rig = posOf() || {};
        rig.t = 0;
        localStorage.setItem(KEY, JSON.stringify(rig));
        triggerHidden(true);
        var o3 = posOf();
        var ok3 = !!o3 && o3.t > 0 && o3.p === target;
        T('隐藏时强制写', (ok3 ? 'PASS' : 'FAIL') + ' → ' + JSON.stringify(o3));
        allOk = allOk && ok3;
        try { delete document.hidden; } catch (e) {}

        /* ④ pagehide 兜底：同款标记法 */
        rig = posOf() || {};
        rig.t = 0;
        localStorage.setItem(KEY, JSON.stringify(rig));
        window.dispatchEvent(new Event('pagehide'));
        var o4 = posOf();
        var ok4 = !!o4 && o4.t > 0 && o4.p === target;
        T('pagehide 兜底写', (ok4 ? 'PASS' : 'FAIL') + ' → ' + JSON.stringify(o4));
        allOk = allOk && ok4;

        var tPrev = o4 && o4.t;
        scrollToEl(secs[2]);             // ⑤ 换到第三页：应更新为新页
        setTimeout(function () {
          var o5 = posOf();
          var ok5 = !!o5 && o5.p === secs[2].id && o5.t >= (tPrev || 0) && o5.n > 0;
          T('换页更新', (ok5 ? 'PASS' : 'FAIL') + ' → ' + JSON.stringify(o5) + ' 期望 p=' + secs[2].id);
          allOk = allOk && ok5;

          /* ⑥ 结构完整性：课程主页读取端依赖这四件 */
          var ok6 = o5 && o5.v === 1 && typeof o5.p === 'string' &&
            typeof o5.n === 'number' && typeof o5.t === 'number';
          T('键值结构 {v,p,n,t}', (ok6 ? 'PASS' : 'FAIL'));
          allOk = allOk && ok6;

          T('section.pg 数量', String(secs.length));
          T('RESULT', allOk ? 'PASS' : 'FAIL');
          return dump();
        }, 1200);
      }, 1200);
    }, 1200);
  } catch (err) {
    out.push('PROBE_ERROR: ' + (err && err.stack ? err.stack : err));
    return dump();
  }
}
function dump() {
  document.head.innerHTML = '';
  document.body.innerHTML = '<pre id="__r">' + esc(out.join('\n')) + '</pre>';
}
