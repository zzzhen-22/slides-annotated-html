/* ============================================================================
   课程合集入口（index.html）的行为探针
   用法：
     python scripts/probe.py <课程目录>/index.html templates/probe_course.js
     python scripts/probe.py <课程目录>/index.html templates/probe_course.js --hash "sec=keypoints&kp=词"   # 测启动恢复

   它回答的是**单讲那套探针答不了**的问题 —— 课程页的五区块对不对：

     1. 结构自洽：地图行 / 要点讲次块 / 进度行的数量都等于内联索引里的讲次数
        1c. 地图卡片的文本流有分隔（lid 与标题之间是真空格，复制出来不粘连）
     2. 要点总结：条目总数 = 各讲要点之和；**没写要点的讲次必须有显式占位**（不能静默省略）
     3. 出处链接：每条 data-at 的 href 形态正确（相对路径 + #pNN + 无裸空格），
        且目标页 id 在内联索引里真实存在
     4. 跨讲检索：拿索引里的词现搜，命中数 > 0、行数合理、每条结果的跳转 URL 形态正确
     4.5 检索分页：临时把每批条数调成 1，验「首批只渲染一批 → 按钮报剩余数 → 点一次多一批
        → 显示完按钮自行消失」这套机制（命中 <3 条时 SKIP，不假装验过）
     5. 术语总表：每行都有「首见」链接（没有术语时必须是说明性占位，不是空表）
     6. 导出 Markdown：真的能产出非空文本，且含讲次小标题
     7. 过滤：给一个必然 0 命中的词 → 全隐藏 + 空状态提示出现；清空 → 全部复原
     8. 顶栏 scrollspy：滚到不同区块，导航高亮跟着走（顶部 / 底部必测；中间块
        只在页面够高、前置条件成立时测，不假装验过）
     9. 要点「全部折叠 / 展开」：两下点击，讲次块的开合与按钮文案都要跟得上
    10. 术语过滤：0 命中提示 / 清空复原 / 搜术语名命中它自己
    11. URL 解析：kv 段、裸段（手敲的 #glossary）、未知名忽略、值解码
    12. 启动恢复（条件式）：打开时就带 hash 时，参数要已套用、页面已滚到 sec
    13. URL 写入链路（异步）：输入 → 防抖 → 写 hash；清空 → 参数移除；
        hash 外部变化 → 全量套用 / 去参数 → 清空对应项

   ⚠ **探针验不了、也不该假装验的**：跨文件可达性（链接指向的那份产物里到底有没有 #pNN）。
     那是 scripts/course_check.py 的活 —— 它能在磁盘上把两边对起来，探针只能看当前这一页。
   ⚠ 8–13 组多数是「机制自证」：滚动用显式 `behavior:'instant'` 让位置同步可读；
     写入链路在 virtual-time 下靠 setTimeout 推进（防抖临时调小到 10ms 再还原）。
   ========================================================================== */
window.addEventListener('load', function () { setTimeout(run, 950); });

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

    /* 「刚打开」时的现场快照 —— ⑫ 组要靠它断言启动恢复。
       必须在任何操作之前读：后面的滚动、过滤、输入链路都会改变这些值。 */
    var bootH = (C.url && C.url.parse) ? C.url.parse()
                                       : { sec: '', kp: '', find: '', gl: '' };
    var bootKpValue = norm(($('#kpFilter') || {}).value);
    var bootKpShown = (C.state ? C.state().keypointsShown : 0);
    var bootScrollY = Math.round(window.scrollY || 0);

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

    /* ---------- ①c 地图卡片的文本流 ----------
       元素之间必须有**真空格**：flex 的 gap 撑的是视觉间距、进不了文本流 ——
       缺了它，复制卡片那行会得到「L01标题部分完成」这种粘连串。 */
    var lec0 = $('.lec');
    var lid0 = lec0 ? norm(($('.lid', lec0) || {}).textContent) : '';
    var lecTxt = lec0 ? norm(lec0.textContent) : '';
    var okClone = !!lec0 && !!lid0 && lecTxt.indexOf(lid0 + ' ') === 0;
    T('①c 地图卡片文本流（lid 与标题之间有分隔，复制不粘连）',
      okClone ? '✔ ' + lecTxt.slice(0, 64) : '✘ ' + lecTxt.slice(0, 64));
    if (!okClone) bad('.lec 卡片文本流没有分隔 —— 复制这一行会得到粘连串（L01标题）');

    /* ---------- 1.5 公式渲染（要点表 / 术语总表里的 KaTeX） ----------
       防的是这个具体事故（2026-10-15 真实发生）：课程主页没内联 KaTeX，
       各讲汇总来的公式全显示成抽取时留下的占位符〔公式〕——生成期全绿，
       只有人打开页面才看得见。所以这里三条断言，缺一条都拦不住它。 */
    var st = (C.state ? C.state() : {});
    var hasMath = $$('#keypoints script[type^="math/tex"], #glossary script[type^="math/tex"]').length;
    var rendered = $$('#keypoints .katex, #glossary .katex').length;
    var leftSrc = st.mathLeft || 0;
    var failed = st.mathFailed || 0;
    var phLeft = st.placeholderLeft || 0;
    T('①b 可见区公式（源码标签 / 已渲染 / 未渲染残留）',
      hasMath + ' 个源码 → ' + rendered + ' 个已渲染，残留 ' + leftSrc +
      ((leftSrc === 0) ? '  ✔' : '  ✘'));
    if (leftSrc !== 0) {
      bad('要点表/术语总表里还有 ' + leftSrc + ' 个没渲染的公式标签 —— ' +
          '课程主页多半没内联 KaTeX（course_site.py 的 load_katex 取不到 vendor/katex？）');
    }
    T('①b 公式渲染失败数', failed + (failed ? '  ✘（退回显示了 LaTeX 源码）' : '  ✔'));
    if (failed) bad('有 ' + failed + ' 个公式渲染失败 —— 页面上会显示 LaTeX 源码，检查公式是否含非法命令');
    /* 占位符〔公式〕是**给检索索引用的**，不该出现在可见正文里 */
    T('①b 可见正文里的占位符〔公式〕', phLeft + (phLeft ? '  ✘' : '  ✔'));
    if (phLeft) {
      bad('要点表/术语总表里出现了 ' + phLeft + ' 处〔公式〕占位符 —— ' +
          '这是抽取器给检索索引留的记号，显示出来说明渲染链路断了');
    }
    if (rendered && typeof katex === 'undefined') bad('页面渲染了公式却没有 katex 全局对象');

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
        /* 分页语义（v2.4.2 起）：run() 返回命中总数，但首屏只渲染 PAGE_ROWS 条，
           剩下的由列表底部的「显示更多」按钮逐批追加 —— 所以这里比的是
           「已渲染行数 == min(命中数, 每批条数)」，不是「行数 == 命中数」。
           （旧写法用的是 MAX_ROWS 这个已被改名的字段，改名后 Math.min(n, undefined) = NaN，
             断言恒假 —— 而它只在手动跑 run_course 时才执行，于是静默红了很久。） */
        var shown = Math.min(n, C.find.PAGE_ROWS);
        var okNum = (n > 0) && (rows === shown);
        T('④ 检索命中 / 结果行数', n + ' 处 / ' + rows + ' 行（每批 ' + C.find.PAGE_ROWS + ' 条）' +
          (okNum ? '  ✔' : '  ✘'));
        if (!okNum) bad('命中数与列出的结果行数对不上（首屏该是 min(命中数, 每批条数)）');
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

        /* ---------- 4.5 「显示更多」分页（v2.4.2 的 A7 改动） ----------
           为什么不「等命中数自然超过每批条数」再测：那等于把断言绑在这份课件恰好有多长上，
           课件一长一短就变成永真或永假。这里**临时把每批条数改成 1**，逼出分页机制，
           测的是机制本身：首批只渲染一批 → 按钮报出剩余条数 → 点一次多渲染一批 →
           全部显示完按钮消失。跑完必须还原（否则会污染后面几组断言）。 */
        var multi = '';
        for (var bi = 0; bi < C.find.idx.length && !multi; bi++) {
          var bm = /[\u4e00-\u9fff]/.exec(C.find.idx[bi].text);
          if (!bm) continue;
          var ch = bm[0], cnt = 0;
          for (var bj = 0; bj < C.find.idx.length; bj++) {
            if (C.find.idx[bj].lower.indexOf(ch) >= 0) cnt++;
          }
          if (cnt >= 3) multi = ch;
        }
        if (!multi) {
          /* 条件式跳过：课件太短/无 CJK 时命中不足 3 条，分页无从谈起。
             这与 ⑫ 代码块组「没有代码块就 SKIP」同一原则 —— 不假装验过，也不误报红。 */
          T('④c 检索分页', '（SKIP：索引里找不到命中 ≥3 条的词，无从构造分页）');
        } else {
          var keepRows = C.find.PAGE_ROWS;
          C.find.PAGE_ROWS = 1;
          q.value = multi;
          var pn = C.find.run(multi);
          var p1 = $$('.ck-hit').length;
          var more = $('#cres .res-more');
          var okP1 = (pn >= 3) && (p1 === 1) && !!more;
          T('④c 首批按每批条数截断 + 「显示更多」按钮出现',
            '命中 ' + pn + ' 条 → 首批渲染 ' + p1 + ' 条，按钮 ' +
            (more ? '「' + norm(more.textContent) + '」' : '✘ 没有') + (okP1 ? '  ✔' : '  ✘'));
          if (!okP1) bad('分页首屏不对：没按每批条数截断，或缺「显示更多」按钮');
          var sumTxt = norm(($('#cres .ck-sum') || {}).textContent || '');
          var okSum = sumTxt.indexOf('已显示 ' + p1 + ' 条') >= 0;
          T('④c 摘要报出「已显示 N 条」', (okSum ? '✔ ' : '✘ ') + sumTxt);
          if (!okSum) bad('还剩没显示的命中时，摘要应写明「已显示 N 条」—— 否则读者不知道列表被截过');
          var okLeft = !!more && norm(more.textContent).indexOf(String(pn - p1)) >= 0;
          if (!okLeft) bad('「显示更多」按钮没报出剩余条数 —— 读者不知道还有多少没看');
          /* 点一次：应当**增量追加**一批（不是重渲染整段） */
          if (more) more.click();
          var p2 = $$('.ck-hit').length;
          var okP2 = (p2 === Math.min(2 * 1, pn));
          T('④c 点一次「显示更多」→ 多渲染一批',
            p2 + ' 条' + (okP2 ? '  ✔' : '（期望 ' + Math.min(2, pn) + '）✘'));
          if (!okP2) bad('点「显示更多」后条数不对（应逐批追加，不是一次全出也不是不动）');
          /* 点到没有剩余：按钮应自行消失，条数 == 命中数。
             ⚠ 先把批量**还原成正常值**再重跑一次，然后才点 —— 「每批 1 条」只用于
             上面两步验证分页**机制**；拿它点到耗尽的话，命中数一大就要点几百次
             （2026-10-17 实测：桌面课件里「这」字命中 275 处，60 次上限点不完 →
             误报红）。还原后点 2~3 次即到底，断言的是同一条语义。 */
          C.find.PAGE_ROWS = keepRows;
          var pn2 = C.find.run(multi);
          var guard = 0;
          while ((more = $('#cres .res-more')) && guard++ < 50) more.click();
          var pAll = $$('.ck-hit').length;
          var okAll = (pAll === pn2) && (!$('#cres .res-more'));
          T('④c 全部显示后按钮自行消失',
            pAll + '/' + pn2 + ' 条，按钮 ' + ($('#cres .res-more') ? '✘ 还在' : '✔ 已移除') +
            (okAll ? '  ✔' : '  ✘'));
          if (!okAll) bad('点到没有剩余后按钮应消失（否则点了没反应，像坏了）');
        }

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

    /* ---------- 6. 导出 Markdown ----------
       断言按「可见量」条件式：打开时若带着 0 命中的过滤词，导出件本来就该是
       「空表 + 覆盖说明」（markdown() 导出的是**当前可见的那一份**，这是设计），
       此时不该要求它含讲次小标题。 */
    var md = '';
    try { md = C.kp.markdown() || ''; } catch (e) { md = ''; }
    var visLec = 0, visRows = 0;
    $$('.klec').forEach(function (lec) {
      if (lec.hidden) return;
      visLec++;
      visRows += $$('.kpl li', lec).filter(function (x) { return !x.hidden; }).length;
    });
    var okMd = (md.indexOf('#') === 0) && (md.length > 40);
    if (visRows) okMd = okMd && (md.match(/\n## /g) || []).length > 0;
    T('⑥ 导出 Markdown', md.length + ' 字符（可见 ' + visLec + ' 讲 / ' + visRows + ' 条）' +
      (okMd ? '  ✔' : '  ✘'));
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

    /* ---------- ⑧ 顶栏 scrollspy ----------
       滚动位置在无头 virtual-time 下不派发原生 scroll 事件（pitfalls 里的老坑），
       所以不走「等 scroll 事件」的路，而是：用显式 behavior:'instant' 的
       scrollTo 同步生效 → **直接调 spy.update()** 同步算高亮并断言。 */
    var spy = C.spy;
    if (!spy || !spy.links.length) {
      T('⑧ 顶栏 scrollspy', '✘ window.__course.spy 不存在或没有任何导航项');
      bad('scrollspy 没接上（顶栏导航无法高亮当前区块）');
    } else {
      var de = document.documentElement;
      /* 滚动一律用显式 behavior:'instant' —— 它压过 CSS 的 scroll-behavior:smooth，
         即改即读，不会读到动画中间态。
         （第一版是「临时改 <html> 的 style 再 scrollTo」，实测在「打开就带 hash、
         页面已在滚动位置」的场景翻车：style 写入后 computed 值还没 recalc，
         scrollTo 仍按 smooth 起动画，随即读到的还是旧位置。） */
      var spyGo = function (y) {
        try { window.scrollTo({ top: y, behavior: 'instant' }); }
        catch (e) { window.scrollTo(0, y); }     // 老引擎不认 instant → 退回默认行为
        return spy.update();
      };
      /* 断言必须读 **DOM 里的 .active 类**（而不是只用 update() 的返回值）——
         只读返回值的话，「判定对、类切换坏」的实现缺陷会永远绿着。 */
      var activeNow = function () {
        return $$('.cnav a.active').map(function (a) {
          return String(a.getAttribute('href') || '').replace(/^#/, '');
        }).join(',');
      };
      var rTop = spyGo(0), dTop = activeNow();     // 顶部：还没越过任何区块 → 应点亮第一节
      var rBot = spyGo(1e7), dBot = activeNow();   // 底部：最后一节的 top 可能永远越不过判定线 → 应点亮它
      /* 中间块逐块尝试。前置条件（用文档坐标先算，不靠滚完再猜）：
         · 滚到「该块 top + 6」不会贴到底部（否则会撞上「滚到底」分支）；
         · 该块与**下一块**的间距 > 判定线 + 6 —— 不满足说明这个位置
           本来就该点亮下一块，换下一块再试（页面太短时中间块天生测不了，如实跳过）。
         判定线 = 80px（顶部撞击线，与实现同源：区块顶部进入顶栏下沿就算「正在读」）。 */
      var NEXT = { map: 'keypoints', keypoints: 'search', search: 'glossary',
                   glossary: 'progress', progress: '' };
      var line = 80;
      var maxY = (de.scrollHeight || 0) - (window.innerHeight || 800);
      var midOK = [], midSkip = [], midBad = [];
      spy.links.forEach(function (x) {
        var nid = NEXT[x.id];
        if (!nid) return;
        var el = document.getElementById(x.id), nx = document.getElementById(nid);
        if (!el || !nx) return;
        var elTop = el.getBoundingClientRect().top + window.scrollY;
        var nxTop = nx.getBoundingClientRect().top + window.scrollY;
        if (elTop + 6 > maxY - 40 || nxTop - elTop - 6 <= line) { midSkip.push(x.id); return; }
        var got = spyGo(elTop + 6), dom = activeNow();
        if (got === x.id && dom === x.id) midOK.push(x.id);
        else midBad.push(x.id + ': 判定 ' + got + ' / DOM ' + (dom || '（空）'));
      });
      spyGo(0);                            // 复位（instant，同步生效）
      spy.update();
      /* ⑧b 点击导航的接管：滚到区块 + 高亮立刻跟上 + hash 记下 sec 段（参数段随行） */
      var nav = $('.cnav a[href="#glossary"]');
      var navHash = '', navOK = false;
      if (nav) {
        nav.click();
        navHash = String(location.hash || '');
        navOK = (spy.cur === 'glossary') && (activeNow() === 'glossary') &&
          (navHash.indexOf('sec=glossary') >= 0);
        T('⑧b 点击导航（高亮跟上 + hash 带 sec 段）',
          'cur=' + spy.cur + '，DOM=' + (activeNow() || '（空）') + '，hash=' + navHash +
          (navOK ? '  ✔' : '  ✘'));
        if (!navOK) bad('点击导航后高亮没跟上，或 hash 里没有 sec= 段 —— 点击接管断了');
      } else {
        T('⑧b 点击导航', '（SKIP：找不到指向 #glossary 的导航项）');
      }
      var okSpy = (rTop === spy.links[0].id) && (dTop === spy.links[0].id) &&
        (rBot === spy.links[spy.links.length - 1].id) &&
        (dBot === spy.links[spy.links.length - 1].id) && !midBad.length;
      T('⑧ 顶栏 scrollspy（顶/底/中间块高亮）',
        '顶→' + rTop + '/' + (dTop || '（空）') + '，底→' + rBot + '/' + (dBot || '（空）') +
        '，中间测了 ' + (midOK.join('、') || '无') + '（跳过 ' + (midSkip.join('、') || '无') + '）' +
        (okSpy ? '  ✔' : '  ✘'));
      if (rTop !== spy.links[0].id || dTop !== spy.links[0].id) {
        bad('滚到顶部时高亮的不是第一节 —— scrollspy 判定或类切换有问题');
      }
      if (rBot !== spy.links[spy.links.length - 1].id || dBot !== spy.links[spy.links.length - 1].id) {
        bad('滚到底部时高亮的不是最后一个区块');
      }
      if (midBad.length) bad('中间区块高亮不对：' + midBad.join('、'));
    }

    /* ---------- ⑨ 要点「全部折叠 / 展开」开关 ---------- */
    var tgl = $('#kpToggle');
    var klecAll = $$('.klec');
    if (!tgl) {
      T('⑨ 折叠开关', '✘ 页面上没有 #kpToggle');
      bad('缺折叠开关按钮');
    } else if (!klecAll.length) {
      T('⑨ 折叠开关', '（SKIP：本页没有讲次要点块）');
    } else {
      var t0 = norm(tgl.textContent);
      tgl.click();
      var nFold = $$('.klec').filter(function (l) { return l.open; }).length;
      var t1 = norm(tgl.textContent);
      tgl.click();
      var nOpen = $$('.klec').filter(function (l) { return l.open; }).length;
      var t2 = norm(tgl.textContent);
      var okFold = (nFold === 0) && (t1 === '全部展开');
      var okOpen = (nOpen === klecAll.length) && (t2 === '全部折叠');
      T('⑨ 折叠开关（全部折叠 → 全部展开）',
        '初始「' + t0 + '」→ 折叠后 ' + nFold + ' 个仍展开、「' + t1 + '」→ 再点 ' +
        nOpen + '/' + klecAll.length + ' 个展开、「' + t2 + '」' + ((okFold && okOpen) ? '  ✔' : '  ✘'));
      if (!okFold) bad('「全部折叠」没折起讲次块（或按钮文案没跟上）');
      if (!okOpen) bad('「全部展开」没展开讲次块（或按钮文案没跟上）');
    }

    /* ---------- ⑩ 术语总表过滤 ---------- */
    var gf = $('#glFilter');
    var glRows = $$('#glossary tbody tr');
    if (!gf && glRows.length) {
      T('⑩ 术语过滤', '✘ 术语表有行但页面上没有 #glFilter');
      bad('术语过滤器没接上（表有行、控件不在）');
    } else if (!gf || !glRows.length) {
      T('⑩ 术语过滤', '（SKIP：本页没有术语行 —— 术语区渲染的是说明性占位）');
    } else {
      C.gl.apply('zzz-必然不存在-zzz');
      var gz = glRows.filter(function (r) { return !r.hidden; }).length;
      var geOn = (($('#glEmpty') || {}).hidden === false);
      C.gl.apply('');
      var gback = glRows.filter(function (r) { return !r.hidden; }).length;
      /* 命中测试：取第一行的术语名（第一格粗体）原样搜 —— 至少该命中它自己 */
      var nameEl = $('td b', glRows[0]) || $('td', glRows[0]);
      var gname = norm(nameEl && nameEl.textContent).split(/[\s（(]/)[0] || '';
      var ghit = gname ? C.gl.apply(gname) : -1;
      C.gl.apply('');
      var okG = (gz === 0) && geOn && (gback === glRows.length) && (!gname || ghit >= 1);
      T('⑩ 术语过滤（0 命中提示 / 清空复原 / 命中）',
        '0 命中时可见 ' + gz + '，空状态 ' + (geOn ? '出现' : '没出现') +
        '，清空复原 ' + gback + '/' + glRows.length + '，搜「' + gname + '」命中 ' + ghit +
        (okG ? '  ✔' : '  ✘'));
      if (!okG) bad('术语过滤行为不对（0 命中没提示 / 清空没复原 / 搜术语名命中不了自己）');
    }

    /* ---------- ⑪ URL 状态解析（纯函数） ---------- */
    if (!C.url || typeof C.url.parse !== 'function') {
      T('⑪ URL 状态解析', '✘ window.__course.url 不存在');
      bad('course.js 没有暴露 URL 状态模块');
    } else {
      var p1 = C.url.parse('#sec=search&kp=%E6%A2%AF%E5%BA%A6&find=abc&gl=x&unknown=1');
      var p2 = C.url.parse('#glossary');
      var okP = (p1.sec === 'search') && (p1.kp === '梯度') && (p1.find === 'abc') &&
        (p1.gl === 'x') && !('unknown' in p1) &&
        (p2.sec === 'glossary') && (p2.kp === '');
      T('⑪ URL 状态解析（kv 段 / 裸段 / 未知名忽略 / 值解码）',
        JSON.stringify(p1) + ' ｜ 裸段 → sec=' + p2.sec + (okP ? '  ✔' : '  ✘'));
      if (!okP) bad('URL 解析不对（裸段没认成 sec / kv 没解出来 / 值没解码 / 未知名被吃进来）');
    }

    /* ---------- ⑫ 启动恢复（仅当打开时就带参数 —— 由 probe.py --hash 触发） ----------
       断言用的是 run() 开头那份快照（那时页面还是刚打开的状态）。 */
    if (!bootH.kp && !bootH.sec) {
      T('⑫ 启动恢复', '（SKIP：打开页面时 URL 未带参数）');
    } else {
      var exp0 = 0;
      if (bootH.kp) {
        var ws = bootH.kp.toLowerCase().split(' ');
        C.kp.items.forEach(function (it) {
          var hit = true;
          for (var wi = 0; wi < ws.length; wi++) if (it.text.indexOf(ws[wi]) < 0) hit = false;
          if (hit) exp0++;
        });
      }
      var okV = (bootKpValue === bootH.kp) && (bootKpShown === exp0);
      var okS = true;
      if (bootH.sec) {
        var secEl = document.getElementById(bootH.sec);
        okS = (bootScrollY > 0) && !!secEl &&
          (secEl.getBoundingClientRect().top < (window.innerHeight || 800) * 0.6);
      }
      T('⑫ 启动恢复（打开页面时就带参数）',
        '过滤框=' + JSON.stringify(bootKpValue) + '，可见要点 ' + bootKpShown +
        '（期望 ' + exp0 + '），scrollY=' + bootScrollY + '，sec=' + (bootH.sec || '（无）') +
        ((okV && okS) ? '  ✔' : '  ✘'));
      if (bootKpValue !== bootH.kp) bad('打开带参链接后过滤框没有恢复 —— 启动读取链断了');
      if (bootKpShown !== exp0) bad('启动恢复后的过滤结果与参数的口径对不上');
      if (bootH.sec && !okS) bad('打开带 sec 段的链接后页面没有滚到那个区块');
    }

    /* ---------- ⑭ 学习进度（读各讲 localStorage → 渲染） ----------
       预置键必须用 cdata 里的 ns（真实接线）—— 拿猜的 ns 测不到「ns 链路对不对」。
       预置结构与单讲 site.js 的 Pos.save / Notes.save 同构；跑完清掉（还原现场）。 */
    if (!C.lp || typeof C.lp.refresh !== 'function') {
      T('⑭ 学习进度', '✘ window.__course.lp 不存在');
      bad('course.js 没有暴露学习进度模块');
    } else {
      var A = null, B = null;
      lecs.forEach(function (l) {
        if (!(l.ns && l.href)) return;
        if (!A) A = l;
        else if (!B) B = l;
      });
      if (!A) {
        T('⑭ 学习进度', '（SKIP：内联数据里没有带 ns 的讲次）');
      } else {
        /* 0）boot 时的初始渲染（initLP 真的跑了）：#lpTop 不该是空的
              —— 空态引导 tip 也算「有内容」。防「initLP 从 boot 里掉了」这类静默断链。 */
        var topAtBoot = norm(($('#lpTop') || {}).textContent);
        var okBoot = topAtBoot.length > 0;
        T('⑭ 初始渲染（boot 后 #lpTop 有内容）',
          '「' + topAtBoot.slice(0, 40) + '…」' + (okBoot ? '  ✔' : '  ✘'));
        if (!okBoot) bad('boot 后 #lpTop 是空的 —— initLP 没跑或 LP.render 没执行');

        var KEY_P = A.ns + 'pos', KEY_N = A.ns + 'notes';
        localStorage.setItem(KEY_P, JSON.stringify({
          v: 1, p: 'p02', n: 2, t: Date.now() - 3 * 86400000
        }));
        localStorage.setItem(KEY_N, JSON.stringify({ v: 1, seq: 4, items: [{}, {}, {}] }));
        C.lp.refresh();
        var cellA = $('tr[data-lec="' + A.id + '"] .lp-cell');
        var txtA = norm(cellA && cellA.textContent);
        var goA = cellA ? $('.lp-go', cellA) : null;
        var hrefA = String((goA && goA.getAttribute('href')) || '');
        var okA = /上次读到/.test(txtA) && /P2/.test(txtA) && /3 条笔记/.test(txtA) &&
          /天前/.test(txtA) && hrefA.slice(-4) === '#p02';
        var topTxt = norm(($('#lpTop') || {}).textContent);
        var okTop = topTxt.indexOf('已开始 1 /') >= 0 && topTxt.indexOf('3 条笔记') >= 0;
        T('⑭ 学习进度渲染（预置痕迹 → 行 + 总览）',
          '行=「' + txtA + '」go=' + (hrefA || '✘') + '，总览=「' + topTxt + '」' +
          ((okA && okTop) ? '  ✔' : '  ✘'));
        if (!okA) bad('学习进度行没按预置的痕迹渲染（或「继续」链接不是 #p02 结尾）');
        if (!okTop) bad('学习进度总览没显示（已开始 N 讲 / 笔记数）');

        if (B) {
          var txtB = norm((($('tr[data-lec="' + B.id + '"] .lp-cell') || {}).textContent));
          var okB = txtB.indexOf('还没有阅读记录') >= 0;
          T('⑭ 学习进度：无记录的讲显示空态', '「' + txtB + '」' + (okB ? '  ✔' : '  ✘'));
          if (!okB) bad('没有痕迹的讲次行没有显示「还没有阅读记录」');
        }

        /* 清掉痕迹 → 回到空态引导（顺带证明「只读」：页面没把数据写回去） */
        localStorage.removeItem(KEY_P);
        localStorage.removeItem(KEY_N);
        C.lp.refresh();
        var topTxt2 = norm(($('#lpTop') || {}).textContent);
        var txtA2 = norm((($('tr[data-lec="' + A.id + '"] .lp-cell') || {}).textContent));
        var okEmpty = topTxt2.indexOf('打开任一讲') >= 0 && txtA2.indexOf('还没有阅读记录') >= 0;
        T('⑭ 学习进度空态（清掉痕迹 → 引导文案）',
          '总览=「' + topTxt2 + '」' + (okEmpty ? '  ✔' : '  ✘'));
        if (!okEmpty) bad('清掉痕迹后没有回到空态引导');
      }
    }

    /* ---------- ⑮ 术语表排序（首见顺 → English A–Z → 还原） ---------- */
    var sSel = $('#glSort');
    if (!glRows.length) {
      T('⑮ 术语排序', '（SKIP：本页没有术语行）');
    } else if (!sSel || !C.gl || typeof C.gl.sort !== 'function') {
      T('⑮ 术语排序', '✘ 术语表有行但缺 #glSort 或 sort()');
      bad('术语排序控件没接上（表有行、控件或实现不在）');
    } else if (glRows.length < 2) {
      T('⑮ 术语排序', '（SKIP：术语行不足 2 行，排序无意义）');
    } else {
      var cmpEn = function (a, b) {
        return a.localeCompare(b, 'en', { sensitivity: 'base' });
      };
      var enOf = function (tr) { return norm((tr.cells[1] || {}).textContent).toLowerCase(); };
      C.gl.sort('en');
      var rowsEn = $$('#glossary tbody tr');
      var sortedOk = rowsEn.length === glRows.length;
      for (var ei = 1; sortedOk && ei < rowsEn.length; ei++) {
        if (cmpEn(enOf(rowsEn[ei - 1]), enOf(rowsEn[ei])) > 0) sortedOk = false;
      }
      C.gl.sort('first');
      var rowsBack = $$('#glossary tbody tr');
      var backOk = rowsBack.length === glRows.length;
      for (var bi = 0; backOk && bi < rowsBack.length; bi++) {
        if (rowsBack[bi] !== glRows[bi]) backOk = false;      // 元素引用逐项比对
      }
      T('⑮ 术语排序（English A–Z / 还原首见序）',
        'A–Z ' + (sortedOk ? '✔' : '✘') + '，还原 ' + (backOk ? '✔' : '✘') +
        '（' + rowsEn.length + ' 行）');
      if (!sortedOk) bad('切 English 排序后行序不是字母序（或行了丢行）');
      if (!backOk) bad('切回首见顺序没有还原初始行序');
    }
  } catch (err) {
    out.push('PROBE_ERROR: ' + (err && err.stack ? err.stack : err));
    return finish();
  }
  /* ⑬ URL 写入链路要等防抖，移到异步尾段（见 tail） */
  tail();
}

function finish() {
  T('RESULT', fail ? ('FAIL（' + fail + ' 项）') : 'PASS');
  done();
}

/* ================= 异步尾段：⑬ URL 写入链路 =================
   输入事件 → 防抖 → 写 hash 这条链要真实走一遍；探针在 virtual-time 下跑，
   setTimeout 会被推进，直接等就行。防抖从 300ms 临时调小到 10ms ——
   测的是「链路通不通」而不是「300ms 这个数字」（与 ④c 临时调 PAGE_ROWS 同一手法），
   跑完还原。 */
function tail() {
  var C = window.__course;
  if (!C || !C.url || !C.url.schedule) {
    T('⑬ URL 写入链路', '（SKIP：course.js 没暴露 url 模块）');
    return finish();
  }
  var keepDb = C.url.DEBOUNCE;
  C.url.DEBOUNCE = 10;

  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function fire(el, v) {
    el.value = v;
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }
  function H() { return String(location.hash || ''); }

  var f = $('#kpFilter'), q = $('#cq');
  var chain = Promise.resolve();

  /* 1) 输入要点过滤词 → 防抖后 hash 出现 kp= */
  chain = chain.then(function () {
    if (!f) return;
    fire(f, 'zzz-kp-abc');
    return wait(90).then(function () {
      var ok = H().indexOf('kp=zzz-kp-abc') >= 0;
      T('⑬ URL 写入：要点过滤词进 hash', H() + (ok ? '  ✔' : '  ✘'));
      if (!ok) bad('输入过滤词后 hash 里没有 kp= —— URL 状态同步断了');
    });
  });

  /* 2) 清空 → 参数移除 */
  chain = chain.then(function () {
    if (!f) return;
    fire(f, '');
    return wait(90).then(function () {
      var ok = H().indexOf('kp=') < 0;
      T('⑬ URL 写入：清空后参数移除', H() + (ok ? '  ✔' : '  ✘'));
      if (!ok) bad('清空过滤词后 hash 里仍留着 kp= —— 清空没写回 URL');
    });
  });

  /* 3) 输入检索词 → hash 出现 find= */
  chain = chain.then(function () {
    if (!q) return;
    fire(q, 'zzz-find-abc');
    return wait(90).then(function () {
      var ok = H().indexOf('find=zzz-find-abc') >= 0;
      T('⑬ URL 写入：检索词进 hash', H() + (ok ? '  ✔' : '  ✘'));
      if (!ok) bad('输入检索词后 hash 里没有 find=');
    });
  });

  /* 4) 清空检索 */
  chain = chain.then(function () {
    if (!q) return;
    fire(q, '');
    return wait(90);
  });

  /* 5) hash 外部变化 → 全量套用（与「手改地址栏 / 前进后退」同一条链） */
  chain = chain.then(function () {
    location.hash = 'sec=keypoints&kp=zzz-null-abc';
    return wait(140).then(function () {
      var kf = $('#kpFilter');
      var ok = !!kf && kf.value === 'zzz-null-abc';
      T('⑬ hash 外部变化 → 全量套用（恢复过滤词）',
        '过滤框=' + JSON.stringify(kf ? kf.value : null) + '，hash=' + H() + (ok ? '  ✔' : '  ✘'));
      if (!ok) bad('外部改 hash 后页面没有套用参数 —— hashchange 恢复链断了');
    });
  });

  /* 6) hash 去掉参数 → 对应筛选项清空（前进后退的语义） */
  chain = chain.then(function () {
    location.hash = 'sec=keypoints';
    return wait(140).then(function () {
      var kf = $('#kpFilter');
      var ok = !!kf && kf.value === '';
      T('⑬ hash 去掉参数 → 对应筛选项清空',
        '过滤框=' + JSON.stringify(kf ? kf.value : null) + (ok ? '  ✔' : '  ✘'));
      if (!ok) bad('hash 里省掉参数后页面没清空对应项 —— 前进后退的语义会不一致');
    });
  });

  chain.then(function () {
    C.url.DEBOUNCE = keepDb;                 // 还原（虽然探针跑完页面即销毁，也保持干净）
  }).catch(function (err) {
    out.push('PROBE_ERROR(tail): ' + (err && err.stack ? err.stack : err));
    fail++;
  }).then(finish);
}
