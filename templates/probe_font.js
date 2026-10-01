/* ============================================================================
   正文字号调节回归探针（通用，不依赖具体课件内容）

   覆盖 2026-09-30 新增的「A−/A＋ 调正文字号，档位存 localStorage」功能：
     · 初始档位 100%，--fs 变量与顶栏标签同步
     · step() 后 --fs 变量、localStorage、标签三者一致
     · Font.init() 从 localStorage 恢复（等价于重新打开页面）
     · MIN(0.9) / MAX(1.4) 钳制 + 按钮 disabled 状态

   用法（配合 scripts/probe.py，两遍验证持久化）：
     python probe.py <输出.html> templates/probe_font.js --profile font
     python probe.py <输出.html> templates/probe_font.js --profile font
   第一遍（localStorage 为空）走「核心逻辑 + 写入」，并把档位固定到 130%；
   第二遍（复用同一 profile）走「跨进程恢复」断言，验证重开浏览器后字号仍在。

   为什么测持久化必须两遍 + --profile：localStorage 只在真实复用同一份
   browser profile 时才跨进程保留；单遍里用 init() 重读只能模拟「同页重载」。
   ========================================================================== */
window.addEventListener('load', function () { setTimeout(run, 900); });
var out = [];
function T(k, v) { out.push(k + ': ' + (typeof v === 'string' ? v : JSON.stringify(v))); }
function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function fsVar() { return document.documentElement.style.getPropertyValue('--fs').trim(); }
function label() { var l = document.getElementById('fontSizeLabel'); return l ? l.textContent : ''; }
function lsGet() { try { return localStorage.getItem((window.DOC_NS || '') + 'font-size'); } catch (e) { return null; } }

function run() {
  try {
    var d = window.__doc;
    if (!d || !d.font) { T('FATAL', 'window.__doc.font 不存在（页面没跑起来？）'); return dump(); }
    var f = d.font;
    var allOk = true;
    var pre = lsGet();   // 进入本脚本前 LS 里已有的值（null = 第一遍）

    if (pre === null) {
      /* ---- 第一遍：核心逻辑 + 写入 + 固定到 130% ---- */
      var c0 = (f.cur === 1 && fsVar() === '1' && label() === '100%');
      allOk = allOk && c0;
      T('初始档位', c0 ? 'PASS' : 'FAIL', 'cur=' + f.cur + ' --fs=' + fsVar() + ' label=' + label());

      f.step(1); f.step(1); f.step(1);
      var c1 = (f.cur === 1.3 && fsVar() === '1.3' && label() === '130%');
      allOk = allOk && c1;
      T('放大到 130%', c1 ? 'PASS' : 'FAIL', 'cur=' + f.cur + ' --fs=' + fsVar() + ' label=' + label());

      var c2 = (lsGet() === '1.3');
      allOk = allOk && c2;
      T('localStorage 写入', c2 ? 'PASS' : 'FAIL', 'value=' + lsGet());

      f.cur = 1; f.apply();       // 模拟页面状态被清空
      f.init();                   // 重新从 localStorage 读
      var c3 = (f.cur === 1.3 && label() === '130%');
      allOk = allOk && c3;
      T('init 从 LS 恢复', c3 ? 'PASS' : 'FAIL', 'cur=' + f.cur);

      f.step(1);
      var plusDisabled = document.getElementById('fontPlus').disabled;
      var c4 = (f.cur === 1.4 && plusDisabled === true);
      f.step(1);                  // 已到顶，应保持不变
      c4 = c4 && (f.cur === 1.4);
      allOk = allOk && c4;
      T('MAX 钳制 + 按钮禁用', c4 ? 'PASS' : 'FAIL', 'cur=' + f.cur + ' plusDisabled=' + plusDisabled);

      var i;
      for (i = 0; i < 10; i++) f.step(-1);
      var minusDisabled = document.getElementById('fontMinus').disabled;
      var c5 = (f.cur === 0.9 && minusDisabled === true);
      allOk = allOk && c5;
      T('MIN 钳制 + 按钮禁用', c5 ? 'PASS' : 'FAIL', 'cur=' + f.cur + ' minusDisabled=' + minusDisabled);

      for (i = 0; i < 4; i++) f.step(1);   // 回落到 130%，留给第二遍读
      var c6 = (f.cur === 1.3);
      allOk = allOk && c6;
      T('固定到 130%（供第二遍）', c6 ? 'PASS' : 'FAIL', 'cur=' + f.cur);
    } else {
      /* ---- 第二遍（复用 profile）：断言跨进程恢复到上次值 ---- */
      var c = (f.cur === 1.3 && fsVar() === '1.3' && label() === '130%');
      allOk = allOk && c;
      T('重开恢复（跨进程）', c ? 'PASS' : 'FAIL', 'pre=' + pre + ' cur=' + f.cur + ' --fs=' + fsVar() + ' label=' + label());
    }

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
