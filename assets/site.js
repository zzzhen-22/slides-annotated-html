/* ============================================================================
   逐页精解 · 前端交互
   1) KaTeX 渲染                  2) 目录逐级折叠 + 滚动高亮
   3) 侧栏收起（缩略图自动放大）    4) 内容标记 → 笔记抽屉
   5) 缩略图灯箱 / 进度条 / 快捷键 / 移动端
   暴露 window.__doc 供无头测试调用。
   ========================================================================== */
(function () {
  'use strict';

  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };
  var LS = {
    get: function (k, d) {
      try { var v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); }
      catch (e) { return d; }
    },
    set: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  };
  var MOBILE = window.matchMedia('(max-width:1024px)');
  // 注意：file:// 协议下所有本地页面共享同一个 localStorage 域，
  // 因此命名空间必须由 build.py 按文档注入（window.DOC_NS），否则不同讲解文档会串笔记。
  var NS = window.DOC_NS || 'lr-doc:';
  var NOTES_KEY = NS + 'notes';
  var COLLAPSED_KEY = NS + 'toc-collapsed';
  var NAVHIDDEN_KEY = NS + 'nav-hidden';
  var HIDETHUMB_KEY = NS + 'hide-thumb';
  var FS_KEY = NS + 'font-size';

  /* ======================= 1. KaTeX 渲染 ======================= */
  function renderMath() {
    $$('script[type^="math/tex"]').forEach(function (el) {
      var display = /mode=display/.test(el.getAttribute('type') || '');
      var tex = el.textContent || '';
      var span = document.createElement('span');
      try {
        katex.render(tex, span, {
          displayMode: display, throwOnError: false,
          strict: false, trust: false, output: 'htmlAndMathml'
        });
      } catch (e) {
        span.textContent = tex;
        span.style.fontFamily = 'monospace';
        span.style.fontSize = '12.5px';
      }
      el.parentNode.replaceChild(span, el);
    });
  }

  /* ======================= 2. 目录：逐级折叠 ======================= */
  var Toc = {
    groups: [],
    collapsed: {},
    init: function () {
      var self = this;
      this.collapsed = LS.get(COLLAPSED_KEY, {}) || {};
      this.groups = $$('.toc-group', $('.toc-nav'));
      this.groups.forEach(function (g) {
        if (self.collapsed[g.getAttribute('data-gid')]) g.classList.add('collapsed');
      });
      var nav = $('.toc-nav');
      if (nav && nav.addEventListener) {
        nav.addEventListener('click', function (ev) {
          var btn = ev.target.closest ? ev.target.closest('.toc-toggle') : null;
          if (!btn) return;
          ev.preventDefault();
          ev.stopPropagation();
          var g = btn.closest('.toc-group');
          if (g) self.toggle(g, g.classList.contains('collapsed'));
        });
      }
      var ex = $('#tocExpand'), co = $('#tocCollapse');
      if (ex) ex.addEventListener('click', function () { self.setAll(false); });
      if (co) co.addEventListener('click', function () { self.setAll(true); });
      var q = $('#q');
      if (q) {
        /* 输入交给 Find：它会建正文索引、渲染 #qres 结果面板；
           产物若来自旧外壳（没有 #qres），Find 内部会自动退化成「只过滤目录标题」。 */
        q.addEventListener('input', function () { Find.run(q); });
        q.addEventListener('keydown', function (ev) { Find.key(q, ev); });
      }
      this.syncToggles();
    },
    toggle: function (g, expand) {
      g.classList.toggle('collapsed', !expand);
      var btn = $('.toc-toggle', g);
      if (btn) btn.setAttribute('aria-expanded', expand ? 'true' : 'false');
      var gid = g.getAttribute('data-gid');
      if (gid) { this.collapsed[gid] = !expand; LS.set(COLLAPSED_KEY, this.collapsed); }
    },
    setAll: function (collapse) {
      var self = this;
      this.groups.forEach(function (g) { self.toggle(g, !collapse); });
    },
    syncToggles: function () {
      this.groups.forEach(function (g) {
        var btn = $('.toc-toggle', g);
        if (btn) btn.setAttribute('aria-expanded', g.classList.contains('collapsed') ? 'false' : 'true');
      });
    },
    /* ---- 搜索过滤（支持嵌套分组）---- */
    filter: function (raw) {
      var self = this;
      var q = String(raw || '').trim().toLowerCase();
      var nav = $('.toc-nav');
      if (!nav) return;
      var links = $$('a[href^="#"]', nav);
      if (!q) {
        links.forEach(function (a) { a.classList.remove('hide'); });
        this.groups.forEach(function (g) { g.classList.remove('hide'); });
        return;
      }
      links.forEach(function (a) {
        a.classList.toggle('hide', a.textContent.toLowerCase().indexOf(q) < 0);
      });
      // 自底向上：子孙里有命中，或组名本身命中，就保留
      function walk(g) {
        var hit = false;
        var own = $('.gt', g);
        if (own && own.textContent.toLowerCase().indexOf(q) >= 0) hit = true;
        $$('a[href^="#"]', g).forEach(function (a) { if (!a.classList.contains('hide')) hit = true; });
        $$('.toc-group', g).forEach(function (sub) { if (walk(sub)) hit = true; });
        g.classList.toggle('hide', !hit);
        return hit;
      }
      this.groups.forEach(function (g) { if (g.parentNode === nav) walk(g); });
      // 有命中的组自动展开，方便直接看到结果
      this.groups.forEach(function (g) {
        if (!g.classList.contains('hide') && $$('a[href^="#"]', g).some(function (a) {
          return !a.classList.contains('hide');
        })) self.toggle(g, true);
      });
    },
    revealLink: function (a) {
      var p = a.parentNode;
      while (p && p !== document) {
        if (p.classList && p.classList.contains('toc-group') && p.classList.contains('collapsed')) {
          this.toggle(p, true);
        }
        p = p.parentNode;
      }
    },
    scrollIntoView: function (a) {
      var nav = $('.toc-nav');
      if (!nav) return;
      var nr = nav.getBoundingClientRect(), ar = a.getBoundingClientRect();
      /* 一级表头是 sticky 的，会盖住它下面的条目 —— 这里用它的**真实高度**当上边距，
         不要写死数值（表头高度会随字号/缩放变化）。 */
      var head = nav.querySelector(':scope > .toc-group > .toc-head');
      var pad = (head ? head.getBoundingClientRect().height : 0) + 14;
      if (ar.top < nr.top + pad || ar.bottom > nr.bottom - 16) {
        var free = Math.max(60, nav.clientHeight - pad);   // 表头以下的可用高度
        nav.scrollTop += (ar.top - nr.top) - pad - free * 0.3;
      }
    }
  };

  /* ======================= 3. 滚动高亮 ======================= */
  function initSpy() {
    var links = {}, order = [];
    $$('.toc-nav a[href^="#"]').forEach(function (a) {
      var id = a.getAttribute('href').slice(1);
      links[id] = a;
      order.push(a);
    });
    var targets = order.map(function (a) {
      return document.getElementById(a.getAttribute('href').slice(1));
    }).filter(Boolean);

    function setActive(id) {
      var a = links[id];
      if (!a || a.classList.contains('active')) return;
      order.forEach(function (x) { x.classList.remove('active'); });
      a.classList.add('active');
      Toc.revealLink(a);
      Toc.scrollIntoView(a);
    }
    if (!('IntersectionObserver' in window)) return;
    var current = null;
    var obs = new IntersectionObserver(function (entries) {
      var best = null;
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        if (!best || en.boundingClientRect.top < best.boundingClientRect.top) best = en;
      });
      if (best && best.target.id !== current) { current = best.target.id; setActive(current); }
    }, { rootMargin: '-70px 0px -70% 0px', threshold: [0, 1] });
    targets.forEach(function (t) { obs.observe(t); });
  }

  /* ======================= 4. 侧栏收起 / 缩略图 ======================= */
  function initLayout() {
    var body = document.body;
    var navBtn = $('#navToggle');
    var navHidden = !!LS.get(NAVHIDDEN_KEY, false);
    var lastMobile = MOBILE.matches;

    function applyNav(hidden) {
      if (MOBILE.matches) {
        body.classList.toggle('nav-shown', !hidden);
        body.classList.remove('nav-hidden');
      } else {
        body.classList.toggle('nav-hidden', hidden);
        body.classList.remove('nav-shown');
      }
      if (navBtn) {
        navBtn.setAttribute('aria-expanded', hidden ? 'false' : 'true');
        var lbl = $('.tb-label', navBtn);
        if (lbl) lbl.textContent = hidden ? '目录' : '收起';
      }
    }
    applyNav(MOBILE.matches ? true : navHidden);

    if (navBtn) {
      navBtn.addEventListener('click', function () {
        var cur = MOBILE.matches
          ? body.classList.contains('nav-shown')   // 移动端：当前是否展开
          : !body.classList.contains('nav-hidden'); // 桌面：当前是否可见
        var next = !cur;
        if (!MOBILE.matches) { navHidden = !next; LS.set(NAVHIDDEN_KEY, navHidden); }
        applyNav(!next);
      });
    }
    var onMQ = function () {
      if (MOBILE.matches === lastMobile) return;
      lastMobile = MOBILE.matches;
      applyNav(MOBILE.matches ? true : navHidden);
    };
    if (typeof MOBILE.addEventListener === 'function') MOBILE.addEventListener('change', onMQ);
    else if (MOBILE.addListener) MOBILE.addListener(onMQ);

    // 移动端点目录项后自动收抽屉
    $$('.toc-nav a').forEach(function (a) {
      a.addEventListener('click', function () { if (MOBILE.matches) applyNav(true); });
    });

    // 缩略图显示 / 隐藏
    var thumbBtn = $('#thumbToggle');
    if (thumbBtn) {
      var hiddenT = !!LS.get(HIDETHUMB_KEY, false);
      var sync = function () {
        body.classList.toggle('hide-thumb', hiddenT);
        thumbBtn.setAttribute('aria-pressed', hiddenT ? 'true' : 'false');
        var lb = $('.tb-label', thumbBtn);
        if (lb) lb.textContent = hiddenT ? '显示缩略图' : '隐藏缩略图';
      };
      sync();
      thumbBtn.addEventListener('click', function () {
        hiddenT = !hiddenT; LS.set(HIDETHUMB_KEY, hiddenT); sync();
      });
    }
  }

  /* ======================= 4b. 正文字号调节 =======================
     A− / A＋ 按钮把正文（.wrap）整体等比缩放，档位存 localStorage。
     缩放系数写进 CSS 变量 --fs（site.css 的 .wrap 用 zoom:var(--fs)），
     max-width 反向除以同一系数，故放大字号时内容区不会变窄。 */
  var Font = {
    MIN: 0.9, MAX: 1.4, STEP: 0.1,
    cur: 1,
    init: function () {
      var saved = LS.get(FS_KEY, 1);
      this.cur = (typeof saved === 'number' && isFinite(saved) &&
        saved >= this.MIN && saved <= this.MAX) ? saved : 1;
      this.apply();
      var minus = $('#fontMinus'), plus = $('#fontPlus');
      if (minus) minus.addEventListener('click', function () { Font.step(-1); });
      if (plus) plus.addEventListener('click', function () { Font.step(1); });
    },
    apply: function () {
      document.documentElement.style.setProperty('--fs', String(this.cur));
      var lbl = $('#fontSizeLabel');
      if (lbl) lbl.textContent = Math.round(this.cur * 100) + '%';
      var minus = $('#fontMinus'), plus = $('#fontPlus');
      if (minus) minus.disabled = this.cur <= this.MIN;
      if (plus) plus.disabled = this.cur >= this.MAX;
    },
    step: function (dir) {
      var next = Math.round((this.cur + dir * this.STEP) * 10) / 10;
      next = Math.min(this.MAX, Math.max(this.MIN, next));
      if (next === this.cur) return;
      this.cur = next;
      LS.set(FS_KEY, this.cur);
      this.apply();
    }
  };

  /* ======================= 5. 灯箱 ======================= */
  var LB = {
    el: null,
    init: function () {
      this.el = $('#lightbox');
      if (!this.el) return;
      var img = $('img', this.el), cap = $('.lb-cap', this.el), self = this;
      $$('.thumb img').forEach(function (im) {
        im.addEventListener('click', function () {
          img.src = im.src;
          cap.textContent = im.getAttribute('data-cap') || '';
          self.el.classList.add('on');
        });
      });
      this.el.addEventListener('click', function () { self.close(); });
    },
    close: function () { if (this.el) this.el.classList.remove('on'); }
  };

  /* ======================= 6. 笔记：数据层 ======================= */
  /* ---------- 原文位置标签 ----------
     逐页区块带 data-page（"P12"），而**概述卡 / 封面 / 速查表 / 补充篇**这些没有页码的区块
     过去一律显示「P？」，用户根本不知道标的是哪里（用户 2026-09-24 反馈）。
     这里给它们算一个可读的位置：
       概述卡    -> "本节概述 · 第二节（P9–P39）"（页码区间从 .ov-range 里抠出来）
       其它卡片  -> 卡片自己的 h2/h3 标题（去掉 <em> 英文副标题），过长就截断（完整值在 title 里）
       兜底      -> "#id"
     注意：一律**在渲染时重算**（`locOf(document.getElementById(m.pid))`），
     老笔记没存过 loc 也能自动补上，不必等用户重标。 */
  function plainText(el) {
    if (!el) return '';
    var c = el.cloneNode(true);
    Array.prototype.slice.call(c.querySelectorAll('em')).forEach(function (e) {
      if (e.parentNode) e.parentNode.removeChild(e);
    });
    return (c.textContent || '').replace(/\s+/g, ' ').trim();
  }
  function locOf(sec) {
    if (!sec) return '';
    var pg = sec.getAttribute('data-page');
    if (pg) return '原文件 P' + pg;
    var kicker = $('.ov-kicker', sec);
    if (kicker) {
      var k = plainText(kicker);
      var rng = $('.ov-range', sec);
      var r = rng ? plainText(rng) : '';
      var m = r.match(/P\s?\d+\s*[–\-—~～]\s*P?\s?\d+/);
      return m ? (k + '（' + m[0].replace(/\s+/g, '') + '）') : k;
    }
    var t = plainText($('h2, h3', sec));
    if (t) return t.length > 18 ? (t.slice(0, 17) + '…') : t;
    return sec.id ? ('#' + sec.id) : '本文档';
  }
  /** 悬停提示：把「位置」补全（页码页补小标题，概述卡补 ov-range）。 */
  function locTip(sec, loc) {
    if (!sec) return loc;
    var pg = sec.getAttribute('data-page');
    if (pg) {
      var h = plainText($('.pg-head h3', sec));
      return h ? ('原文件 P' + pg + ' · ' + h) : loc;
    }
    var rng = $('.ov-range', sec);
    return rng ? (loc + ' · ' + plainText(rng)) : loc;
  }
  /** 给没有 id 的顶层卡片补一个稳定 id（否则这些内容根本标不了：
      markSelection 用的是 closest('section[data-page], section[id]')）。
      文档是静态的，按文档序编号在每次加载都一致，所以 pid 可用。 */
  function ensureSectionIds() {
    var secs = $$('section');
    for (var i = 0; i < secs.length; i++) {
      if (!secs[i].id) secs[i].id = 'sec-' + (i + 1);
    }
  }

  var Notes = {
    items: [],
    seq: 1,
    drawer: null,
    load: function () {
      var d = LS.get(NOTES_KEY, null);
      if (d && d.items) { this.items = d.items; this.seq = d.seq || (this.items.length + 1); }
      else { this.items = []; this.seq = 1; }
    },
    save: function () { LS.set(NOTES_KEY, { v: 1, seq: this.seq, items: this.items }); },
    add: function (o) {
      o.id = 'n' + (this.seq++);
      o.ts = Date.now();
      this.items.push(o);
      this.save();
      this.render();
      return o;
    },
    get: function (id) {
      for (var i = 0; i < this.items.length; i++) if (this.items[i].id === id) return this.items[i];
      return null;
    },
    unwrap: function (mk) {
      var p = mk.parentNode;
      while (mk.firstChild) p.insertBefore(mk.firstChild, mk);
      p.removeChild(mk);
      if (p.normalize) p.normalize();
    },
    remove: function (id) {
      this.items = this.items.filter(function (x) { return x.id !== id; });
      /* 一条笔记可能对应**多个** <mark>（跨单元格/跨段落时按块拆开上色，见 §7），
         所以这里必须全部拆掉，只拆第一个会留下高亮残影。 */
      $$('mark.hl[data-nid="' + id + '"]').forEach(function (mk) { Notes.unwrap(mk); });
      this.save(); this.render();
    },
    clear: function () {
      if (!this.items.length) return true;
      if (window.confirm && !window.confirm('确定清空全部 ' + this.items.length + ' 条笔记标记吗？（不可撤销）')) return false;
      var self = this;
      $$('mark.hl').forEach(function (mk) { self.unwrap(mk); });
      this.items = []; this.save(); this.render();
      return true;
    },
    exportMd: function () {
      var L = [];
      L.push('# 我的标记笔记');
      L.push('');
      L.push('> 导出时间：' + new Date().toLocaleString('zh-CN'));
      L.push('> 来源：' + (document.title || ''));
      L.push('> 共 ' + this.items.length + ' 条');
      L.push('');
      var last = null;
      this.items.slice().sort(function (a, b) { return a.ts - b.ts; }).forEach(function (m) {
        /* 标题就是「原文位置」：页码页 -> "原文件 P12 · 小标题"；
           无页码的卡片 -> "本节概述 · 第二节（P9–P39）"（含 ov-range 详情）。 */
        var sec = document.getElementById(m.pid);
        var head = sec ? locTip(sec, locOf(sec))
          : (m.loc || (m.page ? ('原文件 P' + m.page) : (m.pid ? ('#' + m.pid) : '本文档')));
        if (head !== last) { L.push('## ' + head); L.push(''); last = head; }
        L.push('- **摘录**：' + m.quote);
        if (m.note) L.push('  - 备注：' + m.note);
        L.push('  - 位置：`#' + m.pid + '`');
      });
      return L.join('\n');
    }
  };

  /* ======================= 7. 笔记：投影 → 定位 → 上色 =======================
     这一节是整个「标记」功能的地基，下面三条铁律每一条都对应一个真实事故，
     改之前请先读完：

     ① **上色只许动「文字节点内部」，绝不许搬动元素。**
        旧实现用 range.surroundContents()，跨元素时它抛异常，于是退回
        「取出内容再插回」那条退路（extractContents / insertNode）。它会把被
        「部分包含」的块级元素
        **克隆进 <mark>**（mark 是行内元素，一旦吞了 <p>/<td>，浏览器就把这些
        内容当独立块渲染）：
          · 症状 A：标记处凭空多出一个换行，且被标内容不再高亮（inline 盒子被
            块级子元素打断，背景渐变画不出来）；
          · 症状 B：跨单元格划线时 <td> 被搬进 <mark>，整张表散架。
        实测：跨段落标记一个 range，段落块数 27 → 29，mark 里躺着两个 <p>。

     ② **记录的文本空间与定位的文本空间必须同源。**
        浏览器 Selection.toString() 会在块级/单元格边界插入 \n 与 \t
        （Range::text() 的 ShouldEmitNewline/Tab），而 TreeWalker 把文本节点
        直接拼接、不带任何分隔符。两边不同源 → 标记时存下的 quote
        在回访时必然匹配不上（跨行、跨格、跨公式尤其明显），
        表现为「重新进入页面后全部定位失效」。
        统一做法：存和找都走 projOf() 的投影。

     ③ **公式只认「看得见的那一份」。**
        KaTeX 以 htmlAndMathml 输出，同一串公式在 DOM 里有两份：
        .katex-mathml（clip 到 1px、绝对定位）与 .katex-html（可见）。
        投影必须跳过前者，否则 quote 里公式出现两三遍（实测
        `20.5020.5020.50`），而且回访时可能把标记打在隐藏副本上 ——
        用户什么都看不见。

     另外：一条笔记允许对应**多个** <mark>（按块拆分），这是 ① 的代价，
     所有 @ 到 mark 的地方都用 `mark.hl[data-nid="…"]` 全量选择，
     不要退化成只取第一个。
     ------------------------------------------------------------------------- */
  var SKIP_SEL = '.katex-mathml, annotation, script, style, noscript, svg';
  var BLOCK_TAGS = /^(P|DIV|LI|TD|TH|TR|TABLE|UL|OL|DL|DT|DD|H1|H2|H3|H4|H5|H6|BLOCKQUOTE|SECTION|PRE|FIGURE|DETAILS|SUMMARY|ADDRESS|HR)$/;
  var CELL_TAGS = /^(TD|TH|TR|TABLE|LI|UL|OL)$/;

  /* 零宽字符（U+200B–U+200F、U+202A–U+202E、U+2060、U+FEFF）：
     视觉上完全不存在，但 **KaTeX 的 .vlist-s 等结构里会真的插入 U+200B**
     （\frac 的分式线定位就靠它）。`\s` 并不匹配 U+200B，所以若把它当成
     「可见文字」，跨公式划线时就会在这些字符上生成 **宽度为 0 的 <mark>**
     —— 用户看不到任何高亮，而 probe_marks.js 的 zeroWidth 断言会报 FAIL。
     统一按空白处理，且**存（canon）与找（candidates）两端都用同一规则**，
     这样旧记录里的零宽字符也会在归一化时被消掉，不会导致「定位失效」。
     （2026-09-24 修） */
  var INVIS_RE = /[\s\u200b-\u200f\u202a-\u202e\u2060\ufeff]/;
  var INVIS_G = /[\s\u200b-\u200f\u202a-\u202e\u2060\ufeff]/g;
  /** 整串是否「只有空白」（把零宽字符也算作空白） */
  function isBlankStr(s) { return !String(s == null ? '' : s).replace(INVIS_G, '').length; }

  /** 把 root 里「用户看得见的文字」按文档序拼成一个字符串。
      includeHidden=true 时不跳 KaTeX 隐藏副本 —— **只给旧记录兼容层用**（见 locateLegacy）。
      返回 {str, parts}；parts[i] = {node, start, len}。 */
  function projOf(root, includeHidden) {
    var parts = [], str = '';
    if (!root || !root.ownerDocument) return { str: str, parts: parts };
    var w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (n.nodeType === 1) {
          if ((n.matches && n.matches('script, style, noscript, svg')) ||
            (n.hasAttribute && n.hasAttribute('hidden'))) return NodeFilter.FILTER_REJECT;
          if (!includeHidden && n.matches && n.matches(SKIP_SEL)) return NodeFilter.FILTER_REJECT;
          return NodeFilter.FILTER_SKIP;      // 只看文字，元素本身不出现在结果里
        }
        return (n.nodeValue && n.nodeValue.length) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    });
    var n;
    while ((n = w.nextNode())) {
      parts.push({ node: n, start: str.length, len: n.nodeValue.length });
      str += n.nodeValue;
    }
    return { str: str, parts: parts };
  }
  function partOf(proj, node) {
    for (var i = 0; i < proj.parts.length; i++) if (proj.parts[i].node === node) return proj.parts[i];
    return null;
  }
  /** 把 DOM 边界 (node, offset) 映射成投影串下标。
      边界可能落在被跳过的隐藏子树里（比如 .katex-mathml），
      这时取文档序上最近的**可见**边界。 */
  function snap(proj, node, offset, isEnd) {
    if (!node) return isEnd ? 0 : proj.str.length;
    var p = partOf(proj, node);
    if (p) return p.start + Math.max(0, Math.min(offset | 0, p.len));
    if (node.nodeType === 1) {
      var kids = node.childNodes, k = Math.max(0, Math.min(offset | 0, kids.length));
      var inner = null, i;
      for (i = 0; i < proj.parts.length; i++) {
        if (node.contains(proj.parts[i].node)) { (inner = inner || []).push(proj.parts[i]); }
      }
      if (inner && inner.length) {
        var tail = inner[inner.length - 1];
        if (k >= kids.length) return tail.start + tail.len;
        for (i = 0; i < inner.length; i++) {
          var rel = kids[k].compareDocumentPosition(inner[i].node);
          if (inner[i].node === kids[k] || (rel & 4)) return inner[i].start;
        }
        return tail.start + tail.len;
      }
    }
    var acc = 0;
    for (var m = 0; m < proj.parts.length; m++) {
      var q = proj.parts[m];
      var r = node.compareDocumentPosition(q.node);
      if ((r & 4) && !(r & 16)) return isEnd ? acc : q.start;   // q 在边界之后
      if ((r & 2) && !(r & 16)) acc = q.start + q.len;          // q 在边界之前
    }
    return isEnd ? acc : proj.str.length;
  }
  /** 两种压缩空间：'space' 把空白折叠成一个空格（默认，可读性好）；
      'tight' 去掉全部空白（兜底，用来兼容旧版记录里混着的 \n / \t）。 */
  function squash(raw, mode) {
    var out = '', map = [], prevSp = true, i, c;
    for (i = 0; i < raw.length; i++) {
      c = raw.charAt(i);
      if (INVIS_RE.test(c)) {
        if (mode === 'tight') continue;
        if (prevSp) continue;
        out += ' '; map.push(i); prevSp = true;
      } else { out += c; map.push(i); prevSp = false; }
    }
    return { s: out, map: map };
  }
  /** 在投影串下标空间里取回一个真实 Range */
  function rangeAt(proj, from, to) {
    function bnd(idx) {
      for (var k = proj.parts.length - 1; k >= 0; k--) {
        var p = proj.parts[k];
        if (p.start <= idx) return { node: p.node, off: Math.min(idx - p.start, p.len) };
      }
      return null;
    }
    var a = bnd(from), b = bnd(to);
    if (!a || !b) return null;
    var r = document.createRange();
    try { r.setStart(a.node, a.off); r.setEnd(b.node, b.off); } catch (e) { return null; }
    return r.collapsed ? null : r;
  }
  /** 候选匹配：分层收集**全部**出现位置（每层最多 40 个），交给 rankRange 挑最干净的那个。
      T1 压缩空白空间里 prefix+quote   T2 压缩空白空间里 quote
      T3 去空白空间里 prefix+quote     T4 去空白空间里 quote（旧版记录的兜底）
      注意 skip：命中的是 prefix+quote，但**上色范围只能从 quote 的第一个字开始**，
      否则连前缀一起标黄（踩过：笔记的 quote 会越滚越长）。 */
  function candidates(proj, prefix, quote) {
    var sp = squash(proj.str, 'space'), tg = squash(proj.str, 'tight');
    var normQuote = String(quote == null ? '' : quote).replace(INVIS_G, ' ').replace(/\s+/g, ' ').trim();
    var normPre = String(prefix == null ? '' : prefix).replace(INVIS_G, ' ').replace(/\s+/g, ' ').trim().slice(-24);
    var tightQuote = String(quote == null ? '' : quote).replace(INVIS_G, '');
    var tightPre = String(prefix == null ? '' : prefix).replace(INVIS_G, '').slice(-16);
    var res = [];
    function push(space, needle, skip) {
      if (!needle) return;
      var from = 0, i, n = 0;
      while (n < 40 && (i = space.s.indexOf(needle, from)) >= 0) {
        var a = space.map[i + skip], b = space.map[i + needle.length - 1];
        if (a != null && b != null && b >= a) res.push({ from: a, to: b + 1 });
        from = i + 1; n++;
      }
    }
    push(sp, normPre && (normPre + normQuote), normPre ? normPre.length : 0);
    push(sp, normQuote, 0);
    push(tg, tightPre && (tightPre + tightQuote), tightPre ? tightPre.length : 0);
    push(tg, tightQuote, 0);
    return res;
  }
  function blockAncestor(node) {
    var el = (node && node.nodeType === 1) ? node : (node ? node.parentNode : null);
    while (el && el.nodeType === 1) {
      if (BLOCK_TAGS.test(el.tagName)) return el;
      el = el.parentNode;
    }
    return null;
  }
  function cellAncestor(node) {
    var el = blockAncestor(node);
    while (el && el !== document.body) {
      if (CELL_TAGS.test(el.tagName)) return el;
      el = blockAncestor(el.parentNode);
    }
    return null;
  }
  /** 给候选打分，越低越好：
      0 = 起止落在**同一个块**内（理想）；1 = 跨块；2 = 跨块且涉及表格/列表。 */
  function rankRange(r) {
    var a = blockAncestor(r.startContainer), b = blockAncestor(r.endContainer);
    if (a && a === b) return 0;
    if (cellAncestor(r.startContainer) || cellAncestor(r.endContainer) ||
      cellAncestor(r.commonAncestorContainer)) return 2;
    return 1;
  }
  /** 在 root 内按「前缀 + 引用」找 Range；找不到返回 null。 */
  function pick(proj, prefix, quote) {
    if (!proj.str) return null;
    var cands = candidates(proj, prefix, quote);
    var best = null, bestRank = 9;
    for (var i = 0; i < cands.length; i++) {
      var r = rangeAt(proj, cands[i].from, cands[i].to);
      if (!r) continue;
      var rk = rankRange(r);
      if (rk < bestRank) { best = r; bestRank = rk; if (rk === 0) break; }
    }
    return best;
  }
  /** 兼容层：**旧版记录**的 quote 里混着 .katex-mathml 的隐藏副本
      （实测公式会出现三遍：MathML 的 M、annotation 的 \mathcal{M}、可见的 M）。
      在「含隐藏副本」的旧文本空间里再找一遍，然后把边界**吸附到可见文本**上 ——
      这样既能救回旧笔记，又不会把标记打在 1px 的隐藏副本上（那会「什么都看不见」）。 */
  function locateLegacy(root, prefix, quote) {
    var all = projOf(root, true), proj = projOf(root, false);
    var cands = candidates(all, prefix, quote);
    for (var i = 0; i < cands.length; i++) {
      var rAll = rangeAt(all, cands[i].from, cands[i].to);
      if (!rAll) continue;
      var a = snap(proj, rAll.startContainer, rAll.startOffset, false);
      var b = snap(proj, rAll.endContainer, rAll.endOffset, true);
      if (b <= a) continue;
      var r = rangeAt(proj, a, b);
      if (r) return r;
    }
    return null;
  }
  function locate(root, prefix, quote) {
    return pick(projOf(root), prefix, quote) || locateLegacy(root, prefix, quote);
  }
  /** 由一段 Range 反算出「投影空间」的 quote / prefix —— 存与找共用同一套口径。 */
  function canon(sec, range) {
    var proj = projOf(sec);
    var ia = snap(proj, range.startContainer, range.startOffset, false);
    var ib = snap(proj, range.endContainer, range.endOffset, true);
    if (ib <= ia) return null;
    var q = proj.str.slice(ia, ib).replace(INVIS_G, ' ').replace(/\s+/g, ' ').trim();
    if (!q) return null;
    return { quote: q, prefix: proj.str.slice(0, ia).replace(INVIS_G, ' ').replace(/\s+/g, ' ').trim().slice(-24) };
  }

  /* 造一个高亮元素。cls 两种取值：
       'hl'（默认）—— 「我的标记」，带 data-nid 供笔记系统定位、可点击编辑；
       'q-hit'      —— 正文搜索的**临时命中高亮**，不带 data-nid、不进笔记系统，
                       清空查询时被 clearHits() 全部拆除。
     两者共用同一套「只在文字节点内部动手」的封装（铁律①），
     但类名严格分开 —— 笔记的 unwrapAll / audit / restoreAll 只认 mark.hl，
     因此搜索高亮绝不会被误当成笔记（反之亦然）。 */
  function newMark(nid, cls) {
    var mk = document.createElement('mark');
    mk.className = cls || 'hl';
    if (mk.className === 'hl') {
      mk.setAttribute('data-nid', nid);
      mk.title = '点击查看／编辑这条笔记';
    }
    return mk;
  }
  /* 上色过程的追踪开关（排查「为什么这条边记拆成了 N 个 mark」用）：
     window.__doc.traceWrap(true) 打开，mark 一次，再 __doc.lastTrace() 读。 */
  var wrapTrace = null;
  function trace(msg) { if (wrapTrace) wrapTrace.push(msg); }
  function brief(t) { return String(t).replace(/\s+/g, '·').slice(0, 18); }
  /** 把一个「片段」包成 mark。片段完全落在一个文字节点内 → 一定能成功，
      且绝不会惊动块级结构（铁律 ①）。返回是否成功。
      **刻意不用 extractContents 兜底**：它会把被「部分包含」的元素克隆进 mark，
      unwrap 之后留下克隆残骸，反复标记/删除会不断堆积。宁可多拆几个 mark。 */
  function wrapOne(a, b, nid, cls) {
    var r = document.createRange();
    try {
      r.setStart(a.node, a.s);
      r.setEnd(b.node, b.e);
      if (r.collapsed) return false;
      trace('  try 「' + brief(a.node.nodeValue.slice(a.s, a.s + 18)) + '」→ 「' +
        brief(b.node.nodeValue.slice(Math.max(0, b.e - 18), b.e)) + '」');
      r.surroundContents(newMark(nid, cls));
      trace('    ok');
      return true;
    } catch (e) { trace('    ' + e.name); return false; }
  }
  /** 一组内二分收敛：先试整组（能合成一个 mark 最好），失败就把组对半拆开再试。
      这样既不会搬动块级结构，又能把 mark 数量压到最少。
      实测：<td> 里「实数，如 20.50、42」会被 KaTeX 的内联片段挡住，
      surroundContents 报 InvalidStateError（部分包含 <span class="katex">），
      于是拆到四个单节点 mark —— 这是**有意的保守选择**：
      宁可多拆，也不用 extractContents（那条路会克隆元素、留下残骸）。 */
  function wrapGroup(items, nid, cls) {
    if (!items.length) return 0;
    if (items.length === 1) return wrapOne(items[0], items[0], nid, cls) ? 1 : 0;
    if (wrapOne(items[0], items[items.length - 1], nid, cls)) return 1;
    var h = Math.floor(items.length / 2);
    return wrapGroup(items.slice(0, h), nid, cls) + wrapGroup(items.slice(h), nid, cls);
  }
  /** 结构安全的上色：把 range 拆成「文字节点级」的片段，
      按最近的块级祖先分组，每组交给 wrapGroup 收敛。
      纯空白片段直接跳过 —— 那是「标记处多出一个换行」的元凶之一。
      返回实际生成的 mark 数量。 */
  function wrapRange(range, nid, cls) {
    var anc = range.commonAncestorContainer;
    var root = (anc && anc.nodeType === 1) ? anc : (anc ? anc.parentNode : null);
    if (!root || !root.ownerDocument) return 0;
    var proj = projOf(root);
    /* 已经上过色的片段要跳过，否则同一次操作会把 mark 套进 mark。
       两种高亮各查各的祖先：'hl' 认自己的 nid，'q-hit' 认类名。 */
    var skipSel = (cls === 'q-hit') ? 'mark.q-hit' : ('mark.hl[data-nid="' + nid + '"]');
    var segs = [], i;
    for (i = 0; i < proj.parts.length; i++) {
      var p = proj.parts[i], n = p.node;
      var hits = false;
      try { hits = range.intersectsNode(n); } catch (e) { hits = false; }
      if (!hits) continue;
      if (isBlankStr(n.nodeValue)) continue;
      var s = 0, e = p.len;
      if (n === range.startContainer) s = range.startOffset;
      if (n === range.endContainer) e = range.endOffset;
      if (e <= s) continue;
      if (isBlankStr(n.nodeValue.slice(s, e))) continue;
      if (n.parentNode && n.parentNode.closest && n.parentNode.closest(skipSel)) continue;
      segs.push({ node: n, s: s, e: e });
    }
    if (!segs.length) return 0;

    var groups = [], cur = null;
    for (i = 0; i < segs.length; i++) {
      var blk = blockAncestor(segs[i].node);
      if (cur && cur.blk === blk) cur.items.push(segs[i]);
      else { cur = { blk: blk, items: [segs[i]] }; groups.push(cur); }
    }
    var made = 0;
    for (i = 0; i < groups.length; i++) made += wrapGroup(groups[i].items, nid, cls);
    return made;
  }
  function restore(m) {
    if ($('mark.hl[data-nid="' + m.id + '"]')) return true;
    var sec = document.getElementById(m.pid);
    if (!sec) return false;
    var r = locate(sec, m.prefix || '', m.quote);
    if (!r) return false;
    /* 先算好「投影口径」的 quote/prefix 再上色：命中走了 T3/T4（去空白）这两层兜底时，
       顺手把记录改写成规范形式，下次就能在 T1 一次命中 —— 旧版记录自愈。 */
    var c = canon(sec, r);
    if (!wrapRange(r, m.id)) return false;
    if (c && (c.quote !== m.quote || c.prefix !== m.prefix)) {
      m.quote = c.quote; m.prefix = c.prefix; Notes.save();
    }
    return true;
  }

  /* ======================= 8. 笔记：UI ======================= */
  var selBar = null;
  function hideSelBar() { if (selBar) selBar.classList.remove('on'); }

  /* 剪贴板：优先用异步 API（file:// 下多数浏览器可用），失败退回 execCommand。

     **必须带超时**。`navigator.clipboard.writeText()` 在「文档没有焦点」时
     既不会 resolve 也不会 reject —— Promise 永远挂着。无头浏览器里 100% 复现；
     真实浏览器里，用户用键盘快捷键或脚本触发时同样会遇到。
     没有超时的话，复制按钮点下去会**完全没有任何反馈**（不弹提示、按钮不变色），
     用户只会以为按钮坏了。实测确认过这一点（probe 报 pending 直到超时）。
     超时后走 execCommand 兜底：成功就报成功、失败就报失败，无论如何都有反馈。

     `done(ok)` 可选回调，告诉调用方到底成没成。 */
  function copyText(t, done) {
    var fired = false;
    function finish(ok) { if (!fired) { fired = true; if (done) done(!!ok); } return !!ok; }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      /* 600ms 足够：正常情况这个 Promise 是微秒级返回的，慢到这里说明它挂住了 */
      var timer = setTimeout(function () { finish(fallbackCopy(t)); }, 600);
      navigator.clipboard.writeText(t).then(
        function () { clearTimeout(timer); finish(true); },
        function () { clearTimeout(timer); finish(fallbackCopy(t)); });
      return true;
    }
    return finish(fallbackCopy(t));
  }
  function fallbackCopy(t) {
    var ta = document.createElement('textarea');
    ta.value = t; ta.style.position = 'fixed'; ta.style.top = '0';
    ta.style.left = '0'; ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus(); ta.select();
    if (ta.setSelectionRange) { try { ta.setSelectionRange(0, ta.value.length); } catch (e) {} }
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }
  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  /* 轻提示条。**这个函数此前一直缺失** —— site.js 里有 8 处 toast(...) 调用
     （标记失败提示、Markdown 引用已复制、内嵌原文件打不开…），却没有任何定义，
     跑到那些分支就是一个 ReferenceError，而且报错点离真正的写法很远、极难追。
     模块加载期不会暴露（只在被调用时才炸），所以静态体检和截图都照不出来。
     现在补上：单例 DOM、2.4 秒自动隐去，连点则重置计时。 */
  var toastEl = null, toastTimer = 0;
  function toast(msg) {
    if (!toastEl) {
      toastEl = document.createElement('div');
      toastEl.className = 'toast';
      toastEl.setAttribute('role', 'status');
      toastEl.setAttribute('aria-live', 'polite');
      document.body.appendChild(toastEl);
    }
    toastEl.textContent = String(msg == null ? '' : msg);
    toastEl.classList.add('on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove('on'); }, 2400);
  }

  /* 把「当前选区」加入笔记。返回 true 表示成功。
     三处复用：选区工具条 / 顶栏 #markBtn / 自绘右键菜单 / 快捷键 M。
     为什么需要 lastSel 缓存：点击顶栏按钮时浏览器可能已经把选区收起来了，
     所以点击时要能回退到「最近一次有效选区」。 */
  var lastSel = null;
  function captureSelection() {
    var sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) return false;
    var text = sel.toString().replace(INVIS_G, ' ').replace(/\s+/g, ' ').trim();
    if (!text) return false;
    var node = sel.getRangeAt(0).startContainer;
    var host = node.nodeType === 1 ? node : node.parentNode;
    if (!host || !host.closest || !host.closest('.pg-text, .card')) return false;
    lastSel = { range: sel.getRangeAt(0).cloneRange(), text: text };
    return true;
  }

  function markSelection() {
    var sel = window.getSelection();
    var live = sel && !sel.isCollapsed && sel.rangeCount > 0 && !isBlankStr(sel.toString());
    var range = live ? sel.getRangeAt(0).cloneRange() : (lastSel && lastSel.range);
    var text = live ? sel.toString().replace(INVIS_G, ' ').replace(/\s+/g, ' ').trim() : (lastSel && lastSel.text);
    if (!range || !text) {
      toast('先在正文里选一段文字，再点「标记选中」（选中后直接按 M 也行）');
      return false;
    }
    var host = range.startContainer.nodeType === 1 ? range.startContainer : range.startContainer.parentNode;
    var sec = host && host.closest ? host.closest('section[data-page], section[id]') : null;
    if (!sec) { toast('这里的内容不在讲解正文里，标记不了'); return false; }
    /* quote / prefix 一律从「投影空间」取（见 §7 铁律 ②）：
       浏览器给的 text 只在选区整个落在隐藏副本里时兜底。 */
    var c = canon(sec, range);
    var m = Notes.add({
      pid: sec.id, page: sec.getAttribute('data-page') || '',
      loc: locOf(sec),
      quote: (c && c.quote) || text, prefix: (c && c.prefix) || '', note: ''
    });
    try {
      var r2 = range.cloneRange();
      if (sel) sel.removeAllRanges();
      wrapRange(r2, m.id);
    } catch (e3) {}
    /* 必须在这儿再重绘一次：Notes.add() 内部的 render() 发生在上色之前，
       那一刻 DOM 里还没有 mark.hl，卡片会被误判成「定位失效」并一直留着。 */
    Notes.render();
    lastSel = null;
    hideSelBar(); hideCtx();
    Notes.openDrawer(true);
    Notes.flashItem(m.id);
    markBtnState();
    return true;
  }

  /* 顶栏「标记选中」按钮的可用状态提示 */
  function markBtnState() {
    var b = document.getElementById('markBtn');
    if (!b) return;
    var ok = captureSelection();
    b.setAttribute('data-empty', ok ? '0' : '1');
  }

  function buildSelBar() {
    selBar = document.createElement('div');
    selBar.className = 'selbar';
    selBar.innerHTML = '<button type="button" data-act="mark">✎ 标记</button>' +
      '<button type="button" data-act="copy">复制</button>' +
      '<button type="button" data-act="cancel">×</button>';
    document.body.appendChild(selBar);
    selBar.addEventListener('mousedown', function (e) { e.preventDefault(); });
    selBar.addEventListener('click', function (e) {
      var b = e.target.closest ? e.target.closest('button') : null;
      if (!b) return;
      var act = b.getAttribute('data-act');
      if (act === 'cancel') { hideSelBar(); return; }
      if (act === 'mark') { markSelection(); return; }
      if (act === 'copy') {
        var s = window.getSelection();
        if (s && !s.isCollapsed) copyText(s.toString());
        hideSelBar();
      }
    });
  }

  /* ---------------------------------------------------------------------------
     选区工具条的定位
     关键：Edge/Chrome 选中文本后会浮出浏览器自己的「迷你菜单」，那条菜单由浏览器
     UI 层绘制，网页里 z-index 再高也压不住。它默认出现在选区【上方】，所以这里
     把工具条优先放到选区【下方】来做避让，只有下面实在没地方了才翻回上方。
     另外还提供两条完全不经浮层的入口：顶栏 #markBtn 与快捷键 M。
     --------------------------------------------------------------------------- */
  function onSelectionEnd(e) {
    if (!selBar) return;
    if (e && e.target && e.target.closest &&
      (e.target.closest('.toc') || e.target.closest('.drawer') ||
       e.target.closest('.selbar') || e.target.closest('.ctxmenu'))) return;

    if (!captureSelection()) { hideSelBar(); markBtnState(); return; }
    var r = lastSel.range.getBoundingClientRect();
    if (!r.width && !r.height) return;

    selBar.classList.add('on');
    var w = selBar.offsetWidth || 190, h = selBar.offsetHeight || 34;
    var left = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), window.innerWidth - w - 8);

    /* 方向决策全部用视口坐标（r 就是视口坐标），最后再转成文档坐标 */
    var vh = window.innerHeight;
    var roomBelow = vh - r.bottom, roomAbove = r.top;
    var useBelow = (roomBelow >= h + 14) || (roomAbove < h + 14);
    if (r.top > vh) useBelow = true;          // 选区落在视口下方（罕见）→ 也放下方
    var top = useBelow ? (r.bottom + 12) : (r.top - h - 12);
    /* 夹紧到视口内，避免贴边时露出一半 */
    var docTop = top + window.scrollY;
    docTop = Math.max(window.scrollY + 8, Math.min(docTop, window.scrollY + vh - h - 10));
    selBar.classList.toggle('below', useBelow);
    selBar.classList.toggle('above', !useBelow);
    selBar.style.left = left + 'px';
    selBar.style.top = docTop + 'px';
    markBtnState();
  }

  /* ---------------------------------------------------------------------------
     自绘右键菜单
     只在「正文里有选区」时接管右键，此时系统菜单根本不会出现，两者不会再互相遮挡；
     菜单里补上「复制」以免用户失去这个能力。
     想用系统菜单时按住 Shift 再右键（常规的 Web 逃生通道）。
     --------------------------------------------------------------------------- */
  var ctx = null, ctxX = 0, ctxY = 0;
  function hideCtx() { if (ctx) ctx.classList.remove('on'); }
  function buildCtx() {
    ctx = document.createElement('div');
    ctx.className = 'ctxmenu';
    ctx.innerHTML =
      '<div class="hint">已选中文字 · 按住 <b>Shift</b> 右键可调出系统菜单</div>' +
      '<button type="button" data-act="mark">✎ 加入笔记<span class="k">M</span></button>' +
      '<button type="button" data-act="copy">复制<span class="k">Ctrl C</span></button>' +
      '<button type="button" data-act="quote">复制为引用</button>';
    document.body.appendChild(ctx);
    ctx.addEventListener('mousedown', function (e) { e.preventDefault(); });
    ctx.addEventListener('click', function (e) {
      var b = e.target.closest ? e.target.closest('button') : null;
      if (!b) return;
      var act = b.getAttribute('data-act');
      if (act === 'mark') { markSelection(); return; }
      if (act === 'copy') {
        var s = window.getSelection();
        if (s && !s.isCollapsed) copyText(s.toString());
        hideCtx(); return;
      }
      if (act === 'quote') {
        var s2 = window.getSelection();
        var t = (s2 && !s2.isCollapsed) ? s2.toString() : (lastSel && lastSel.text) || '';
        var lines = t.replace(/\r/g, '').split('\n').map(function (x) { return '> ' + x; }).join('\n');
        copyText(lines);
        toast('已复制为 Markdown 引用');
        hideCtx(); return;
      }
    });
    document.addEventListener('contextmenu', function (e) {
      if (e.shiftKey) { hideCtx(); return; }              // Shift+右键 → 交给系统
      var t = e.target;
      if (!t || !t.closest) return;
      if (t.closest('.toc') || t.closest('.drawer') || t.closest('.topbar')) return;
      if (!t.closest('.pg-text, .card')) return;
      var sel = window.getSelection();
      var hasSel = sel && !sel.isCollapsed && sel.toString().trim();
      if (!hasSel) { hideCtx(); return; }                 // 没选区 → 交给系统
      captureSelection();
      e.preventDefault();
      ctxX = e.pageX; ctxY = e.pageY;
      ctx.classList.add('on');
      var w = ctx.offsetWidth || 170, h2 = ctx.offsetHeight || 120;
      ctx.style.left = Math.min(ctxX, window.scrollX + window.innerWidth - w - 8) + 'px';
      ctx.style.top = Math.min(ctxY, window.scrollY + window.innerHeight - h2 - 8) + 'px';
    });
    document.addEventListener('mousedown', function (e) {
      if (ctx && ctx.classList.contains('on') && !(e.target.closest && e.target.closest('.ctxmenu'))) hideCtx();
    });
  }

  /* 顶栏「标记选中」：不依赖任何浮层，选中后点它即可（或直接按 M） */
  function initMarkBtn() {
    var b = document.getElementById('markBtn');
    if (!b) return;
    b.addEventListener('mousedown', function (e) { e.preventDefault(); });  // 保住选区
    b.addEventListener('click', function () { markSelection(); });
    markBtnState();
  }

  /* ---------- 抽屉 ---------- */
  var Drawer = {
    init: function () {
      Notes.drawer = $('#drawer');
      var self = this;
      var btn = $('#notesBtn');
      if (btn) btn.addEventListener('click', function () { Notes.toggleDrawer(); });
      var close = $('#drawerClose');
      if (close) close.addEventListener('click', function () { Notes.closeDrawer(); });
      var clr = $('#notesClear');
      if (clr) clr.addEventListener('click', function () { Notes.clear(); });
      var exp = $('#notesExport');
      if (exp) exp.addEventListener('click', function () {
        copyText(Notes.exportMd());
        var old = exp.textContent;
        exp.textContent = '已复制 ✓';
        setTimeout(function () { exp.textContent = old; }, 1600);
      });
      var list = $('#drawerList');
      if (list) {
        list.addEventListener('click', function (ev) {
          var t = ev.target.closest ? ev.target.closest('[data-act]') : null;
          if (!t) return;
          var id = t.getAttribute('data-nid');
          if (t.getAttribute('data-act') === 'del') Notes.remove(id);
          else if (t.getAttribute('data-act') === 'jump') Notes.jump(id);
        });
        list.addEventListener('input', function (ev) {
          var ta = ev.target;
          if (!ta.classList || !ta.classList.contains('note-input')) return;
          var m = Notes.get(ta.getAttribute('data-nid'));
          if (m) { m.note = ta.value; Notes.save(); }
        });
      }
      // 点击正文里的标记 → 打开抽屉并定位到对应条目
      document.addEventListener('click', function (ev) {
        var mk = ev.target.closest ? ev.target.closest('mark.hl') : null;
        if (!mk) return;
        Notes.openDrawer(false);
        Notes.flashItem(mk.getAttribute('data-nid'));
      });
      void self;
    }
  };

  Notes.toggleDrawer = function () {
    var d = Notes.drawer || $('#drawer');
    if (!d) return;
    if (d.classList.contains('on')) Notes.closeDrawer(); else Notes.openDrawer(false);
  };
  Notes.openDrawer = function (focus) {
    var d = Notes.drawer || $('#drawer');
    if (!d) return;
    d.classList.add('on');
    document.body.classList.add('drawer-open');
    var b = $('#notesBtn'); if (b) b.setAttribute('aria-expanded', 'true');
    if (focus) {
      var items = $$('#drawerList .note-item');
      var last = items[items.length - 1];
      var inp = last ? $('.note-input', last) : null;
      if (inp) { try { inp.focus({ preventScroll: true }); } catch (e) {} }
    }
  };
  Notes.closeDrawer = function () {
    var d = Notes.drawer || $('#drawer');
    if (!d) return;
    d.classList.remove('on');
    document.body.classList.remove('drawer-open');
    var b = $('#notesBtn'); if (b) b.setAttribute('aria-expanded', 'false');
  };
  Notes.jump = function (id) {
    var m = Notes.get(id);
    if (!m) return;
    var mk = $('mark.hl[data-nid="' + id + '"]');
    var el = mk || document.getElementById(m.pid);
    if (!el) return;
    if (mk) {
      try { mk.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
      catch (e) { mk.scrollIntoView(); }
      mk.classList.add('flash');
      setTimeout(function () { mk.classList.remove('flash'); }, 1900);
    } else {
      window.scrollTo({ top: el.offsetTop - 80, behavior: 'smooth' });
    }
    Notes.flashItem(id);
    if (MOBILE.matches) Notes.closeDrawer();
  };
  Notes.flashItem = function (id) {
    var card = $('#note-' + id);
    if (!card) return;
    card.classList.add('flash');
    setTimeout(function () { card.classList.remove('flash'); }, 1700);
    var d = $('#drawer');
    if (d && d.classList.contains('on')) {
      var dr = d.getBoundingClientRect(), cr = card.getBoundingClientRect();
      if (cr.top < dr.top + 70 || cr.bottom > dr.bottom) {
        d.scrollTop += (cr.top - dr.top) - 110;
      }
    }
  };

  Notes.render = function () {
    var list = $('#drawerList');
    var n = Notes.items.length;
    var badge = $('#notesBtnCount');
    if (badge) { badge.textContent = String(n); badge.classList.toggle('zero', n === 0); }
    var cnt = $('#drawerCount');
    if (cnt) cnt.textContent = n ? (n + ' 条') : '';
    if (!list) return;
    if (!n) {
      list.innerHTML = '<div class="empty">还没有标记。<br>' +
        '<span>在正文里选中一段文字，点浮出的「✎ 标记」，就会出现在这里。</span></div>';
      return;
    }
    list.innerHTML = Notes.items.slice().sort(function (a, b) { return a.ts - b.ts; })
      .map(function (m) {
        var alive = !!document.querySelector('mark.hl[data-nid="' + m.id + '"]');
        var t = new Date(m.ts);
        var ts = (t.getMonth() + 1) + '/' + t.getDate() + ' ' +
          ('0' + t.getHours()).slice(-2) + ':' + ('0' + t.getMinutes()).slice(-2);
        /* 位置一律重算（老笔记没存 loc 也能补上）；有页码就显示纯页码徽标，
           没有页码的卡片显示位置标签 —— 别再出现「P？」。 */
        var sec = document.getElementById(m.pid);
        var loc = locOf(sec) || m.loc || (m.page ? ('原文件 P' + m.page) : (m.pid ? ('#' + m.pid) : '本文档'));
        var tip = esc(sec ? locTip(sec, loc) : loc);
        var badge = m.page
          ? ('<span class="ni-page" title="' + tip + '">P' + esc(m.page) + '</span>')
          : ('<span class="ni-loc" title="' + tip + '">' + esc(loc) + '</span>');
        return '<div class="note-item" id="note-' + m.id + '">' +
          '<div class="ni-head">' + badge +
          '<span class="ni-time">' + ts + '</span>' +
          (alive ? '' : '<span class="ni-stale" title="正文中未找到对应文字（内容可能已更新）">定位失效</span>') +
          '</div>' +
          '<blockquote class="ni-quote">' + esc(m.quote) + '</blockquote>' +
          '<textarea class="note-input" data-nid="' + m.id + '" rows="2" ' +
          'placeholder="写点备注…（自动保存）">' + esc(m.note || '') + '</textarea>' +
          '<div class="ni-actions">' +
          '<button type="button" data-act="jump" data-nid="' + m.id + '">跳转 ›</button>' +
          '<button type="button" class="danger" data-act="del" data-nid="' + m.id + '">删除</button>' +
          '</div></div>';
      }).join('');
  };

  Notes.restoreAll = function () {
    var ok = 0, fail = 0;
    Notes.items.forEach(function (m) { if (restore(m)) ok++; else fail++; });
    Notes.render();
    return { ok: ok, fail: fail };
  };

  /* ======================= 8b. 正文搜索 =======================
     和「目录标题过滤」（Toc.filter）的分工与配合：
       · Toc.filter  —— 只匹配**目录条目文字**，命中项留在左栏目录里。
                         正文一条都没命中时回退到它，让「标题命中」照样可见；
                         老外壳（没有 #qres 的产物）也走这条路。
       · Find        —— 建一次**正文索引**，匹配每一节的可见文字（跳过 KaTeX 隐藏副本），
                         在 #qres 面板里给出「页码 + 标题 + 上下文片段」，点一条即跳转，
                         并在正文里把**该节内命中词的每一处**临时高亮。
     与笔记系统共存的四条约束（踩过的坑都在这）：
       ① 高亮元素用 <mark class="q-hit">，与笔记的 <mark class="hl"> 严格分开 ——
          笔记的 unwrapAll / audit / restoreAll 只认 mark.hl，两者永不互相误伤；
       ② 只对**单个文字节点内部**的一段动手（沿用 wrapRange 的铁律①，不搬元素）；
          跨内联边界的命中不给它套 mark，改让所在块级元素闪一下背景（.q-flash）；
       ③ 清空查询时把所有 mark.q-hit 拆掉并对父节点 normalize()，正文回到原样
          （否则文本节点会被反复切碎，笔记定位的候选会越来找越碎）；
       ④ 索引惰性建（首次输入才建），一节一个条目，只存小写全文，不存 DOM。
     ========================================================== */

  /** 在 root 里把 term 的**全部**命中包成 <mark class=cls>，返回生成的 mark 数。
      只在单个文字节点内部匹配 —— 这是唯一不需要动元素、因而绝对安全的粒度。
      倒序处理每个节点内的命中：先包后面的，前面的下标才不受 splitText 影响。 */
  function wrapTextHits(root, term, cls) {
    if (!root || !term) return 0;
    var t = String(term).toLowerCase();
    if (!t) return 0;
    var nodes = [];
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (!n.nodeValue || !n.nodeValue.length) return NodeFilter.FILTER_REJECT;
        var p = n.parentNode;
        if (p && p.closest &&
          (p.closest(SKIP_SEL) || p.closest('mark.hl, mark.q-hit'))) {
          return NodeFilter.FILTER_REJECT;      // KaTeX 隐藏副本 / 已上色的片段
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var n;
    while ((n = w.nextNode())) nodes.push(n);
    var made = 0;
    nodes.forEach(function (node) {
      var s = node.nodeValue, low = s.toLowerCase();
      if (low.length !== s.length) return;      // 极小概率的长度变化，直接跳过最稳
      var from = 0, p, hits = [];
      while ((p = low.indexOf(t, from)) >= 0) { hits.push(p); from = p + t.length; }
      for (var k = hits.length - 1; k >= 0; k--) {
        try {
          var r = document.createRange();
          r.setStart(node, hits[k]);
          r.setEnd(node, hits[k] + t.length);
          var mk = document.createElement('mark');
          mk.className = cls;
          r.surroundContents(mk);
          made++;
        } catch (e) { /* 不该发生：单节点内的 Range 一定可包围。真发生就跳过 */ }
      }
    });
    return made;
  }

  /** 哪一块是「命中的那一块」—— 用于高亮的兜底反馈（跨内联边界时套不上 mark）。 */
  function hitBlockOf(sec, terms) {
    var blocks = $$('p, li, td, th, h3, h4, .note, .tip, .flag, .quote', sec);
    for (var i = 0; i < blocks.length; i++) {
      var t = (blocks[i].textContent || '').toLowerCase();
      for (var k = 0; k < terms.length; k++) if (t.indexOf(terms[k]) >= 0) return blocks[i];
    }
    return null;
  }

  var Find = {
    idx: null,          // [{sec,id,page,title,text,lower}]，惰性建
    items: [],          // 当前结果行（与 #qres 里的 .qhit 一一对应）
    terms: [],          // 当前查询词（已小写、去重）
    on: -1,             // 键盘选中的行号
    MAX_ROWS: 120,
    PER_SEC: 3,         // 每节最多列几条片段

    /** 把查询拆成词：空白分隔，多词是**且**的关系。CJK 无空格，整串就是一个词。 */
    split: function (raw) {
      var seen = {}, out = [];
      String(raw == null ? '' : raw).toLowerCase()
        .replace(/[\s\u200b-\u200f\u202a-\u202e\u2060\ufeff]+/g, ' ')
        .split(' ')
        .forEach(function (t) { if (t && !seen[t]) { seen[t] = 1; out.push(t); } });
      return out;
    },

    /** 一节的显示名：页章节给「P12 · 标题」，卡片给它的 h2。 */
    titleOf: function (sec) {
      var h = $('.pg-head h3', sec) || $('h2', sec) || $('h3', sec);
      var t = '';
      if (h) t = (h.textContent || '').replace(/\s+/g, ' ').trim();
      if (!t) t = (sec.getAttribute('data-page') ? ('原文件 P' + sec.getAttribute('data-page')) : sec.id);
      return t.length > 46 ? (t.slice(0, 45) + '…') : t;
    },

    build: function () {
      var idx = [];
      $$('section[id]').forEach(function (sec) {
        var sp = squash(projOf(sec).str, 'space');
        if (!sp.s || isBlankStr(sp.s)) return;      // 空节（纯图占位/分隔）不进索引
        idx.push({
          sec: sec, id: sec.id,
          page: sec.getAttribute('data-page') || '',
          title: Find.titleOf(sec),
          text: sp.s, lower: sp.s.toLowerCase()
        });
      });
      this.idx = idx;
      return idx;
    },

    search: function (terms) {
      var idx = this.idx || this.build();
      var out = [], i, k;
      for (i = 0; i < idx.length; i++) {
        var e = idx[i], ok = true, anchor = null;
        for (k = 0; k < terms.length; k++) {
          var at = e.lower.indexOf(terms[k]);
          if (at < 0) { ok = false; break; }
          if (anchor == null) anchor = terms[k];
        }
        if (!ok) continue;
        var titleHit = 0;
        for (k = 0; k < terms.length; k++) if (e.title.toLowerCase().indexOf(terms[k]) >= 0) titleHit = 1;
        var from = 0, n = 0, pos;
        while (n < this.PER_SEC && (pos = e.lower.indexOf(anchor, from)) >= 0) {
          out.push({
            e: e, at: pos, len: anchor.length, titleHit: titleHit,
            prefix: e.text.slice(Math.max(0, pos - 24), pos)
          });
          from = pos + anchor.length; n++;
        }
      }
      /* 标题命中的节排前面，其余保持文档序（稳定排序：比较函数只用 titleHit）。 */
      out.forEach(function (r, n) { r.seq = n; });
      out.sort(function (a, b) { return (b.titleHit - a.titleHit) || (a.seq - b.seq); });
      return out;
    },

    /** 片段：命中处前后各留一段上下文，窗口内的**所有**查询词都上高亮。 */
    snippet: function (r) {
      var text = r.e.text;
      var from = Math.max(0, r.at - 34);
      var to = Math.min(text.length, r.at + r.len + 46);
      var head = (from > 0 ? '…' : '') + text.slice(from, to) + (to < text.length ? '…' : '');
      var lo = head.toLowerCase();
      var cuts = [], k, f, p;
      for (k = 0; k < this.terms.length; k++) {
        f = 0;
        while ((p = lo.indexOf(this.terms[k], f)) >= 0) {
          cuts.push([p, p + this.terms[k].length]);
          f = p + this.terms[k].length;
        }
      }
      cuts.sort(function (a, b) { return a[0] - b[0]; });
      var frag = document.createDocumentFragment(), cur = 0;
      cuts.forEach(function (c) {
        if (c[0] < cur) return;
        if (c[0] > cur) frag.appendChild(document.createTextNode(head.slice(cur, c[0])));
        var mk = document.createElement('mark');
        mk.className = 'q-hit';
        mk.textContent = head.slice(c[0], c[1]);
        frag.appendChild(mk);
        cur = c[1];
      });
      if (cur < head.length) frag.appendChild(document.createTextNode(head.slice(cur)));
      return frag;
    },

    render: function () {
      var box = $('#qres');
      if (!box) return 0;
      var self = this;
      var rows = this.search(this.terms);
      this.items = rows;
      this.on = -1;
      box.innerHTML = '';
      var pages = {}, acc = 0;
      rows.forEach(function (r) { if (!pages[r.e.id]) { pages[r.e.id] = 1; acc++; } });
      var sum = document.createElement('div');
      sum.className = 'qsum';
      sum.textContent = rows.length
        ? ('正文命中 ' + rows.length + ' 处 · 涉及 ' + acc + ' 页' +
           (rows.length > this.MAX_ROWS ? '（只列前 ' + this.MAX_ROWS + ' 条）' : '') +
           '　↑↓ 选择 · Enter 跳转 · Esc 清除')
        : ('正文里没有「' + this.terms.join(' ') + '」。换个更短的词试试；' +
           '下面目录只剩标题命中的条目。');
      box.appendChild(sum);
      if (rows.length) {
        var shown = rows.slice(0, this.MAX_ROWS), lastId = null;
        shown.forEach(function (r, i) {
          var d = document.createElement('div');
          d.className = 'qhit';
          if (r.e.id !== lastId) {
            var h = document.createElement('div');
            h.className = 'qp';
            h.textContent = (r.e.page ? ('P' + r.e.page + ' · ') : '') + r.e.title;
            d.appendChild(h);
            lastId = r.e.id;
          }
          var s = document.createElement('div');
          s.className = 'qs';
          s.appendChild(self.snippet(r));
          d.appendChild(s);
          d.addEventListener('click', function () { self.goto(i); });
          box.appendChild(d);
        });
      }
      box.hidden = false;
      box.classList.add('on');
      return rows.length;
    },

    /* 没有正文命中时：把目录交还给用户，只留标题过滤（老行为） */
    fallbackToToc: function (raw) {
      var nav = $('.toc-nav');
      if (nav) nav.classList.remove('off');
      Toc.filter(raw);
    },

    run: function (input) {
      var raw = input ? String(input.value || '') : '';
      var box = $('#qres');
      if (!box) { Toc.filter(raw); return 0; }   // 老外壳：退化成「只过滤目录标题」
      this.terms = this.split(raw);
      this.clearHits();
      if (!this.terms.length) {
        box.hidden = true;
        box.classList.remove('on');
        box.innerHTML = '';
        this.items = [];
        var nav = $('.toc-nav');
        if (nav) nav.classList.remove('off');
        return 0;
      }
      var n = this.render();
      var nav2 = $('.toc-nav');
      if (!n) {
        this.fallbackToToc(raw);
      } else if (nav2) {
        nav2.classList.add('off');   // 正文命中优先，目录让位给结果面板
      }
      return n;
    },

    /** 跳到第 i 条结果：拆掉上一批高亮 → 高亮本节所有命中 → 滚到第一处命中。 */
    goto: function (i) {
      var r = this.items[i];
      if (!r) return false;
      this.on = i;
      this.syncActive();
      this.clearHits();          // 只保留「当前这一节」的高亮，避免整篇越点越花
      var sec = r.e.sec;
      var made = 0, k;
      for (k = 0; k < this.terms.length; k++) {
        made += wrapTextHits(sec, this.terms[k], 'q-hit');
      }
      var mk = $('mark.q-hit', sec);
      if (mk && mk.scrollIntoView) {
        mk.scrollIntoView({ block: 'center' });
      } else {
        /* 命中跨了内联元素边界（例如「1×1 卷积」被 <script> 公式切成两半）：
           套不上 mark 就让所在块闪一下，至少告诉读者「在这一段里」。 */
        var blk = hitBlockOf(sec, this.terms);
        if (blk) {
          if (blk.scrollIntoView) blk.scrollIntoView({ block: 'center' });
          blk.classList.add('q-flash');
          setTimeout(function () { blk.classList.remove('q-flash'); }, 1500);
        } else if (sec.scrollIntoView) {
          sec.scrollIntoView({ block: 'start' });
        }
      }
      return true;
    },

    clearHits: function () {
      $$('mark.q-hit').forEach(function (mk) {
        var p = mk.parentNode;
        if (!p) return;
        while (mk.firstChild) p.insertBefore(mk.firstChild, mk);
        p.removeChild(mk);
        if (p.normalize) p.normalize();     // 合并被切碎的文本节点，别让候选越来越碎
      });
      $$('.q-flash').forEach(function (b) { b.classList.remove('q-flash'); });
    },

    syncActive: function () {
      var self = this;
      var box = $('#qres');
      $$('.qhit', box).forEach(function (el, i) {
        el.classList.toggle('on', i === self.on);
        if (i !== self.on || !box) return;
        var er = el.getBoundingClientRect(), br = box.getBoundingClientRect();
        if (er.top < br.top || er.bottom > br.bottom) {
          box.scrollTop += (er.top - br.top) - box.clientHeight * 0.3;
        }
      });
    },

    move: function (d) {
      var rows = $$('.qhit', $('#qres'));
      if (!rows.length) return;
      var i = this.on < 0 ? (d > 0 ? 0 : rows.length - 1) : (this.on + d);
      if (i < 0) i = 0;
      if (i >= rows.length) i = rows.length - 1;
      this.on = i;
      this.syncActive();
    },

    /** 搜索框的键盘处理（挂在 #q 上；全局 Esc 在 initChrome 里，输入框会被它跳过）。 */
    key: function (input, ev) {
      if (ev.key === 'ArrowDown') { ev.preventDefault(); this.move(1); return; }
      if (ev.key === 'ArrowUp') { ev.preventDefault(); this.move(-1); return; }
      if (ev.key === 'Enter') {
        ev.preventDefault();
        this.goto(this.on < 0 ? 0 : this.on);
        return;
      }
      if (ev.key === 'Escape') {
        input.value = '';
        this.run(input);
        input.blur();
      }
    },

    /** 无头测试用：把当前状态摊平成纯数据。 */
    stat: function () {
      var box = $('#qres');
      return {
        terms: this.terms.slice(),
        indexed: this.idx ? this.idx.length : 0,
        rows: this.items.length,
        shown: $$('.qhit', box).length,
        open: !!(box && box.classList.contains('on')),
        hits: $$('mark.q-hit').length,
        notes: $$('mark.hl').length,
        active: this.on
      };
    }
  };

  /* ======================= 9. 进度条 / 回到顶部 / 快捷键 ======================= */
  function initChrome() {
    var bar = $('#progress'), top = $('#toTop');
    function onScroll() {
      var h = document.documentElement;
      var max = h.scrollHeight - h.clientHeight;
      if (bar) bar.style.width = (max > 0 ? h.scrollTop / max * 100 : 0).toFixed(2) + '%';
      if (top) top.classList.toggle('on', h.scrollTop > 600);
    }
    document.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    if (top) top.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
    document.addEventListener('scroll', hideCtx, { passive: true });

    document.addEventListener('keydown', function (e) {
      if (e.target && /input|textarea/i.test(e.target.tagName)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      var k = e.key.toLowerCase();
      if (e.key === 'Escape') {
        if (LB.el && LB.el.classList.contains('on')) { LB.close(); return; }
        hideSelBar();
        hideCtx();
        Notes.closeDrawer();
        return;
      }
      if (k === 'm') { e.preventDefault(); markSelection(); return; }
      if (k === 'n') { e.preventDefault(); Notes.toggleDrawer(); return; }
      if (k === 't') { e.preventDefault(); var tb = $('#thumbToggle'); if (tb) tb.click(); return; }
      if (k === 'b') { e.preventDefault(); var nb = $('#navToggle'); if (nb) nb.click(); return; }
      /* 「/」对焦搜索框 —— 侧栏被收起时先展开，否则聚焦了也看不见（有焦点却无处可看最难解释） */
      if (k === '/') {
        e.preventDefault();
        var qq = $('#q');
        if (!qq) return;
        var navOff = MOBILE.matches
          ? !document.body.classList.contains('nav-shown')
          : document.body.classList.contains('nav-hidden');
        if (navOff) { var nb2 = $('#navToggle'); if (nb2) nb2.click(); }
        qq.focus();
        if (qq.select) qq.select();
        return;
      }
      if (k === 'j' || k === 'k') {
        var secs = $$('section[id]');
        var y = window.scrollY + 90, cur = 0;
        for (var i = 0; i < secs.length; i++) if (secs[i].offsetTop <= y) cur = i;
        var nx = k === 'j' ? secs[cur + 1] : secs[cur - 1];
        if (nx) { e.preventDefault(); window.scrollTo({ top: nx.offsetTop - 74, behavior: 'smooth' }); }
      }
    });
    document.addEventListener('mouseup', onSelectionEnd);
    document.addEventListener('touchend', function () { setTimeout(function () { onSelectionEnd(null); }, 30); });
  }

  /* ======================= 10. 代码块：一键复制 =======================
     标题栏里的「复制」按钮由 build.py 在构建期注入（分片里不手写，20 个块改一处即可）。
     这里只负责挂逻辑。

     为什么要从 <pre> 的 textContent 取、而不是 innerHTML：
     构建期给源码加了着色 <span>，innerHTML 会把标记一起复制走；
     textContent 拿到的才是**看着一模一样的纯代码** —— 粘到编辑器里能直接跑。
     注意一定取 pre 的而不是整个 .codeblk：头部那行「Python 原文件 P24 …」不该被复制。 */
  function codeOf(blk) {
    var pre = blk.querySelector('pre.code');
    if (!pre) return '';
    var t = pre.textContent || '';
    if (t.indexOf('\u00a0') >= 0) t = t.replace(/\u00a0/g, ' ');   // 不间断空格换回普通空格
    return t.replace(/\s+$/, '');                                  // 去掉尾部空白与空行
  }
  function markCopyBtn(btn, ok) {
    var old = btn.getAttribute('data-label') || btn.textContent || '复制';
    btn.setAttribute('data-label', old);
    btn.textContent = ok ? '已复制' : '复制失败';
    btn.classList.toggle('done', !!ok);
    btn.classList.toggle('fail', !ok);
    clearTimeout(btn._t);
    btn._t = setTimeout(function () {
      btn.textContent = btn.getAttribute('data-label');
      btn.classList.remove('done', 'fail');
    }, 1600);
  }
  function initCodeCopy() {
    $$('.codeblk').forEach(function (blk) {
      var head = blk.querySelector('.codeblk-head');
      var btn = blk.querySelector('.code-copy');
      /* 老文档 / 外部模板可能没有标题栏（这一版之前的产物就是这样）。
         别让「有没有按钮」变成「代码能不能复制」的前提 —— 缺按钮就现场补一个。 */
      if (!btn) {
        if (!head) {
          head = document.createElement('div');
          head.className = 'codeblk-head';
          var lb = document.createElement('b');
          lb.textContent = (blk.getAttribute('data-lang') || 'code');
          head.appendChild(lb);
          blk.insertBefore(head, blk.firstChild);
        }
        btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'code-copy';
        btn.setAttribute('data-copy', '1');
        btn.textContent = '复制';
        head.appendChild(btn);
      }
      /* 代码块整体不可选会让「选中 → 标记笔记」失效，所以刻意**不**禁用选择。
         但按钮本身不该被划进选区：mousedown 时把默认行为拦掉即可。 */
      btn.addEventListener('mousedown', function (e) { e.preventDefault(); });
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();                 // 别让点击冒到卡片上触发「定位」
        var t = codeOf(blk);
        if (!t) { markCopyBtn(btn, false); toast('这块代码是空的，没东西可复制'); return; }
        /* 复用统一入口：它自带 600ms 超时兜底，不会「点了没反应」。
           早先这里自己写了一套 clipboard 分支，正好踩上「writeText 永久 pending」
           那个坑 —— 无头下按钮永远不变色，真实场景里失焦时也一样。 */
        copyText(t, function (ok) {
          markCopyBtn(btn, ok);
          toast(ok ? '已复制 ' + t.split('\n').length + ' 行代码' : '复制失败，请手动选中代码复制');
        });
      });
    });
  }

  /* ======================= 11. PDF 深链 ======================= */
  function initPdfLinks() {
    $$('a.pdf-link').forEach(function (a) {
      var p = a.getAttribute('data-page');
      if (!p) return;                       // 内嵌模式用的是 data-embed-page，跳过
      if (!a.getAttribute('href')) a.setAttribute('href', (window.PDFURL_BASE || '') + '#page=' + p);
      a.title = '用系统默认阅读器打开原 PDF 第 ' + p + ' 页';
    });
  }

  /* ======================= 12. 内嵌原文件（可选） =======================
     build.py 以 embed_pdf=true 生成时，#pdfB64 里装着原 PDF 的 base64。
     点每页的「打开原文件该页」→ 惰性解码成 Blob → 用 blob: URL 打开，带上 #page=N。
     为什么用 blob: 而不是 data:：浏览器会拦顶层 data: 导航，blob: 不会。
     惰性 + 缓存：首次点击才解码（约 1.5 MB），之后复用同一个 blob URL。
     ⚠ #page=N 能否生效取决于浏览器内置 PDF 阅读器对 blob: URL 的处理，
       不可靠时至少能把整份原文件打开（页码已在 toast 里提示）。 */
  var pdfBlobUrl = null;
  function pdfBlob() {
    if (pdfBlobUrl) return pdfBlobUrl;
    var el = document.getElementById('pdfB64');
    if (!el) return null;
    var b64 = (el.textContent || '').replace(/\s+/g, '');
    if (!b64) return null;
    var bin;
    try { bin = atob(b64); } catch (e) { return null; }
    var buf = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
    try {
      pdfBlobUrl = URL.createObjectURL(new Blob([buf], { type: 'application/pdf' }));
    } catch (e2) { return null; }
    return pdfBlobUrl;
  }
  function openEmbeddedPdf(page) {
    var u = pdfBlob();
    if (!u) { toast('内嵌的原文件读不出来，可试试顶栏的「另存原 PDF」'); return false; }
    var w = null;
    try { w = window.open(u + (page ? ('#page=' + page) : ''), '_blank'); } catch (e) { w = null; }
    if (!w) toast('浏览器拦截了新标签页，请允许本站弹出窗口后重试');
    else toast('已打开内嵌原文件' + (page ? (' · 第 ' + page + ' 页') : ''));
    return true;
  }
  function initEmbeddedPdf() {
    var el = document.getElementById('pdfB64');
    if (!el) return;
    var links = $$('a.pdf-link[data-embed-page]');
    links.forEach(function (a) {
      a.setAttribute('title', '打开内嵌在本文档里的原文件，并跳到第 ' +
        a.getAttribute('data-embed-page') + ' 页（不用另外找 PDF）');
      a.addEventListener('click', function (e) {
        e.preventDefault();
        openEmbeddedPdf(a.getAttribute('data-embed-page'));
      });
    });
    if (!links.length && !el.getAttribute('data-pdf-name')) return;
    var name = el.getAttribute('data-pdf-name') || 'original.pdf';
    var btn = document.getElementById('savePdf');
    if (btn) {
      btn.hidden = false;                   // 内嵌模式下才把它显示出来
      btn.title = '把内嵌的原文件（' + name + '）另存为 PDF';
      btn.addEventListener('click', function () {
        var u = pdfBlob();
        if (!u) { toast('内嵌的原文件读不出来'); return; }
        var a = document.createElement('a');
        a.href = u;
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        toast('已另存：' + name);
      });
    }
  }

  /* ======================= 9.5 深链：#q=<词> =======================
     课程合集入口的「跨讲检索」会生成这种链接，形如：
         xxx-逐页精解.html#q=残差
         xxx-逐页精解.html#q=残差&p=p51
     比 query string 好在哪：hash 是纯前端可读的，不触发任何网络行为 —— 与 C1「断网可用」相容。

     为什么还要 p=<页id> 这一半：只给 #q= 的话用户还得在结果面板里再点一次；
     课程页那一侧已经知道这条命中属于哪一页，把页锚点一起带过来就能**直接跳过去并高亮**。
     （普通页锚点如 #p51 不用管 —— 浏览器原生就会滚过去，本函数只认 #q= 开头的。） */
  function initDeepLink() {
    var h = String(location.hash || '');
    if (h.indexOf('#q=') !== 0) return;
    var fields = {}, parts = ('q=' + h.slice(3)).split('&');
    for (var i = 0; i < parts.length; i++) {
      var kv = parts[i].split('=');
      if (kv.length < 2) continue;                 // 形如 "&foo" 的残段，跳过
      try { fields[kv[0]] = decodeURIComponent(kv.slice(1).join('=')); }
      catch (e) { fields[kv[0]] = kv.slice(1).join('='); }
    }
    var word = String(fields.q || '').replace(/\+/g, ' ').replace(/\s+/g, ' ').trim();
    if (!word) return;
    var qq = $('#q');
    if (!qq) return;
    /* 侧栏收起时先展开再搜索 —— 否则结果面板生成了却看不见，
       与「/」快捷键同一条理由（有结果却无处可看最难解释）。 */
    var navOff = MOBILE.matches
      ? !document.body.classList.contains('nav-shown')
      : document.body.classList.contains('nav-hidden');
    if (navOff) { var nb = $('#navToggle'); if (nb) nb.click(); }
    qq.value = word;
    Find.run(qq);
    var want = String(fields.p || '');
    if (!want || !Find.items.length) return;
    for (var k = 0; k < Find.items.length; k++) {
      if (Find.items[k].e.id === want) { Find.goto(k); return; }   // 高亮该节全部命中并滚过去
    }
    var el = document.getElementById(want);                        // 该页没被检索到就至少滚到它
    if (el && el.scrollIntoView) el.scrollIntoView({ block: 'start' });
  }

  /* ======================= 启动 ======================= */
  function boot() {
    ensureSectionIds();          // 先补 id：没有 id 的卡片标不了，也存不下 pid
    renderMath();
    Toc.init();
    initSpy();
    initLayout();
    Font.init();
    LB.init();
    Notes.load();
    buildSelBar();
    buildCtx();
    initMarkBtn();
    Drawer.init();
    Notes.restoreAll();
    initChrome();
    initCodeCopy();
    initPdfLinks();
    initEmbeddedPdf();
    initDeepLink();       // 放最后：它要用到 #q / #qres 与 Find，前面都准备好才跑
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();

  /* 无头测试入口 */
  window.__doc = {
    notes: Notes, toc: Toc, font: Font, find: Find,
    markSelection: markSelection,
    openEmbeddedPdf: openEmbeddedPdf,
    pdfBlob: pdfBlob,
    markBtnState: markBtnState,
    /* 代码块：供无头探针断言「按钮已接线 + 复制到的确实是纯代码」。
       探针不能真去点（headless 下没有剪贴板权限），所以额外给一个 codeOf，
       让探针能直接读到「按下去会复制到的东西」并与 pre.textContent 对照。 */
    initCodeCopy: initCodeCopy,
    codeOf: function (i) {
      var blks = $$('.codeblk');
      return blks[i || 0] ? codeOf(blks[i || 0]) : null;
    },
    toast: toast,
    addNote: function (pid, quote, note) {
      var sec = document.getElementById(pid);
      var m = Notes.add({
        pid: pid, page: sec ? (sec.getAttribute('data-page') || '') : '',
        loc: sec ? locOf(sec) : '',
        quote: quote, prefix: '', note: note || ''
      });
      /* 必须走**和真实入口同一条路**：locate → canon → wrapRange。
         之前这里手搓 prefix、并自己补一次 restore，导致测试绿而真实入口红。 */
      var r = sec ? locate(sec, m.prefix, m.quote) : null;
      if (r) {
        var c = canon(sec, r);
        if (wrapRange(r, m.id) && c) { m.quote = c.quote; m.prefix = c.prefix; Notes.save(); }
      }
      Notes.render();
      return m.id;
    },
    /* 标记体检：每条笔记还原出几个 <mark>、是否定位失效、
       有没有把块级元素吞进 mark（=结构被改坏）、标记宽度是否为 0（=看不见） */
    audit: function () {      var all = $$('mark.hl');
      return {
        notes: Notes.items.length,
        marks: all.length,
        perNote: Notes.items.map(function (m) {
          var ms = $$('mark.hl[data-nid="' + m.id + '"]');
          var sec = document.getElementById(m.pid);
          return {
            id: m.id, pid: m.pid, quote: m.quote.slice(0, 26),
            loc: locOf(sec) || m.loc || '',
            marks: ms.length,
            stale: ms.length === 0,
            width: ms.length ? Math.round(ms[0].getBoundingClientRect().width) : 0,
            blockInsideMark: ms.some(function (x) {
              return !!x.querySelector('p,div,table,td,tr,th,li,ul,ol,h3,blockquote');
            }),
            inHidden: ms.some(function (x) { return !!x.closest('.katex-mathml'); }),
            nested: ms.some(function (x) { return !!(x.parentNode && x.parentNode.closest('mark.hl')); })
          };
        })
      };
    },
    /* 打开上色追踪：traceWrap(true) → 触发一次标记 → lastTrace() 看每次
       surroundContents 的尝试与结果，用来解释「为什么被拆成 N 个 mark」。 */
    traceWrap: function (on) { wrapTrace = on ? [] : null; return !!wrapTrace; },
    lastTrace: function () { return wrapTrace || []; },
    /* 某区块的「原文位置」标签（无页码卡片不再显示 P？） */
    locOf: function (pid) { return locOf(document.getElementById(pid)); },
    /* 结构体检：划线只该加元素，不该改文字、不该动块级结构。
       把 mark 全拆掉后与当前状态对比即可自证。 */
    structAudit: function (pid) {
      var sec = document.getElementById(pid);
      if (!sec) return null;
      var c = sec.cloneNode(true);
      Array.prototype.forEach.call(c.querySelectorAll('mark.hl'), function (mk) {
        var p = mk.parentNode;
        while (mk.firstChild) p.insertBefore(mk.firstChild, mk);
        p.removeChild(mk);
        if (p.normalize) p.normalize();
      });
      var sel = 'p,div,table,tr,td,th,li,ul,ol,h3,blockquote';
      return {
        textSame: c.textContent.replace(/\s+/g, ' ').trim() === sec.textContent.replace(/\s+/g, ' ').trim(),
        blocksNow: sec.querySelectorAll(sel).length,
        blocksAfterUnwrap: c.querySelectorAll(sel).length,
        cells: sec.querySelectorAll('td,th').length,
        cellsAfterUnwrap: c.querySelectorAll('td,th').length
      };
    },
    exportMd: function () { return Notes.exportMd(); },
    clearNotes: function () { Notes.items = []; Notes.save(); Notes.render(); },
    openDrawer: function () { Notes.openDrawer(false); },
    toggleToc: function (gid) {
      var g = document.querySelector('.toc-group[data-gid="' + gid + '"]');
      if (g) Toc.toggle(g, g.classList.contains('collapsed'));
      return !!g;
    },
    collapseAllToc: function () { Toc.setAll(true); },
    state: function () {
      return {
        notes: Notes.items.length,
        marks: $$('mark.hl').length,
        tocGroups: Toc.groups.length,
        tocCollapsed: $$('.toc-group.collapsed').length,
        navHidden: document.body.classList.contains('nav-hidden'),
        navShown: document.body.classList.contains('nav-shown'),
        hideThumb: document.body.classList.contains('hide-thumb'),
        drawerOpen: document.body.classList.contains('drawer-open')
      };
    }
  };
})();
