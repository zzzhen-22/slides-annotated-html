/* ============================================================================
   截图 harness：用「真实入口」在正文里标一段，然后打开笔记抽屉。
   通用版 —— 不依赖具体课件内容：自己找一段够长的正文来标。

   用法：
     python scripts/shot.py <输出.html> _extract/v_note.png --section p03 \
            --script templates/harness_markshot.js --profile notetest

   为什么必须走真实入口：造 Range → selection.addRange → 派发 mouseup →
   点浮出的「✎ 标记」。直接调 window.__doc.addNote() 会绕过 selbar/captureSelection，
   历史上正是「测试入口与真实入口走了不同分支」而漏掉过必现 bug（见 pitfalls 第 23 条）。
   ========================================================================== */
window.addEventListener('load', function () {
  setTimeout(function () {
    var st = document.createElement('style');
    st.textContent = '.drawer,.toc,.selbar{transition:none!important} html{scroll-behavior:auto!important}';
    document.head.appendChild(st);
    try { localStorage.clear(); } catch (e) {}
    var d = window.__doc;
    if (!d) { document.title = 'PROBE: no __doc'; return; }

    function norm(t) { return String(t).replace(/\s+/g, ' ').trim(); }
    /* 只挑「看得见」的文字节点：跳过 .pg-head（页头）与 .katex-mathml（公式隐藏副本） */
    function visTexts(el) {
      var out = [], w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null), n;
      while ((n = w.nextNode())) {
        if (!norm(n.nodeValue)) continue;
        if (n.parentNode && n.parentNode.closest &&
          n.parentNode.closest('.katex-mathml, annotation, .pg-head, script, style')) continue;
        out.push(n);
      }
      return out;
    }
    function realMark(range) {
      var sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
      var btn = document.querySelector('.selbar.on button[data-act="mark"]');
      if (!btn) return false;
      btn.click();
      return true;
    }

    /* 目标一：跨表格单元格（最能暴露「上色搬坏结构」的那种选区） */
    var done = 0;
    var rows = Array.prototype.filter.call(
      document.querySelectorAll('.pg-text table.tbl tr'),
      function (tr) { return tr.querySelectorAll('td').length >= 3; });
    if (rows.length) {
      var tds = rows[0].querySelectorAll('td');
      var a = visTexts(tds[0])[0], b = visTexts(tds[2]).pop();
      if (a && b) {
        var r = document.createRange();
        r.setStart(a, 0);
        r.setEnd(b, Math.min(b.nodeValue.length, 24));
        if (realMark(r)) done++;
      }
    }
    /* 目标二：跨段落 */
    var ps = Array.prototype.filter.call(document.querySelectorAll('.pg-text > p'),
      function (p) { return norm(p.textContent).length >= 20; });
    for (var i = 0; i + 1 < ps.length && !done; i++) {
      if (ps[i].nextElementSibling !== ps[i + 1]) continue;
      var ta = visTexts(ps[i]).pop(), tb = visTexts(ps[i + 1])[0];
      if (!ta || !tb) continue;
      var r2 = document.createRange();
      r2.setStart(ta, Math.max(0, ta.nodeValue.length - 12));
      r2.setEnd(tb, Math.min(tb.nodeValue.length, 8));
      if (realMark(r2)) done++;
    }
    document.title = 'PROBE: marks=' + done + ' notes=' + d.notes.items.length;

    /* ⚠ 这里**刻意不做任何滚动**。实测（2026-09-24）：无论 scrollIntoView
       ({block:'center'}) 还是手算 scrollTo 夹紧，都会让无头截图把视口滚出内容
       范围、截出整页空白（不带 --section 也一样必现，8 KB 空图）。
       配合 shot.py --section，目标区块本来就排在最前，无需滚动；
       需要看画面别处时，请改用 --section <另一个区块> 重新截一张。 */
    d.openDrawer();
    /* 留一条自检信息（仅供人工查看：本元素带 style 属性，probe.py 靠字面
       <pre id="__r"> 匹配，因此读不到它 —— 要跑探针请用 body.innerHTML 写法，
       见 references/pitfalls.md 第 36 条）。 */
    var pre = document.createElement('pre');
    pre.id = '__r';
    pre.style.display = 'none';
    pre.textContent = JSON.stringify(d.audit());
    document.body.appendChild(pre);
  }, 900);
});
