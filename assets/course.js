/* ============================================================================
   课程合集入口（index.html）的交互 —— **与单讲产物的 site.js 完全独立**。
   它只管四件事，都是「课程层」才有意义的：
     ① 要点过滤（纯 DOM 过滤，不建索引 —— 要点已经内联在页面里了）
     ② 导出 Markdown（把当前这张要点表落成文件）
     ③ 跨讲检索（搜内联在页面里的全课程索引；命中 → 跳到那一讲的该页并高亮）
     ④ 回到顶部
   五区块的内容本身是**在 Python 侧预渲染**的，所以断网、禁用 JS 也读得到全部内容，
   这个脚本只做增强。
   ========================================================================== */
(function () {
  'use strict';

  function $(s, c) { return (c || document).querySelector(s); }
  function $$(s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); }
  function norm(t) { return String(t == null ? '' : t).replace(/\s+/g, ' ').trim(); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  /* ======================= ⓪ KaTeX 渲染 =======================
     要点表与术语总表里带着各讲产物里的公式标签（type="math/tex" 的内联
     script 块，由 coursekit.html_rich 原样保留下来），这里把它们换成渲染好的
     公式 —— 否则页面上只会看到一坨 LaTeX 源码。

     ⚠ 本段注释**故意不写字面的起止标签**：这段代码是要被内联进 HTML 的，
     注释里一旦出现闭合标签，解析器会把它当成这个 script 元素的结尾而提前收尾，
     整页脚本就此报废（2026-10-15 真实事故）。course_site.py 生成期会拦住这种写法。

     为什么渲染函数**必须现在执行、而不是等 DOMContentLoaded**：
     Kp.build() 靠 li.textContent 建索引与过滤，要是那时公式还没渲染，
     取到的就是 LaTeX 源码；渲染完再改 DOM 又会让 Kp.items 里的文本过期。
     所以顺序是：先渲染公式 → 再 build 索引。**顺序反了过滤就会失灵。**
     ===================================================================== */
  function renderMath(root) {
    if (typeof katex === 'undefined') return 0;
    var n = 0;
    $$('script[type^="math/tex"]', root).forEach(function (el) {
      var display = /mode=display/.test(el.getAttribute('type') || '');
      var tex = el.textContent || '';
      var span = document.createElement('span');
      try {
        katex.render(tex, span, {
          displayMode: display, throwOnError: false,
          strict: false, trust: false, output: 'htmlAndMathml'
        });
      } catch (err) {
        /* 渲染失败**不许静默吃掉公式** —— 退回显示源码，让人看得见哪里错了 */
        span.textContent = tex;
        span.className = 'katex-failed';
      }
      if (el.parentNode) el.parentNode.replaceChild(span, el);
      n++;
    });
    return n;
  }

  /* ======================= ① 要点过滤 ======================= */
  var Kp = {
    items: [],          // [{li, lec, text}]

    build: function () {
      var out = [];
      $$('.klec').forEach(function (lec) {
        var name = norm(($('summary', lec) || {}).textContent);
        $$('.kpl li', lec).forEach(function (li) {
          out.push({ li: li, lec: lec, lecName: name, text: norm(li.textContent).toLowerCase() });
        });
      });
      this.items = out;
      return out;
    },

    apply: function (raw) {
      var q = norm(raw).toLowerCase();
      var terms = q ? q.split(' ') : [];
      var hit = 0;
      $$('.klec').forEach(function (lec) {
        var shown = 0;
        $$('.kpl li', lec).forEach(function (li) {
          var t = norm(li.textContent).toLowerCase();
          var ok = terms.every(function (w) { return t.indexOf(w) >= 0; });
          li.hidden = !ok;
          if (ok) shown++;
        });
        lec.hidden = shown === 0;
        /* 过滤时把命中的讲次展开 —— 折着的讲次里筛出结果却看不见，等于没筛 */
        if (terms.length && shown) lec.open = true;
        hit += shown;
      });
      var empty = $('#kpEmpty');
      if (empty) empty.hidden = hit > 0;
      var cnt = $('#kpCount');
      if (cnt) cnt.textContent = terms.length ? (hit + ' / ' + this.items.length + ' 条') : '';
      return hit;
    },

    /* 导出的是**当前可见的**那一份：用户先筛出「梯度」相关再导出，是明确意图，不该被无视 */
    markdown: function () {
      var title = norm(($('.chero h1') || {}).textContent) || '课程';
      var sum = norm(($('.csum') || {}).textContent);
      var L = ['# ' + title + ' — 要点总结', ''];
      if (sum) { L.push('> ' + sum); L.push(''); }
      var lecs = 0, items = 0, missing = [];
      $$('.klec').forEach(function (lec) {
        if (lec.hidden) return;
        var rows = $$('.kpl li', lec).filter(function (x) { return !x.hidden; });
        if (!rows.length) return;
        lecs++;
        L.push('## ' + norm(($('summary', lec) || {}).textContent));
        L.push('');
        var note = $('.kp-hold', lec);        // 占位说明（未写完的讲次），在循环外取一次
        rows.forEach(function (li, i) {
          var at = $('.kp-at', li);
          items++;
          /* 取纯要点文本：把「→P12」与概念徽标摘掉再读 ——
             直接读 textContent 会把它们粘进句子里（「…的关键。→P12 ⟡feature-hierarchy」） */
          var clone = li.cloneNode(true);
          $$('.kp-at, .kp-topic', clone).forEach(function (x) {
            if (x.parentNode) x.parentNode.removeChild(x);
          });
          L.push((i + 1) + '. ' + norm(clone.textContent) +
                 (at ? ('（' + norm(at.textContent).replace(/^[→⟡\s]*/, '') + '）') : ''));
        });
        if (norm((note || {}).textContent)) L.push('', '> ' + norm(note.textContent));
        L.push('');
      });
      $$('.klec').forEach(function (lec) {
        var s = norm(($('summary', lec) || {}).textContent);
        if (/待建|骨架|未写完|部分完成/.test(s)) missing.push(s);
      });
      L.push('---');
      L.push('');
      L.push('导出时间：' + new Date().toLocaleString());
      L.push('覆盖讲次：' + lecs + ' 讲 / ' + items + ' 条' +
             (missing.length ? ('；**未完成 ' + missing.length + ' 讲**：' + missing.join('、')) : ''));
      return L.join('\n');
    },

    download: function () {
      var md = this.markdown();
      var name = (norm(($('.chero h1') || {}).textContent) || 'course') + '-要点总结.md';
      try {
        var blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
      } catch (e) {
        /* Blob / download 被环境禁用时，退化成「让用户自己复制」而不是静默失败 */
        var w = window.open('', '_blank');
        if (w) { w.document.write('<pre>' + esc(md) + '</pre>'); }
        else { window.alert('这个环境不支持直接下载文件，请手动复制。'); }
      }
      return md.length;
    }
  };

  /* ======================= ③ 跨讲检索 ======================= */
  var CFind = {
    data: null,
    idx: [],
    rows: [],
    terms: [],
    MAX_ROWS: 120,
    PER_PAGE: 3,

    load: function () {
      var el = document.getElementById('cdata');
      if (!el) return null;
      try { this.data = JSON.parse(el.textContent || '{}'); }
      catch (e) { this.data = null; }
      return this.data;
    },

    build: function () {
      var idx = [], self = this;
      ((this.data || {}).lectures || []).forEach(function (l) {
        (l.pages || []).forEach(function (p) {
          var t = norm(p.text);
          if (!t) return;                       // 空节（纯图页）不进索引
          idx.push({
            lec: l.id, lecTitle: l.title, href: l.href,
            id: p.id, page: p.page, title: p.title,
            text: t, lower: t.toLowerCase(),
            tl: norm(p.title).toLowerCase()
          });
        });
      });
      self.idx = idx;
      return idx;
    },

    split: function (raw) {
      var seen = {}, out = [];
      norm(raw).toLowerCase().split(' ').forEach(function (t) {
        if (t && !seen[t]) { seen[t] = 1; out.push(t); }
      });
      return out;
    },

    search: function (terms) {
      var idx = this.idx.length ? this.idx : this.build();
      var out = [], self = this;
      idx.forEach(function (e) {
        var anchor = null;
        for (var k = 0; k < terms.length; k++) {
          var at = e.lower.indexOf(terms[k]);
          if (at < 0) return;
          if (anchor == null) anchor = terms[k];
        }
        var titleHit = 0;
        for (var j = 0; j < terms.length; j++) if (e.tl.indexOf(terms[j]) >= 0) titleHit = 1;
        var from = 0, n = 0, pos;
        while (n < self.PER_PAGE && (pos = e.lower.indexOf(anchor, from)) >= 0) {
          out.push({ e: e, at: pos, len: anchor.length, titleHit: titleHit, seq: out.length });
          from = pos + anchor.length; n++;
        }
      });
      out.sort(function (x, y) { return (y.titleHit - x.titleHit) || (x.seq - y.seq); });
      return out;
    },

    snippet: function (r) {
      var text = r.e.text;
      var from = Math.max(0, r.at - 30), to = Math.min(text.length, r.at + r.len + 44);
      var head = (from > 0 ? '…' : '') + text.slice(from, to) + (to < text.length ? '…' : '');
      var lo = head.toLowerCase();
      var cuts = [];
      this.terms.forEach(function (w) {
        var f = 0, p;
        while ((p = lo.indexOf(w, f)) >= 0) { cuts.push([p, p + w.length]); f = p + w.length; }
      });
      cuts.sort(function (a, b) { return a[0] - b[0]; });
      var html = '', cur = 0;
      cuts.forEach(function (c) {
        if (c[0] < cur) return;
        if (c[0] > cur) html += esc(head.slice(cur, c[0]));
        html += '<mark class="ch">' + esc(head.slice(c[0], c[1])) + '</mark>';
        cur = c[1];
      });
      if (cur < head.length) html += esc(head.slice(cur));
      return html;
    },

    /* 命中要跳到「那一讲的该页」并让目标讲高亮命中词 —— 所以链接带 #q=<词>&p=<页id>。
       目标讲的 site.js 里有一个 initDeepLink() 专门接这一对参数（见 §5.1）。 */
    linkOf: function (r) {
      return r.e.href + '#q=' + encodeURIComponent(this.terms.join(' ')) + '&p=' + r.e.id;
    },

    render: function () {
      var box = $('#cres');
      if (!box) return 0;
      var self = this;
      var rows = this.search(this.terms);
      this.rows = rows;
      box.innerHTML = '';
      var lecs = {}, acc = 0;
      rows.forEach(function (r) { if (!lecs[r.e.lec]) { lecs[r.e.lec] = 1; acc++; } });
      var sum = document.createElement('div');
      sum.className = 'ck-sum';
      sum.textContent = rows.length
        ? ('全书命中 ' + rows.length + ' 处 · 涉及 ' + acc + ' 讲的 ' +
           (function () { var s = {}, n = 0; rows.forEach(function (r) { if (!s[r.e.lec + r.e.id]) { s[r.e.lec + r.e.id] = 1; n++; } }); return n; })() +
           ' 页' + (rows.length > this.MAX_ROWS ? '（只列前 ' + this.MAX_ROWS + ' 条）' : '') + '　点一条跳到那一页')
        : ('全课程正文里没有「' + this.terms.join(' ') + '」。换个更短的词试试。');
      box.appendChild(sum);
      rows.slice(0, this.MAX_ROWS).forEach(function (r) {
        var d = document.createElement('div');
        d.className = 'ck-hit';
        d.innerHTML =
          '<div class="ch-loc">' + esc(r.e.lec + ' · ' + r.e.lecTitle + ' · P' + (r.e.page || '?') +
          ' · ' + r.e.title) + '</div>' +
          '<div class="ch-s">' + self.snippet(r) + '</div>';
        d.addEventListener('click', function () { location.href = self.linkOf(r); });
        box.appendChild(d);
      });
      box.hidden = false;
      return rows.length;
    },

    run: function (raw) {
      var box = $('#cres');
      if (!box) return 0;
      this.terms = this.split(raw);
      if (!this.terms.length) { box.hidden = true; box.innerHTML = ''; return 0; }
      return this.render();
    }
  };

  /* ======================= 启动 ======================= */
  function initTop() {
    var btn = $('#toTop');
    if (!btn) return;
    window.addEventListener('scroll', function () {
      btn.classList.toggle('on', window.scrollY > 400);
    });
    btn.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
  }

  function initKp() {
    Kp.build();
    var f = $('#kpFilter');
    if (f) {
      f.addEventListener('input', function () { Kp.apply(f.value); });
      f.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { f.value = ''; Kp.apply(''); f.blur(); }
      });
    }
    var b = $('#kpExport');
    if (b) b.addEventListener('click', function () { Kp.download(); });
  }

  function initFind() {
    if (!CFind.load()) return;
    /* **立刻建索引**，而不是等第一次输入再懒建。
       这里的数据已经是解析好的 JSON（不像单讲侧要从 DOM 文本投影里抽），建一次是微秒级；
       懒建的话 window.__course.find.idx 在首次搜索前是空的 ——
       探针与状态检查会读到「索引是空的」这种**假故障**。 */
    CFind.build();
    var q = $('#cq');
    if (!q) return;
    q.addEventListener('input', function () { CFind.run(q.value); });
    q.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { q.value = ''; CFind.run(''); q.blur(); }
    });
  }

  function boot() {
    /* ⚠ 顺序不能反：先渲染公式，再建要点索引。
       Kp.build() 读的是 li.textContent —— 公式没渲染完就读，索引里存的是
       LaTeX 源码；等公式渲染好，文本变了、索引没变，过滤就会按错误的词去匹配。 */
    var nMath = renderMath(document);
    initTop();
    initKp();
    initFind();
    return nMath;
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();

  /* 无头测试入口（与单讲侧同一个约定：探针靠它读结构，而不是靠猜 DOM） */
  window.__course = {
    kp: Kp,
    find: CFind,
    renderMath: renderMath,
    state: function () {
      return {
        lectures: $$('.klec').length,
        keypoints: Kp.items.length,
        keypointsShown: $$('.kpl li').filter(function (x) { return !x.hidden; }).length,
        mapRows: $$('.lec').length,
        indexedPages: CFind.idx.length,
        glossaryRows: $$('#glossary tbody tr').length,
        progressRows: $$('#progress tbody tr').length,
        emptyShown: !!(($('#kpEmpty') || {}).hidden === false),
        /* 公式体检用：渲染出来的公式数 / 尚未渲染的残留 / 渲染失败数 */
        mathRendered: $$('.katex').length,
        mathLeft: $$('script[type^="math/tex"]').length,
        mathFailed: $$('.katex-failed').length,
        /* 已渲染的正文里还有没有占位符（不该有 —— 那是给检索索引用，不该显示） */
        placeholderLeft: (function () {
          var txt = $$('#keypoints, #glossary').map(function (x) { return x.textContent; }).join('');
          return (txt.match(/〔公式〕/g) || []).length;
        })()
      };
    }
  };
})();
