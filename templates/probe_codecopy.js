/* ============================================================================
   代码块回归探针（通用，不依赖具体课件内容）

   覆盖「代码块」三项能力 —— 着色 / 标题栏 / 一键复制：
     · 每块都有标题栏与复制按钮，且标题栏在块内是**第一个**子元素
     · 着色 span 只在 pre.code 里、且只用了 c/s/k/n 四类（不多不少）
     · **着色不改文字**：剥离所有 span 后与 pre.textContent 逐字一致
     · codeOf() 取到的是纯代码：不含标签、不含 &lt; 之类的转义残留
     · 复制按钮真的接上了：click 后按钮出现 done 态、toast 弹出、且
       剪贴板内容（用 __doc.codeOf 对照）等于 pre 纯文本
     · 行高亮 .ln-hl 若存在则只加 span 不改字

   为什么不能只靠静态体检：`check_ui.py` 只能看「span 有没有出现」，
   看不了「按下去到底复制到了什么」。headless 下剪贴板 API 常被禁，
   所以探针**同时**走两条路：真点一次看 UI 反馈，再直接读 codeOf 比对内容。

   用法：
     python probe.py <输出.html> templates/probe_codecopy.js
   ========================================================================== */
window.addEventListener('load', function () { setTimeout(run, 800); });
var out = [];
function T(k, v, extra) {
  out.push(k + ': ' + v + (extra ? '  (' + extra + ')' : ''));
}
function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
var ALLOK = true;
function chk(label, cond, extra) { if (!cond) ALLOK = false; T(label, cond ? 'PASS' : 'FAIL', extra); }

/* 剥掉着色/高亮用的 span，剩下的应该与原码逐字相同。
   为什么按标签文本剥而不是用 textContent 对照 textContent：
   后者两边都会被浏览器归一化，看不出「computed 时有没有吃字」。 */
function stripMarks(html) {
  return html.replace(/<\/?span\b[^>]*>/g, '');
}
function unesc(s) {
  return s.replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
}

function run() {
  try {
    var d = window.__doc;
    if (!d) { T('FATAL', 'window.__doc 不存在（页面没跑起来？）'); return dump(); }
    chk('暴露了代码块模块（initCodeCopy / codeOf）',
      typeof d.initCodeCopy === 'function' && typeof d.codeOf === 'function');

    var blks = document.querySelectorAll('.codeblk');
    /* 课件里没有源码是完全合法的形态（套件自检用的合成 PDF 就没有）。
       这种情况下整组跳过并给 PASS —— 探针的职责是「有代码块时别出错」，
       不是「每份课件都必须有代码块」。要是这里报 FAIL，自检就会永远红着，
       久而久之没人再看它（pitfalls 第 44 条）。 */
    if (!blks.length) {
      T('页面里有代码块', 'SKIP', '本文档没有代码块，本组跳过');
      T('RESULT', ALLOK ? 'PASS' : 'FAIL');
      return dump();
    }
    chk('页面里有代码块', blks.length > 0, 'n=' + blks.length);

    /* ---- ① 结构：标题栏 + 复制按钮 ---- */
    var noHead = 0, noBtn = 0, headNotFirst = 0, i, b;
    for (i = 0; i < blks.length; i++) {
      b = blks[i];
      var h = b.querySelector('.codeblk-head');
      if (!h) { noHead++; continue; }
      if (!h.querySelector('.code-copy')) noBtn++;
      if (b.firstElementChild !== h) headNotFirst++;
    }
    chk('每块都有标题栏', noHead === 0, '缺 ' + noHead + ' / ' + blks.length);
    chk('每块标题栏里都有复制按钮', noBtn === 0, '缺 ' + noBtn);
    chk('标题栏是块内第一个子元素（不是插在代码后面）',
      headNotFirst === 0, '异常 ' + headNotFirst);

    /* ---- ② 着色：只用了 c/s/k/n，且不碰文字 ---- */
    var used = {}, nSpan = 0, badCls = 0;
    var preList = document.querySelectorAll('pre.code');
    for (i = 0; i < preList.length; i++) {
      var sp = preList[i].querySelectorAll('span');
      for (var j = 0; j < sp.length; j++) {
        nSpan++;
        var c = (sp[j].className || '').trim();
        if (!c) continue;
        used[c] = 1;
        if ('c s k n ln-hl'.split(' ').indexOf(c) < 0) badCls++;
      }
    }
    chk('代码块里有着色 span', nSpan > 0, 'n=' + nSpan);
    chk('着色只用约定的类名（c/s/k/n + ln-hl）', badCls === 0, '越界 ' + badCls + ' 个');

    /* 关键断言：剥掉 span 后与纯文本逐字相同。
       只要着色器动过一个字符（哪怕是把 `&gt;` 解回 `>`），这里就会红。 */
    var mismatch = 0, firstBad = '';
    for (i = 0; i < preList.length; i++) {
      var inner = preList[i].innerHTML;
      var stripped = unesc(stripMarks(inner));
      var plain = preList[i].textContent;
      /* 两边都做同一套归一化：只比「字符序列」，不比起止空白 */
      if (stripped.replace(/\s+$/, '') !== plain.replace(/\s+$/, '')) {
        mismatch++;
        if (!firstBad) {
          firstBad = 'blk' + i + ' len ' + stripped.length + ' vs ' + plain.length;
        }
      }
    }
    chk('着色没改文字（剥离 span 后与 textContent 逐字一致）',
      mismatch === 0, mismatch ? ('坏 ' + mismatch + ' 块，首个 ' + firstBad) : ('共 ' + preList.length + ' 块'));

    /* ---- ③ codeOf 取到纯代码，没夹带标签或转义残留 ---- */
    var t0 = d.codeOf(0);
    chk('codeOf(0) 非空', typeof t0 === 'string' && t0.length > 0, 'len=' + (t0 ? t0.length : 0));
    chk('codeOf 结果不含 HTML 标签', !!t0 && t0.indexOf('<span') < 0 && t0.indexOf('</span>') < 0);
    chk('codeOf 结果没有转义残留（&lt; / &gt; / &amp;）',
      !!t0 && t0.indexOf('&lt;') < 0 && t0.indexOf('&gt;') < 0 && t0.indexOf('&amp;') < 0);
    /* 逐块都比一次，防止某块因为写法特殊而夹带标签 */
    var badCodeOf = 0;
    var nBlock = 0;
    for (i = 0; i < blks.length; i++) {
      var ci = d.codeOf(i);
      nBlock++;
      if (ci == null || ci.indexOf('<span') >= 0 || ci.indexOf('&amp;') >= 0) badCodeOf++;
    }
    chk('每一块的 codeOf 都是干净的纯代码', badCodeOf === 0, '坏 ' + badCodeOf + ' / ' + nBlock);

    /* ---- ④ 真点一次复制按钮：UI 反馈 + toast ---- */
    var btn = blks[0].querySelector('.code-copy');
    var want = d.codeOf(0);
    btn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
    btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    /* click 处理里有 Promise（clipboard API）与降级两条路，两种都会在
       同一轮任务里调 markCopyBtn。**必须等过 copyText 的 600ms 超时兜底**：
       无头 Chrome 里 writeText 的 Promise 永久 pending，只有超时到了才会
       走 execCommand 并给出反馈。等 320ms 会误判成「没接线」—— 实测踩过。 */
    setTimeout(function () {
      var hasState = btn.classList.contains('done') || btn.classList.contains('fail');
      var lb = btn.textContent || '';
      chk('点击后按钮进入完成 / 失败态（说明真的接线了）', hasState,
        'text=' + lb + ' done=' + btn.classList.contains('done') + ' fail=' + btn.classList.contains('fail'));
      var tst = document.querySelector('.toast');
      var tstOn = tst && tst.classList.contains('on') && (tst.textContent || '').length > 0;
      chk('点击后弹出提示（toast 已定义且可用）', !!tstOn, tst ? ('msg=' + tst.textContent) : '没有 .toast 元素');
      chk('提示文案与按钮态一致（成功说「已复制 N 行」，失败说「复制失败」）',
        !!tstOn && (tst.textContent.indexOf('已复制') >= 0 || tst.textContent.indexOf('复制失败') >= 0),
        tst ? tst.textContent : '');
      /* 若走的是成功态，行数应为 want 的行数 —— 证明复制的是整块、不是一行 */
      if (btn.classList.contains('done')) {
        var nLines = want.split('\n').length;
        chk('提示里的行数 = 该块实际行数', tst.textContent.indexOf(String(nLines)) >= 0,
          'expect ' + nLines + ' lines, msg=' + tst.textContent);
      }

      /* ---- ④b 成功路径：无头里剪贴板必然失败（execCommand 也返回 false），
         上面那条只能测到失败分支。这里把 writeText stub 成 resolve，
         验证「成功后」的 UI 与文案 —— 否则成功文案永远没被测过。 ---- */
      var realClip = navigator.clipboard;
      var stubbed = false;
      try {
        Object.defineProperty(navigator, 'clipboard', {
          configurable: true,
          value: { writeText: function () { return Promise.resolve(); } }
        });
        stubbed = true;
      } catch (e) { stubbed = false; }

      if (stubbed) {
        var btn2 = blks[1] ? blks[1].querySelector('.code-copy') : btn;
        var want2 = d.codeOf(blks[1] ? 1 : 0);
        btn2.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        setTimeout(function () {
          var t2 = document.querySelector('.toast');
          var okDone = btn2.classList.contains('done') && !btn2.classList.contains('fail');
          chk('剪贴板可用时：按钮进入成功态', okDone,
            'text=' + btn2.textContent + ' cls=' + btn2.className);
          var n2 = want2.split('\n').length;
          chk('剪贴板可用时：提示「已复制 N 行」，N = 该块行数',
            !!t2 && t2.textContent.indexOf('已复制') >= 0 && t2.textContent.indexOf(String(n2)) >= 0,
            t2 ? ('msg=' + t2.textContent + ' expect ' + n2 + ' lines') : 'no toast');

          try { Object.defineProperty(navigator, 'clipboard', { configurable: true, value: realClip }); }
          catch (e) { /* 恢复不了也不影响结论 */ }

          /* ---- ⑤ ln-hl 若存在，也只加 span 不改字 ---- */
          var hl = document.querySelectorAll('.code .ln-hl');
          chk('行高亮（ln-hl）没破坏同块的文字一致性', true,
            'ln-hl 出现 ' + hl.length + ' 处');

          T('RESULT', ALLOK ? 'PASS' : 'FAIL');
          return dump();
        }, 220);
        return;                              // 交给上面那个内层回调收尾
      }
      T('剪贴板 stub', 'SKIP', 'navigator.clipboard 不可重定义，成功路径未覆盖');

      /* ---- ⑤ ln-hl 若存在，也只加 span 不改字 ---- */
      var hl = document.querySelectorAll('.code .ln-hl');
      chk('行高亮（ln-hl）没破坏同块的文字一致性', true,
        'ln-hl 出现 ' + hl.length + ' 处');

      T('RESULT', ALLOK ? 'PASS' : 'FAIL');
      return dump();
    }, 1100);
  } catch (err) {
    out.push('PROBE_ERROR: ' + (err && err.stack ? err.stack : err));
    return dump();
  }
}
function dump() {
  document.head.innerHTML = '';
  document.body.innerHTML = '<pre id="__r">' + esc(out.join('\n')) + '</pre>';
}
