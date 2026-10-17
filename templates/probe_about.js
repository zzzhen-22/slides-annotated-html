/* ============================================================================
   关于面板回归（2026-10-17 · 顶栏「关于」→ 使用说明 + 生成工具）

   覆盖完整的打开 / 关闭链路（modal 语义），全部走真实接线：
     ① 入口与面板存在
     ② 初始关闭
     ③ 点「关于」打开（遮罩 .on，焦点进面板）
     ④ 面板内容可见（使用说明 + GitHub 链接）
     ⑤ Esc 关闭
     ⑥ 点遮罩关闭
     ⑦ × 关闭 + 焦点回到「关于」按钮
     ⑧ 点卡片内部不误关（e.target 判定的边界）

   与 ⑫ 代码块组同一约定：跑完清空页面，只留 <pre id="__r">（pitfalls 第 23 条）。
   语言无关：中英两版文案都认（使用说明标题 / GitHub 域名）。
   ========================================================================== */
(function () {
  var out = [], fail = 0;
  function T(k, v) { out.push(k + ': ' + v); }
  function bad(m) { out.push('  ✘ ' + m); fail++; }
  function norm(t) { return String(t == null ? '' : t).replace(/\s+/g, ' ').trim(); }
  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  function done() {
    document.head.innerHTML = '';
    document.body.innerHTML = '<pre id="__r">' + esc(out.join('\n')) + '</pre>';
  }

  window.addEventListener('load', function () {
    setTimeout(function () {
      try {
        var btn = document.getElementById('aboutBtn');
        var mask = document.getElementById('aboutMask');
        var close = document.getElementById('aboutClose');
        var card = mask ? mask.querySelector('.ab-card') : null;
        T('关于面板 ① 入口与面板存在', (btn && mask && close && card ? '✔' : '✘') +
          '（btn=' + !!btn + ' mask=' + !!mask + ' close=' + !!close + ' card=' + !!card + '）');
        if (!btn || !mask || !close || !card) {
          bad('缺关于入口或面板结构');
          T('RESULT', 'FAIL');
          return done();
        }

        function isOn() { return mask.classList.contains('on'); }

        T('关于面板 ② 初始关闭', (!isOn() && mask.hidden ? '✔' : '✘') +
          '（on=' + isOn() + ' hidden=' + mask.hidden + '）');
        if (isOn() || !mask.hidden) bad('初始状态应当是关闭的');

        btn.click();
        T('关于面板 ③ 点「关于」打开', (isOn() && !mask.hidden ? '✔' : '✘') +
          '（on=' + isOn() + ' 焦点在关闭按钮=' + (document.activeElement === close) + '）');
        if (!isOn()) bad('点击后遮罩没有 .on（面板没打开）');
        if (document.activeElement !== close) bad('打开后焦点没进面板（键盘用户无法继续）');

        var txt = norm(card.textContent);
        var hasHowto = (txt.indexOf('这份文档怎么用') >= 0) ||
                       (txt.indexOf('How to use this document') >= 0);
        var hasGit = txt.indexOf('github.com/zzzhen-22/slides-annotated-html') >= 0;
        T('关于面板 ④ 内容可见（使用说明 + 生成工具）',
          (hasHowto && hasGit ? '✔' : '✘') + '（使用说明=' + hasHowto + ' GitHub=' + hasGit +
          ' 文本 ' + txt.length + ' 字）');
        if (!hasHowto) bad('面板里找不到使用说明');
        if (!hasGit) bad('面板里找不到生成工具的 GitHub 链接');

        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
        T('关于面板 ⑤ Esc 关闭', (!isOn() ? '✔' : '✘') + '（on=' + isOn() + '）');
        if (isOn()) bad('Esc 没关掉面板');

        btn.click();
        /* 派发到遮罩本身（e.target === mask 才会关 —— 真实用户点的是空白处） */
        mask.dispatchEvent(new MouseEvent('click', { bubbles: true }));
        T('关于面板 ⑥ 点遮罩关闭', (!isOn() ? '✔' : '✘'));
        if (isOn()) bad('点遮罩没关掉面板');

        btn.click();
        close.click();
        var refocus = document.activeElement === btn;
        T('关于面板 ⑦ × 关闭 + 焦点归还', (!isOn() && refocus ? '✔' : '✘') +
          '（on=' + isOn() + ' 焦点回到按钮=' + refocus + '）');
        if (isOn()) bad('× 没关掉面板');
        if (!refocus) bad('关闭后焦点没回到「关于」按钮（键盘用户会迷路）');

        btn.click();
        card.dispatchEvent(new MouseEvent('click', { bubbles: true }));
        T('关于面板 ⑧ 点卡片内部不误关', (isOn() ? '✔' : '✘'));
        if (!isOn()) bad('点面板内部被误判成「点遮罩」—— 阅读时一点就关');
        close.click();
      } catch (e) {
        out.push('PROBE_ERROR: ' + (e && e.stack ? e.stack : e));
        fail++;
      }
      T('RESULT', fail ? 'FAIL' : 'PASS');
      done();
    }, 600);
  });
})();
