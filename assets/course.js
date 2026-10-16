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

  /* ======================= 顶栏 scrollspy（当前区块高亮） =======================
     让顶栏 5 个导航链接跟着滚动点亮「当前区块」。
     做法是**计算式**的：update() 现场数「最后一个 top 已越过判定线的区块」，
     而不是 IntersectionObserver —— 同类机制在本套件踩过「无头下原生事件不派发」
     的坑（#toTop 显隐的假象，见审查报告「误报排除」），计算式可以被探针
     **同步调用**并断言，行为也更好推理。

     判定线是「顶部撞击线」（80px，与 .card 的 scroll-margin-top:64px 配套）：
     **顶部已撞到顶栏下沿的最后一个区块**就是「正在读的那一块」。
     滚到页面底部时直接点亮最后一节（它的 top 可能永远撞不到那条线）；
     一个都没撞线（还在顶部）时点亮第一节 —— 任何时刻恰有一个高亮，不会闪断。
     （不用「视口 45%」这类更宽的线：连续矮区块 —— 比如小课程的地图区很短 ——
     会好几个同时越线，高亮会从一开始就跳过第一节，看着像「提前跳」。） */
  var Spy = {
    links: [],          // [{id, a}]，按顶栏顺序；只收「锚到真实区块」的导航项
    cur: '',

    build: function () {
      var out = [];
      $$('.cnav a').forEach(function (a) {
        var id = (a.getAttribute('href') || '').replace(/^#/, '');
        if (id && document.getElementById(id)) out.push({ id: id, a: a });
      });
      this.links = out;
      return out.length;
    },

    at: function () {
      var links = this.links, n = links.length;
      if (!n) return '';
      var vh = window.innerHeight || 800;
      var doc = document.documentElement;
      if (window.scrollY + vh >= (doc.scrollHeight || 0) - 4) return links[n - 1].id;
      var best = links[0].id;
      for (var i = 0; i < n; i++) {
        var el = document.getElementById(links[i].id);
        if (el && el.getBoundingClientRect().top <= 80) best = links[i].id;
      }
      return best;
    },

    set: function (id) {
      this.cur = id || '';
      var cur = this.cur;
      this.links.forEach(function (x) { x.a.classList.toggle('active', x.id === cur); });
      return this.cur;
    },

    update: function () {
      var id = this.at();
      if (id !== this.cur) this.set(id);       // 没变就不动 DOM，滚动时省掉无谓的类切换
      return id;
    }
  };

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

  /* ==================== 要点「全部折叠 / 展开」开关 ====================
     默认全展开是设计稿 §5.2 的决定（首页要一眼看到要点），这个开关只做
     **批量动作**、不动默认值。按钮文案跟着「当前是否还有展开的讲次块」走 ——
     手动逐个折叠也会被同步：<details> 的 toggle 事件不冒泡，所以用捕获阶段监听。 */
  var Fold = {
    btn: null,

    anyOpen: function () {
      return $$('.klec').filter(function (lec) { return lec.open; }).length > 0;
    },

    sync: function () {
      if (this.btn) this.btn.textContent = this.anyOpen() ? '全部折叠' : '全部展开';
      return this;
    },

    setAll: function (open) {
      $$('.klec').forEach(function (lec) { lec.open = open; });
      return this.sync();
    }
  };

  /* ======================= 术语总表过滤 =======================
     与要点过滤同一套模式：纯 DOM indexOf、多词是「且」、0 命中给显式空态。
     刻意**只加过滤、不堆视图** —— 术语表是「字典」（设计稿 §5.8 的三表分工），
     排序一类会改变这张表语义的操作不在这里做。 */
  var Gl = {
    rows: [],

    build: function () {
      this.rows = $$('#glossary tbody tr');
      return this.rows.length;
    },

    apply: function (raw) {
      if (!this.rows.length) return 0;
      var q = norm(raw).toLowerCase();
      var terms = q ? q.split(' ') : [];
      var hit = 0;
      this.rows.forEach(function (tr) {
        var t = norm(tr.textContent).toLowerCase();
        var ok = terms.every(function (w) { return t.indexOf(w) >= 0; });
        tr.hidden = !ok;
        if (ok) hit++;
      });
      var empty = $('#glEmpty');
      if (empty) empty.hidden = !(terms.length && !hit);
      var cnt = $('#glCount');
      if (cnt) cnt.textContent = terms.length ? (hit + ' / ' + this.rows.length + ' 条') : '';
      return hit;
    }
  };

  /* ======================= ③ 跨讲检索 ======================= */
  var CFind = {
    data: null,
    idx: [],
    rows: [],
    terms: [],
    shown: 0,
    /* 结果分页：每批渲染多少条；超出部分由列表底部的「显示更多」按钮逐批追加 */
    PAGE_ROWS: 120,
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

    /* 一条命中 = 一个 <a>（不是 div + JS 点击）——保键盘可达（Tab 聚焦）、
       可新标签打开、可复制链接。与要点区的 .kp-at 同一原则：能跳的东西就做成链接。 */
    hitEl: function (r) {
      var d = document.createElement('a');
      d.className = 'ck-hit';
      d.href = this.linkOf(r);
      d.innerHTML =
        '<div class="ch-loc">' + esc(r.e.lec + ' · ' + r.e.lecTitle + ' · P' + (r.e.page || '?') +
        ' · ' + r.e.title) + '</div>' +
        '<div class="ch-s">' + this.snippet(r) + '</div>';
      return d;
    },

    /* 摘要一行：命中总数 + 讲数 + 页数；只显示了一批时补「已显示 N 条」 */
    sumText: function () {
      var rows = this.rows;
      /* 0 命中是「找不到不等于没有」最需要被提醒的时刻（检索区上方的 caveat 写着
         索引边界，但读者搜空了才最需要它）——所以这里直接把它带上一句。 */
      if (!rows.length) {
        return '全课程正文里没有「' + this.terms.join(' ') + '」。换个更短的词试试 —— ' +
          '索引只含每页前段正文，找不到不等于没有。';
      }
      var lecs = {}, pages = {}, nLec = 0, nPage = 0;
      rows.forEach(function (r) {
        if (!lecs[r.e.lec]) { lecs[r.e.lec] = 1; nLec++; }
        if (!pages[r.e.lec + r.e.id]) { pages[r.e.lec + r.e.id] = 1; nPage++; }
      });
      var t = '全书命中 ' + rows.length + ' 处 · 涉及 ' + nLec + ' 讲的 ' + nPage + ' 页';
      if (this.shown < rows.length) t += '（已显示 ' + this.shown + ' 条）';
      return t + '　点一条跳到那一页';
    },

    /* 把 [from, to) 的命中行追加到列表末尾 —— 「显示更多」时增量追加，不重渲染整段 */
    appendHits: function (from, to) {
      var box = $('#cres');
      if (!box) return;
      var more = box.querySelector('.res-more');
      for (var i = from; i < to; i++) {
        var el = this.hitEl(this.rows[i]);
        if (more) box.insertBefore(el, more); else box.appendChild(el);
      }
    },

    /* 「显示更多」按钮：还有没显示的条时存在（文案带剩余数），显示完了就移除 */
    updateMore: function () {
      var box = $('#cres');
      if (!box) return;
      var more = box.querySelector('.res-more');
      var left = this.rows.length - this.shown;
      if (left <= 0) { if (more) more.parentNode.removeChild(more); return; }
      if (!more) {
        var self = this;
        more = document.createElement('button');
        more.type = 'button';
        more.className = 'res-more';
        more.addEventListener('click', function () { self.showMore(); });
        box.appendChild(more);
      }
      more.textContent = '显示更多（还剩 ' + left + ' 条）';
    },

    showMore: function () {
      var from = this.shown;
      this.shown = Math.min(this.shown + this.PAGE_ROWS, this.rows.length);
      this.appendHits(from, this.shown);
      var box = $('#cres');
      var sum = box && box.querySelector('.ck-sum');
      if (sum) sum.textContent = this.sumText();
      this.updateMore();
      return this.shown;
    },

    render: function () {
      var box = $('#cres');
      if (!box) return 0;
      var rows = this.search(this.terms);
      this.rows = rows;
      this.shown = Math.min(this.PAGE_ROWS, rows.length);
      box.innerHTML = '';
      var sum = document.createElement('div');
      sum.className = 'ck-sum';
      sum.textContent = this.sumText();
      box.appendChild(sum);
      this.appendHits(0, this.shown);
      this.updateMore();
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

  /* ======================= URL 状态同步 =======================
     过滤词 / 检索词 / 术语过滤词写进 location.hash，刷新与分享都能恢复。
     格式：`#sec=<区块id>&kp=<词>&find=<词>&gl=<词>`，全 kv、值 %-编码。

     为什么第一段也用 `sec=` 而不是写成裸锚点（#keypoints&kp=x）：
       · 写入用 `location.hash =` 时，浏览器只在「找得到同 id 的元素」时才滚动 ——
         裸锚点形态会在「用户清空过滤词」的写入瞬间把页面滚走（意外滚动）；
         kv 形态没有匹配 id，写入本身永不触发滚动，语义干净。
       · 手动敲裸 `#glossary` 仍然兼容（parse 把裸段认成 sec），浏览器原生滚动照常。

     三条路径的语义（URL 是单一真源）：
       · 页面内操作（输入 / 点导航）→ 写入 hash（debounce；导航即刻写、且参数随行）；
       · 打开带参数的链接 → 启动时套用 + 滚到 sec；
       · 前进 / 后退 / 手动改地址栏 → 以 hash 为准**全量套用**（缺参数 = 清空该项），
         与浏览器前进后退的认知模型一致。 */
  var Url = {
    DEBOUNCE: 300,      // 连续输入时不要每个字符都写一次 URL
    _timer: 0,
    last: null,         // 我们写过的 hash（不含 #），用来识别「自己触发的变化」

    /* 解析 hash → {sec, kp, find, gl}；'sec=search&kp=x' 与裸 'keypoints' 都认。
       不认识的键直接忽略 —— 将来加参数时，旧页面读到新链接也不会被吓到。 */
    parse: function (raw) {
      var out = { sec: '', kp: '', find: '', gl: '' };
      var s = String(raw == null ? (location.hash || '') : raw).replace(/^#/, '');
      if (!s) return out;
      s.split('&').forEach(function (seg) {
        if (!seg) return;
        var i = seg.indexOf('=');
        if (i < 0) {
          if (!out.sec && document.getElementById(seg)) out.sec = seg;
          return;
        }
        var k = seg.slice(0, i), v = seg.slice(i + 1);
        try { v = decodeURIComponent(v); } catch (e) { /* 坏编码保留原样，别打断整条链 */ }
        if (k === 'sec') out.sec = v;
        else if (k === 'kp' || k === 'find' || k === 'gl') out[k] = v;
      });
      return out;
    },

    /* 组装当前该写的 hash（不含 #）。值一律 encodeURIComponent —— 这样浏览器读回
       location.hash 时不会二次编码，last 比对才是可靠的字符串比较。 */
    build: function (sec) {
      var parts = [];
      var s = sec || Spy.at();
      if (s) parts.push('sec=' + encodeURIComponent(s));
      var kp = norm(($('#kpFilter') || {}).value);
      var find = norm(($('#cq') || {}).value);
      var gl = norm(($('#glFilter') || {}).value);
      if (kp) parts.push('kp=' + encodeURIComponent(kp));
      if (find) parts.push('find=' + encodeURIComponent(find));
      if (gl) parts.push('gl=' + encodeURIComponent(gl));
      return parts.join('&');
    },

    write: function (sec) {
      var h = this.build(sec);
      if (!h) return '';
      if (h === String(location.hash || '').replace(/^#/, '')) return h;   // 没变就别写
      this.last = h;
      location.hash = h;
      return h;
    },

    /* 输入防抖：把「读输入框 → 写」包一层定时器（连续敲键只落一次历史条目） */
    schedule: function () {
      var self = this;
      if (this._timer) clearTimeout(this._timer);
      this._timer = setTimeout(function () { self._timer = 0; self.write(); }, this.DEBOUNCE);
    },

    /* 从 hash 全量套用。allowScroll 时滚到 sec（打开带参链接 / 前进后退）。
       点击导航的滚动由点击接管处理，不走这里。 */
    applyAll: function (h, allowScroll) {
      var kf = $('#kpFilter');
      if (kf) { kf.value = h.kp || ''; Kp.apply(kf.value); }
      var q = $('#cq');
      if (q) { q.value = h.find || ''; CFind.run(q.value); }
      var gf = $('#glFilter');
      if (gf) { gf.value = h.gl || ''; Gl.apply(gf.value); }
      if (allowScroll && h.sec) {
        var el = document.getElementById(h.sec);
        if (el && h.sec !== Spy.at()) {
          /* 'instant' 显式压过 CSS 的平滑滚动：打开带参链接时要直接定位，
             不要从顶部滑过去。老引擎不认识这个枚举值会抛错，退回默认行为。 */
          try { el.scrollIntoView({ behavior: 'instant', block: 'start' }); }
          catch (e) { el.scrollIntoView(); }
        }
      }
      return h;
    }
  };

  /* 页内锚点点击接管：滚到区块 + 高亮跟上 + **把现有参数段写进新 hash**。
     不接管的话，点导航会把 hash 覆盖成裸 #xxx（我们写入形态以外的东西），
     参数段随之丢失。只接管「目标是真实 id 的裸锚点」—— 跨页链接与 #q= 深链不碰。 */
  function initNav() {
    document.addEventListener('click', function (e) {
      var a = e.target && e.target.closest ? e.target.closest('a[href^="#"]') : null;
      if (!a) return;
      var raw = (a.getAttribute('href') || '').slice(1);
      if (!raw || raw.indexOf('=') >= 0) return;
      var el = document.getElementById(raw);
      if (!el) return;
      e.preventDefault();
      el.scrollIntoView();          // 不带参数 → 走 CSS 的平滑滚动，与原生锚点一致
      Spy.set(raw);                 // 高亮立刻跟上（滚动事件随后会再校准）
      Url.write(raw);
    });
  }

  function initUrl() {
    Url.last = String(location.hash || '').replace(/^#/, '');
    Url.applyAll(Url.parse(), true);          // 启动恢复：打开带参数的链接直接到位
    window.addEventListener('hashchange', function () {
      var cur = String(location.hash || '').replace(/^#/, '');
      if (cur === Url.last) return;           // 自己写的（write 里已记 last）
      Url.last = cur;
      Url.applyAll(Url.parse(cur), true);
    });
  }

  /* ======================= 启动 ======================= */
  function initTop() {
    var btn = $('#toTop');
    if (!btn) return;
    window.addEventListener('scroll', function () {
      btn.classList.toggle('on', window.scrollY > 400);
    });
    btn.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
  }

  /* 顶栏高亮：scroll / resize 只做「排程」，真正的判定在 Spy.update 里同步完成
     （rAF 节流，快速滚动时不会每个事件都重算） */
  function initSpy() {
    if (!Spy.build()) return 0;
    var tick = false;
    function onScroll() {
      if (tick) return;
      tick = true;
      requestAnimationFrame(function () { tick = false; Spy.update(); });
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    Spy.update();
    return Spy.links.length;
  }

  function initKp() {
    Kp.build();
    var f = $('#kpFilter');
    if (f) {
      f.addEventListener('input', function () { Kp.apply(f.value); Url.schedule(); });
      f.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { f.value = ''; Kp.apply(''); Url.schedule(); f.blur(); }
      });
    }
    var b = $('#kpExport');
    if (b) b.addEventListener('click', function () { Kp.download(); });
    /* 「全部折叠 / 展开」：按钮点击走批量动作；手动折叠单个讲次时靠捕获监听同步文案
       （<details> 的 toggle 事件不冒泡，但捕获阶段仍会经过 document） */
    Fold.btn = $('#kpToggle');
    if (Fold.btn) {
      Fold.btn.addEventListener('click', function () { Fold.setAll(!Fold.anyOpen()); });
      document.addEventListener('toggle', function () { Fold.sync(); }, true);
      Fold.sync();
    }
  }

  function initGl() {
    if (!Gl.build()) {
      /* 还没有术语时渲染的是说明性占位而不是表 —— 整个过滤工具条收起来，
         别让读者面对一个永远筛不出东西的输入框 */
      var tools = $('#glTools');
      if (tools) tools.hidden = true;
      return 0;
    }
    var f = $('#glFilter');
    if (f) {
      f.addEventListener('input', function () { Gl.apply(f.value); Url.schedule(); });
      f.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { f.value = ''; Gl.apply(''); Url.schedule(); f.blur(); }
      });
    }
    return Gl.rows.length;
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
    q.addEventListener('input', function () { CFind.run(q.value); Url.schedule(); });
    q.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { q.value = ''; CFind.run(''); Url.schedule(); q.blur(); }
      /* Enter = 焦点跳到第一条命中（聚焦而不是直接导航 —— 两步式，防误跳走）。
         到结果行后由 Tab / Enter 接管：它本来就是 <a>，键盘一路可达。 */
      if (e.key === 'Enter') {
        var first = $('#cres .ck-hit');
        if (first) { e.preventDefault(); first.focus(); }
      }
    });
  }

  function boot() {
    /* ⚠ 顺序不能反：先渲染公式，再建要点索引。
       Kp.build() 读的是 li.textContent —— 公式没渲染完就读，索引里存的是
       LaTeX 源码；等公式渲染好，文本变了、索引没变，过滤就会按错误的词去匹配。 */
    var nMath = renderMath(document);
    initTop();
    initSpy();
    initKp();
    initGl();
    initFind();
    initNav();
    initUrl();
    return nMath;
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();

  /* 无头测试入口（与单讲侧同一个约定：探针靠它读结构，而不是靠猜 DOM） */
  window.__course = {
    kp: Kp,
    find: CFind,
    spy: Spy,
    fold: Fold,
    gl: Gl,
    url: Url,
    renderMath: renderMath,
    state: function () {
      return {
        lectures: $$('.klec').length,
        keypoints: Kp.items.length,
        keypointsShown: $$('.kpl li').filter(function (x) { return !x.hidden; }).length,
        mapRows: $$('.lec').length,
        indexedPages: CFind.idx.length,
        glossaryRows: $$('#glossary tbody tr').length,
        glossaryShown: $$('#glossary tbody tr').filter(function (x) { return !x.hidden; }).length,
        progressRows: $$('#progress tbody tr').length,
        emptyShown: !!(($('#kpEmpty') || {}).hidden === false),
        /* 检索结果：当前渲染出的命中行数（分页后 = 已显示条数） */
        resultHits: $$('.ck-hit').length,
        /* scrollspy：当前高亮的导航项（逗号分隔的 href 列表，正常 0 或 1 个） */
        navActive: $$('.cnav a.active').map(function (a) {
          return String(a.getAttribute('href') || '').replace(/^#/, '');
        }).join(','),
        /* 要点折叠开关：还开着的讲次块数 / 按钮当前文案 */
        kpOpen: $$('.klec').filter(function (x) { return x.open; }).length,
        kpToggleText: norm(($('#kpToggle') || {}).textContent),
        /* URL 状态同步：当前 hash 与视口位置（探针读它们做断言） */
        hash: String(location.hash || ''),
        scrollY: Math.round(window.scrollY || 0),
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
