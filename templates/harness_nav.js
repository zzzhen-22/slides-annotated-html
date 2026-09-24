/* ============================================================================
   截图 harness：收起左栏（验证缩略图列由 268px 放大到 400px）
   用法：
     python scripts/shot.py <输出.html> _extract/v_nav.png --section p12 \
            --script templates/harness_nav.js
   注意：transition 与 scroll-behavior 在无头虚拟时间下不推进，必须显式关掉，
        否则量出来的坐标/列宽全是错的（见 references/pitfalls.md 第 16、22 条）。
   ========================================================================== */
window.addEventListener('load', function () {
  var st = document.createElement('style');
  st.textContent = '.drawer,.toc,.selbar{transition:none!important} html{scroll-behavior:auto!important}';
  document.head.appendChild(st);
  setTimeout(function () {
    var b = document.getElementById('navToggle');
    if (b) b.click();
  }, 700);
});
