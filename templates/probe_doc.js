/* ============================================================================
   交付体检探针：这一份文档「做完了没有、坏没坏」
   用法：
     python scripts/probe.py <输出.html> templates/probe_doc.js

   它回答五个问题（都是静态检查回答不了的）：
     1. 内容进度：还有多少页是「待补」占位（TODO 卡）、多少 TODO 注释没清
     2. 结构一致性：逐页区块数 = 缩略图数 = 深链数；目录锚点是否都能落到元素上
     3. 公式与目录：KaTeX 渲染后的公式块数量、目录条目数
     4. 交互健康：标记一次跨块选区，检查有没有把块级元素吞进 <mark>（结构被改坏）
     5. 正文符号：缺字风险（组合符号 U+20D0–U+20FF 会渲染成方框）、
        非法命名实体（&oiint; 这类非 HTML5 实体会显示成字面文本）
   ========================================================================== */
window.addEventListener('load', function () { setTimeout(run, 900); });
var out = [];
function T(k, v) { out.push(k + ': ' + (typeof v === 'string' ? v : JSON.stringify(v))); }
function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function $$(s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); }
function norm(t) { return String(t).replace(/\s+/g, ' ').trim(); }

function run() {
  try {
    var pg = $$('section.pg');
    // 缩略图只数「逐页区块内部的」——灯箱里那张大图也是 <img>，
    // 用全局 figure.thumb 在不同模板下会数错，所以按区块内查（见 pitfalls 第 30 条）。
    var thumbs = $$('section.pg figure.thumb img');
    var links = $$('a.pdf-link');
    T('逐页区块 / 缩略图 / 深链', pg.length + ' / ' + thumbs.length + ' / ' + links.length +
      (pg.length === thumbs.length && pg.length === links.length ? '  ✔ 一致' : '  ✘ 不一致'));

    var missingThumb = pg.filter(function (s) { return !s.querySelector('figure.thumb img'); });
    T('缺缩略图的页', missingThumb.length ? missingThumb.map(function (s) { return s.id; }).join(',') : '0');

    // 公式：渲染成功后 <script type="math/tex"> 会被替换成 .katex
    T('公式（KaTeX 已渲染）', $$('.katex').length + ' 条；未渲染的 script 残留 ' +
      $$('script[type^="math/tex"]').length + ' 条');

    // 目录锚点
    var dead = $$('.toc-nav a[href^="#"]').filter(function (a) {
      var id = a.getAttribute('href').slice(1);
      return id && !document.getElementById(id);
    });
    T('目录条目数 / 断链', $$('.toc-nav a[href^="#"]').length + ' / ' +
      (dead.length ? dead.map(function (a) { return a.getAttribute('href'); }).join(',') : '0'));

    // 内容进度：占位卡片 + 未清的 TODO 注释
    var todoCards = $$('.pg-text .note').filter(function (d) {
      return /待补/.test(norm(d.textContent));
    });
    T('内容进度：待补页面', todoCards.length + ' / ' + pg.length +
      (todoCards.length ? '  → 还需逐页补写（先看 _extract/page-NN.png）' : '  ✔ 全部写完'));
    /* TODO 扫描只走「用户看得见的文字节点」。两个都必须跳过的坑：
       ① script —— probe.py 把本文件注入成页面的 <script>，**本文件自己的注释里
          就写着 TODO**（以及 &oiint; 这类例子），不跳过就会自己命中自己；
       ② 内嵌 PDF 的 base64 —— 随机字符里完全可能碰巧拼出 TODO。
       第一版用 documentElement.innerHTML 扫，结果永远报「6 处」，见 pitfalls 第 34 条。 */
    var tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (n.parentNode && n.parentNode.closest &&
          n.parentNode.closest('script, style')) return NodeFilter.FILTER_REJECT;
        return /TODO/.test(n.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    });
    var tn, todoVisible = 0;
    while ((tn = tw.nextNode())) todoVisible += (tn.nodeValue.match(/TODO/g) || []).length;
    T('  TODO 残留（可见正文）', todoVisible + ' 处' +
      (todoVisible ? '  ✘' : '  ✔') +
      '　（源码层面的残留由 check_math.js 的 ⑤ 把关）');

    // 位置标签（无页码区块不该出现 P？）
    var qm = $$('#drawerList .ni-page').filter(function (b) { return /P\?/.test(b.textContent); });
    T('抽屉里的「P？」残留', qm.length + ' 处');

    /* ---------- 正文符号体检（两类，都是「体检看不到、用户一眼就看到」的错） ----------
       ① 组合符号 U+20D0–U+20FF（典型是拿 U+20D7 当矢量符号写「J⃗」）：
          中文字体栈普遍没有这些字形 → 渲染成方框（tofu）。
          正文里表示矢量请用 <b class="vec">J</b> 加粗。见 pitfalls 第 34 条。
       ② 非法命名实体（如 &oiint; &iint; &iiint; —— 它们存在于 MathML/LaTeX，
          **不在 HTML5 实体表里**）：浏览器不解码，原样显示成「&oiint;」这串字面文本。
          判定办法最可靠：把这段字面文本塞进 innerHTML 试一次，
          textContent 没变就说明解析器不认识它。 */
    var tofu = [];
    $$('section[id], .toc-nav').forEach(function (sec) {
      var w = document.createTreeWalker(sec, NodeFilter.SHOW_TEXT, {
        acceptNode: function (n) {
          if (n.parentNode && n.parentNode.closest &&
            n.parentNode.closest('.katex, script, style')) return NodeFilter.FILTER_REJECT;
          return NodeFilter.FILTER_ACCEPT;
        }
      });
      var n, hit = 0;
      while ((n = w.nextNode())) hit += (n.nodeValue.match(/[\u20d0-\u20ff]/g) || []).length;
      if (hit) tofu.push(sec.id + '×' + hit);
    });
    T('正文缺字风险（组合符号 U+20D0–U+20FF）', tofu.length
      ? tofu.slice(0, 8).join(', ') + '  ✘ 会渲染成方框，请改用加粗表示矢量'
      : '0 处  ✔');

    var badEnt = [], seenEnt = {};
    /* 只扫「用户看得见的文字节点」：
       —— 必须跳过 script / style：probe.py 是把本文件注入成页面的 <script> 的，
          **本文件的注释里就写着 &oiint; 这些例子**，不跳过就会自己命中自己
          （第一版就是这么误报的，见 pitfalls 第 34 条）。
       —— 必须跳过 .katex-mathml / annotation：公式只要用 \oiint \iint
          这类算子，KaTeX 的 MathML 副本里就会出现字面实体（且不可见）。 */
    var ew = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (n.parentNode && n.parentNode.closest &&
          n.parentNode.closest('script, style, .katex-mathml, annotation')) {
          return NodeFilter.FILTER_REJECT;
        }
        return /&[a-zA-Z][a-zA-Z0-9]{1,31};/.test(n.nodeValue)
          ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    });
    var en;
    while ((en = ew.nextNode())) {
      (en.nodeValue.match(/&[a-zA-Z][a-zA-Z0-9]{1,31};/g) || []).forEach(function (ent) {
        if (seenEnt[ent]) return;
        seenEnt[ent] = 1;
        var box = document.createElement('div');
        box.innerHTML = ent;
        if (box.textContent === ent) badEnt.push(ent);   // 没被解码 → 不是 HTML5 实体
      });
    }
    T('非法命名实体（会显示成字面文本）', badEnt.length
      ? badEnt.slice(0, 8).join(' ') + '  ✘ 请改用该字符本身或 LaTeX 公式'
      : '0 处  ✔');

    // 交互健康：真实入口标一次跨块选区，检查结构
    var d = window.__doc;
    if (d) {
      var t1 = null, t2 = null;
      var ps = $$('.pg-text > p').filter(function (p) { return norm(p.textContent).length >= 20; });
      for (var i = 0; i + 1 < ps.length; i++) {
        if (ps[i].nextElementSibling !== ps[i + 1]) continue;
        var a = null, b = null, w = document.createTreeWalker(ps[i], NodeFilter.SHOW_TEXT, null), n;
        while ((n = w.nextNode())) if (norm(n.nodeValue)) a = n;
        w = document.createTreeWalker(ps[i + 1], NodeFilter.SHOW_TEXT, null);
        while ((n = w.nextNode())) if (norm(n.nodeValue)) { b = n; break; }
        if (a && b) { t1 = a; t2 = b; break; }
      }
      if (t1 && t2) {
        var r = document.createRange();
        r.setStart(t1, Math.max(0, t1.nodeValue.length - 10));
        r.setEnd(t2, Math.min(t2.nodeValue.length, 6));
        var sel = window.getSelection();
        sel.removeAllRanges(); sel.addRange(r);
        document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
        var btn = document.querySelector('.selbar.on button[data-act="mark"]');
        if (btn) {
          btn.click();
          var aud = d.audit();
          var last = aud.perNote[aud.perNote.length - 1] || {};
          T('标记回归（跨段）', 'marks=' + (last.marks || 0) +
            ' blockInsideMark=' + last.blockInsideMark +
            ' inHidden=' + last.inHidden + ' width=' + last.width +
            ((last.marks > 0 && !last.blockInsideMark && !last.inHidden && last.width > 0) ? '  ✔' : '  ✘'));
          T('  （这一条是探针造的，不会存盘以外的副作用）', 'note=' + JSON.stringify(last.quote || ''));
        } else {
          T('标记回归（跨段）', '✘ 选区工具条没出现（可能是 headless 下选区 API 受限）');
        }
      }
    } else {
      T('window.__doc', '✘ 不存在 —— 页面脚本没跑起来？');
    }

    document.head.innerHTML = '';
    document.body.innerHTML = '<pre id="__r">' + esc(out.join('\n')) + '</pre>';
  } catch (err) {
    out.push('PROBE_ERROR: ' + (err && err.stack ? err.stack : err));
    document.head.innerHTML = '';
    document.body.innerHTML = '<pre id="__r">' + esc(out.join('\n')) + '</pre>';
  }
}
