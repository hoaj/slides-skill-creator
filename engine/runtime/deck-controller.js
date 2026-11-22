/* === DECK CONTROLLER ===
   Everything that differs per brand (themes, default theme, bloom themes, classification
   labels and default) comes from window.DeckBrand, which `deck.py build` generates from
   the Brand pack. There are no fallbacks: a deck without it cannot run. */
const DECK_MONTHS = {
  en: ['January','February','March','April','May','June','July','August','September','October','November','December'],
  da: ['januar','februar','marts','april','maj','juni','juli','august','september','oktober','november','december']
};
if (!window.DeckBrand) throw new Error('window.DeckBrand is missing: build this deck with deck.py build.');
const DECK_BRAND = window.DeckBrand;
const DEFAULT_THEME = DECK_BRAND.defaultTheme;
const BLOOM_THEMES = DECK_BRAND.bloomThemes;
const THEME_OPTIONS = DECK_BRAND.themes;
const CLASSIFICATIONS = DECK_BRAND.classifications;
const DEFAULT_CLASSIFICATION = DECK_BRAND.defaultClassification;
const STORE_PREFIX = DECK_BRAND.slug + '-deck';
class Deck {
  constructor() {
    this.stage = document.getElementById('deckStage');
    this.slides = Array.from(document.querySelectorAll('.slide'));
    this.chrome = document.querySelector('.deck-frame');
    this.current = 0;
    this.editing = false;
    this._fileHandle = null;
    // Unique per-deck key so multiple decks (even with the same title) never
    // share state. data-deck-id is baked in at generation; fall back to the path.
    this.STORE_KEY = STORE_PREFIX + ':' + (this.stage.dataset.deckId || (location.pathname + '|' + (document.title || 'deck')));
    // The slide position has its own key: a rebuild discards the stale edit draft
    // (STORE_KEY) but keeps the slide the viewer was on.
    this.POS_KEY = this.STORE_KEY + ':slide';
    this._buildChrome();
    this._scale(); window.addEventListener('resize', () => this._scale());
    this._keys(); this._touch(); this._wheel();
    this._restore();
    this._initChrome();
    this._syncPanel();
    this.go(this._startSlide());
    addEventListener('hashchange', () => {
      const n = this._hashSlide();
      if (n != null && n !== this.current) this.go(n);
    });
    this._buildOverview();
    this._bindDismiss();
    this._maybeShowHint();
  }

  /* Show a small badge when the view includes local edits not in the file, or when
     a stale draft was just discarded because the file was rebuilt. */
  _maybeShowHint() {
    if (!this.hint) return;
    if (this._restoredDraft) { this._localEditsShown = true; this._showHint('Local edits — not saved to file', true); }
    else if (this._staleCleared) this._showHint('Rebuilt deck loaded — earlier local edits cleared', false, 6000);
  }
  /* Reveal the "local edits" badge as soon as an edit is autosaved (not just after a
     reload). Shown once per unsaved session; cleared when the edits are saved to file. */
  _notifyLocalEdits() {
    if (!this.hint || this._suppressEditHint || this._localEditsShown) return;
    this._localEditsShown = true;
    this._showHint('Local edits — not saved to file', true);
  }
  _showHint(msg, withActions, autoHideMs) {
    this.hint.innerHTML = '';
    const span = document.createElement('span'); span.textContent = msg;
    this.hint.appendChild(span);
    if (withActions) {
      const save = document.createElement('button'); save.type = 'button'; save.className = 'hint-save'; save.textContent = 'Save';
      save.addEventListener('click', () => this.save());   // write edits to the file (hides the badge on success)
      this.hint.appendChild(save);
      const discard = document.createElement('button'); discard.type = 'button'; discard.className = 'hint-discard'; discard.textContent = 'Discard';
      discard.addEventListener('click', () => { try { localStorage.removeItem(this.STORE_KEY); } catch (e) {} location.reload(); });
      this.hint.appendChild(discard);
    }
    this.hint.classList.add('show');
    if (autoHideMs) setTimeout(() => this.hint.classList.remove('show'), autoHideMs);
  }

  /* --- scaling --- */
  _scale() {
    const f = Math.min(innerWidth / 1920, innerHeight / 1080);
    const x = (innerWidth - 1920 * f) / 2, y = (innerHeight - 1080 * f) / 2;
    this.stage.style.transform = `translate(${x}px, ${y}px) scale(${f})`;
  }

  /* --- navigation --- */
  go(i) {
    this.current = Math.max(0, Math.min(i, this.slides.length - 1));
    this.slides.forEach((s, n) => {
      const on = n === this.current;
      s.classList.toggle('active', on);
      s.classList.toggle('visible', on);
    });
    if (this.counter) this.counter.textContent = `${this.current + 1} / ${this.slides.length}`;
    if (this.themeSelect) {
      const s = this.slides[this.current];
      this.themeSelect.value = (s && s.dataset.theme) || this.stage.dataset.theme || DEFAULT_THEME;
    }
    this._resetWidgets();
    this._updateChrome();
    this._updateBloomControl();
    this._rememberSlide();
  }
  next() { this.go(this.current + 1); }

  /* --- slide position: survives a reload and a rebuild ---
     The URL hash #/N (1-based, like the page number) wins, so a link opens slide N.
     Without one, the deck opens on the last slide viewed. go() clamps an index that
     no longer exists (slides removed) to the last slide. */
  _startSlide() {
    const fromHash = this._hashSlide();
    if (fromHash != null) return fromHash;
    try {
      const n = parseInt(localStorage.getItem(this.POS_KEY), 10);
      if (n >= 0) return n;
    } catch (e) {}
    return 0;
  }
  _hashSlide() {
    const m = /^#\/(\d+)$/.exec(location.hash);
    return m ? Math.max(0, parseInt(m[1], 10) - 1) : null;
  }
  _rememberSlide() {
    try { localStorage.setItem(this.POS_KEY, String(this.current)); } catch (e) {}
    const h = '#/' + (this.current + 1);
    // replaceState, not location.hash: no history entry per slide, no hashchange loop.
    if (location.hash !== h) { try { history.replaceState(null, '', h); } catch (e) {} }
  }
  prev() { this.go(this.current - 1); }

  _resetWidgets() {
    const s = this.slides[this.current];
    if (!s) return;
    s.querySelectorAll('[data-step]').forEach(el => el.classList.remove('step-shown'));
    s._stepIndex = 0;
    if (window.DeckWidgets) window.DeckWidgets.activate(s);
  }

  _advance(dir) {
    const s = this.slides[this.current];
    const steps = s ? Array.from(s.querySelectorAll('[data-step]')) : [];
    if (dir > 0 && steps.length) {
      const hidden = steps.find(el => !el.classList.contains('step-shown'));
      if (hidden) { hidden.classList.add('step-shown'); return; }
    }
    dir > 0 ? this.next() : this.prev();
  }

  _keys() {
    addEventListener('keydown', (e) => {
      if (this.editing && e.target.isContentEditable && e.key !== 'Escape') return;
      switch (e.key) {
        case 'ArrowRight': case ' ': case 'PageDown': e.preventDefault(); this._advance(1); break;
        case 'ArrowLeft': case 'PageUp': e.preventDefault(); this._advance(-1); break;
        case 'Home': this.go(0); break;
        case 'End': this.go(this.slides.length - 1); break;
        case 'o': case 'O': this.toggleOverview(); break;
        case 'e': case 'E': if (!e.target.isContentEditable) this.toggleEdit(); break;
        case 'f': case 'F': this.presentNow(); break;
        case 'Escape':
          if (document.body.classList.contains('presenting')) this.exitPresent();
          else if (this.overview.classList.contains('open')) this.closeOverview();
          else if (this.editing) this.toggleEdit();
          break;
      }
    });
  }
  _touch() {
    let x0 = null;
    addEventListener('touchstart', e => x0 = e.touches[0].clientX, { passive: true });
    addEventListener('touchend', e => {
      if (x0 === null) return;
      const dx = e.changedTouches[0].clientX - x0;
      if (Math.abs(dx) > 60) (dx < 0 ? this._advance(1) : this._advance(-1));
      x0 = null;
    }, { passive: true });
  }
  _wheel() {
    let lock = false;
    addEventListener('wheel', e => {
      if (this.editing || lock) return;
      if (Math.abs(e.deltaY) < 24) return;
      lock = true; setTimeout(() => lock = false, 600);
      this._advance(e.deltaY > 0 ? 1 : -1);
    }, { passive: true });
  }

  /* --- present mode (fullscreen) --- */
  presentNow() {
    const el = document.documentElement;
    if (!document.fullscreenElement && el.requestFullscreen) el.requestFullscreen().catch(()=>{});
    document.body.classList.add('presenting');
    if (this.editing) this.toggleEdit();
    if (this.toolbar) this.toolbar.classList.remove('show'); // no toolbar while presenting
  }
  exitPresent() {
    document.body.classList.remove('presenting');
    if (document.fullscreenElement && document.exitFullscreen) document.exitFullscreen().catch(()=>{});
  }

  /* --- export to PDF (browser print → "Save as PDF") ---
     Goal: one page per slide, every slide in its END-STATE — all reveals/build-steps
     resolved and all widget animations (chart fills, donuts, counters) at their final
     value. We do that by making EVERY slide visible at once (so the .slide.visible
     rules that drive those animations fire) while body.deck-pdf-export kills all
     transitions so the end-state is reached instantly with no mid-animation snapshot.
     The persistent chrome is a single layer, so we clone it into each slide with the
     right page number; the @media print rules (viewport-base.css) lay each slide out
     as its own page. Everything is torn down on `afterprint`. */
  exportPDF() {
    if (this._pdfExporting) return;
    // The layout is already exact — @page declares 1920x1080 and each slide is laid
    // out at that size. What ruins an export is the browser dialog: Chrome reuses
    // whatever paper size / margins / scale were set last time, and any one of them
    // wrong crops the slide (a half-cut logo is the usual symptom). The person
    // clicking this button is never told that, so tell them here, once, at the only
    // moment it can be acted on.
    this._showPdfHint();
  }
  /* Export to PowerPoint: the slide as rendered, plus a live text layer. Unlike the PDF
     path this needs no print dialog — DeckPPTX rasterises each slide itself and writes the
     .pptx in the browser. Slow enough (a second or two per slide) to deserve a progress
     line, so it borrows the same hint strip. */
  exportPPTX() {
    if (this._pptxExporting) return;
    if (!window.DeckPPTX || typeof PptxGenJS === 'undefined') {
      // Not _flash: that writes into the edit panel's save button, which only exists
      // while the panel is open — the message would be invisible in the normal case.
      this._showHint('PowerPoint export unavailable in this deck', false, 5000);
      return;
    }
    this._pptxExporting = true;
    const say = msg => this._showHint(msg);   // same .deck-hint convention as everywhere else
    say('Building PowerPoint…');
    window.DeckPPTX.export({
      onProgress: (n, total) => say(`Building PowerPoint… slide ${n} of ${total}`)
    }).then(r => {
      const uncalibrated = DECK_BRAND.pptxLead ? '' : ' (no line-spacing calibration in this Brand pack)';
      say(`PowerPoint exported — ${r.slides} slides, ${r.boxes} editable text boxes${uncalibrated}`);
      setTimeout(() => { if (this.hint) this.hint.classList.remove('show'); this._maybeShowHint(); }, 4000);
    }).catch(e => {
      say('PowerPoint export failed: ' + (e && e.message ? e.message : e));
      setTimeout(() => { if (this.hint) this.hint.classList.remove('show'); this._maybeShowHint(); }, 6000);
    }).then(() => { this._pptxExporting = false; });
  }

  _showPdfHint() {
    if (!this.hint) return this._print();          // no hint layer — just print
    this.hint.innerHTML = '';
    const span = document.createElement('span');
    span.innerHTML = 'In the print dialog set <b>Destination: Save as PDF</b>, ' +
                     '<b>Margins: None</b>, <b>Scale: 100%</b>, and tick ' +
                     '<b>Background graphics</b> \u2014 otherwise the slide is cropped.';
    this.hint.appendChild(span);
    // This is the same element the "local edits" badge uses, so dismissing has to put
    // that warning back — otherwise one PDF export silently retires it for the session
    // (_notifyLocalEdits only fires once) and unsaved edits stop announcing themselves.
    // Safe on the print path too: .deck-hint is .deck-chrome, which @media print hides.
    const dismiss = () => {
      this.hint.classList.remove('show');
      if (this._localEditsShown) this._showHint('Local edits — not saved to file', true);
    };
    const go = document.createElement('button');
    go.type = 'button'; go.className = 'hint-save'; go.textContent = 'Open print dialog';
    go.addEventListener('click', () => { dismiss(); this._print(); });
    this.hint.appendChild(go);
    const cancel = document.createElement('button');
    cancel.type = 'button'; cancel.textContent = 'Cancel';
    cancel.addEventListener('click', dismiss);
    this.hint.appendChild(cancel);
    this.hint.classList.add('show');
  }
  _print() {
    if (this._pdfExporting) return;
    this._pdfPrep();
    const done = () => { window.removeEventListener('afterprint', done); this._teardownPDF(); };
    window.addEventListener('afterprint', done);
    // Two frames so the no-transition end-state is fully applied before the snapshot.
    requestAnimationFrame(() => requestAnimationFrame(() => {
      try { window.print(); } catch (e) { this._teardownPDF(); }
    }));
  }
  /* Put the whole deck into its printable end-state (separated from exportPDF so it
     is callable headlessly, e.g. via page.pdf(), where window.print() is a no-op). */
  _pdfPrep() {
    this._pdfExporting = true;
    this._pdfPrev = this.current;
    if (this.editing) this.toggleEdit();
    if (this.overview) this.closeOverview();
    document.body.classList.remove('presenting');
    document.body.classList.add('deck-pdf-export');
    this.slides.forEach((s, n) => {
      s.classList.add('active', 'visible');                              // fire .slide.visible animations
      s.querySelectorAll('[data-step]').forEach(el => el.classList.add('step-shown')); // resolve build-steps
      if (window.DeckWidgets) window.DeckWidgets.activate(s, { instant: true }); // widgets to end-state
      if (this.chrome) {                                                 // per-page chrome with its own page number
        const c = this.chrome.cloneNode(true);
        c.classList.add('deck-frame--print');
        c.removeAttribute('id');
        c.dataset.theme = s.dataset.theme || this.stage.dataset.theme || DEFAULT_THEME;
        const pn = c.querySelector('.deck-pagenum'); if (pn) pn.textContent = String(n + 1);
        s.appendChild(c);
      }
    });
    // The contrast guard only ever runs on the slide that is active, so in an export —
    // where every slide is laid out at once — slides 2..N would print the authored
    // colours instead of the guarded ones the presenter actually saw (on a light theme
    // an unreadable accent is demoted to a neutral, so agenda numerals would keep the
    // accent instead). Guard them all; guardEl restores the authored colour before measuring,
    // so running it repeatedly is safe.
    if (window.DeckContrast && window.DeckContrast.guard) {
      this.slides.forEach(s => window.DeckContrast.guard(s, this.stage));
    }
  }
  _teardownPDF() {
    if (!this._pdfExporting) return;
    this.slides.forEach(s => {
      s.querySelectorAll('.deck-frame--print').forEach(el => el.remove());
      s.querySelectorAll('[data-step].step-shown').forEach(el => el.classList.remove('step-shown'));
    });
    document.body.classList.remove('deck-pdf-export');
    this._pdfExporting = false;
    this.go(this._pdfPrev || 0);   // restore single-slide view + widget state
  }

  /* --- persistent chrome --- */
  _todayISO() {
    const d = new Date(); const p = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  }
  _formatISO(iso, lang) {
    const parts = iso.split('-'); const y = +parts[0], m = +parts[1], day = +parts[2];
    const M = DECK_MONTHS[lang] || DECK_MONTHS.en;
    return lang === 'da' ? `${day}. ${M[m - 1]} ${y}` : `${day} ${M[m - 1]} ${y}`;
  }
  _renderDate() {
    const el = this.chrome && this.chrome.querySelector('.deck-date'); if (!el) return;
    const iso = this.stage.dataset.date || this._todayISO();
    el.textContent = this._formatISO(iso, this.stage.getAttribute('lang') || 'en');
  }
  _renderClassification() {
    const el = this.chrome && this.chrome.querySelector('.deck-classification'); if (!el) return;
    const v = this._classification();
    el.textContent = (v === 'none') ? '' : v;
  }
  /* The deck's classification, always one of the Brand pack's labels. */
  _classification() {
    const v = this.stage.dataset.classification;
    return CLASSIFICATIONS.indexOf(v) !== -1 ? v : DEFAULT_CLASSIFICATION;
  }
  _renderHeader() {
    const el = this.chrome && this.chrome.querySelector('.deck-header');
    if (el) el.textContent = this.stage.dataset.header || '';
  }
  _initChrome() { if (!this.chrome) return; this._renderDate(); this._renderClassification(); this._renderHeader(); }
  _updateChrome() {
    if (!this.chrome) return;
    const slide = this.slides[this.current];
    this.chrome.dataset.theme = (slide && slide.dataset.theme) || this.stage.dataset.theme || DEFAULT_THEME;
    const pn = this.chrome.querySelector('.deck-pagenum');
    if (pn) pn.textContent = String(this.current + 1);
  }
  /* Bloom slider is contextual: only shown for the brand's bloom/hero backgrounds
     (window.DeckBrand.bloomThemes); reflects this slide. Hidden entirely for brands
     with no bloom themes. */
  _updateBloomControl() {
    if (!this.bloomRow) return;
    const s = this.slides[this.current];
    const theme = (s && s.dataset.theme) || this.stage.dataset.theme || DEFAULT_THEME;
    const isBloom = BLOOM_THEMES.indexOf(theme) !== -1;
    this.bloomRow.style.display = isBloom ? '' : 'none';
    const amt = (s && s.style.getPropertyValue('--bloom-amount')) || '';
    if (isBloom) this.bloomInput.value = amt || '100';
    if (this.bloomReset) this.bloomReset.style.display = (isBloom && amt && amt !== '100') ? 'inline-block' : 'none';
  }

  /* --- chrome: toolbar + counter + control panel --- */
  _buildChrome() {
    const bar = document.createElement('div');
    bar.className = 'deck-chrome deck-toolbar';
    bar.innerHTML = `
      <button data-act="present" title="Present (F)"><span class="ti">▶</span><span>Present now</span></button>
      <button data-act="edit" title="Edit (E)"><span class="ti">✎</span><span>Edit presentation</span></button>
      <button data-act="pdf" title="Export every slide to PDF (one page per slide, animations resolved)"><span class="ti">⤓</span><span>Export to PDF</span></button>
      <button data-act="pptx" title="Export to PowerPoint — the design as rendered, with the text still editable"><span class="ti">⤓</span><span>Export to PPTX</span></button>
      <button data-act="overview" title="Overview (O)"><span class="ti">▦</span></button>`;
    document.body.appendChild(bar);
    this.toolbar = bar;
    bar.addEventListener('click', e => {
      const a = e.target.closest('button')?.dataset.act;
      if (a === 'present') this.presentNow();
      if (a === 'edit') this.toggleEdit();
      if (a === 'pdf') this.exportPDF();
      if (a === 'pptx') this.exportPPTX();
      if (a === 'overview') this.toggleOverview();
    });
    // Auto-hide: any mouse movement reveals the toolbar (moving the mouse means the
    // user wants to act); it fades back after a short idle. Never reveal while
    // presenting — present mode shows no chrome at all.
    let hideT;
    const presenting = () => document.body.classList.contains('presenting');
    const hideBar = () => { if (!this.editing) bar.classList.remove('show'); };
    addEventListener('mousemove', () => {
      if (presenting()) return;
      clearTimeout(hideT);
      bar.classList.add('show');
      hideT = setTimeout(hideBar, 2000); // recede after the pointer stops
    });
    // Keep it up while the pointer is over the toolbar itself.
    bar.addEventListener('mouseenter', () => { if (presenting()) return; clearTimeout(hideT); bar.classList.add('show'); });
    bar.addEventListener('mouseleave', () => { clearTimeout(hideT); hideT = setTimeout(hideBar, 2000); });

    this.counter = document.createElement('div');
    this.counter.className = 'deck-chrome deck-counter';
    document.body.appendChild(this.counter);

    this.hint = document.createElement('div');
    this.hint.className = 'deck-chrome deck-hint';
    document.body.appendChild(this.hint);

    const panel = document.createElement('div');
    panel.className = 'deck-chrome deck-panel';
    panel.innerHTML = `
      <div class="panel-group">
        <h4>This slide</h4>
        <label>Background
          <select data-ctl="theme"></select></label>
        <div data-bloom-row>
          <label class="bloom-line">Bloom <input type="range" min="0" max="200" data-ctl="bloom"></label>
          <button type="button" data-ctl="bloom-reset" title="Reset bloom to default">Reset to default</button>
        </div>
        <p class="panel-tip">Click any text on a slide to edit just that slide.</p>
      </div>
      <div class="panel-group">
        <h4>All slides</h4>
        <label>Classification
          <select data-ctl="classification"></select></label>
        <label>Header <input type="text" data-ctl="header" placeholder="(optional)"></label>
        <label>Date <input type="date" data-ctl="date"></label>
      </div>
      <button data-ctl="save">Save</button>`;
    document.body.appendChild(panel);
    this.panel = panel;
    this.themeSelect = panel.querySelector('[data-ctl="theme"]');
    // Populate the background picker from the active brand's theme list.
    THEME_OPTIONS.forEach(t => this.themeSelect.add(new Option(t.label, t.value)));
    // The classification picker lists the Brand pack's labels; "none" hides the badge.
    const classSelect = panel.querySelector('[data-ctl="classification"]');
    CLASSIFICATIONS.forEach(c => classSelect.add(new Option(c === 'none' ? 'None' : c, c)));
    this.themeSelect.addEventListener('change', e => {
      const s = this.slides[this.current]; if (s) s.dataset.theme = e.target.value;
      this._updateChrome(); this._updateBloomControl(); this._save();
    });
    this.bloomRow = panel.querySelector('[data-bloom-row]');
    this.bloomInput = panel.querySelector('[data-ctl="bloom"]');
    this.bloomReset = panel.querySelector('[data-ctl="bloom-reset"]');
    this.bloomInput.addEventListener('input', e => {
      const s = this.slides[this.current];
      if (s) s.style.setProperty('--bloom-amount', e.target.value);
      this.bloomReset.style.display = (e.target.value !== '100') ? 'inline-block' : 'none';
      this._save();
    });
    this.bloomReset.addEventListener('click', () => {
      const s = this.slides[this.current];
      if (s) s.style.removeProperty('--bloom-amount'); // back to default (100 = full)
      this._updateBloomControl();
      this._save();
    });
    classSelect.addEventListener('change', e => {
      this.stage.dataset.classification = e.target.value; this._renderClassification(); this._save();
    });
    panel.querySelector('[data-ctl="header"]').addEventListener('input', e => {
      this.stage.dataset.header = e.target.value; this._renderHeader(); this._save();
    });
    panel.querySelector('[data-ctl="date"]').addEventListener('change', e => {
      this.stage.dataset.date = e.target.value; this._renderDate(); this._save();
    });
    panel.querySelector('[data-ctl="save"]').addEventListener('click', () => this.save());
  }

  /* set panel field values from current deck state (after restore) */
  _syncPanel() {
    if (!this.panel) return;
    const set = (sel, val) => { const el = this.panel.querySelector(sel); if (el != null && val != null) el.value = val; };
    set('[data-ctl="classification"]', this._classification());
    set('[data-ctl="header"]', this.stage.dataset.header || '');
    set('[data-ctl="date"]', this.stage.dataset.date || this._todayISO());
  }

  /* --- overview grid --- */
  _buildOverview() {
    const ov = document.createElement('div');
    ov.className = 'deck-chrome deck-overview';
    this.slides.forEach((s, n) => {
      const t = document.createElement('button'); t.className = 'ov-thumb';
      t.textContent = `${n + 1}. ${(s.dataset.title || s.querySelector('h1,h2')?.textContent || 'Slide').slice(0, 30)}`;
      t.addEventListener('click', () => { this.go(n); this.closeOverview(); });
      ov.appendChild(t);
    });
    ov.addEventListener('click', e => { if (e.target === ov) this.closeOverview(); });
    document.body.appendChild(ov);
    this.overview = ov;
  }
  toggleOverview() { this.overview.classList.toggle('open'); }
  closeOverview() { this.overview.classList.remove('open'); }

  /* Click-away to dismiss the edit panel; keep present mode in sync with fullscreen. */
  _bindDismiss() {
    document.addEventListener('click', e => {
      if (!this.editing) return;
      if (e.target.closest('.deck-panel') || e.target.closest('.deck-toolbar') ||
          e.target.closest('.deck-overview') || e.target.closest('[contenteditable]') ||
          e.target.closest('.deck-icon') || e.target.closest('.deck-icon-picker')) return;
      this.toggleEdit();
    });
    document.addEventListener('fullscreenchange', () => {
      if (!document.fullscreenElement) document.body.classList.remove('presenting');
    });
  }

  /* --- edit mode ---
     All static text in a slide's .slide-content is editable by default. We mark the
     OUTERMOST element that directly holds text (so inline <em>/<a> are edited within
     it, never as nested editable regions), skipping a denylist: icons (handled by the
     picker), widget-managed text (counters, chart values/labels, donut), and any
     [data-noedit] opt-out. data-edit is no longer required — kept only as harmless
     legacy markup on older decks. */
  _hasDirectText(el) {
    return Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim());
  }

  _markEditable(slide, on) {
    const content = slide.querySelector('.slide-content');
    if (!content) return;
    if (!on) {
      content.querySelectorAll('[contenteditable]').forEach(el => el.removeAttribute('contenteditable'));
      return;
    }
    // Icons are atomic objects, never text-editable, so a caret never lands inside one.
    // Use setAttribute (not the .contentEditable property — it's HTMLElement-only and
    // does not reflect on SVG, leaving the icon non-atomic inside an editable heading).
    content.querySelectorAll('.deck-icon').forEach(ic => { ic.setAttribute('contenteditable', 'false'); });
    Deck.editableLeaves(content).forEach(el => { el.contentEditable = 'true'; });
  }

  /* The outermost elements inside `content` that directly hold text, minus EDIT_DENY —
     i.e. exactly what edit mode makes editable. The PPTX export calls this too, so the
     two can never disagree about what counts as text. Static: it needs no deck state. */
  static editableLeaves(content) {
    const hasText = el => Array.from(el.childNodes)
      .some(n => n.nodeType === 3 && n.textContent.trim());
    const out = [];
    content.querySelectorAll('*').forEach(el => {
      if (el.closest(Deck.EDIT_DENY)) return;
      if (!hasText(el)) return;
      // An ancestor that bears text is the one we mark, not this element. `el.closest`
      // above already proved no ancestor matches EDIT_DENY, so only the text test is left.
      let p = el.parentElement;
      while (p && p !== content) {
        if (hasText(p)) return;
        p = p.parentElement;
      }
      out.push(el);
    });
    return out;
  }

  toggleEdit() {
    this.editing = !this.editing;
    document.body.classList.toggle('editing', this.editing);
    this.slides.forEach(s => this._markEditable(s, this.editing));
    if (this.editing) {
      document.body.classList.remove('presenting');
      this.slides.forEach(s => s.addEventListener('input', this._onInput = () => this._save(), { once: false }));
    }
    // Entering/leaving edit mode snapshots state but isn't itself a content edit, so
    // don't pop the "local edits" badge for it — only actual edits should.
    this._suppressEditHint = true; this._save(); this._suppressEditHint = false;
  }

  /* --- persistence (localStorage autosave) --- */
  _save() {
    const data = {
      rev: this.stage.dataset.deckRev || '',   // version this draft was made on
      classification: this._classification(),
      header: this.stage.dataset.header || '',
      date: this.stage.dataset.date || null,
      themes: {}, bloom: {}, html: {}
    };
    this.slides.forEach((s, n) => {
      data.themes[n] = s.dataset.theme || null;
      data.bloom[n] = s.style.getPropertyValue('--bloom-amount') || null;
      data.html[n] = s.querySelector('.slide-content')?.innerHTML;
    });
    try { localStorage.setItem(this.STORE_KEY, JSON.stringify(data)); this._notifyLocalEdits(); } catch (e) {}
  }
  _restore() {
    let data; try { data = JSON.parse(localStorage.getItem(this.STORE_KEY)); } catch (e) {}
    if (!data) return;
    // If the file was (re)generated since this draft was saved, its content stamp
    // changed — so the draft is stale. Discard it and show the fresh file, instead
    // of overlaying old text on top of the rebuilt deck.
    if ((data.rev || '') !== (this.stage.dataset.deckRev || '')) {
      try { localStorage.removeItem(this.STORE_KEY); } catch (e) {}
      this._staleCleared = true;
      return;
    }
    if (CLASSIFICATIONS.indexOf(data.classification) !== -1) this.stage.dataset.classification = data.classification;
    if (data.header != null) this.stage.dataset.header = data.header;
    if (data.date) this.stage.dataset.date = data.date;
    if (data.themes) this.slides.forEach((s, n) => { if (data.themes[n]) s.dataset.theme = data.themes[n]; });
    if (data.bloom) this.slides.forEach((s, n) => { if (data.bloom[n]) s.style.setProperty('--bloom-amount', data.bloom[n]); });
    if (data.html) this.slides.forEach((s, n) => {
      const c = s.querySelector('.slide-content');
      if (c && data.html[n] != null) c.innerHTML = data.html[n];
    });
    this._restoredDraft = true;
  }

  /* --- save to file (File System Access API; download fallback) --- */
  _serialize() {
    const clone = document.documentElement.cloneNode(true);
    clone.querySelectorAll('.deck-chrome').forEach(el => el.remove());
    clone.querySelectorAll('[contenteditable]').forEach(el => el.removeAttribute('contenteditable'));
    return '<!DOCTYPE html>\n' + clone.outerHTML;
  }
  async save() {
    const html = this._serialize();
    if (window.showSaveFilePicker) {
      try {
        if (!this._fileHandle) {
          this._fileHandle = await window.showSaveFilePicker({
            // id makes the browser reopen the last folder used for this deck's saves,
            // so after the first save it lands in the deck's own folder for easy overwrite.
            id: ('deck' + (this.stage.dataset.deckId || 'deck')).replace(/[^A-Za-z0-9_-]/g, '').slice(0, 32),
            suggestedName: (document.title || 'deck').replace(/\s+/g, '-') + '.html',
            types: [{ description: 'HTML', accept: { 'text/html': ['.html'] } }]
          });
        }
        const w = await this._fileHandle.createWritable();
        await w.write(html); await w.close();
        // Silent save: keep the handle (no reload) so every later save writes
        // straight to the file with no picker. Edits are now in the file, so drop
        // the local draft and clear the "local edits" hint.
        try { localStorage.removeItem(this.STORE_KEY); } catch (e) {}
        if (this.hint) this.hint.classList.remove('show');
        this._localEditsShown = false;   // edits are in the file now; let the badge return on the next edit
        this._flash('✓ Saved'); return;
      } catch (e) { if (e && e.name === 'AbortError') return; }
    }
    const blob = new Blob([html], { type: 'text/html' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = (document.title || 'deck').replace(/\s+/g, '-') + '.html';
    a.click(); URL.revokeObjectURL(a.href);
    this._flash('✓ Downloaded');
  }
  _flash(msg) {
    const btn = this.panel && this.panel.querySelector('[data-ctl="save"]');
    if (!btn) return;
    const old = btn.textContent; btn.textContent = msg;
    setTimeout(() => { btn.textContent = old; }, 1500);
  }
}
/* Elements never made text-editable in edit mode: icons (use the picker), widget-
   managed text (counters, chart values/labels, donut), and the [data-noedit] opt-out. */
Deck.EDIT_DENY = '.deck-icon,.counter-stat,.chart-bars .bar .value,.chart-bars .bar .label,.chart-donut,[data-noedit]';
document.addEventListener('DOMContentLoaded', () => { window.deck = new Deck(); });
