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
        q.addEventListener('input', function () { self.filter(q.value); });
        q.addEventListener('keydown', function (ev) {
          if (ev.key === 'Escape') { q.value = ''; self.filter(''); q.blur(); }
        });
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

  function newMark(nid) {
    var mk = document.createElement('mark');
    mk.className = 'hl';
    mk.setAttribute('data-nid', nid);
    mk.title = '点击查看／编辑这条笔记';
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
  function wrapOne(a, b, nid) {
    var r = document.createRange();
    try {
      r.setStart(a.node, a.s);
      r.setEnd(b.node, b.e);
      if (r.collapsed) return false;
      trace('  try 「' + brief(a.node.nodeValue.slice(a.s, a.s + 18)) + '」→ 「' +
        brief(b.node.nodeValue.slice(Math.max(0, b.e - 18), b.e)) + '」');
      r.surroundContents(newMark(nid));
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
  function wrapGroup(items, nid) {
    if (!items.length) return 0;
    if (items.length === 1) return wrapOne(items[0], items[0], nid) ? 1 : 0;
    if (wrapOne(items[0], items[items.length - 1], nid)) return 1;
    var h = Math.floor(items.length / 2);
    return wrapGroup(items.slice(0, h), nid) + wrapGroup(items.slice(h), nid);
  }
  /** 结构安全的上色：把 range 拆成「文字节点级」的片段，
      按最近的块级祖先分组，每组交给 wrapGroup 收敛。
      纯空白片段直接跳过 —— 那是「标记处多出一个换行」的元凶之一。
      返回实际生成的 mark 数量。 */
  function wrapRange(range, nid) {
    var anc = range.commonAncestorContainer;
    var root = (anc && anc.nodeType === 1) ? anc : (anc ? anc.parentNode : null);
    if (!root || !root.ownerDocument) return 0;
    var proj = projOf(root);
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
      if (n.parentNode && n.parentNode.closest &&
        n.parentNode.closest('mark.hl[data-nid="' + nid + '"]')) continue;
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
    for (i = 0; i < groups.length; i++) made += wrapGroup(groups[i].items, nid);
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

  function copyText(t) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(t).catch(function () { fallbackCopy(t); });
    } else fallbackCopy(t);
  }
  function fallbackCopy(t) {
    var ta = document.createElement('textarea');
    ta.value = t; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); } catch (e) {}
    document.body.removeChild(ta);
  }
  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
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

  /* ======================= 10. PDF 深链 ======================= */
  function initPdfLinks() {
    $$('a.pdf-link').forEach(function (a) {
      var p = a.getAttribute('data-page');
      if (!p) return;                       // 内嵌模式用的是 data-embed-page，跳过
      if (!a.getAttribute('href')) a.setAttribute('href', (window.PDFURL_BASE || '') + '#page=' + p);
      a.title = '用系统默认阅读器打开原 PDF 第 ' + p + ' 页';
    });
  }

  /* ======================= 11. 内嵌原文件（可选） =======================
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

  /* ======================= 启动 ======================= */
  function boot() {
    ensureSectionIds();          // 先补 id：没有 id 的卡片标不了，也存不下 pid
    renderMath();
    Toc.init();
    initSpy();
    initLayout();
    LB.init();
    Notes.load();
    buildSelBar();
    buildCtx();
    initMarkBtn();
    Drawer.init();
    Notes.restoreAll();
    initChrome();
    initPdfLinks();
    initEmbeddedPdf();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();

  /* 无头测试入口 */
  window.__doc = {
    notes: Notes, toc: Toc,
    markSelection: markSelection,
    openEmbeddedPdf: openEmbeddedPdf,
    pdfBlob: pdfBlob,
    markBtnState: markBtnState,
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
