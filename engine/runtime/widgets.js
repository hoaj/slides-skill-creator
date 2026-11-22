/* === DECK WIDGETS ===
   Markup contracts (see widgets.md):
   - Bars:   .chart-bars > .bar[data-value][data-max] (label/value children)
   - Donut:  .chart-donut[data-percent]
   - Counter:.counter-stat[data-to][data-decimals]
   - Toggle: .toggle-group[role=tablist] button[aria-controls] + .toggle-panel#id
   - Steps:  any element with [data-step] (revealed by the controller)
   - Embed:  iframe.embed-frame[data-src] (src set lazily on activate) */
window.DeckWidgets = {
  _wired: new WeakSet(),

  /* opts.instant — jump widgets straight to their final value (no animation).
     Used by PDF export so the snapshot captures the end-state. */
  activate(slide, opts) {
    if (!slide) return;
    const instant = !!(opts && opts.instant);
    slide.querySelectorAll('.chart-bars .bar').forEach(bar => {
      const v = +bar.dataset.value, max = +(bar.dataset.max || 100);
      bar.querySelector('.fill').style.setProperty('--h', Math.max(0, Math.min(100, v / max * 100)) + '%');
    });
    slide.querySelectorAll('.chart-donut').forEach(d => {
      d.style.setProperty('--p', Math.max(0, Math.min(100, +d.dataset.percent || 0)));
    });
    slide.querySelectorAll('.counter-stat').forEach(el => this._count(el, instant));
    slide.querySelectorAll('iframe.embed-frame[data-src]').forEach(f => {
      if (!f.src || f.src === 'about:blank') f.src = f.dataset.src;
    });
    if (!this._wired.has(slide)) { this._wireToggles(slide); this._wired.add(slide); }
  },

  /* The Brand pack's optional number format (window.DeckBrand.numberFormat), for example
     thousands "." and decimal ",". Without one: 159365 and 3.5. */
  _formatNumber(v, dec) {
    const nf = (window.DeckBrand && window.DeckBrand.numberFormat) || {};
    const [int, frac] = v.toFixed(dec).split('.');
    const grouped = nf.thousands ? int.replace(/\B(?=(\d{3})+(?!\d))/g, nf.thousands) : int;
    return frac ? grouped + (nf.decimal || '.') + frac : grouped;
  },

  _count(el, instant) {
    const to = +el.dataset.to, dec = +(el.dataset.decimals || 0), dur = 1100;
    const render = v => { el.textContent = this._formatNumber(v, dec) + (el.dataset.suffix || ''); };
    if (instant) { render(to); return; }
    const t0 = performance.now();
    const tick = (t) => {
      const k = Math.min(1, (t - t0) / dur);
      const e = 1 - Math.pow(1 - k, 3);
      render(to * e);
      if (k < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  },

  _wireToggles(slide) {
    slide.querySelectorAll('.toggle-group').forEach(group => {
      const btns = Array.from(group.querySelectorAll('button'));
      btns.forEach(btn => btn.addEventListener('click', () => {
        btns.forEach(b => b.setAttribute('aria-selected', b === btn ? 'true' : 'false'));
        const targetId = btn.getAttribute('aria-controls');
        const scope = group.closest('.slide') || document;
        scope.querySelectorAll('.toggle-panel').forEach(p =>
          p.classList.toggle('active', p.id === targetId));
      }));
    });
  }
};
