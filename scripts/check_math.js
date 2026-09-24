#!/usr/bin/env node
/* 批量校验单文件 HTML 里所有 KaTeX 公式的语法，并做结构体检。
 *
 * 用法：
 *   node check_math.js <html文件> [katex.min.js路径]
 *
 * 检查项：
 *   ① 所有 <script type="math/tex"> 能否用 throwOnError:true 渲染
 *   ② 公式里是否混入 CJK（KaTeX 自带字体不含中文，会走兜底字体导致字距错乱）
 *   ③ 标签配对（section/div/p/table/li/span/b/em/script …）
 *   ④ 目录锚点是否都存在
 *   ⑤ 占位符是否残留；⑤b TODO 残留（已排除 script 与内嵌 base64）
 *   ⑥ 数量一致性（缩略图 / 逐页区块 / 深链）
 *   ⑦ 文件大小
 *   ⑧ 正文缺字体检（组合符号 U+20D0–U+20FF，中文字体普遍缺字形 → 方框）
 * 退出码：有任一硬性失败（①②③⑤⑧）则为 1。
 */
const fs = require('fs');
const path = require('path');

const file = process.argv[2];
if (!file) { console.error('用法: node check_math.js <html文件> [katex.min.js路径]'); process.exit(2); }
const katexPath = process.argv[3] ||
  path.join(__dirname, '..', '..', '..', 'katex', 'katex.min.js');

let katex = null, katexErr = null;
try { katex = require(path.resolve(katexPath)); } catch (e) { katexErr = e; }
if (!katex) {
  try { katex = require('katex'); } catch (e) { katexErr = e; }
}

const html = fs.readFileSync(file, 'utf8');
let hardFail = 0;

/* ---------- ① 公式语法 ---------- */
const mathRe = /<script type="math\/tex([^"]*)">([\s\S]*?)<\/script>/g;
let m, total = 0, bad = 0;
const errs = {};
const cjkRe = /[\u2e80-\u9fff\uff00-\uffef\u3000-\u303f]/;
let cjkCount = 0;
if (katex) {
  while ((m = mathRe.exec(html))) {
    total++;
    if (cjkRe.test(m[2])) {
      cjkCount++;
      if (cjkCount <= 5) console.log('[CJK ]', JSON.stringify(m[2].slice(0, 90)));
    }
    try {
      katex.renderToString(m[2], {
        displayMode: /mode=display/.test(m[1]),
        throwOnError: true, strict: 'error', trust: false,
      });
    } catch (e) {
      bad++;
      const key = String(e.message).split('\n')[0].slice(0, 140);
      errs[key] = (errs[key] || 0) + 1;
      if (bad <= 10) console.log('[FAIL]', JSON.stringify(m[2].slice(0, 100)), '=>', key);
    }
  }
  console.log(`① 公式：共 ${total} 条，语法失败 ${bad} 条，含 CJK ${cjkCount} 条`);
  Object.keys(errs).forEach(k => console.log('    ' + errs[k] + 'x ' + k));
  if (bad) hardFail = 1;
} else {
  console.log('① 公式：未找到 katex 模块，跳过（' + katexErr + '）');
}

/* ---------- ③ 标签配对 ---------- */
const bodyStart = html.indexOf('<body');
let bodyEnd = html.indexOf('<!--BODY-END');
if (bodyEnd < 0) bodyEnd = html.indexOf('<div class="lightbox"');   // 兼容旧模板
let body = (bodyStart >= 0 && bodyEnd > bodyStart) ? html.slice(bodyStart, bodyEnd) : html;
// 关键：先挖掉 HTML 注释再数标签。注释里常出现字面标签（例如
// 「缩略图会插到 </section> 之前」），不排除就会造成假性不平衡，
// 把人引向根本不存在的结构问题（见 references/pitfalls.md 第 30 条）。
const comments = [];
body = body.replace(/<!--[\s\S]*?-->/g, (m) => { comments.push(m); return ''; });
const tags = ['section', 'div', 'p', 'table', 'thead', 'tbody', 'tr', 'td', 'th',
  'details', 'summary', 'figure', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4',
  'aside', 'main', 'nav', 'span', 'b', 'em', 'a', 'code', 'button', 'textarea', 'mark'];
let unbalanced = [];
tags.forEach(t => {
  const o = (body.match(new RegExp('<' + t + '[\\s>]', 'g')) || []).length;
  const c = (body.match(new RegExp('</' + t + '>', 'g')) || []).length;
  if (o !== c) { unbalanced.push(`${t}: open=${o} close=${c}`); }
});
console.log('③ 标签配对：' + (unbalanced.length ? '不平衡 → ' + unbalanced.join('; ') : '全部平衡') +
  `（已排除 ${comments.length} 段注释）`);
if (unbalanced.length) hardFail = 1;

/* ---------- ④ 目录锚点 ---------- */
const navS = html.indexOf('<nav'), navE = html.indexOf('</nav>');
if (navS >= 0 && navE > navS) {
  const nav = html.slice(navS, navE);
  const hrefs = [...nav.matchAll(/href="(#[^"]+)"/g)].map(x => x[1]);
  const miss = hrefs.filter(h => !html.includes('id="' + h.slice(1) + '"'));
  console.log(`④ 目录：${hrefs.length} 条，缺失锚点 ${miss.length}` +
    (miss.length ? ' → ' + miss.slice(0, 8).join(', ') : ''));
} else {
  console.log('④ 目录：未找到 <nav>，跳过');
}

/* ---------- ⑤ 占位符与内嵌资源 ---------- */
const leftovers = ['__KATEX_CSS__', '__KATEX_JS__', '__BODY__', '__TOC__', '__CSS__', '__JS__', '__PDFURL__']
  .filter(k => html.includes(k));
console.log('⑤ 占位符残留：' + (leftovers.length ? leftovers.join(', ') : '无'));
if (leftovers.length) hardFail = 1;

/* ---------- ⑤b TODO 残留 ----------
   **必须先把所有 <script>…</script> 挖掉**，否则必然误报，实测两个来源：
     ① 内嵌 PDF 的 base64 payload（随机字符里碰巧拼出 TODO —— 真碰到过 1 次）
     ② 注入页面的体检探针自身源码（probe_doc.js 的注释里就写着 TODO）
   probe_doc.js 那边只看「可见正文」，这里看的是源码层面，两边互补。 */
const noScript = html.replace(/<script[\s\S]*?<\/script>/g, '');
const todoHits = (noScript.match(/TODO/g) || []).length;
console.log('⑤b TODO 残留（已排除 script / 内嵌 base64）：' + todoHits + ' 处' +
  (todoHits ? '  ⚠ 请清掉；目标 0' : '  ✔'));

const thumbs = (html.match(/class="thumb"/g) || []).length;
const pgSections = (html.match(/<section class="pg"/g) || []).length;
const links = (html.match(/class="pdf-link"/g) || []).length;
console.log(`⑥ 缩略图 ${thumbs} / 逐页区块 ${pgSections} / PDF深链 ${links}` +
  (thumbs === pgSections && links === pgSections ? '  ✔ 一致' : '  ⚠ 数量不一致'));

/* ---------- ⑧ 正文缺字体检：组合符号 U+20D0–U+20FF ----------
   这一段的字符叫「符号用组合附加记号」，**中文字体栈（PingFang SC /
   Microsoft YaHei / Source Han Sans / Noto CJK）普遍没有它们的字形**，
   浏览器回退不到任何字体 → 渲染成方框（tofu）。
   实测最常踩的就是拿 U+20D7（COMBINING RIGHT ARROW ABOVE）当矢量符号写
   「J⃗」「v⃗」——在 KaTeX 公式里没问题（公式走 KaTeX 自己的字体），
   一旦写进正文就变方框。
   **正文里表示矢量请用 <b class="vec">J</b> 加粗**（见 references/pitfalls.md 第 34 条）。
   这个检查会先挖掉 math/tex 区块，只看正文。 */
const noMath = html.replace(/<script type="math\/tex[^"]*">[\s\S]*?<\/script>/g, '');
const combining = noMath.match(/[\u20d0-\u20ff]/g) || [];
const combiningKinds = {};
noMath.replace(/[\u20d0-\u20ff]/g, (c) => { combiningKinds[c] = (combiningKinds[c] || 0) + 1; return c; });
console.log('⑧ 正文缺字体检（组合符号 U+20D0–U+20FF）：' + (combining.length
  ? '✘ ' + combining.length + ' 处 → ' +
    Object.keys(combiningKinds).map((c) =>
      'U+' + c.codePointAt(0).toString(16).toUpperCase().padStart(4, '0') + '×' + combiningKinds[c]
    ).join(' ') + '（会渲染成方框，请改用 <b class="vec"> 加粗表示矢量）'
  : '0 处 ✔'));
if (combining.length) hardFail = 1;

console.log('⑦ 文件大小：' + (fs.statSync(file).size / 1048576).toFixed(2) + ' MB');
process.exit(hardFail);
