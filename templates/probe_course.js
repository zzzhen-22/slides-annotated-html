/* ============================================================================
   课程合集入口（index.html）的行为探针
   用法：
     python scripts/probe.py <课程目录>/index.html templates/probe_course.js

   它回答的是**单讲那套探针答不了**的问题 —— 课程页的五区块对不对：

     1. 结构自洽：地图行 / 要点讲次块 / 进度行的数量都等于内联索引里的讲次数
     2. 要点总结：条目总数 = 各讲要点之和；**没写要点的讲次必须有显式占位**（不能静默省略）
     3. 出处链接：每条 data-at 的 href 形态正确（相对路径 + #pNN + 无裸空格），
        且目标页 id 在内联索引里真实存在
     4. 跨讲检索：拿索引里的词现搜，命中数 > 0、行数合理、每条结果的跳转 URL 形态正确
     5. 术语总表：每行都有「首见」链接（没有术语时必须是说明性占位，不是空表）
     6. 导出 Markdown：真的能产出非空文本，且含讲次小标题
     7. 过滤：给一个必然 0 命中的词 → 全隐藏 + 空状态提示出现；清空 → 全部复原

   ⚠ **探针验不了、也不该假装验的**：跨文件可达性（链接指向的那份产物里到底有没有 #pNN）。
     那是 scripts/course_check.py 的活 —— 它能在磁盘上把两边对起来，探针只能看当前这一页。
   ========================================================================== */
window.addEventListener('load', function () { setTimeout(run, 900); });

var out = [];
var fail = 0;
function T(k, v) { out.push(k + ': ' + (typeof v === 'string' ? v : JSON.stringify(v))); }
function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function $$(s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); }
function $(s, c) { return (c || document).querySelector(s); }
function norm(t) { return String(t == null ? '' : t).replace(/\s+/g, ' ').trim(); }
function bad(msg) { out.push('  ✘ ' + msg); fail++; }
function done() {
  document.head.innerHTML = '';
  document.body.innerHTML = '<pre id="__r">' + esc(out.join('\n')) + '</pre>';
}

function run() {
  try {
    var C = window.__course;
    if (!C) {
      T('window.__course', '✘ 不存在 —— 课程页的脚本没跑起来？');
      T('RESULT', 'FAIL');
      return done();
    }

    var data = (C.find.data || {});
    var lecs = data.lectures || [];

    /* ---------- 1. 结构自洽 ---------- */
    var mapRows = $$('.lec').length;
    var kpBlocks = $$('.klec').length;
    var pRows = $$('#progress tbody tr').length;
    var ok1 = (mapRows === lecs.length) && (kpBlocks === lecs.length) && (pRows === lecs.length);
    T('① 结构自洽（地图/要点块/进度行 = 内联索引里的讲次数）',
      mapRows + ' / ' + kpBlocks + ' / ' + pRows + ' vs ' + lecs.length + (ok1 ? '  ✔' : '  ✘'));
    if (!ok1) bad('三个区块的讲次数对不上内联索引 —— 生成时漏了某个区块，或某一讲被跳过');

    /* ---------- 2. 要点总结：条数与「显式占位」 ---------- */
    var items = 0, holds = 0, emptyBlocks = [];
    $$('.klec').forEach(function (lec) {
      var n = $$('.kpl li', lec).length;
      var hold = $('.kp-hold', lec);
      items += n;
      if (hold) holds++;
      if (!n && !hold) emptyBlocks.push(lec.getAttribute('data-lec'));
    });
    var wantItems = 0;
    (C.kp.items || []).forEach(function () { wantItems++; });
    T('② 要点条目数（可见 + 过滤掉的）', items + ' 条，期望 ' + wantItems +
      (items === wantItems ? '  ✔' : '  ✘'));
    if (items !== wantItems) bad('要点条目数和 DOM 里数出来的不一致 —— 生成或过滤脚本动过 li');
    T('② 没写要点的讲次有显式占位', holds + ' 个占位' +
      (emptyBlocks.length ? ('  ✘ 这些讲次既无要点也无占位：' + emptyBlocks.join(',')) : '  ✔'));
    if (emptyBlocks.length) bad('有讲次在要点表里是空的 —— 静默省略会让人以为遗漏了');
    if (holds === 0 && lecs.length && items === 0) bad('一条要点都没有，也没有占位 —— 整块等于空白');

    /* ---------- 3. 出处链接形态 + 目标页自洽 ---------- */
    var pageIds = {};
    lecs.forEach(function (l) { (l.pages || []).forEach(function (p) { pageIds[l.id + '#' + p.id] = 1; }); });
    var atAll = $$('.kp-at'), atBad = 0, atMiss = 0;
    atAll.forEach(function (a) {
      var h = a.getAttribute('href') || '';
      if (!h || h.indexOf('://') >= 0 || h.indexOf(' ') >= 0 || h.indexOf('#') < 0) { atBad++; return; }
      var i = h.indexOf('#');
      /* 链接得能反推出「哪一讲的哪一个页 id」—— 从 href 里拿不到讲次名就没法核对，
         所以改为核对「锚点在内联索引里存在」这一半（另一半由 course_check.py 查文件） */
      var pid = h.slice(i + 1);
      if (!pid) { atBad++; return; }
      var hit = false;
      lecs.forEach(function (l) { if (!hit && h.indexOf(l.href) === 0) hit = !!pageIds[l.id + '#' + pid]; });
      if (!hit) atMiss++;
    });
    T('③ 要点出处链接（形态正确 / 锚点在内联索引里存在）',
      atAll.length ? (atAll.length - atBad - atMiss) + ' / ' + atAll.length +
        '（形态错 ' + atBad + '，锚点对不上 ' + atMiss + '）' +
        ((atBad || atMiss) ? '  ✘' : '  ✔') : '（本页没有带出处的要点）');
    if (atBad) bad('有出处链接不是「相对路径 + #锚点」的形态，或含裸空格');
    if (atMiss) bad('有出处链接的锚点在内联索引里找不到 —— 多半指向了不存在的页');

    /* ---------- 4. 跨讲检索 ---------- */
    var q = $('#cq');
    if (!q) {
      T('④ 跨讲检索', '✘ 页面上没有 #cq 搜索框');
      bad('缺搜索框');
    } else if (!C.find.idx.length) {
      T('④ 跨讲检索', '✘ 索引是空的（内联数据没解析出来？）');
      bad('内联索引为空');
    } else {
      /* 从索引里**现抓**一个词，不写死任何课文词 —— 依赖被测文档恰好长成某样是隐患 */
      var word = '';
      for (var i = 0; i < C.find.idx.length; i++) {
        var m = /[\u4e00-\u9fff]{2,4}/.exec(C.find.idx[i].text);
        if (m) { word = m[0]; break; }
      }
      if (!word) {
        for (var j = 0; j < C.find.idx.length; j++) {
          var t = norm(C.find.idx[j].text);
          if (t.length >= 2) { word = t.slice(0, 2); break; }
        }
      }
      T('④ 取到的测试词', word ? ('「' + word + '」') : '（✘ 索引里取不到任何可搜的词）');
      if (word) {
        q.value = word;
        var n = C.find.run(word);
        var rows = $$('.ck-hit').length;
        var shown = Math.min(n, C.find.MAX_ROWS);
        var okNum = (n > 0) && (rows === shown);
        T('④ 检索命中 / 结果行数', n + ' 处 / ' + rows + ' 行（上限 ' + C.find.MAX_ROWS + '）' +
          (okNum ? '  ✔' : '  ✘'));
        if (!okNum) bad('命中数与列出的结果行数对不上');
        var linkBad = 0, sample = '';
        /* 形态要求（写直白点，别用一条正则糊住 —— 上次就是正则自己写错了）：
             · 相对路径：不带协议、不以 / 开头
             · 无裸空格
             · 命中锚点与页锚点都在：`.html#q=...&p=...` */
        C.find.rows.slice(0, 20).forEach(function (r) {
          var u = C.find.linkOf(r);
          if (!sample) sample = u;
          var okU = (u.indexOf('://') < 0) && (u.charAt(0) !== '/') &&
            (u.indexOf(' ') < 0) &&
            (u.indexOf('.html#q=') > 0) && (u.indexOf('&p=') > 0) &&
            (u.indexOf('&p=') < u.length - 1);
          if (!okU) linkBad++;
        });
        T('④ 结果跳转 URL 形态（相对路径 + #q=&p=）', linkBad
          ? ('✘ ' + linkBad + ' 条不合格，例：' + sample)
          : ('✔ 全部合格，例：' + sample));
        if (linkBad) bad('结果链接形态不对；跨讲深链靠 #q=&p= 让目标讲自动高亮，形态错就白给');
        /* 高亮：命中片段里该有 <mark class="ch"> */
        T('④ 命中片段带 <mark class="ch"> 高亮', $$('.ck-hit mark.ch').length + ' 处' +
          ($$('.ck-hit mark.ch').length ? '  ✔' : '  ✘'));
        q.value = '';
        C.find.run('');
      }
    }

    /* ---------- 5. 术语总表 ---------- */
    var gRows = $$('#glossary tbody tr');
    if (gRows.length) {
      var noLink = gRows.filter(function (tr) {
        return !$$('a[href]', tr).length;
      }).length;
      T('⑤ 术语总表：行数 / 每行都有「首见」链接', gRows.length + ' 行，缺链接 ' + noLink +
        (noLink ? '  ✘' : '  ✔'));
      if (noLink) bad('有术语行没有「首见」链接 —— 那一条术语就没法跳到它第一次出现的地方');
    } else {
      var ph = $('#glossary .dim');
      T('⑤ 术语总表', ph ? '✔ 没有术语时给了说明性占位（不是空表）' : '✘ 既没有术语行也没有占位说明');
      if (!ph) bad('术语总表是空的，也没有说明 —— 读者会以为页面坏了');
    }

    /* ---------- 6. 导出 Markdown ---------- */
    var md = '';
    try { md = C.kp.markdown() || ''; } catch (e) { md = ''; }
    var okMd = md.length > 40 && md.indexOf('#') === 0 &&
      ((md.match(/\n## /g) || []).length > 0 || items === 0);
    T('⑥ 导出 Markdown', md.length + ' 字符' + (okMd ? '  ✔' : '  ✘'));
    if (!okMd) bad('导出的 Markdown 太短或没有讲次小标题 —— 导出按钮等于没接上');
    T('⑥ 导出件含「未完成讲次」提醒', /未完成|覆盖讲次/.test(md) ? '✔' : '✘ 少了这一行');
    if (!/未完成|覆盖讲次/.test(md)) bad('导出件没标明覆盖范围，容易被误当成完整版');

    /* ---------- 7. 过滤 ---------- */
    var f = $('#kpFilter');
    if (f && C.kp.items.length) {
      var total = C.kp.items.length;
      C.kp.apply('zzz-必然不存在-zzz');
      var zero = $$('.kpl li').filter(function (x) { return !x.hidden; }).length;
      var emptyOn = !!(($('#kpEmpty') || {}).hidden === false);
      C.kp.apply('');
      var back = $$('.kpl li').filter(function (x) { return !x.hidden; }).length;
      var okF = (zero === 0) && emptyOn && (back === total);
      T('⑦ 要点过滤（0 命中提示 / 清空复原）',
        '0 命中时可见 ' + zero + '，空状态 ' + (emptyOn ? '出现' : '没出现') +
        '，清空后复原 ' + back + '/' + total + (okF ? '  ✔' : '  ✘'));
      if (!okF) bad('过滤行为不对：要么 0 命中时没给提示，要么清空后没复原');
    } else {
      T('⑦ 要点过滤', '（本页没有可过滤的要点，跳过）');
    }

    T('RESULT', fail ? ('FAIL（' + fail + ' 项）') : 'PASS');
    done();
  } catch (err) {
    out.push('PROBE_ERROR: ' + (err && err.stack ? err.stack : err));
    T('RESULT', 'FAIL');
    done();
  }
}
